"""Une vraie sondes SNMP, utilisable par B1 Découverte et B3 Supervision.

Elle pose de vraies questions SNMP à un équipement (avec la bibliothèque pysnmp).
Dans le labo, c'est snmpsim qui lui répond, en imitant un switch Cisco.

Pour rester simple, cette première version :
- utilise SNMP v2c avec une « communauté » (un mot de passe en clair), comme dans le labo.
  En production, on passera à SNMP v3, chiffré (voir la section Sécurité du dossier) ;
- considère qu'un équipement « répond au ping » s'il répond en SNMP. Un vrai ping ICMP
  viendra plus tard.
"""

import asyncio
import time

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
    walk_cmd,
)

# Les OID : l'« adresse » de chaque information dans un équipement SNMP.
SYS_DESCR = "1.3.6.1.2.1.1.1.0"
SYS_NAME = "1.3.6.1.2.1.1.5.0"
SYS_LOCATION = "1.3.6.1.2.1.1.6.0"
IF_DESCR = "1.3.6.1.2.1.2.2.1.2"  # le nom de chaque port (Gi1/0/12…)
IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"  # l'état de chaque port : 1 = up, 2 = down


class SondeSNMP:
    """Interroge les équipements en SNMP v2c.

    « adresses » associe le nom d'un équipement à son IP, pour B3 qui travaille par nom.
    """

    def __init__(
        self,
        communaute: str,
        port: int = 161,
        adresses: dict[str, str] | None = None,
        delai_s: float = 1.0,
    ) -> None:
        self.communaute = communaute
        self.port = port
        self.adresses = adresses or {}
        self.delai_s = delai_s

    # --- Pour B1 Découverte (les méthodes reçoivent une IP) ---------------------

    def ping(self, ip: str) -> bool:
        """Vrai si l'équipement répond en SNMP."""
        return self._get(ip, [SYS_NAME]) is not None

    def lire_sysinfo(self, ip: str) -> dict[str, str] | None:
        """Lit sysName, sysDescr et sysLocation, ou None si pas de réponse."""
        valeurs = self._get(ip, [SYS_NAME, SYS_DESCR, SYS_LOCATION])
        if valeurs is None:
            return None
        return {
            "sysName": valeurs[SYS_NAME],
            "sysDescr": valeurs[SYS_DESCR],
            "sysLocation": valeurs[SYS_LOCATION],
        }

    # --- Pour B3 Supervision (les méthodes reçoivent un nom d'équipement) -------

    def etat_interfaces(self, equipement: str) -> dict[str, bool] | None:
        """Renvoie {nom du port: up ?}, ou None si l'équipement ne répond pas."""
        ip = self.adresses.get(equipement, equipement)
        noms = self._walk(ip, IF_DESCR)
        etats = self._walk(ip, IF_OPER_STATUS)
        if noms is None or etats is None:
            return None
        # Les deux listes se correspondent par le numéro de port (la fin de l'OID).
        return {noms[index]: etats.get(index) == "1" for index in noms}

    def cpu(self, equipement: str) -> float | None:
        """Le CPU n'est pas encore lu : chaque fabricant le range à un endroit différent."""
        return None

    def latence_ms(self, equipement: str) -> float | None:
        """Mesure le temps de réponse SNMP, en millisecondes."""
        ip = self.adresses.get(equipement, equipement)
        debut = time.perf_counter()
        if self._get(ip, [SYS_NAME]) is None:
            return None
        return round((time.perf_counter() - debut) * 1000, 1)

    # --- La mécanique SNMP --------------------------------------------------------

    def _get(self, ip: str, oids: list[str]) -> dict[str, str] | None:
        """Lit plusieurs OID précis ; renvoie {oid: valeur} ou None si pas de réponse."""
        return asyncio.run(self._get_async(ip, oids))

    def _walk(self, ip: str, racine: str) -> dict[str, str] | None:
        """Parcourt toute une table (par exemple tous les ports) ; renvoie {index: valeur}."""
        return asyncio.run(self._walk_async(ip, racine))

    async def _get_async(self, ip: str, oids: list[str]) -> dict[str, str] | None:
        moteur = SnmpEngine()
        try:
            cible = await UdpTransportTarget.create(
                (ip, self.port), timeout=self.delai_s, retries=0
            )
            erreur, statut, _, resultats = await get_cmd(
                moteur,
                CommunityData(self.communaute),
                cible,
                ContextData(),
                *[ObjectType(ObjectIdentity(oid)) for oid in oids],
            )
            if erreur or statut:
                return None
            return {str(oid): str(valeur) for oid, valeur in resultats}
        finally:
            moteur.close_dispatcher()

    async def _walk_async(self, ip: str, racine: str) -> dict[str, str] | None:
        moteur = SnmpEngine()
        try:
            cible = await UdpTransportTarget.create(
                (ip, self.port), timeout=self.delai_s, retries=0
            )
            table: dict[str, str] = {}
            async for erreur, statut, _, resultats in walk_cmd(
                moteur,
                CommunityData(self.communaute),
                cible,
                ContextData(),
                ObjectType(ObjectIdentity(racine)),
                lexicographicMode=False,  # s'arrêter à la fin de la table demandée
            ):
                if erreur or statut:
                    return None
                for oid, valeur in resultats:
                    index = str(oid).rsplit(".", 1)[-1]  # « …2.2.1.8.12 » -> « 12 »
                    table[index] = str(valeur)
            return table
        finally:
            moteur.close_dispatcher()

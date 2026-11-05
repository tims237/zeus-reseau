"""B1 Découverte.

Le principe : pour chaque adresse d'une plage (par exemple 10.3.0.0/24), on demande
« tu es là ? » (ping), puis « qui es-tu ? » (lecture SNMP de sysName et sysDescr).

La découverte ne parle jamais directement au réseau : elle passe par une « sondes ».
- En vrai, la sondes enverra de vrais pings et de vraies requêtes SNMP.
- Dans les tests, on lui donne une FAUSSE sondes, qui répond ce qu'on veut.
Le code de decouvrir() ne change pas : c'est l'injection de dépendance.
"""

from ipaddress import IPv4Address, ip_network
from typing import Protocol

from zeus_core.modeles import Equipement, TypeEquipement


class Sonde(Protocol):
    """Ce dont la découverte a besoin pour interroger une adresse.

    Un Protocol décrit des méthodes sans dire comment elles marchent : n'importe
    quelle classe qui a ces deux méthodes peut servir de sondes.
    """

    def ping(self, ip: str) -> bool:
        """Vrai si l'adresse répond au ping."""
        ...

    def lire_sysinfo(self, ip: str) -> dict[str, str] | None:
        """Lit sysName et sysDescr en SNMP, ou renvoie None si SNMP ne répond pas."""
        ...


def adresses_de_la_plage(plage: str, limite: int = 4096) -> list[str]:
    """Liste les adresses à interroger dans une plage, par exemple « 10.3.0.0/24 ».

    Refuse les plages trop grandes, pour éviter de scanner tout un /8 par erreur.
    """
    reseau = ip_network(plage, strict=False)
    if reseau.num_addresses > limite:
        raise ValueError(f"Plage trop grande : {reseau.num_addresses} adresses (limite {limite})")
    # hosts() enlève l'adresse du réseau (.0) et l'adresse de diffusion (.255)
    return [str(ip) for ip in reseau.hosts()]


# Mots-clés cherchés dans sysDescr, dans l'ordre : le premier trouvé gagne.
# « switch » est avant « cisco », sinon un switch Cisco serait pris pour un routeur.
MOTS_CLES: list[tuple[str, TypeEquipement]] = [
    ("switch", TypeEquipement.SWITCH),
    ("catalyst", TypeEquipement.SWITCH),
    ("fortigate", TypeEquipement.PARE_FEU),
    ("firewall", TypeEquipement.PARE_FEU),
    ("esxi", TypeEquipement.SERVEUR),
    ("windows server", TypeEquipement.SERVEUR),
    ("unifi", TypeEquipement.BORNE_WIFI),
    ("access point", TypeEquipement.BORNE_WIFI),
    ("camera", TypeEquipement.CAMERA),
    ("axis", TypeEquipement.CAMERA),
    ("isr", TypeEquipement.ROUTEUR),
    ("router", TypeEquipement.ROUTEUR),
    ("meraki", TypeEquipement.BORNE_WIFI),
]


def deviner_type(sys_descr: str) -> TypeEquipement:
    """Devine la famille d'un équipement à partir de son texte sysDescr."""
    texte = sys_descr.lower()  # en minuscules, pour que « Switch » et « switch » se valent
    for mot, type_equipement in MOTS_CLES:
        if mot in texte:
            return type_equipement
    return TypeEquipement.INCONNU  # aucun mot-clé trouvé


def decouvrir(plage: str, sonde: Sonde) -> list[Equipement]:
    """Interroge chaque adresse de la plage et renvoie les équipements trouvés."""
    trouves: list[Equipement] = []
    for ip in adresses_de_la_plage(plage):
        # 1. Personne ne répond à cette adresse : on passe à la suivante
        if not sonde.ping(ip):
            continue

        # 2. Ça répond au ping : on demande qui c'est
        info = sonde.lire_sysinfo(ip)
        if info is None:
            # Répond au ping mais pas au SNMP (une imprimante, un PC…) :
            # on le garde quand même, avec son IP comme nom.
            trouves.append(Equipement(id=ip, ip=IPv4Address(ip)))
            continue

        # 3. SNMP a répondu : on remplit la fiche
        descr = info.get("sysDescr", "")
        trouves.append(
            Equipement(
                id=info.get("sysName", ip),  # le nom, ou l'IP si le nom manque
                ip=IPv4Address(ip),
                type=deviner_type(descr),
                modele=descr or None,
            )
        )
    return trouves

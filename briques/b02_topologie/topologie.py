"""B2 Topologie.

Chaque switch ou routeur sait qui est branché sur ses ports, grâce au protocole LLDP
(ou CDP chez Cisco) : il échange régulièrement une petite carte d'identité avec ses
voisins directs. B2 demande ces voisins à chaque équipement et en tire les câbles.

Comme B1, B2 passe par une sondes : une vraie sondes lira LLDP en SNMP, une fausse
sondes suffit pour les tests.
"""

from typing import Protocol

from zeus_core.modeles import Lien


class SondeLLDP(Protocol):
    """Ce dont la topologie a besoin pour lire les voisins d'un équipement."""

    def voisins_lldp(self, equipement: str) -> list[dict[str, str]]:
        """Renvoie les voisins vus par LLDP.

        Chaque voisin est un dictionnaire avec trois clés :
        - « port_local » : le port de l'équipement interrogé, par exemple Gi1/0/12
        - « voisin » : le nom de l'équipement d'en face
        - « port_voisin » : le port d'en face, par exemple eth0
        """
        ...


def construire_liens(equipements: list[str], sonde: SondeLLDP) -> list[Lien]:
    """Interroge chaque équipement et renvoie la liste des câbles, sans doublon.

    Un même câble est vu deux fois, une fois par chaque bout : le switch voit la borne,
    et la borne voit le switch. On ne le garde qu'une fois.
    """
    liens: list[Lien] = []
    deja_vus: set[frozenset[tuple[str, str]]] = set()
    for equipement in equipements:
        for v in sonde.voisins_lldp(equipement):
            bout_a = (equipement, v["port_local"])
            bout_b = (v["voisin"], v["port_voisin"])
            # frozenset : un ensemble sans ordre, donc {A, B} est égal à {B, A}
            cle = frozenset({bout_a, bout_b})
            if cle in deja_vus:
                continue  # ce câble a déjà été vu depuis l'autre bout
            deja_vus.add(cle)
            liens.append(
                Lien(
                    equipement_a=equipement,
                    interface_a=v["port_local"],
                    equipement_b=v["voisin"],
                    interface_b=v["port_voisin"],
                )
            )
    return liens


def voisins_de(equipement: str, liens: list[Lien]) -> list[str]:
    """Renvoie les noms des équipements directement branchés à celui-ci."""
    voisins: list[str] = []
    for lien in liens:
        if lien.equipement_a == equipement:
            voisins.append(lien.equipement_b)
        elif lien.equipement_b == equipement:
            voisins.append(lien.equipement_a)
    return sorted(voisins)


def equipements_injoignables(racine: str, liens: list[Lien], en_panne: set[str]) -> set[str]:
    """Renvoie les équipements qu'on ne peut plus joindre depuis la racine.

    La racine est le point de départ, en général le routeur cœur du datacenter.
    Les équipements en panne bloquent le passage : tout ce qui se trouve derrière eux
    devient injoignable. C'est ce qui permet d'envoyer UNE alerte « site hors ligne »
    au lieu d'une alerte par équipement.

    Algorithme : parcours en largeur. On part de la racine, on visite ses voisins,
    puis les voisins des voisins, en sautant les équipements en panne.
    """
    tous = {lien.equipement_a for lien in liens} | {lien.equipement_b for lien in liens}
    if racine in en_panne:
        return tous - {racine}

    joignables = {racine}
    a_visiter = [racine]  # la liste des équipements dont on doit encore regarder les voisins
    while a_visiter:
        courant = a_visiter.pop(0)  # on prend le premier de la liste
        for voisin in voisins_de(courant, liens):
            if voisin in joignables or voisin in en_panne:
                continue
            joignables.add(voisin)
            a_visiter.append(voisin)

    # Injoignables = tous, sauf ceux qu'on a pu atteindre, sauf ceux déjà en panne
    return tous - joignables - en_panne

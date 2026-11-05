"""Tests de B2 Topologie, avec une fausse sonde LLDP.

Le petit réseau simulé :

    RT-DC (cœur, au datacenter)
      └── RT-LIL (routeur de l'Agence Lille)
            └── SW-LIL (switch de Lille)
                  ├── AP-LIL-01 (borne Wi-Fi)
                  └── AP-LIL-02 (borne Wi-Fi)
"""

from briques.b02_topologie import construire_liens, equipements_injoignables, voisins_de
from zeus_core.modeles import Lien


class FausseSondeLLDP:
    """Chaque équipement voit ses voisins directs, comme en vrai avec LLDP."""

    def __init__(self) -> None:
        self.voisins: dict[str, list[dict[str, str]]] = {
            "RT-DC": [{"port_local": "Gi0/0/1", "voisin": "RT-LIL", "port_voisin": "Gi0/0/0"}],
            "RT-LIL": [
                {"port_local": "Gi0/0/0", "voisin": "RT-DC", "port_voisin": "Gi0/0/1"},
                {"port_local": "Gi0/0/1", "voisin": "SW-LIL", "port_voisin": "Gi1/0/1"},
            ],
            "SW-LIL": [
                {"port_local": "Gi1/0/1", "voisin": "RT-LIL", "port_voisin": "Gi0/0/1"},
                {"port_local": "Gi1/0/11", "voisin": "AP-LIL-01", "port_voisin": "eth0"},
                {"port_local": "Gi1/0/12", "voisin": "AP-LIL-02", "port_voisin": "eth0"},
            ],
            "AP-LIL-01": [{"port_local": "eth0", "voisin": "SW-LIL", "port_voisin": "Gi1/0/11"}],
            "AP-LIL-02": [{"port_local": "eth0", "voisin": "SW-LIL", "port_voisin": "Gi1/0/12"}],
        }

    def voisins_lldp(self, equipement: str) -> list[dict[str, str]]:
        return self.voisins.get(equipement, [])


EQUIPEMENTS = ["RT-DC", "RT-LIL", "SW-LIL", "AP-LIL-01", "AP-LIL-02"]


def liens_du_reseau() -> list[Lien]:
    """Raccourci : construit les liens du petit réseau de test."""
    return construire_liens(EQUIPEMENTS, FausseSondeLLDP())


# --- construire_liens -----------------------------------------------------------


def test_chaque_cable_n_est_garde_qu_une_fois() -> None:
    # 4 câbles dans le réseau, chacun vu par ses 2 bouts : on doit en garder 4, pas 8.
    assert len(liens_du_reseau()) == 4


def test_le_lien_garde_les_bons_ports() -> None:
    lien = next(lien for lien in liens_du_reseau() if lien.equipement_b == "AP-LIL-02")
    assert lien.equipement_a == "SW-LIL"
    assert lien.interface_a == "Gi1/0/12"
    assert lien.interface_b == "eth0"


def test_equipement_sans_voisin() -> None:
    # Un équipement que la sonde ne connaît pas n'ajoute aucun câble.
    assert construire_liens(["INCONNU"], FausseSondeLLDP()) == []


# --- voisins_de -----------------------------------------------------------------


def test_voisins_du_switch() -> None:
    assert voisins_de("SW-LIL", liens_du_reseau()) == ["AP-LIL-01", "AP-LIL-02", "RT-LIL"]


def test_voisins_d_une_borne() -> None:
    assert voisins_de("AP-LIL-02", liens_du_reseau()) == ["SW-LIL"]


# --- equipements_injoignables ---------------------------------------------------


def test_tout_est_joignable_sans_panne() -> None:
    assert equipements_injoignables("RT-DC", liens_du_reseau(), en_panne=set()) == set()


def test_panne_du_switch_coupe_les_bornes() -> None:
    # Le switch tombe : les deux bornes branchées derrière lui deviennent injoignables.
    resultat = equipements_injoignables("RT-DC", liens_du_reseau(), en_panne={"SW-LIL"})
    assert resultat == {"AP-LIL-01", "AP-LIL-02"}


def test_panne_d_une_borne_ne_coupe_rien_d_autre() -> None:
    # Une borne en bout de chaîne tombe : personne n'est derrière elle.
    resultat = equipements_injoignables("RT-DC", liens_du_reseau(), en_panne={"AP-LIL-02"})
    assert resultat == set()


def test_panne_du_routeur_coupe_tout_le_site() -> None:
    # Le routeur de Lille tombe : tout ce qui est derrière lui devient injoignable.
    # RT-LIL lui-même n'est pas dans le résultat : on sait déjà qu'il est en panne.
    resultat = equipements_injoignables("RT-DC", liens_du_reseau(), en_panne={"RT-LIL"})
    assert resultat == {"SW-LIL", "AP-LIL-01", "AP-LIL-02"}

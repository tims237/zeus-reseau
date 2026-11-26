"""Tests du collecteur, avec une fausse sonde qui imite le labo à quatre équipements.

    rt-dc ── rt-lil ── sw-lil ── ap-lil-01

Plus une imprimante (répond au ping, pas en SNMP) et un équipement qui tombe juste
après sa découverte, pour vérifier que la photo est prise même quand ça va mal.
"""

from datetime import datetime

from zeus_app.collecte import collecter, decoder_emplacement
from zeus_core.modeles import TypeEquipement

PHOTO_DE = datetime(2026, 11, 22, 15, 12, 4)
PLAGE = "172.20.20.0/28"


class FausseSondeLabo:
    """Répond comme les équipements du labo. B1 lui donne des IP ; B2 et B3 des noms."""

    def __init__(self, tout_eteint: bool = False) -> None:
        self.adresses: dict[str, str] = {}
        self.tout_eteint = tout_eteint
        # IP -> (sysName, sysDescr) ; None : répond au ping mais pas en SNMP
        self.sysinfo: dict[str, tuple[str, str] | None] = {
            "172.20.20.2": ("rt-lil", "SRLinux-v26.7.2 7220 IXR-D2L"),
            "172.20.20.3": ("sw-lil", "SRLinux-v26.7.2 7220 IXR-D2L"),
            "172.20.20.4": ("ap-lil-01", "Access point simule du labo ZeusReseau"),
            "172.20.20.5": ("rt-dc", "SRLinux-v26.7.2 7220 IXR-D2L"),
            "172.20.20.6": None,  # l'imprimante
            "172.20.20.7": ("sw-tombe", "Cisco IOS Software, C1000 Switch"),
        }
        # sysName -> sysLocation ; un nom absent n'a pas de sysLocation
        self.locations: dict[str, str] = {
            "ap-lil-01": "LIL/BatA/E2/OpenSpace",
            "sw-tombe": "LIL/BatA/Etage2",  # mal écrit : B13 attend E2
        }
        self.voisins: dict[str, list[dict[str, str]]] = {
            "rt-dc": [
                {"port_local": "ethernet-1/1", "voisin": "rt-lil", "port_voisin": "ethernet-1/1"}
            ],
            "rt-lil": [
                {"port_local": "ethernet-1/1", "voisin": "rt-dc", "port_voisin": "ethernet-1/1"},
                {"port_local": "ethernet-1/2", "voisin": "sw-lil", "port_voisin": "ethernet-1/1"},
            ],
            "sw-lil": [
                {"port_local": "ethernet-1/1", "voisin": "rt-lil", "port_voisin": "ethernet-1/2"},
                {"port_local": "ethernet-1/2", "voisin": "ap-lil-01", "port_voisin": "eth1"},
            ],
        }

    # Pour B1 (reçoit une IP)
    def ping(self, ip: str) -> bool:
        return not self.tout_eteint and ip in self.sysinfo

    def lire_sysinfo(self, ip: str) -> dict[str, str] | None:
        info = self.sysinfo.get(ip)
        if info is None:
            return None
        return {
            "sysName": info[0],
            "sysDescr": info[1],
            "sysLocation": self.locations.get(info[0], ""),
        }

    # Pour B2 et B3 (reçoivent un nom)
    def voisins_lldp(self, equipement: str) -> list[dict[str, str]]:
        return self.voisins.get(equipement, [])

    def etat_interfaces(self, equipement: str) -> dict[str, bool] | None:
        if equipement in ("sw-tombe", "172.20.20.6"):
            return None  # tombé juste après la découverte, ou pas de SNMP
        return {"ethernet-1/1": True}

    def cpu(self, equipement: str) -> float | None:
        return None

    def latence_ms(self, equipement: str) -> float | None:
        return 2.0


def test_la_photo_porte_l_heure_donnee() -> None:
    assert collecter(PLAGE, FausseSondeLabo(), PHOTO_DE).horodatage == PHOTO_DE


def test_b1_trouve_tous_les_equipements_meme_l_imprimante() -> None:
    etat = collecter(PLAGE, FausseSondeLabo(), PHOTO_DE)
    types = {e.id: e.type for e in etat.equipements}
    assert types == {
        "rt-lil": TypeEquipement.ROUTEUR,
        "sw-lil": TypeEquipement.ROUTEUR,  # un SR Linux : le futur travail de B17
        "ap-lil-01": TypeEquipement.BORNE_WIFI,
        "rt-dc": TypeEquipement.ROUTEUR,
        "172.20.20.6": TypeEquipement.INCONNU,  # pas de SNMP : son IP sert de nom
        "sw-tombe": TypeEquipement.SWITCH,
    }


def test_le_carnet_d_adresses_est_donne_a_la_sonde() -> None:
    sonde = FausseSondeLabo()
    collecter(PLAGE, sonde, PHOTO_DE)
    assert sonde.adresses["rt-dc"] == "172.20.20.5"
    assert sonde.adresses["ap-lil-01"] == "172.20.20.4"


def test_b2_trouve_les_trois_cables_sans_doublon() -> None:
    etat = collecter(PLAGE, FausseSondeLabo(), PHOTO_DE)
    cables = {frozenset({lien.equipement_a, lien.equipement_b}) for lien in etat.liens}
    assert cables == {
        frozenset({"rt-dc", "rt-lil"}),
        frozenset({"rt-lil", "sw-lil"}),
        frozenset({"sw-lil", "ap-lil-01"}),
    }
    assert len(etat.liens) == 3


def test_b3_releve_chaque_equipement_meme_ceux_qui_ne_repondent_plus() -> None:
    etat = collecter(PLAGE, FausseSondeLabo(), PHOTO_DE)
    repond = {r.equipement_id: r.repond for r in etat.releves}
    assert len(etat.releves) == len(etat.equipements)
    assert repond["rt-dc"] is True
    assert repond["sw-tombe"] is False  # tombé : il figure quand même sur la photo
    assert repond["172.20.20.6"] is False  # l'imprimante, sans SNMP


def test_personne_ne_repond_photo_vide_mais_datee() -> None:
    etat = collecter(PLAGE, FausseSondeLabo(tout_eteint=True), PHOTO_DE)
    assert etat.equipements == []
    assert etat.liens == []
    assert etat.releves == []
    assert etat.horodatage == PHOTO_DE


# --- B13 : l'emplacement de chaque équipement -------------------------------------


def test_collecter_decode_le_syslocation() -> None:
    etat = collecter(PLAGE, FausseSondeLabo(), PHOTO_DE)
    borne = next(e for e in etat.equipements if e.id == "ap-lil-01")
    assert borne.emplacement is not None
    assert borne.emplacement.site == "LIL"
    assert borne.emplacement.etage == 2


def test_syslocation_mal_ecrit_ne_bloque_pas_la_photo() -> None:
    # sw-tombe a "LIL/BatA/Etage2" : illisible pour B13. La photo est quand même prise,
    # le texte brut est gardé, et l'équipement n'a simplement pas d'emplacement.
    etat = collecter(PLAGE, FausseSondeLabo(), PHOTO_DE)
    switch = next(e for e in etat.equipements if e.id == "sw-tombe")
    assert switch.sys_location == "LIL/BatA/Etage2"
    assert switch.emplacement is None


def test_decoder_emplacement_sans_texte_donne_none() -> None:
    assert decoder_emplacement(None) is None

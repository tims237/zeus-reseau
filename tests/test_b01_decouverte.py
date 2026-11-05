"""Tests de B1 Découverte, avec une fausse sondes : aucun vrai réseau n'est utilisé."""

import pytest

from briques.b01_decouverte import adresses_de_la_plage, decouvrir, deviner_type
from zeus_core.modeles import TypeEquipement


class FausseSonde:
    """Simule un petit réseau de l'Agence Lille.

    - 10.3.0.1 : un routeur qui répond au ping et au SNMP
    - 10.3.0.2 : un switch qui répond au ping et au SNMP
    - 10.3.0.9 : une imprimante qui répond au ping, mais pas au SNMP (None)
    Toutes les autres adresses ne répondent pas.
    """

    def __init__(self) -> None:
        self.reponses: dict[str, dict[str, str] | None] = {
            "10.3.0.1": {"sysName": "RT-LIL", "sysDescr": "Cisco IOS XE Software, ISR1100"},
            "10.3.0.2": {"sysName": "SW-LIL", "sysDescr": "Cisco IOS Software, C1000 Switch"},
            "10.3.0.9": None,
        }

    def ping(self, ip: str) -> bool:
        return ip in self.reponses

    def lire_sysinfo(self, ip: str) -> dict[str, str] | None:
        return self.reponses.get(ip)


# --- adresses_de_la_plage -------------------------------------------------------


def test_plage_24_donne_254_adresses() -> None:
    # Un /24 a 256 adresses, moins celle du réseau (.0) et celle de diffusion (.255).
    assert len(adresses_de_la_plage("10.3.0.0/24")) == 254


def test_plage_trop_grande_refusee() -> None:
    # Un /8 compte plus de 16 millions d'adresses : refusé.
    with pytest.raises(ValueError):
        adresses_de_la_plage("10.0.0.0/8")


# --- deviner_type ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("descr", "attendu"),
    [
        ("Cisco IOS XE Software, ISR1100", TypeEquipement.ROUTEUR),
        ("Cisco IOS Software, C1000 Switch", TypeEquipement.SWITCH),
        ("FortiGate-100F v7.2", TypeEquipement.PARE_FEU),
        ("VMware ESXi 8.0", TypeEquipement.SERVEUR),
        ("UniFi U6-Pro", TypeEquipement.BORNE_WIFI),
        ("AXIS P3265-LVE Network Camera", TypeEquipement.CAMERA),
        ("Quelque chose d'inconnu", TypeEquipement.INCONNU),
        ("Meraki MR46", TypeEquipement.BORNE_WIFI),
    ],
)
def test_deviner_type(descr: str, attendu: TypeEquipement) -> None:
    # parametrize lance ce même test 7 fois, une fois par ligne de la liste.
    assert deviner_type(descr) is attendu


# --- decouvrir ------------------------------------------------------------------


def test_decouvrir_trouve_les_equipements_vivants() -> None:
    # Sur les 14 adresses de 10.3.0.0/28, seules 3 répondent.
    trouves = decouvrir("10.3.0.0/28", FausseSonde())
    assert [e.id for e in trouves] == ["RT-LIL", "SW-LIL", "10.3.0.9"]


def test_decouvrir_devine_le_type() -> None:
    trouves = decouvrir("10.3.0.0/28", FausseSonde())
    assert trouves[0].type is TypeEquipement.ROUTEUR
    assert trouves[1].type is TypeEquipement.SWITCH


def test_equipement_sans_snmp_garde_son_ip_comme_nom() -> None:
    # L'imprimante répond au ping mais pas au SNMP : on la garde, sans modèle.
    imprimante = decouvrir("10.3.0.0/28", FausseSonde())[-1]
    assert imprimante.id == "10.3.0.9"
    assert imprimante.modele is None
    assert imprimante.type is TypeEquipement.INCONNU


def test_plage_sans_reponse_donne_une_liste_vide() -> None:
    # Personne ne répond sur 192.168.1.0/28 : aucun équipement trouvé.
    assert decouvrir("192.168.1.0/28", FausseSonde()) == []

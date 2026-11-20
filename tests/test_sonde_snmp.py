"""Tests de la sonde SNMP qui ne demandent pas de réseau.

On teste ici assembler_voisins_lldp : la fonction qui relie les tables LLDP entre elles.
Les vraies lectures SNMP sont testées à part, contre snmpsim (test_labo_snmp.py).
"""

from sondes.sonde_snmp import assembler_voisins_lldp

# Ce que renvoie un routeur SR Linux, rangé comme le fait _walk : {index: valeur}.
PORTS_LOCAUX = {"1": "ethernet-1/1", "2": "ethernet-1/2", "99": "mgmt0"}
NOMS_VOISINS = {"0.1.1": "rt-lil", "0.99.1": "rt-lil"}
PORTS_VOISINS = {"0.1.1": "ethernet-1/1", "0.99.1": "mgmt0"}


def test_un_voisin_par_ligne() -> None:
    voisins = assembler_voisins_lldp(PORTS_LOCAUX, {}, NOMS_VOISINS, PORTS_VOISINS, {})
    assert voisins == [
        {"port_local": "ethernet-1/1", "voisin": "rt-lil", "port_voisin": "ethernet-1/1"}
    ]


def test_le_port_d_administration_est_ignore() -> None:
    # mgmt0 est relié au réseau d'administration, pas au réseau supervisé.
    voisins = assembler_voisins_lldp(PORTS_LOCAUX, {}, NOMS_VOISINS, PORTS_VOISINS, {})
    assert all(v["port_local"] != "mgmt0" for v in voisins)


def test_aucun_voisin() -> None:
    assert assembler_voisins_lldp(PORTS_LOCAUX, {}, {}, {}, {}) == []


def test_port_voisin_illisible_remplace_par_sa_description() -> None:
    # Certains équipements donnent une adresse MAC en octets bruts au lieu d'un nom de port.
    voisins = assembler_voisins_lldp(
        PORTS_LOCAUX,
        {},
        {"0.2.1": "AP-LIL-01"},
        {"0.2.1": "\x00\x1a\x2b\x3c\x4d\x5e"},
        {"0.2.1": "eth0"},
    )
    assert voisins[0]["port_voisin"] == "eth0"


def test_port_local_inconnu_garde_son_numero() -> None:
    voisins = assembler_voisins_lldp({}, {}, {"0.7.1": "SW-LIL"}, {"0.7.1": "Gi1/0/1"}, {})
    assert voisins[0]["port_local"] == "7"


def test_ligne_mal_formee_ignoree() -> None:
    assert assembler_voisins_lldp(PORTS_LOCAUX, {}, {"1": "rt-lil"}, {}, {}) == []


def test_port_voisin_annonce_par_adresse_mac_remplace_par_sa_description() -> None:
    # Bug trouvé sur le labo : lldpd annonce son port par son adresse MAC (sous-type 3).
    # Certains octets ressemblent à des lettres (« zØu »), et passaient pour un nom de port.
    # Le sous-type dit ce que contient l'identifiant : c'est lui qu'il faut croire.
    voisins = assembler_voisins_lldp(
        PORTS_LOCAUX,
        {},
        {"0.2.1": "ap-lil-01"},
        {"0.2.1": "zØu"},
        {"0.2.1": "eth1"},
        sous_types_voisins={"0.2.1": "3"},
    )
    assert voisins[0]["port_voisin"] == "eth1"


def test_port_voisin_annonce_par_nom_garde_son_nom() -> None:
    # Sous-type 5 : l'identifiant est le nom du port (cas des SR Linux).
    voisins = assembler_voisins_lldp(
        PORTS_LOCAUX,
        {},
        {"0.1.1": "rt-lil"},
        {"0.1.1": "ethernet-1/1"},
        {"0.1.1": "lien vers Lille"},
        sous_types_voisins={"0.1.1": "5"},
    )
    assert voisins[0]["port_voisin"] == "ethernet-1/1"

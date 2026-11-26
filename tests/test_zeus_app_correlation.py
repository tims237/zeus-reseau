"""Tests de la corrélation, sur la topologie du labo à quatre équipements.

    rt-dc ──e1-1────e1-1── rt-lil ──e1-2────e1-1── sw-lil ──e1-2────eth1── ap-lil-01

La racine est rt-dc, le routeur du datacenter.
"""

from datetime import datetime, timedelta

from zeus_app.correlation import correler
from zeus_core.modeles import Evenement, Lien

T0 = datetime(2026, 11, 26, 9, 0, 0)
RACINE = "rt-dc"

LIENS = [
    Lien(
        equipement_a="rt-dc",
        interface_a="ethernet-1/1",
        equipement_b="rt-lil",
        interface_b="ethernet-1/1",
    ),
    Lien(
        equipement_a="rt-lil",
        interface_a="ethernet-1/2",
        equipement_b="sw-lil",
        interface_b="ethernet-1/1",
    ),
    Lien(
        equipement_a="sw-lil",
        interface_a="ethernet-1/2",
        equipement_b="ap-lil-01",
        interface_b="eth1",
    ),
]


def evt(
    equipement: str,
    nature: str,
    interface: str | None = None,
    valeur: float | None = None,
    secondes: int = 0,
) -> Evenement:
    """Petit raccourci pour fabriquer un événement, « secondes » après T0."""
    return Evenement.model_validate(
        {
            "equipement_id": equipement,
            "interface": interface,
            "nature": nature,
            "horodatage": T0 + timedelta(seconds=secondes),
            "valeur": valeur,
        }
    )


# --- Règle 2 : un câble coupé ----------------------------------------------------------


def test_deux_bouts_du_meme_cable_donnent_un_seul_incident() -> None:
    # Le cas de l'essai B3 sur le labo : Lille coupe son port, les deux bouts tombent.
    incidents = correler(
        [
            evt("rt-dc", "port_down", "ethernet-1/1"),
            evt("rt-lil", "port_down", "ethernet-1/1"),
        ],
        LIENS,
        RACINE,
    )
    assert len(incidents) == 1
    cable = incidents[0]
    assert cable.categorie == "cable"
    assert cable.gravite == "down"
    assert cable.titre == "Câble coupé entre rt-dc/ethernet-1/1 et rt-lil/ethernet-1/1"
    assert cable.equipements_touches == ["rt-dc", "rt-lil"]


def test_le_meme_cable_a_toujours_le_meme_identifiant() -> None:
    # Que les événements arrivent dans un sens ou dans l'autre, même câble, même id :
    # plus tard, c'est ce qui évitera d'ouvrir deux fois le même incident.
    dans_un_sens = correler(
        [evt("rt-dc", "port_down", "ethernet-1/1"), evt("rt-lil", "port_down", "ethernet-1/1")],
        LIENS,
        RACINE,
    )
    dans_l_autre = correler(
        [evt("rt-lil", "port_down", "ethernet-1/1"), evt("rt-dc", "port_down", "ethernet-1/1")],
        LIENS,
        RACINE,
    )
    assert dans_un_sens[0].id == dans_l_autre[0].id


# --- Règle 3 : un port seul ------------------------------------------------------------


def test_un_seul_bout_tombe_donne_un_incident_port() -> None:
    incidents = correler([evt("sw-lil", "port_down", "ethernet-1/2")], LIENS, RACINE)
    assert len(incidents) == 1
    assert incidents[0].categorie == "port"
    assert incidents[0].titre == "Port ethernet-1/2 de sw-lil tombé"


def test_cable_inconnu_donne_deux_incidents_port() -> None:
    # Sans B2, impossible de savoir que ces deux ports sont reliés : deux incidents.
    incidents = correler(
        [
            evt("rt-dc", "port_down", "ethernet-1/1"),
            evt("rt-lil", "port_down", "ethernet-1/1"),
        ],
        [],  # aucun câble connu
        RACINE,
    )
    assert [i.categorie for i in incidents] == ["port", "port"]


# --- Règle 1 : un équipement hors ligne, et la cascade ---------------------------------


def test_routeur_mort_un_seul_incident_avec_ses_consequences() -> None:
    # rt-lil tombe : sw-lil et la borne, derrière lui, ne répondent plus non plus.
    incidents = correler(
        [
            evt("sw-lil", "injoignable", secondes=2),
            evt("rt-lil", "injoignable", secondes=1),
            evt("ap-lil-01", "injoignable", secondes=3),
        ],
        LIENS,
        RACINE,
    )
    assert len(incidents) == 1
    panne = incidents[0]
    assert panne.categorie == "equipement"
    assert panne.equipement_id == "rt-lil"  # la cause, pas les conséquences
    assert panne.equipements_touches == ["rt-lil", "ap-lil-01", "sw-lil"]  # la cause d'abord
    assert panne.titre == (
        "rt-lil hors ligne, 2 équipement(s) coupé(s) derrière lui : ap-lil-01, sw-lil"
    )
    assert panne.ouvert_le == T0 + timedelta(seconds=1)  # l'heure du premier symptôme


def test_les_ports_d_un_routeur_mort_ne_font_pas_d_incident_en_plus() -> None:
    # rt-lil est mort : le port de rt-dc qui va vers lui tombe aussi. Ce n'est qu'un
    # symptôme de la même panne : un seul incident, celui de rt-lil.
    incidents = correler(
        [
            evt("rt-lil", "injoignable"),
            evt("sw-lil", "injoignable"),
            evt("ap-lil-01", "injoignable"),
            evt("rt-dc", "port_down", "ethernet-1/1"),
        ],
        LIENS,
        RACINE,
    )
    assert [i.id for i in incidents] == ["equipement:rt-lil"]


def test_equipement_au_bout_de_la_chaine_sans_consequence() -> None:
    incidents = correler([evt("ap-lil-01", "injoignable")], LIENS, RACINE)
    assert incidents[0].titre == "ap-lil-01 hors ligne"
    assert incidents[0].equipements_touches == ["ap-lil-01"]


def test_equipement_inconnu_de_la_topologie() -> None:
    # Une imprimante sans câble connu : elle est sa propre cause, sans conséquence.
    incidents = correler([evt("172.20.20.6", "injoignable")], LIENS, RACINE)
    assert incidents[0].equipement_id == "172.20.20.6"


# --- Règle 4 : les lenteurs ------------------------------------------------------------


def test_cpu_et_latence_du_meme_equipement_un_seul_incident_lent() -> None:
    incidents = correler(
        [
            evt("ap-lil-01", "latence_elevee", valeur=545.1),
            evt("ap-lil-01", "cpu_eleve", valeur=92.0),
        ],
        LIENS,
        RACINE,
    )
    assert len(incidents) == 1
    assert incidents[0].gravite == "lent"
    assert incidents[0].categorie == "lenteur"
    assert incidents[0].titre == "ap-lil-01 lent (latence 545.1 ms, CPU 92.0 %)"


def test_un_equipement_mort_n_est_pas_lent() -> None:
    incidents = correler(
        [evt("rt-lil", "injoignable"), evt("rt-lil", "latence_elevee", valeur=500.0)],
        LIENS,
        RACINE,
    )
    assert [i.categorie for i in incidents] == ["equipement"]


# --- Ce qui ne fait pas d'incident -----------------------------------------------------


def test_les_retours_a_la_normale_ne_font_pas_d_incident() -> None:
    incidents = correler(
        [evt("rt-dc", "port_up", "ethernet-1/1"), evt("rt-lil", "joignable")],
        LIENS,
        RACINE,
    )
    assert incidents == []


def test_aucun_evenement_aucun_incident() -> None:
    assert correler([], LIENS, RACINE) == []


# --- Tout à la fois --------------------------------------------------------------------


def test_plusieurs_pannes_en_meme_temps() -> None:
    # Un câble coupé au datacenter, et une borne lente : deux incidents bien séparés.
    incidents = correler(
        [
            evt("rt-dc", "port_down", "ethernet-1/1"),
            evt("rt-lil", "port_down", "ethernet-1/1"),
            evt("ap-lil-01", "latence_elevee", valeur=300.0),
        ],
        LIENS,
        RACINE,
    )
    assert [i.categorie for i in incidents] == ["cable", "lenteur"]

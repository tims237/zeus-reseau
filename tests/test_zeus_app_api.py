"""Tests de l'API, avec une fausse photo à la place du vrai réseau."""

from datetime import datetime

from fastapi.testclient import TestClient

from zeus_app.api import Memoire, creer_api
from zeus_core.modeles import Equipement, EtatReseau, Lien, Releve

PHOTO = EtatReseau(
    horodatage=datetime(2026, 11, 22, 16, 0, 0),
    equipements=[
        Equipement(id="rt-dc", ip="172.20.20.5"),
        Equipement(id="rt-lil", ip="172.20.20.2"),
    ],
    liens=[
        Lien(
            equipement_a="rt-dc",
            interface_a="ethernet-1/1",
            equipement_b="rt-lil",
            interface_b="ethernet-1/1",
        )
    ],
)


def fausse_photo() -> EtatReseau:
    return PHOTO


def photo_qui_echoue() -> EtatReseau:
    raise RuntimeError("le réseau ne répond pas")


def test_etat_renvoie_la_photo_complete() -> None:
    with TestClient(creer_api(fausse_photo)) as client:  # « with » lance le démarrage
        reponse = client.get("/etat")
    assert reponse.status_code == 200
    assert EtatReseau.model_validate(reponse.json()) == PHOTO


def test_equipements() -> None:
    with TestClient(creer_api(fausse_photo)) as client:
        reponse = client.get("/equipements")
    assert [e["id"] for e in reponse.json()] == ["rt-dc", "rt-lil"]


def test_liens() -> None:
    with TestClient(creer_api(fausse_photo)) as client:
        reponse = client.get("/liens")
    assert reponse.json()[0]["equipement_b"] == "rt-lil"


def test_pas_encore_de_photo_reponse_503() -> None:
    # La collecte échoue au démarrage : l'API tourne quand même, et dit d'attendre.
    with TestClient(creer_api(photo_qui_echoue)) as client:
        reponse = client.get("/etat")
    assert reponse.status_code == 503


# --- Le registre des incidents -----------------------------------------------------------

T = datetime(2026, 11, 26, 10, 0, 0)
LIEN_DC_LIL = Lien(
    equipement_a="rt-dc",
    interface_a="ethernet-1/1",
    equipement_b="rt-lil",
    interface_b="ethernet-1/1",
)


def photo_a(minute: int, cable_ok: bool, latence_lil: float = 2.0) -> EtatReseau:
    """La photo de 10 h « minute » : le câble rt-dc ↔ rt-lil est-il branché ?"""
    heure = T.replace(minute=minute)
    return EtatReseau(
        horodatage=heure,
        liens=[LIEN_DC_LIL],
        releves=[
            Releve(
                equipement_id="rt-dc",
                horodatage=heure,
                repond=True,
                interfaces={"ethernet-1/1": cable_ok},
                latence_ms=2.0,
            ),
            Releve(
                equipement_id="rt-lil",
                horodatage=heure,
                repond=True,
                interfaces={"ethernet-1/1": cable_ok},
                latence_ms=latence_lil,
            ),
        ],
    )


def test_premiere_photo_aucun_incident() -> None:
    # Rien à comparer : pas d'événement, donc pas d'incident.
    memoire = Memoire("rt-dc")
    memoire.recevoir(photo_a(0, cable_ok=False))
    assert memoire.incidents == {}


def test_cable_coupe_un_incident() -> None:
    memoire = Memoire("rt-dc")
    memoire.recevoir(photo_a(0, cable_ok=True))
    memoire.recevoir(photo_a(1, cable_ok=False))  # 10 h 01 : le câble est coupé
    assert list(memoire.incidents) == ["cable:rt-dc/ethernet-1/1~rt-lil/ethernet-1/1"]


def test_la_panne_reste_tant_qu_elle_n_est_pas_resolue() -> None:
    # À 10 h 02, plus rien ne change : comparer() ne voit rien. La panne doit rester.
    memoire = Memoire("rt-dc")
    memoire.recevoir(photo_a(0, cable_ok=True))
    memoire.recevoir(photo_a(1, cable_ok=False))
    memoire.recevoir(photo_a(2, cable_ok=False))
    memoire.recevoir(photo_a(3, cable_ok=False))
    assert len(memoire.incidents) == 1
    incident = next(iter(memoire.incidents.values()))
    assert incident.ouvert_le == T.replace(minute=1)  # « depuis 10 h 01 »


def test_une_lenteur_qui_dure_n_est_notee_qu_une_fois() -> None:
    # verifier_seuils() la signale à chaque photo, mais l'id reste lenteur:rt-lil.
    memoire = Memoire("rt-dc")
    memoire.recevoir(photo_a(0, cable_ok=True))
    memoire.recevoir(photo_a(1, cable_ok=True, latence_lil=500.0))
    memoire.recevoir(photo_a(2, cable_ok=True, latence_lil=520.0))
    assert list(memoire.incidents) == ["lenteur:rt-lil"]
    assert memoire.incidents["lenteur:rt-lil"].ouvert_le == T.replace(minute=1)


def test_route_incidents() -> None:
    memoire = Memoire("rt-dc")
    memoire.recevoir(photo_a(0, cable_ok=True))
    memoire.recevoir(photo_a(1, cable_ok=False))
    # La photo du démarrage échoue : l'API garde la mémoire qu'on lui a donnée.
    with TestClient(creer_api(photo_qui_echoue, memoire=memoire)) as client:
        reponse = client.get("/incidents")
    assert reponse.status_code == 200
    assert [i["categorie"] for i in reponse.json()] == ["cable"]


def test_route_incidents_vide_quand_tout_va_bien() -> None:
    with TestClient(creer_api(fausse_photo)) as client:
        reponse = client.get("/incidents")
    assert reponse.json() == []


# --- La fermeture des incidents ----------------------------------------------------------


def test_cable_rebranche_l_incident_est_ferme() -> None:
    memoire = Memoire("rt-dc")
    memoire.recevoir(photo_a(0, cable_ok=True))
    memoire.recevoir(photo_a(1, cable_ok=False))  # 10 h 01 : coupé
    memoire.recevoir(photo_a(2, cable_ok=False))  # 10 h 02 : toujours coupé
    memoire.recevoir(photo_a(3, cable_ok=True))  # 10 h 03 : rebranché
    assert memoire.incidents == {}  # plus rien d'ouvert
    assert len(memoire.historique) == 1
    ferme = memoire.historique[0]
    assert ferme.ouvert_le == T.replace(minute=1)
    assert ferme.clos_le == T.replace(minute=3)  # la panne a duré 2 minutes
    assert not ferme.est_ouvert


def test_cable_a_moitie_revenu_reste_ouvert() -> None:
    # Un seul bout revenu : le câble n'est pas réparé, l'incident reste ouvert.
    memoire = Memoire("rt-dc")
    memoire.recevoir(photo_a(0, cable_ok=True))
    memoire.recevoir(photo_a(1, cable_ok=False))
    a_moitie = photo_a(2, cable_ok=False)
    a_moitie.releves[0].interfaces["ethernet-1/1"] = True  # rt-dc revient, pas rt-lil
    memoire.recevoir(a_moitie)
    assert len(memoire.incidents) == 1
    assert memoire.historique == []


def test_lenteur_finie_l_incident_est_ferme() -> None:
    memoire = Memoire("rt-dc")
    memoire.recevoir(photo_a(0, cable_ok=True))
    memoire.recevoir(photo_a(1, cable_ok=True, latence_lil=500.0))
    memoire.recevoir(photo_a(2, cable_ok=True, latence_lil=3.0))  # la latence est revenue
    assert memoire.incidents == {}
    assert [i.id for i in memoire.historique] == ["lenteur:rt-lil"]


def test_une_panne_qui_revient_rouvre_un_incident() -> None:
    # Fermé à 10 h 02, recoupé à 10 h 03 : un nouvel incident, ouvert à 10 h 03.
    memoire = Memoire("rt-dc")
    memoire.recevoir(photo_a(0, cable_ok=True))
    memoire.recevoir(photo_a(1, cable_ok=False))
    memoire.recevoir(photo_a(2, cable_ok=True))
    memoire.recevoir(photo_a(3, cable_ok=False))
    assert len(memoire.historique) == 1
    nouveau = next(iter(memoire.incidents.values()))
    assert nouveau.ouvert_le == T.replace(minute=3)


def test_route_historique() -> None:
    memoire = Memoire("rt-dc")
    memoire.recevoir(photo_a(0, cable_ok=True))
    memoire.recevoir(photo_a(1, cable_ok=False))
    memoire.recevoir(photo_a(2, cable_ok=True))
    with TestClient(creer_api(photo_qui_echoue, memoire=memoire)) as client:
        ouverts = client.get("/incidents").json()
        fermes = client.get("/incidents/historique").json()
    assert ouverts == []
    assert [i["categorie"] for i in fermes] == ["cable"]
    assert fermes[0]["clos_le"] is not None


# --- La fiche d'un équipement ------------------------------------------------------------


def test_un_equipement_par_son_nom() -> None:
    with TestClient(creer_api(fausse_photo)) as client:
        reponse = client.get("/equipements/rt-lil")
    assert reponse.status_code == 200
    assert reponse.json()["ip"] == "172.20.20.2"


def test_equipement_inconnu_reponse_404() -> None:
    with TestClient(creer_api(fausse_photo)) as client:
        reponse = client.get("/equipements/rt-paris")
    assert reponse.status_code == 404
    assert "rt-paris" in reponse.json()["detail"]

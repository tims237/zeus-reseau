"""Tests de l'API, avec une fausse photo à la place du vrai réseau."""

from datetime import datetime

from fastapi.testclient import TestClient

from zeus_app.api import creer_api
from zeus_core.modeles import Equipement, EtatReseau, Lien

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

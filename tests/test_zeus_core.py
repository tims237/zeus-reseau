"""Tests des modèles partagés.

Deux sortes de tests :
- les tests « normaux » vérifient qu'une donnée correcte est acceptée ;
- les tests avec pytest.raises vérifient qu'une donnée interdite est bien refusée.
  Ils PASSENT quand l'erreur arrive, puisque c'est ce qu'on attend.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from zeus_core.modeles import (
    Emplacement,
    Equipement,
    EtatReseau,
    Incident,
    Lien,
    Releve,
    TypeEquipement,
)

# --- Emplacement ---------------------------------------------------------------


def test_emplacement_avec_site_seul() -> None:
    # Seul le site est obligatoire : les autres champs valent None.
    emp = Emplacement(site="LIL")
    assert emp.site == "LIL"
    assert emp.baie is None


def test_position_u_hors_limite_refusee() -> None:
    # 70 dépasse la limite haute (le=60) : Pydantic doit refuser.
    with pytest.raises(ValidationError):
        Emplacement(site="LIL", position_u=70)


def test_position_u_zero_refusee() -> None:
    # 0 est sous la limite basse (ge=1) : Pydantic doit refuser.
    with pytest.raises(ValidationError):
        Emplacement(site="LIL", position_u=0)


# --- Equipement ----------------------------------------------------------------


def test_equipement_minimal() -> None:
    # Avec seulement id et ip, les autres champs prennent leur valeur par défaut.
    eq = Equipement(id="SW-LIL-02", ip="10.3.0.2")
    assert eq.type is TypeEquipement.INCONNU
    assert eq.interfaces == []


def test_equipement_avec_emplacement() -> None:
    # Un modèle dans un modèle : l'équipement contient un Emplacement.
    eq = Equipement(
        id="SW-LIL-02",
        ip="10.3.0.2",
        type=TypeEquipement.SWITCH,
        emplacement=Emplacement(site="LIL", etage=2, baie="B2", position_u=14),
    )
    assert eq.emplacement is not None  # rassure mypy : l'emplacement existe
    assert eq.emplacement.baie == "B2"


def test_equipement_avec_modele() -> None:
    # id et ip sont obligatoires, même quand on veut seulement tester le modèle.
    eq = Equipement(
        id="SW-LIL-02",
        ip="10.3.0.2",
        modele="Cisco Catalyst 9200",
    )
    assert eq.modele == "Cisco Catalyst 9200"


def test_ip_invalide() -> None:
    # 999 dépasse 255 : ce n'est pas une IP valide, Pydantic doit refuser.
    with pytest.raises(ValidationError):
        Equipement(id="SW-X", ip="999.1.1.1")


# --- Lien ----------------------------------------------------------------------


def test_lien() -> None:
    # Le port Gi1/0/12 du switch est branché au port eth0 de la borne Wi-Fi.
    lien = Lien(
        equipement_a="SW-LIL-02",
        interface_a="Gi1/0/12",
        equipement_b="AP-LIL-02",
        interface_b="eth0",
    )
    assert lien.equipement_b == "AP-LIL-02"


# --- Incident ------------------------------------------------------------------


def test_incident_ouvert() -> None:
    # Pas de date de clôture : l'incident est encore ouvert.
    inc = Incident(
        id="1",
        equipement_id="SW-LIL-02",
        interface="Gi1/0/12",
        gravite="down",
        ouvert_le=datetime(2026, 11, 4, 9, 0),
    )
    assert inc.est_ouvert


def test_incident_clos() -> None:
    # Une date de clôture est donnée : l'incident n'est plus ouvert.
    inc = Incident(
        id="1",
        equipement_id="SW-LIL-02",
        interface="Gi1/0/12",
        gravite="down",
        ouvert_le=datetime(2026, 11, 4, 9, 0),
        clos_le=datetime(2026, 11, 4, 9, 30),
    )
    assert not inc.est_ouvert  # « not » inverse : on affirme qu'il n'est PAS ouvert


def test_gravite_inconnue_refusee() -> None:
    # "critique" n'est pas dans la liste "down" / "lent" : Pydantic doit refuser.
    with pytest.raises(ValidationError):
        Incident(
            id="2",
            equipement_id="SW-X",
            gravite="critique",
            ouvert_le=datetime(2026, 11, 4, 9, 0),
        )


def test_incident_sans_date_refuse() -> None:
    # ouvert_le est obligatoire : un incident sans date doit être refusé.
    with pytest.raises(ValidationError):
        Incident(id="3", equipement_id="SW-X", gravite="lent")


# --- EtatReseau : la photo du réseau ---------------------------------------------------

PHOTO_DE = datetime(2026, 11, 22, 15, 12, 4)


def test_etat_reseau_vide() -> None:
    # Un réseau où l'on n'a encore rien trouvé : seule l'heure est obligatoire.
    etat = EtatReseau(horodatage=PHOTO_DE)
    assert etat.equipements == []
    assert etat.liens == []
    assert etat.releves == []


def test_etat_reseau_sans_heure_refuse() -> None:
    with pytest.raises(ValidationError):
        EtatReseau()  # type: ignore[call-arg]


def test_etat_reseau_complet() -> None:
    etat = EtatReseau(
        horodatage=PHOTO_DE,
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
        releves=[Releve(equipement_id="rt-dc", horodatage=PHOTO_DE, repond=True)],
    )
    assert [e.id for e in etat.equipements] == ["rt-dc", "rt-lil"]
    assert etat.liens[0].equipement_b == "rt-lil"
    assert etat.releves[0].repond


def test_etat_reseau_mauvais_compartiment_refuse() -> None:
    # Un relevé rangé à la place d'un câble : Pydantic refuse la boîte mal remplie.
    with pytest.raises(ValidationError):
        EtatReseau(
            horodatage=PHOTO_DE,
            liens=[Releve(equipement_id="rt-dc", horodatage=PHOTO_DE, repond=True)],  # type: ignore[list-item]
        )


def test_etat_reseau_aller_retour_json() -> None:
    # Ce que l'API enverra : la photo en JSON, puis relue à l'arrivée, identique.
    etat = EtatReseau(
        horodatage=PHOTO_DE,
        equipements=[Equipement(id="rt-dc", ip="172.20.20.5")],
        releves=[
            Releve(
                equipement_id="rt-dc",
                horodatage=PHOTO_DE,
                repond=True,
                interfaces={"ethernet-1/1": True},
            )
        ],
    )
    texte = etat.model_dump_json()
    assert '"rt-dc"' in texte
    assert EtatReseau.model_validate_json(texte) == etat

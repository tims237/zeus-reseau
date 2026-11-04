"""Tests des modèles partagés.

Deux sortes de tests :
- les tests « normaux » vérifient qu'une donnée correcte est acceptée ;
- les tests avec pytest.raises vérifient qu'une donnée interdite est bien refusée.
  Ils PASSENT quand l'erreur arrive, puisque c'est ce qu'on attend.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from zeus_core.modeles import Emplacement, Equipement, Incident, Lien, TypeEquipement

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

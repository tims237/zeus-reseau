import pytest
from pydantic import ValidationError

from zeus_core.modeles import Emplacement, Equipement, TypeEquipement


def test_emplacement_avec_site_seul() -> None:
    emp = Emplacement(site="LIL")
    assert emp.site == "LIL"
    assert emp.baie is None


def test_position_u_hors_limite_refusee() -> None:
    with pytest.raises(ValidationError):
        Emplacement(site="LIL", position_u=70)


def test_position_u_zero_refusee() -> None:
    with pytest.raises(ValidationError):
        Emplacement(site="LIL", position_u=0)


def test_equipement_minimal() -> None:
    eq = Equipement(id="SW-LIL-02", ip="10.3.0.2")
    assert eq.type is TypeEquipement.INCONNU
    assert eq.interfaces == []


def test_equipement_avec_emplacement() -> None:
    eq = Equipement(
        id="SW-LIL-02",
        ip="10.3.0.2",
        type=TypeEquipement.SWITCH,
        emplacement=Emplacement(site="LIL", etage=2, baie="B2", position_u=14),
    )
    assert eq.emplacement is not None
    assert eq.emplacement.baie == "B2"


def test_equipement_avec_modele() -> None:
    eq = Equipement(
        id="SW-LIL-02",
        ip="10.3.0.2",
        modele="Cisco Catalyst 9200",
    )
    assert eq.modele == "Cisco Catalyst 9200"


def test_ip_invalide() -> None:
    with pytest.raises(ValidationError):
        Equipement(id="SW-X", ip="999.1.1.1")

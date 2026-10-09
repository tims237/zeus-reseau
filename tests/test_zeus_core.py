import pytest
from pydantic import ValidationError

from zeus_core.modeles import Emplacement


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

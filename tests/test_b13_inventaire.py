"""Tests de B13 : lecture du champ sysLocation."""

import pytest

from briques.b13_inventaire import lire_syslocation

# --- Cas normaux ---------------------------------------------------------------


def test_syslocation_complet() -> None:
    # Les 6 morceaux sont présents : chaque champ est rempli.
    emp = lire_syslocation("LIL/BatA/E2/SalleServeur/B2/U14")
    assert emp.site == "LIL"
    assert emp.batiment == "BatA"
    assert emp.etage == 2
    assert emp.salle == "SalleServeur"
    assert emp.baie == "B2"
    assert emp.position_u == 14


def test_syslocation_rdc() -> None:
    # « RDC » veut dire rez-de-chaussée : l'étage 0.
    emp = lire_syslocation("LYO/Principal/RDC")
    assert emp.etage == 0


def test_syslocation_site_seul() -> None:
    # Seul le site est donné : tout le reste vaut None.
    emp = lire_syslocation("DC")
    assert emp.site == "DC"
    assert emp.batiment is None
    assert emp.baie is None


def test_syslocation_avec_espaces() -> None:
    # Les espaces autour des « / » sont ignorés.
    emp = lire_syslocation(" LIL / BatA / E2 ")
    assert emp.batiment == "BatA"
    assert emp.etage == 2


# --- Cas refusés ---------------------------------------------------------------


def test_syslocation_vide_refuse() -> None:
    with pytest.raises(ValueError):
        lire_syslocation("   ")


def test_etage_illisible_refuse() -> None:
    # « deuxieme » n'est ni RDC ni E suivi d'un numéro.
    with pytest.raises(ValueError):
        lire_syslocation("LIL/BatA/deuxieme")


def test_position_u_illisible_refusee() -> None:
    with pytest.raises(ValueError):
        lire_syslocation("LIL/BatA/E2/SalleServeur/B2/quatorze")


def test_trop_de_morceaux_refuse() -> None:
    with pytest.raises(ValueError):
        lire_syslocation("LIL/BatA/E2/SalleServeur/B2/U14/encore")

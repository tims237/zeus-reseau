"""Tests de B3 Supervision, avec une fausse sonde qu'on peut « faire tomber »."""

from datetime import datetime

from briques.b03_supervision import comparer, relever, verifier_seuils

T1 = datetime(2026, 11, 5, 9, 0)  # premier relevé
T2 = datetime(2026, 11, 5, 9, 1)  # relevé suivant, une minute plus tard


class FausseSondeSupervision:
    """Un switch et un routeur dont on peut modifier l'état entre deux relevés."""

    def __init__(self) -> None:
        self.ports: dict[str, dict[str, bool] | None] = {
            "SW-LIL-02": {"Gi1/0/1": True, "Gi1/0/12": True},
            "RT-LIL": {"Gi0/0/0": True},
        }
        self.charge: dict[str, float] = {"SW-LIL-02": 20.0, "RT-LIL": 15.0}
        self.latence: dict[str, float] = {"SW-LIL-02": 3.0, "RT-LIL": 2.0}

    def etat_interfaces(self, equipement: str) -> dict[str, bool] | None:
        etat = self.ports.get(equipement)
        return dict(etat) if etat is not None else None  # une copie, pas l'original

    def cpu(self, equipement: str) -> float | None:
        return self.charge.get(equipement)

    def latence_ms(self, equipement: str) -> float | None:
        return self.latence.get(equipement)


EQUIPEMENTS = ["SW-LIL-02", "RT-LIL"]


# --- relever --------------------------------------------------------------------


def test_relever_prend_les_constantes() -> None:
    releves = relever(EQUIPEMENTS, FausseSondeSupervision(), T1)
    switch = releves[0]
    assert switch.repond
    assert switch.interfaces == {"Gi1/0/1": True, "Gi1/0/12": True}
    assert switch.cpu == 20.0


def test_relever_equipement_muet() -> None:
    sonde = FausseSondeSupervision()
    sonde.ports["RT-LIL"] = None  # le routeur ne répond plus
    routeur = relever(EQUIPEMENTS, sonde, T1)[1]
    assert not routeur.repond
    assert routeur.interfaces == {}


# --- comparer -------------------------------------------------------------------


def test_rien_ne_change_aucun_evenement() -> None:
    sonde = FausseSondeSupervision()
    avant = relever(EQUIPEMENTS, sonde, T1)
    apres = relever(EQUIPEMENTS, sonde, T2)
    assert comparer(avant, apres) == []


def test_un_port_tombe() -> None:
    # Le port 12 du switch tombe entre les deux relevés.
    sonde = FausseSondeSupervision()
    avant = relever(EQUIPEMENTS, sonde, T1)
    sonde.ports["SW-LIL-02"] = {"Gi1/0/1": True, "Gi1/0/12": False}
    apres = relever(EQUIPEMENTS, sonde, T2)

    evenements = comparer(avant, apres)
    assert len(evenements) == 1
    assert evenements[0].nature == "port_down"
    assert evenements[0].equipement_id == "SW-LIL-02"
    assert evenements[0].interface == "Gi1/0/12"


def test_un_port_revient() -> None:
    sonde = FausseSondeSupervision()
    sonde.ports["SW-LIL-02"] = {"Gi1/0/1": True, "Gi1/0/12": False}
    avant = relever(EQUIPEMENTS, sonde, T1)
    sonde.ports["SW-LIL-02"] = {"Gi1/0/1": True, "Gi1/0/12": True}
    apres = relever(EQUIPEMENTS, sonde, T2)
    assert [e.nature for e in comparer(avant, apres)] == ["port_up"]


def test_port_deja_down_ne_recree_pas_d_evenement() -> None:
    # Le port est down aux deux relevés : ce n'est pas un nouveau changement.
    sonde = FausseSondeSupervision()
    sonde.ports["SW-LIL-02"] = {"Gi1/0/1": True, "Gi1/0/12": False}
    avant = relever(EQUIPEMENTS, sonde, T1)
    apres = relever(EQUIPEMENTS, sonde, T2)
    assert comparer(avant, apres) == []


def test_equipement_qui_ne_repond_plus() -> None:
    sonde = FausseSondeSupervision()
    avant = relever(EQUIPEMENTS, sonde, T1)
    sonde.ports["RT-LIL"] = None
    apres = relever(EQUIPEMENTS, sonde, T2)
    evenements = comparer(avant, apres)
    assert [(e.equipement_id, e.nature) for e in evenements] == [("RT-LIL", "injoignable")]


# --- verifier_seuils ------------------------------------------------------------


def test_tout_va_bien_aucun_depassement() -> None:
    assert verifier_seuils(relever(EQUIPEMENTS, FausseSondeSupervision(), T1)) == []


def test_cpu_trop_eleve() -> None:
    sonde = FausseSondeSupervision()
    sonde.charge["RT-LIL"] = 92.0
    evenements = verifier_seuils(relever(EQUIPEMENTS, sonde, T1))
    assert [(e.equipement_id, e.nature, e.valeur) for e in evenements] == [
        ("RT-LIL", "cpu_eleve", 92.0)
    ]


def test_latence_trop_elevee() -> None:
    sonde = FausseSondeSupervision()
    sonde.latence["SW-LIL-02"] = 210.0
    evenements = verifier_seuils(relever(EQUIPEMENTS, sonde, T1))
    assert [e.nature for e in evenements] == ["latence_elevee"]

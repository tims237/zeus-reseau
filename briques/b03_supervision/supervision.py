"""B3 Supervision.

B1, B13 et B2 font l'inventaire une fois. B3 repasse régulièrement (par exemple toutes
les minutes) et prend les « constantes » de chaque équipement : l'état de ses ports,
son CPU, sa latence. Trois étapes :
1. relever()         : prendre les mesures de tous les équipements
2. comparer()        : trouver ce qui a changé depuis le relevé précédent
3. verifier_seuils() : repérer ce qui est trop lent ou trop chargé

Comme B1 et B2, B3 passe par une sondes : la vraie interroge le réseau en SNMP
(sondes/sonde_snmp.py), une fausse sondes suffit pour les tests.
"""

from datetime import datetime
from typing import Protocol

from zeus_core.modeles import Evenement, Releve


class SondeSupervision(Protocol):
    """Ce dont la supervision a besoin pour mesurer un équipement."""

    def etat_interfaces(self, equipement: str) -> dict[str, bool] | None:
        """Renvoie l'état de chaque port (True = up), ou None si l'équipement ne répond pas."""
        ...

    def cpu(self, equipement: str) -> float | None:
        """Renvoie la charge CPU en pourcentage, ou None si inconnue."""
        ...

    def latence_ms(self, equipement: str) -> float | None:
        """Renvoie le temps de réponse en millisecondes, ou None si inconnu."""
        ...


def relever(equipements: list[str], sonde: SondeSupervision, maintenant: datetime) -> list[Releve]:
    """Prend les constantes de chaque équipement.

    « maintenant » est passé en paramètre plutôt que lu dans l'horloge : les tests peuvent
    ainsi choisir l'heure, et le résultat est toujours le même.
    """
    releves: list[Releve] = []
    for equipement in equipements:
        interfaces = sonde.etat_interfaces(equipement)
        if interfaces is None:
            # Aucune réponse : on note seulement qu'il ne répond pas.
            releves.append(Releve(equipement_id=equipement, horodatage=maintenant, repond=False))
            continue
        releves.append(
            Releve(
                equipement_id=equipement,
                horodatage=maintenant,
                repond=True,
                interfaces=interfaces,
                cpu=sonde.cpu(equipement),
                latence_ms=sonde.latence_ms(equipement),
            )
        )
    return releves


def comparer(avant: list[Releve], apres: list[Releve]) -> list[Evenement]:
    """Compare deux relevés et renvoie ce qui a changé.

    On ne signale que les CHANGEMENTS : un port déjà down au relevé précédent ne crée pas
    un nouvel événement à chaque minute.
    """
    precedent = {r.equipement_id: r for r in avant}  # pour retrouver vite l'ancien relevé
    evenements: list[Evenement] = []
    for nouveau in apres:
        ancien = precedent.get(nouveau.equipement_id)
        if ancien is None:
            continue  # équipement absent du relevé précédent : rien à comparer

        # 1. L'équipement lui-même : répond-il encore ?
        if ancien.repond and not nouveau.repond:
            evenements.append(_evenement(nouveau, "injoignable"))
            continue  # inutile de regarder ses ports : on ne les connaît plus
        if not ancien.repond and nouveau.repond:
            evenements.append(_evenement(nouveau, "joignable"))

        # 2. Ses ports : lesquels ont changé d'état ?
        for port, est_up in nouveau.interfaces.items():
            etait_up = ancien.interfaces.get(port)
            if etait_up is True and not est_up:
                evenements.append(_evenement(nouveau, "port_down", interface=port))
            elif etait_up is False and est_up:
                evenements.append(_evenement(nouveau, "port_up", interface=port))
    return evenements


def verifier_seuils(
    releves: list[Releve], seuil_cpu: float = 85, seuil_latence_ms: float = 120
) -> list[Evenement]:
    """Renvoie un événement pour chaque CPU ou latence au-dessus de son seuil."""
    evenements: list[Evenement] = []
    for r in releves:
        if r.cpu is not None and r.cpu > seuil_cpu:
            evenements.append(_evenement(r, "cpu_eleve", valeur=r.cpu))
        if r.latence_ms is not None and r.latence_ms > seuil_latence_ms:
            evenements.append(_evenement(r, "latence_elevee", valeur=r.latence_ms))
    return evenements


def _evenement(
    releve: Releve,
    nature: str,
    interface: str | None = None,
    valeur: float | None = None,
) -> Evenement:
    """Petit raccourci pour créer un Evenement à partir d'un relevé."""
    return Evenement.model_validate(
        {
            "equipement_id": releve.equipement_id,
            "interface": interface,
            "nature": nature,
            "horodatage": releve.horodatage,
            "valeur": valeur,
        }
    )

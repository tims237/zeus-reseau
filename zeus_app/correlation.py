"""La corrélation : transformer des événements en incidents, un par vraie panne.

Une seule panne fait souvent plusieurs événements. Un câble coupé donne deux port_down,
un sur chaque bout ; un routeur mort rend injoignable tout ce qui est derrière lui.
Sans corrélation, l'admin reçoit une alerte par symptôme et cherche la cause tout seul.

correler() applique quatre règles, du plus gros au plus petit :
1. équipement hors ligne : on cherche la cause, et tout ce qui est coupé derrière elle ;
2. câble coupé : les deux bouts d'un même câble sont tombés ;
3. port seul : un port tombé qui n'entre dans aucune règle au-dessus ;
4. lenteur : CPU ou latence trop haut (gravité « lent », pas « down »).
Chaque règle saute ce que les règles précédentes ont déjà expliqué : si rt-lil est mort,
ses câbles sont forcément tombés aussi, inutile d'ouvrir un incident par câble.

Les retours à la normale (port_up, joignable) ne créent pas d'incident : ils serviront
plus tard à fermer les incidents, après la vérification (phase 3).

La corrélation utilise B2 (equipements_injoignables) et les événements de B3 : elle
n'est donc pas une brique, mais une partie du chef d'orchestre, zeus_app.
"""

from datetime import datetime

from briques.b02_topologie import equipements_injoignables
from zeus_core.modeles import Evenement, Incident, Lien


def correler(evenements: list[Evenement], liens: list[Lien], racine: str) -> list[Incident]:
    """Regroupe les événements d'une même panne en un seul incident.

    racine : l'équipement d'où part la supervision, en général le routeur du datacenter.
    C'est depuis lui qu'on regarde qui est « derrière » qui.
    """
    incidents: list[Incident] = []

    # --- Règle 1 : équipements hors ligne ---------------------------------------------
    hors_ligne = {e.equipement_id for e in evenements if e.nature == "injoignable"}
    couverts: set[str] = set()  # les équipements déjà expliqués par un incident
    for cause in sorted(_causes(hors_ligne, liens, racine)):
        # Tout ce qui est coupé de la racine si la cause tombe : ses conséquences.
        derriere = sorted(equipements_injoignables(racine, liens, {cause}))
        touches = [cause, *derriere]
        couverts.update(touches)
        titre = f"{cause} hors ligne"
        if derriere:
            titre += f", {len(derriere)} équipement(s) coupé(s) derrière lui : " + ", ".join(
                derriere
            )
        incidents.append(
            Incident(
                id=f"equipement:{cause}",
                equipement_id=cause,
                gravite="down",
                ouvert_le=_premiere_heure(evenements, touches),
                categorie="equipement",
                titre=titre,
                equipements_touches=touches,
            )
        )

    # Les ports tombés qui restent à expliquer : (équipement, port) -> événement.
    ports_tombes = {
        (e.equipement_id, e.interface): e
        for e in evenements
        if e.nature == "port_down"
        and e.interface is not None
        and e.equipement_id not in couverts  # un équipement mort a forcément ses ports down
        and _autre_bout(e.equipement_id, e.interface, liens) not in couverts
        # ↑ le port de rt-dc vers un rt-lil mort est un symptôme de la panne de rt-lil
    }

    # --- Règle 2 : câbles coupés ------------------------------------------------------
    for lien in liens:
        bout_a = (lien.equipement_a, lien.interface_a)
        bout_b = (lien.equipement_b, lien.interface_b)
        if bout_a in ports_tombes and bout_b in ports_tombes:
            # Les deux bouts sont tombés : un seul câble, un seul incident.
            evenement_a = ports_tombes.pop(bout_a)  # pop : on le retire, il est expliqué
            evenement_b = ports_tombes.pop(bout_b)
            a, b = sorted([bout_a, bout_b])  # trié : le même câble a toujours le même id
            incidents.append(
                Incident(
                    id=f"cable:{a[0]}/{a[1]}~{b[0]}/{b[1]}",
                    equipement_id=a[0],
                    interface=a[1],
                    gravite="down",
                    ouvert_le=min(evenement_a.horodatage, evenement_b.horodatage),
                    categorie="cable",
                    titre=f"Câble coupé entre {a[0]}/{a[1]} et {b[0]}/{b[1]}",
                    equipements_touches=[a[0], b[0]],
                )
            )

    # --- Règle 3 : ports seuls --------------------------------------------------------
    # Ce qui reste : l'autre bout n'est pas tombé, ou on ne connaît pas le câble.
    for (equipement, port), evenement in sorted(ports_tombes.items()):
        incidents.append(
            Incident(
                id=f"port:{equipement}/{port}",
                equipement_id=equipement,
                interface=port,
                gravite="down",
                ouvert_le=evenement.horodatage,
                categorie="port",
                titre=f"Port {port} de {equipement} tombé",
                equipements_touches=[equipement],
            )
        )

    # --- Règle 4 : lenteurs -----------------------------------------------------------
    # Un équipement mort ne peut pas être « lent » : on saute les équipements couverts.
    lents: dict[str, list[Evenement]] = {}
    for e in evenements:
        if e.nature in ("cpu_eleve", "latence_elevee") and e.equipement_id not in couverts:
            lents.setdefault(e.equipement_id, []).append(e)  # crée la liste si besoin
    for equipement, symptomes in sorted(lents.items()):
        # CPU et latence trop hauts en même temps : un seul incident, qui cite les deux.
        details = ", ".join(_detail_lenteur(s) for s in symptomes)
        incidents.append(
            Incident(
                id=f"lenteur:{equipement}",
                equipement_id=equipement,
                gravite="lent",
                ouvert_le=min(s.horodatage for s in symptomes),
                categorie="lenteur",
                titre=f"{equipement} lent ({details})",
                equipements_touches=[equipement],
            )
        )

    return incidents


def _causes(hors_ligne: set[str], liens: list[Lien], racine: str) -> set[str]:
    """Parmi les équipements hors ligne, garde ceux qui ne sont derrière aucun autre.

    sw-lil est derrière rt-lil : si rt-lil est hors ligne, sw-lil n'est qu'une conséquence.
    rt-lil n'est derrière aucun équipement hors ligne : c'est la cause.
    """
    consequences = set()
    for autre in hors_ligne:
        consequences |= equipements_injoignables(racine, liens, {autre})
    return hors_ligne - consequences


def _autre_bout(equipement: str, port: str, liens: list[Lien]) -> str | None:
    """L'équipement à l'autre bout du câble branché sur ce port, s'il est connu."""
    for lien in liens:
        if (lien.equipement_a, lien.interface_a) == (equipement, port):
            return lien.equipement_b
        if (lien.equipement_b, lien.interface_b) == (equipement, port):
            return lien.equipement_a
    return None


def _premiere_heure(evenements: list[Evenement], equipements: list[str]) -> datetime:
    """L'heure du premier événement de ces équipements : le début de la panne."""
    return min(e.horodatage for e in evenements if e.equipement_id in equipements)


def _detail_lenteur(evenement: Evenement) -> str:
    """« latence 545.1 ms » ou « CPU 92.0 % », pour le titre de l'incident."""
    if evenement.nature == "cpu_eleve":
        return f"CPU {evenement.valeur} %"
    return f"latence {evenement.valeur} ms"

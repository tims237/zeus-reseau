"""B11 API : donner la photo du réseau à qui la demande.

L'API ne parle jamais au réseau. Elle garde en mémoire la dernière photo prise par le
collecteur, et la renvoie instantanément. Une tâche de fond reprend une photo à
intervalle régulier.

À chaque nouvelle photo, la mémoire :
1. la compare à la précédente (B3), et corrèle les événements en incidents ;
2. range les nouveaux incidents dans un registre : une panne y reste tant qu'elle n'est
   pas résolue, même si plus rien ne change entre deux photos ;
3. vérifie, pour chaque incident ouvert, si la nouvelle photo montre la panne réparée ;
   si oui, elle le ferme (clos_le) et le range dans l'historique.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from briques.b03_supervision import comparer, verifier_seuils
from zeus_app.correlation import correler
from zeus_core.modeles import Equipement, EtatReseau, Incident, Lien

journal = logging.getLogger("zeus_app.api")

SEUIL_CPU = 85  # en %, les mêmes seuils pour ouvrir et pour fermer un incident « lent »
SEUIL_LATENCE_MS = 120


class Memoire:
    """Garde la dernière photo du réseau, les incidents ouverts, et l'historique."""

    def __init__(self, racine: str) -> None:
        self.racine = racine  # l'équipement d'où part la supervision, pour la corrélation
        self.derniere: EtatReseau | None = None  # None tant qu'aucune photo n'a réussi
        # Le registre : identifiant de l'incident -> incident. Un dictionnaire, pour
        # retrouver tout de suite si une panne est déjà notée.
        self.incidents: dict[str, Incident] = {}
        self.historique: list[Incident] = []  # les incidents fermés, du plus ancien au plus récent

    def recevoir(self, nouvelle: EtatReseau) -> None:
        """Range une nouvelle photo, et met à jour le registre des incidents."""
        if self.derniere is not None:  # la toute première photo n'a rien à comparer
            # Les événements : ce qui a changé depuis la photo précédente, et ce qui
            # dépasse un seuil sur la nouvelle.
            evenements = comparer(self.derniere.releves, nouvelle.releves) + verifier_seuils(
                nouvelle.releves, SEUIL_CPU, SEUIL_LATENCE_MS
            )
            for incident in correler(evenements, nouvelle.liens, self.racine):
                # Déjà dans le registre (même id) : on garde l'ancien, et son heure
                # d'ouverture. Sinon, on l'ajoute.
                self.incidents.setdefault(incident.id, incident)

        # Les pannes réparées : on regarde l'ÉTAT de la nouvelle photo, et pas seulement les
        # événements « port_up » ou « joignable », qu'on aurait pu rater (redémarrage…).
        # list(...) : on fait une copie, car on retire des incidents pendant la boucle.
        for identifiant, incident in list(self.incidents.items()):
            if est_resolu(incident, nouvelle):
                ferme = incident.model_copy(update={"clos_le": nouvelle.horodatage})
                self.historique.append(ferme)
                del self.incidents[identifiant]
        # Limite connue : on ferme dès la première photo en bon état. Plus tard (phase 3),
        # on attendra plusieurs photos de suite, et la vérification avant clôture.

        self.derniere = nouvelle


def est_resolu(incident: Incident, photo: EtatReseau) -> bool:
    """Vrai si la photo montre que la cause de l'incident a disparu."""
    releves = {r.equipement_id: r for r in photo.releves}  # pour retrouver vite un relevé
    releve = releves.get(incident.equipement_id)
    if releve is None:
        return False  # l'équipement n'est même pas sur la photo : on ne peut rien affirmer

    if incident.categorie == "equipement":
        return releve.repond  # la cause répond de nouveau

    if incident.categorie == "port":
        return releve.interfaces.get(incident.interface or "") is True

    if incident.categorie == "cable":
        # Les deux bouts doivent être revenus. L'autre bout, on le retrouve dans les câbles.
        if releve.interfaces.get(incident.interface or "") is not True:
            return False
        for lien in photo.liens:
            if (lien.equipement_a, lien.interface_a) == (
                incident.equipement_id,
                incident.interface,
            ):
                autre = releves.get(lien.equipement_b)
                return autre is not None and autre.interfaces.get(lien.interface_b) is True
            if (lien.equipement_b, lien.interface_b) == (
                incident.equipement_id,
                incident.interface,
            ):
                autre = releves.get(lien.equipement_a)
                return autre is not None and autre.interfaces.get(lien.interface_a) is True
        return False  # le câble n'est plus sur la photo : on ne sait pas, on garde ouvert

    if incident.categorie == "lenteur":
        cpu_ok = releve.cpu is None or releve.cpu <= SEUIL_CPU
        latence_ok = releve.latence_ms is None or releve.latence_ms <= SEUIL_LATENCE_MS
        return releve.repond and cpu_ok and latence_ok

    return False  # incident créé à la main (sans catégorie) : on ne le ferme jamais tout seul


def creer_api(
    prendre_photo: Callable[[], EtatReseau],
    racine: str = "rt-dc",
    intervalle_s: float = 60,
    memoire: Memoire | None = None,
) -> FastAPI:
    """Fabrique l'API, avec la fonction qui prend une photo et l'intervalle entre deux photos.

    On reçoit la fonction plutôt que de l'écrire ici : les tests donnent une fausse photo,
    la vraie application donne collecter() avec la vraie sonde SNMP.
    « memoire » sert aux tests : ils peuvent donner une mémoire déjà remplie.
    """
    if memoire is None:
        memoire = Memoire(racine)

    async def photographier() -> None:
        # collecter() est lent et utilise asyncio.run (la sonde SNMP) : on le lance dans
        # un fil à part, pour ne pas bloquer l'API pendant qu'elle répond aux visiteurs.
        try:
            nouvelle = await asyncio.to_thread(prendre_photo)
            memoire.recevoir(nouvelle)
        except Exception:
            # La collecte a échoué : on le note dans le journal du serveur, et on garde
            # l'ancienne photo. Son heure dira à la carte qu'elle vieillit.
            journal.exception("La photo du réseau a échoué")

    async def photographier_en_boucle() -> None:
        while True:
            await asyncio.sleep(intervalle_s)
            await photographier()

    @asynccontextmanager
    async def cycle_de_vie(_: FastAPI) -> AsyncIterator[None]:
        await photographier()  # une première photo au démarrage
        tache = asyncio.create_task(photographier_en_boucle())
        yield  # l'API tourne et répond aux visiteurs
        tache.cancel()  # à l'arrêt, on arrête aussi la boucle

    app = FastAPI(title="ZeusRéseau", lifespan=cycle_de_vie)

    def photo() -> EtatReseau:
        if memoire.derniere is None:
            # 503 : « service indisponible », il faut réessayer plus tard
            raise HTTPException(status_code=503, detail="Pas encore de photo du réseau")
        return memoire.derniere

    @app.get("/etat")
    def lire_etat() -> EtatReseau:
        """La photo complète du réseau."""
        return photo()

    @app.get("/equipements")
    def lire_equipements() -> list[Equipement]:
        """Les équipements de la dernière photo."""
        return photo().equipements

    @app.get("/liens")
    def lire_liens() -> list[Lien]:
        """Les câbles de la dernière photo."""
        return photo().liens

    @app.get("/incidents")
    def lire_incidents() -> list[Incident]:
        """Les incidents ouverts, du plus ancien au plus récent."""
        # Une liste vide est une bonne nouvelle : aucune panne en cours.
        return sorted(memoire.incidents.values(), key=lambda incident: incident.ouvert_le)

    @app.get("/incidents/historique")
    def lire_historique() -> list[Incident]:
        """Les incidents fermés, du plus récent au plus ancien."""
        return list(reversed(memoire.historique))

    return app

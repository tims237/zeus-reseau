"""B11 API : donner la photo du réseau à qui la demande.

L'API ne parle jamais au réseau. Elle garde en mémoire la dernière photo prise par le
collecteur, et la renvoie instantanément. Une tâche de fond reprend une photo à
intervalle régulier.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from zeus_core.modeles import Equipement, EtatReseau, Lien

journal = logging.getLogger("zeus_app.api")


class Memoire:
    """Garde la dernière photo du réseau (None tant qu'aucune n'a réussi)."""

    def __init__(self) -> None:
        self.derniere: EtatReseau | None = None


def creer_api(prendre_photo: Callable[[], EtatReseau], intervalle_s: float = 60) -> FastAPI:
    """Fabrique l'API, avec la fonction qui prend une photo et l'intervalle entre deux photos.

    On reçoit la fonction plutôt que de l'écrire ici : les tests donnent une fausse photo,
    la vraie application donne collecter() avec la vraie sonde SNMP.
    """
    memoire = Memoire()

    async def photographier() -> None:
        # collecter() est lent et utilise asyncio.run (la sonde SNMP) : on le lance dans
        # un fil à part, pour ne pas bloquer l'API pendant qu'elle répond aux visiteurs.
        try:
            memoire.derniere = await asyncio.to_thread(prendre_photo)
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

    return app

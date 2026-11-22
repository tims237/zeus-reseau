"""Le point de départ de ZeusRéseau : l'API branchée sur le vrai réseau.

Lancer :  ZEUS_COMMUNAUTE=public uvicorn zeus_app.principal:app
La communauté SNMP est un mot de passe : elle vient d'une variable d'environnement,
jamais du code.
"""

import os
from datetime import datetime

from sondes.sonde_snmp import SondeSNMP
from zeus_app.api import creer_api
from zeus_app.collecte import collecter
from zeus_core.modeles import EtatReseau

PLAGE = os.environ.get("ZEUS_PLAGE", "172.20.20.0/28")  # la plage du labo, par défaut
COMMUNAUTE = os.environ.get("ZEUS_COMMUNAUTE")
if not COMMUNAUTE:
    raise SystemExit("Indique la communauté SNMP : ZEUS_COMMUNAUTE=public uvicorn ...")

sonde = SondeSNMP(communaute=COMMUNAUTE, delai_s=0.5)


def prendre_photo() -> EtatReseau:
    """Une photo du réseau, à l'heure actuelle."""
    return collecter(PLAGE, sonde, datetime.now())


app = creer_api(prendre_photo, intervalle_s=60)

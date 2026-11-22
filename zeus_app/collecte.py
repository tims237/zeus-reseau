"""Le collecteur : prendre une « photo » complète du réseau.

collecter() enchaîne les briques dans l'ordre où elles ont besoin les unes des autres :
1. B1 découvre les équipements et fabrique le carnet d'adresses (nom -> IP) ;
2. B2 lit les voisins LLDP, et en tire les câbles ;
3. B3 relève les constantes de chaque équipement.
Le résultat est rangé dans un EtatReseau, que l'API enverra à la carte.
"""

from datetime import datetime
from typing import Protocol

from briques.b01_decouverte import Sonde, decouvrir
from briques.b02_topologie import SondeLLDP, construire_liens
from briques.b03_supervision import SondeSupervision, relever
from zeus_core.modeles import EtatReseau


class SondeComplete(Sonde, SondeLLDP, SondeSupervision, Protocol):
    """Une sonde qui sait répondre à B1, B2 et B3, et qui garde un carnet d'adresses.

    B1 travaille avec des IP ; B2 et B3 avec des noms. Le carnet fait le lien.
    SondeSNMP est une SondeComplete ; dans les tests, une fausse sonde l'imite.
    """

    adresses: dict[str, str]


def collecter(plage: str, sonde: SondeComplete, maintenant: datetime) -> EtatReseau:
    """Prend la photo du réseau d'une plage d'adresses, à l'heure donnée.

    « maintenant » est donné plutôt que lu dans l'horloge, comme pour relever() :
    les tests choisissent l'heure, et le résultat est toujours le même.
    Une panne n'empêche jamais la photo : un équipement muet y figure, marqué comme
    ne répondant pas, puisque c'est justement ce qu'on veut voir.
    """
    # 1. B1 : qui est là ? Il passe en premier, car B2 et B3 ont besoin de ce qu'il trouve.
    equipements = decouvrir(plage, sonde)

    # 2. Le carnet d'adresses, construit à partir de ce que B1 a VRAIMENT lu à chaque IP :
    #    jamais écrit à la main, car les adresses changent.
    sonde.adresses = {e.id: str(e.ip) for e in equipements}
    noms = [e.id for e in equipements]

    # 3. B2 et B3 : qui est branché à qui, et dans quel état. Ils ne dépendent pas
    #    l'un de l'autre : on pourrait les inverser.
    liens = construire_liens(noms, sonde)
    releves = relever(noms, sonde, maintenant)

    # 4. Tout ranger dans la photo.
    return EtatReseau(horodatage=maintenant, equipements=equipements, liens=liens, releves=releves)

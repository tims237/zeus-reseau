"""Modèles partagés par toutes les briques de ZeusRéseau.

Chaque classe décrit une donnée qui circule entre les briques. Pydantic vérifie
ces données au moment où on les crée : une valeur interdite lève une ValidationError.
"""

from datetime import datetime  # pour les dates et heures (ouverture d'un incident)
from enum import StrEnum  # pour les listes fermées de choix
from ipaddress import IPv4Address  # type qui vérifie qu'une adresse IP est valide
from typing import Literal  # pour une petite liste de valeurs autorisées

from pydantic import BaseModel, Field


class Emplacement(BaseModel):
    """Où se trouve physiquement un équipement."""

    site: str  # obligatoire : pas de valeur par défaut
    batiment: str | None = None  # facultatif : vaut None (rien) si on ne le donne pas
    etage: int | None = Field(default=None, ge=0)  # ge=0 : 0 (le RDC) ou plus
    salle: str | None = None  # facultatif : la salle, par exemple "SalleServeur"
    baie: str | None = None
    position_u: int | None = Field(default=None, ge=1, le=60)  # entre 1 et 60


class TypeEquipement(StrEnum):
    """Les familles d'équipements que ZeusRéseau sait afficher.

    Une liste fermée : écrire TypeEquipement.SWITCH évite les fautes comme "swich".
    """

    ROUTEUR = "routeur"
    SWITCH = "switch"
    PARE_FEU = "pare-feu"
    SERVEUR = "serveur"
    BORNE_WIFI = "borne-wifi"
    CAMERA = "camera"
    INCONNU = "inconnu"


class Interface(BaseModel):
    """Un port d'un équipement, par exemple Gi1/0/12."""

    nom: str
    est_up: bool = False  # True si le port est actif, False sinon


class Equipement(BaseModel):
    """Un équipement découvert sur le réseau."""

    id: str  # obligatoire : son nom, par exemple "SW-LIL-02"
    ip: IPv4Address  # obligatoire, et forcément une IP valide
    type: TypeEquipement = TypeEquipement.INCONNU  # la famille, inconnue au départ
    modele: str | None = None  # le produit précis, par exemple "Cisco Catalyst 9200"
    emplacement: Emplacement | None = None  # un modèle dans un modèle
    # Le sysLocation tel que l'équipement l'a dit, sans le décoder ("LIL/BatA/E2").
    # B1 le garde ; c'est zeus_app qui le confie à B13 pour remplir emplacement.
    sys_location: str | None = None
    interfaces: list[Interface] = Field(default_factory=list)  # ses ports, vide au départ


class Lien(BaseModel):
    """Un câble entre deux ports, vu par LLDP ou CDP.

    On note seulement les noms des équipements, pas leurs fiches complètes :
    chaque fiche existe une seule fois ailleurs, comme dans un carnet d'adresses.
    """

    equipement_a: str  # un bout du câble : l'équipement…
    interface_a: str  # … et son port
    equipement_b: str  # l'autre bout du câble
    interface_b: str


class Incident(BaseModel):
    """Une panne détectée, close seulement après vérification."""

    id: str
    equipement_id: str  # le nom de l'équipement en panne
    interface: str | None = None  # le port concerné, s'il y en a un
    gravite: Literal["down", "lent"]  # seulement ces deux valeurs sont acceptées
    ouvert_le: datetime  # obligatoire : sans date, impossible de mesurer la durée
    clos_le: datetime | None = None  # vide tant que la panne n'est pas résolue

    # Ajoutés pour la corrélation (plusieurs événements -> un seul incident) :
    categorie: (
        Literal[
            "equipement",  # un équipement ne répond plus (et tout ce qui est derrière lui)
            "cable",  # les deux bouts d'un même câble sont tombés
            "port",  # un port seul est tombé
            "lenteur",  # CPU ou latence au-dessus du seuil
        ]
        | None
    ) = None  # None : incident créé à la main, sans passer par la corrélation
    titre: str = ""  # la phrase lue par l'admin, par exemple « Câble coupé entre … »
    equipements_touches: list[str] = Field(default_factory=list)  # la cause d'abord

    @property
    def est_ouvert(self) -> bool:
        """Vrai tant que l'incident n'a pas été clos.

        @property permet d'écrire inc.est_ouvert sans parenthèses, comme un champ,
        mais la valeur est recalculée à chaque lecture à partir de clos_le.
        """
        return self.clos_le is None


class Releve(BaseModel):
    """Les « constantes » d'un équipement à un instant donné, prises par B3 Supervision."""

    equipement_id: str
    horodatage: datetime  # le moment du relevé
    repond: bool  # False si l'équipement n'a pas répondu du tout
    interfaces: dict[str, bool] = Field(default_factory=dict)  # nom du port -> up (True) ou down
    cpu: float | None = Field(default=None, ge=0, le=100)  # en pourcentage, si connu
    latence_ms: float | None = Field(default=None, ge=0)  # temps de réponse, si connu


class Evenement(BaseModel):
    """Un changement ou un dépassement repéré par B3, qui pourra devenir un Incident."""

    equipement_id: str
    interface: str | None = None  # le port concerné, s'il y en a un
    nature: Literal[
        "port_down",  # un port est tombé
        "port_up",  # un port est revenu
        "injoignable",  # l'équipement ne répond plus
        "joignable",  # l'équipement répond de nouveau
        "cpu_eleve",  # le CPU dépasse le seuil
        "latence_elevee",  # la latence dépasse le seuil
    ]
    horodatage: datetime
    valeur: float | None = None  # la mesure en cause, pour cpu_eleve et latence_elevee


class EtatReseau(BaseModel):
    """La « photo » du réseau à un instant donné, prise par le collecteur.

    Une simple boîte : elle ne calcule rien, elle range ensemble ce que B1, B2 et B3
    ont trouvé. L'API l'envoie telle quelle, en JSON, à la carte et aux autres écrans.
    """

    horodatage: datetime  # obligatoire : sans l'heure, impossible de savoir si c'est périmé
    equipements: list[Equipement] = Field(default_factory=list)  # trouvés par B1
    liens: list[Lien] = Field(default_factory=list)  # trouvés par B2
    releves: list[Releve] = Field(default_factory=list)  # pris par B3

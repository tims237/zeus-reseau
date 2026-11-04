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

    @property
    def est_ouvert(self) -> bool:
        """Vrai tant que l'incident n'a pas été clos.

        @property permet d'écrire inc.est_ouvert sans parenthèses, comme un champ,
        mais la valeur est recalculée à chaque lecture à partir de clos_le.
        """
        return self.clos_le is None

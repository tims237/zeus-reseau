"""Modèles partagés par toutes les briques de ZeusRéseau."""

from enum import StrEnum
from ipaddress import IPv4Address

from pydantic import BaseModel, Field


class Emplacement(BaseModel):
    """Où se trouve physiquement un équipement."""

    site: str
    batiment: str | None = None
    etage: int | None = Field(default=None, ge=0)
    baie: str | None = None
    position_u: int | None = Field(default=None, ge=1, le=60)


class TypeEquipement(StrEnum):
    """Les familles d'équipements que ZeusRéseau sait afficher."""

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
    est_up: bool = False


class Equipement(BaseModel):
    """Un équipement découvert sur le réseau."""

    id: str
    ip: IPv4Address
    type: TypeEquipement = TypeEquipement.INCONNU
    modele: str | None = None
    emplacement: Emplacement | None = None
    interfaces: list[Interface] = Field(default_factory=list)

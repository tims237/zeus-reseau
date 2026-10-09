"""Modèles partagés par toutes les briques de ZeusRéseau."""

from pydantic import BaseModel, Field


class Emplacement(BaseModel):
    """Où se trouve physiquement un équipement."""

    site: str
    batiment: str | None = None
    etage: int | None = Field(default=None, ge=0)
    baie: str | None = None
    position_u: int | None = Field(default=None, ge=1, le=60)

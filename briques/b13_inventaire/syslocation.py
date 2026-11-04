"""Lecture du champ SNMP sysLocation.

Les admins réseau écrivent dans chaque équipement un texte qui dit où il est rangé.
Convention ZeusRéseau : SITE/Batiment/Etage/Salle/Baie/U
Exemple : « LIL/BatA/E2/SalleServeur/B2/U14 »
  - LIL          le site (obligatoire)
  - BatA         le bâtiment
  - E2           l'étage : E suivi du numéro, ou RDC pour le rez-de-chaussée
  - SalleServeur la salle
  - B2           la baie
  - U14          la position dans la baie : U suivi du numéro
Les morceaux de la fin peuvent manquer : « LIL/BatA » est accepté.
"""

from zeus_core.modeles import Emplacement


def _lire_etage(texte: str) -> int:
    """Transforme « RDC » en 0 et « E2 » en 2."""
    if texte.upper() == "RDC":
        return 0
    # texte[:1] = la première lettre ; texte[1:] = tout le reste
    if texte[:1].upper() == "E" and texte[1:].isdigit():
        return int(texte[1:])
    raise ValueError(f"Étage illisible : {texte!r} (attendu RDC ou E suivi d'un numéro)")


def _lire_position_u(texte: str) -> int:
    """Transforme « U14 » en 14."""
    if texte[:1].upper() == "U" and texte[1:].isdigit():
        return int(texte[1:])
    raise ValueError(f"Position U illisible : {texte!r} (attendu U suivi d'un numéro)")


def lire_syslocation(valeur: str) -> Emplacement:
    """Transforme une valeur sysLocation en Emplacement.

    Lève ValueError si le texte est vide ou si un morceau est illisible.
    """
    # 1. Découper au niveau des « / », enlever les espaces et les morceaux vides
    morceaux = [m.strip() for m in valeur.split("/") if m.strip()]
    if not morceaux:
        raise ValueError("sysLocation vide")
    if len(morceaux) > 6:
        raise ValueError(f"sysLocation trop long : {len(morceaux)} morceaux, 6 au maximum")

    # 2. Compléter avec des textes vides pour avoir toujours 6 morceaux
    morceaux += [""] * (6 - len(morceaux))
    site, batiment, etage, salle, baie, position_u = morceaux

    # 3. Remplir la fiche Emplacement ; un morceau vide devient None
    return Emplacement(
        site=site,
        batiment=batiment or None,
        etage=_lire_etage(etage) if etage else None,
        salle=salle or None,
        baie=baie or None,
        position_u=_lire_position_u(position_u) if position_u else None,
    )

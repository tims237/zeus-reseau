# ZeusRéseau

Supervision réseau visuelle, pensée comme un jeu de gestion.

ZeusRéseau écoute le réseau d'une entreprise depuis un serveur Linux, dessine ses sites sur une carte, et localise une panne en 3D jusqu'au bâtiment, à l'étage, à la baie et au port en cause. Un Conseiller propose ensuite l'action adaptée : envoyer un technicien sur site si l'équipement est hors service, ou donner des directives IA s'il est seulement lent. L'incident n'est clos qu'après une vérification automatique.

## État du projet

**Phase 1 : socle et collecte**, en cours.

- [x] Modèle `Emplacement` et ses tests
- [x] Contrôles avant commit (pre-commit : ruff, mypy, pytest)
- [ ] Intégration continue (GitHub Actions)
- [ ] Autres modèles partagés (équipement, interface, lien, incident)
- [ ] B1 Découverte des équipements
- [ ] B13 Inventaire des emplacements (lecture de sysLocation)

Les phases suivantes ajouteront l'alerte et la vérification, la carte 2D et 3D, puis l'IA.

## Technologies

- **Python 3.12** pour tout le moteur
- **Pydantic** pour les modèles de données partagés
- **pytest, ruff, mypy** pour les tests et la qualité du code
- Plus tard : pysnmp, networkx, FastAPI, Redis, Three.js

## Démarrer

Sous Windows, dans PowerShell, à la racine du projet :

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pre-commit install
```

Si PowerShell refuse d'activer l'environnement, lance une fois :
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

Dans PyCharm : *Settings → Project → Python Interpreter → Add Interpreter → Existing*, puis choisis `.venv\Scripts\python.exe`.

## Vérifier le code

```powershell
pytest          # les tests
ruff check .    # le style et les erreurs courantes
mypy            # les types
```

Ces trois contrôles tournent aussi automatiquement avant chaque commit.

## Arborescence

```
zeus_core/      modèles partagés par toutes les briques (Pydantic)
briques/        les briques du logiciel, une par sous-dossier
tests/          les tests
CLAUDE.md       règles du projet pour Claude Code
```

## Auteur

Elvis Noubissie (Levis), étudiant en Bachelor Informatique Data et IA à l'ECE Paris.

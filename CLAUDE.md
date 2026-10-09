# ZeusRéseau

Logiciel de supervision réseau auto-hébergé (serveur Linux) avec une interface web façon jeu de gestion : carte isométrique des sites, localisation 3D d'une panne jusqu'au port, Conseiller IA, vérification avant clôture.
Le dossier de référence (vision, architecture, briques, feuille de route) est le doc « ZeusRéseau, dossier de projet ». En cas de doute sur le périmètre, il fait foi.

## Mode apprentissage (important)

Levis développe ce projet pour apprendre Python, les tests et la CI/CD. Par défaut :
- Explique avant de coder : propose l'approche, les fichiers touchés et pourquoi, puis attends son accord.
- Quand il a écrit une première version, relis-la et explique les problèmes au lieu de tout réécrire.
- N'écris une brique entière que s'il le demande explicitement ; préfère des indices et des exemples courts.
- Après chaque modification, résume en quelques lignes ce qui a changé et ce qu'il faut retenir.
- Réponds en français, avec des explications simples.

## État actuel

Phase 1 : socle et collecte.
- Fait : `zeus_core/modeles.py` avec le modèle `Emplacement` et ses tests ; pre-commit (ruff, mypy, pytest).
- À venir dans cette phase : les autres modèles de zeus_core, la CI GitHub Actions, B1 Découverte, B13 Inventaire des emplacements, B2 Topologie, B3 Supervision.
Ne pas commencer les briques des phases suivantes (API, carte 3D, IA) sans qu'il le demande.

## Architecture

- `zeus_core/` contient les modèles Pydantic partagés. Toute donnée échangée entre briques y a d'abord un modèle.
- Chaque brique est un sous-dossier de `briques/` (par exemple `briques/b01_decouverte/`) qui ne dépend que de `zeus_core`, jamais d'une autre brique.
- Le code qui touche le réseau passe par une interface (`Protocol`), pour être remplacé par une fausse version dans les tests.

```
zeus_core/        modèles partagés (Pydantic)
briques/          une brique par sous-dossier
tests/            un fichier de tests par module : test_zeus_core.py, test_b01_decouverte.py…
```

## Stack

- Python 3.12, environnement virtuel `.venv`, sous Windows (PowerShell) avec PyCharm
- Installation : `pip install -e ".[dev]"`
- Pydantic v2 ; plus tard pysnmp, networkx, FastAPI, redis-py
- Tests : pytest ; qualité : ruff (lint + format), mypy en mode strict

## Commandes

```
pytest                          # tous les tests
ruff check . ; ruff format .    # lint et formatage
mypy                            # typage
pre-commit run --all-files      # tout ce que lance le hook avant commit
```

Une tâche n'est terminée que si `pytest`, `ruff check` et `mypy` passent. Lance-les et montre le résultat ; ne dis jamais « ça marche » sans l'avoir vérifié.

## Règles de code

- Chaque fonction publique a des annotations de type et une docstring courte en français.
- Chaque règle de validation a ses tests : le cas valide et chaque limite refusée.
- Pas de réseau réel dans les tests : fausses sondes ou réponses enregistrées dans `tests/donnees/`.
- Les noms du domaine restent en français (equipement, emplacement, baie).

## Sécurité

- SNMP en lecture seule ; aucune commande qui modifie un équipement sans demande explicite de Levis.
- Jamais d'identifiant, mot de passe, communauté SNMP ou clé d'API dans le code ou les tests : variables d'environnement via `.env` (ignoré par Git), avec `.env.example` sans valeurs réelles.
- Ne jamais afficher le contenu de `.env`.

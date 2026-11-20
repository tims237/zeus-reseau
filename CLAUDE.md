# ZeusRéseau

Logiciel de supervision réseau auto-hébergé (serveur Linux) avec une interface web façon jeu de gestion : carte isométrique des sites, localisation 3D d'une panne jusqu'au port, Conseiller IA, vérification avant clôture.
Le dossier de référence (vision, architecture, briques B1 à B17, feuille de route) est le doc « ZeusRéseau, dossier de projet ». En cas de doute sur le périmètre, il fait foi.

## Mode apprentissage (important)

Levis développe ce projet pour apprendre Python, les tests, la CI/CD et surtout la **logique** du code et la logique métier. Par défaut :
- Explique avant de coder : propose l'approche, les fichiers touchés et pourquoi, puis attends son accord.
- Écris le code par petites étapes (un modèle, une fonction), jamais une brique entière d'un coup sauf s'il le demande.
- Pour chaque fonction, explique trois niveaux : **ce qu'elle fait** (le quoi), **sa logique** étape par étape (le comment), et **la logique métier** (le pourquoi, côté réseau).
- Demande-lui ensuite de **reformuler avec ses mots** ; corrige ce qu'il a mal compris, y compris le vocabulaire (liste, dictionnaire, classe…).
- Il n'aime pas prédire : ne lui demande pas ce qu'il pense qu'il va se passer. Dis-lui plutôt ce qu'on doit voir, puis, après le résultat, demande-lui d'expliquer pourquoi.
- Il préfère comprendre que réécrire : ne lui impose pas d'exercices d'écriture, propose-les seulement.
- Après chaque modification, résume en quelques lignes ce qui a changé et ce qu'il faut retenir.
- Réponds en français, avec des explications simples ; signale brièvement ses fautes de français entre parenthèses.

## Façon de travailler avec Git

- Il fait lui-même ses commits, push et pull requests **depuis le terminal**, pas avec les boutons de PyCharm. Donne-lui les commandes, ne les lance pas à sa place.
- Petite correction : directement sur `main`. Brique entière ou changement de plusieurs fichiers : une branche (`feat/…`, `fix/…`, `docs/…`) puis une pull request.
- Messages de commit clairs, qui disent ce que fait le commit (`B1 : reconnaître SR Linux comme routeur`).
- Un test rouge se corrige dans le code, pas en supprimant le test.

## État actuel

Phase 1 : socle et collecte des données, presque terminée.
- Fait : les modèles de `zeus_core/modeles.py` (Emplacement, TypeEquipement, Interface, Equipement, Lien, Incident, Releve, Evenement) ; pre-commit ; CI GitHub Actions ; B1 Découverte (`briques/b01_decouverte/`) ; B13 Inventaire (`briques/b13_inventaire/`) ; B2 Topologie (`briques/b02_topologie/`) ; B3 Supervision (`briques/b03_supervision/`) ; vraie sonde SNMP (`sondes/sonde_snmp.py`, y compris la lecture des voisins LLDP) testée contre snmpsim ; labo Containerlab (`labo/containerlab/`) : `rt-dc` → `rt-lil` → `sw-lil` (trois Nokia SR Linux) → `ap-lil-01` (borne simulée, Alpine Linux avec lldpd et snmpd).
- Validé sur Containerlab : B1 (les deux routeurs trouvés, de type `routeur`), B13 (sysLocation lu et décodé), B2 (un seul câble `rt-dc` ↔ `rt-lil`, le voisin vu par `mgmt0` ignoré), B3 (une coupure côté Lille donne exactement deux `port_down`, sur `rt-lil` et sur `rt-dc`, et aucune fausse alerte de latence depuis la correction de `latence_ms`).
- Reste à faire dans cette phase :
  1. valider le labo à quatre équipements (B1 trouve les quatre, B2 trois câbles), puis la panne en cascade avec `equipements_injoignables` (procédure dans `labo/README.md`). Limite : dans Containerlab, `mgmt0` garde chaque équipement joignable ; la panne est donc donnée à la fonction, sur la vraie topologie ;
  2. plus tard dans la sonde : CPU en SNMP, vrai ping ICMP, SNMP v3, et distinguer un port coupé par l'admin (`port-admin-disabled`) d'une vraie panne.
- Idée retenue pour la suite : regrouper les deux `port_down` d'un même câble (ses deux bouts, connus grâce à B2) en un seul incident, c'est la corrélation.
- Idée retenue pour plus tard : **B17 Classification** des équipements inconnus (numéro de fabricant du sysObjectID, capacités LLDP, nombre de ports → type + confiance + validation par l'ingénieur ; machine learning en phase 4). Ne pas la commencer avant la fin de la phase 1.
Ne pas commencer les briques des phases suivantes (API, carte 3D, IA) sans qu'il le demande.

## Architecture

- `zeus_core/` contient les modèles Pydantic partagés. Toute donnée échangée entre briques y a d'abord un modèle.
- Chaque brique est un sous-dossier de `briques/` qui ne dépend que de `zeus_core`, jamais d'une autre brique.
- Le code qui touche le réseau passe par une interface (`Protocol`) et vit dans `sondes/`, pour être remplacé par une fausse version dans les tests.
- La sonde SNMP reçoit une IP pour B1 ; pour B2 et B3, qui travaillent par nom, on lui donne le carnet d'adresses construit par B1 : `sonde.adresses = {e.id: str(e.ip) for e in decouvrir(plage, sonde)}`. Ne jamais écrire les IP du labo à la main : elles changent d'un lancement à l'autre.

```
zeus_core/        modèles partagés (Pydantic)
briques/          une brique par sous-dossier
sondes/           code qui parle au réseau (SondeSNMP)
labo/snmpsim/     faux switch SNMP, utilisé par `pytest -m labo` et la CI
labo/containerlab/ réseau virtuel (routeurs SR Linux), lancé à la main sous Ubuntu
tests/            un fichier de tests par module : test_zeus_core.py, test_b01_decouverte.py…
```

## Environnement

- Windows : projet dans `C:\Users\User\projets\zeus-reseau`, PowerShell, PyCharm, `.venv` (Python 3.14 en local, 3.12 dans la CI).
- Labo : Ubuntu WSL2 installé sur `B:\WSL\Ubuntu` (utilisateur `userlevis`), car `C:` et `G:` sont pleins ; Docker installé **dans Ubuntu** (l'intégration WSL de Docker Desktop doit rester désactivée) ; Containerlab ; copie du projet dans `~/zeus-reseau` avec son propre `.venv`.
- Le labo Containerlab ne tourne pas dans la CI : ses essais sont manuels. Les scripts d'essai (`essai_*.py`) ne sont pas versionnés.

## Stack

- Python 3.12, Pydantic v2, pysnmp
- Tests : pytest ; qualité : ruff (lint + format), mypy en mode strict ; labo : snmpsim, Containerlab
- Plus tard : networkx, FastAPI, redis-py, Three.js

## Commandes

```
pytest                          # tous les tests (sans le labo)
pytest -m labo                  # tests contre le faux switch snmpsim
ruff check . ; ruff format .    # lint et formatage
mypy                            # typage
pre-commit run --all-files      # tout ce que lance le hook avant commit
```

Une tâche n'est terminée que si `pytest`, `ruff check` et `mypy` passent. Lance-les et montre le résultat ; ne dis jamais « ça marche » sans l'avoir vérifié.

## Règles de code

- Chaque fonction publique a des annotations de type et une docstring courte en français.
- Chaque règle de validation a ses tests : le cas valide et chaque limite refusée.
- Pas de réseau réel dans les tests : fausses sondes, snmpsim, ou réponses enregistrées dans `tests/donnees/`.
- Les noms du domaine restent en français (equipement, emplacement, baie).
- Quand le labo révèle un problème, on écrit d'abord le test qui le reproduit, puis on corrige.

## Sécurité

- SNMP en lecture seule ; aucune commande qui modifie un équipement sans demande explicite de Levis.
- Jamais d'identifiant, mot de passe, communauté SNMP ou clé d'API dans le code ou les tests : variables d'environnement via `.env` (ignoré par Git), avec `.env.example` sans valeurs réelles. La communauté `public` du labo est une exception tolérée, propre au labo.
- Ne jamais afficher le contenu de `.env`.

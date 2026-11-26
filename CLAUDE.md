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
- Il recopie lui-même le code dans PyCharm : donne-le dans la conversation, fichier par fichier, commenté ; ne le pousse pas toi-même sauf s'il le demande.
- Il ne veut pas que Claude apparaisse dans le projet : pas de lignes `Co-Authored-By` ni de mention « Generated with Claude Code » dans les commits et pull requests.
- Petite correction : directement sur `main`. Brique entière ou changement de plusieurs fichiers : une branche (`feat/…`, `fix/…`, `docs/…`) puis une pull request.
- Messages de commit clairs, qui disent ce que fait le commit (`B1 : reconnaître SR Linux comme routeur`).
- Un test rouge se corrige dans le code, pas en supprimant le test.

## État actuel

Phase 2 : l'application visible, en cours.
- Fait : `EtatReseau` (la photo du réseau) ; `zeus_app/collecte.py` (`collecter()`) ; **B11 API terminée** dans `zeus_app/api.py` (`creer_api(prendre_photo, racine, intervalle_s, memoire)`) : `/etat`, `/equipements`, `/equipements/{nom}` (404 si inconnu), `/liens`, `/incidents`, `/incidents/historique` ; 503 tant qu'aucune photo n'a réussi ; une collecte ratée est notée dans le journal et garde l'ancienne photo. `zeus_app/principal.py` branche l'API sur la vraie sonde (`ZEUS_COMMUNAUTE`, `ZEUS_PLAGE`, `ZEUS_RACINE`). Lancer : `ZEUS_COMMUNAUTE=public uvicorn zeus_app.principal:app`.
- Le registre des incidents, dans `Memoire.recevoir()` : à chaque photo, `comparer()` + `verifier_seuils()` (B3) → `correler()` → `setdefault` sur l'id stable (une panne reste tant qu'elle dure, notée une seule fois) ; puis `est_resolu()` regarde l'ÉTAT de la nouvelle photo (pas les événements, qu'on peut rater) et ferme l'incident (`clos_le`) dans `historique`. Seuils partagés : `SEUIL_CPU` = 85, `SEUIL_LATENCE_MS` = 120.
- Limites connues de B11 : un incident est fermé dès la première photo en bon état (plus tard : plusieurs photos de suite, et la vérification avant clôture) ; registre et historique sont en mémoire, perdus au redémarrage (plus tard : une base de données) ; l'API n'a pas de clé ni de mot de passe (à ajouter avant un vrai client).
- Fait aussi : le modèle `Incident` complété (`categorie` : equipement, cable, port ou lenteur ; `titre` ; `equipements_touches`, la cause d'abord) ; la corrélation dans `zeus_app/correlation.py` : `correler(evenements, liens, racine)` applique quatre règles, du plus gros au plus petit, et chaque règle saute ce que les précédentes expliquent déjà :
  1. équipement hors ligne : la cause est celui qui n'est derrière aucun autre équipement hors ligne ; ses conséquences viennent de `equipements_injoignables` (B2) ;
  2. câble coupé : les deux bouts d'un même câble ont un `port_down` → un seul incident ;
  3. port seul : un `port_down` qui reste ; le port d'un équipement vivant tourné vers un équipement mort est un symptôme, pas un incident ;
  4. lenteur : CPU et latence d'un même équipement → un seul incident de gravité « lent ».
  Les identifiants sont stables (`cable:a/p~b/q`, `equipement:x`, `port:x/p`, `lenteur:x`) : la même panne garde le même id d'un cycle à l'autre. `port_up` et `joignable` ne créent rien : ils serviront à fermer les incidents (phase 3).
- Reste dans la phase 2 : **B12 Carte 2D/3D**, les prototypes branchés sur l'API (équipements, câbles, incidents réels). Commencer par la logique (quoi, comment, pourquoi), puis donner le code fichier par fichier, qu'il recopie.
- À essayer sur le labo : couper le câble de Lille, voir l'incident sur `/incidents`, le rebrancher, le voir fermé sur `/incidents/historique`.
- Avertissement connu : Starlette signale que `httpx` est remplacé par `httpx2` pour son client de test ; à vérifier avant de changer.

Phase 1 : socle et collecte des données, terminée et validée sur le labo à quatre équipements.
- Fait : les modèles de `zeus_core/modeles.py` (Emplacement, TypeEquipement, Interface, Equipement, Lien, Incident, Releve, Evenement) ; pre-commit ; CI GitHub Actions ; B1 Découverte (`briques/b01_decouverte/`) ; B13 Inventaire (`briques/b13_inventaire/`) ; B2 Topologie (`briques/b02_topologie/`) ; B3 Supervision (`briques/b03_supervision/`) ; vraie sonde SNMP (`sondes/sonde_snmp.py`, y compris la lecture des voisins LLDP) testée contre snmpsim ; labo Containerlab (`labo/containerlab/`) : `rt-dc` → `rt-lil` → `sw-lil` (trois Nokia SR Linux) → `ap-lil-01` (borne simulée, Alpine Linux avec lldpd et snmpd).
- Validé sur Containerlab : B1 (les deux routeurs trouvés, de type `routeur`), B13 (sysLocation lu et décodé), B2 (un seul câble `rt-dc` ↔ `rt-lil`, le voisin vu par `mgmt0` ignoré), B3 (une coupure côté Lille donne exactement deux `port_down`, sur `rt-lil` et sur `rt-dc`, et aucune fausse alerte de latence depuis la correction de `latence_ms`) ; labo à quatre : B1 trouve les quatre équipements (`ap-lil-01` en `borne-wifi`), B2 les trois câbles (port de la borne lu `eth1`), et `equipements_injoignables` donne `{sw-lil, ap-lil-01}` si `rt-lil` tombe, `{ap-lil-01}` si `sw-lil` tombe.
- Limite connue du labo : dans Containerlab, `mgmt0` garde chaque équipement joignable ; la panne en cascade est donc donnée à `equipements_injoignables`, sur la vraie topologie lue par B2.
- Améliorations de la sonde restant à faire : CPU en SNMP, vrai ping ICMP, SNMP v3, et distinguer un port coupé par l'admin (`port-admin-disabled`) d'une vraie panne.
- Idée retenue pour plus tard : **B17 Classification** des équipements inconnus (numéro de fabricant du sysObjectID, capacités LLDP, nombre de ports → type + confiance + validation par l'ingénieur ; machine learning en phase 4). Idées détaillées dans `docs/b17-classification.md` (catalogue en données plutôt que dans le code, hauteur en U, identification une seule fois). À faire après l'API, la corrélation et la carte.
Ne pas commencer les briques des phases 3 et 4 (alertes, IA) sans qu'il le demande.

## Architecture

- `zeus_core/` contient les modèles Pydantic partagés. Toute donnée échangée entre briques y a d'abord un modèle.
- Chaque brique est un sous-dossier de `briques/` qui ne dépend que de `zeus_core`, jamais d'une autre brique.
- `zeus_app/` est le chef d'orchestre : lui seul assemble les briques. `zeus_app/collecte.py` : `collecter(plage, sonde, maintenant)` enchaîne B1 → carnet d'adresses → B2 et B3, et renvoie un `EtatReseau` (la photo du réseau). `zeus_app/correlation.py` : `correler()` utilise B2, c'est pourquoi elle est dans `zeus_app` et pas dans `briques/`.
- Le code qui touche le réseau passe par une interface (`Protocol`) et vit dans `sondes/`, pour être remplacé par une fausse version dans les tests.
- La sonde SNMP reçoit une IP pour B1 ; pour B2 et B3, qui travaillent par nom, on lui donne le carnet d'adresses construit par B1 : `sonde.adresses = {e.id: str(e.ip) for e in decouvrir(plage, sonde)}`. Ne jamais écrire les IP du labo à la main : elles changent d'un lancement à l'autre.

```
zeus_core/        modèles partagés (Pydantic)
briques/          une brique par sous-dossier
zeus_app/         l'application : collecteur, corrélation, API B11, point de départ
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

- Python 3.12, Pydantic v2, pysnmp, FastAPI et uvicorn (API)
- Tests : pytest ; qualité : ruff (lint + format), mypy en mode strict ; labo : snmpsim, Containerlab
- Plus tard : networkx, redis-py, Three.js

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

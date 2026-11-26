# ZeusRéseau

Supervision réseau visuelle, pensée comme un jeu de gestion.

ZeusRéseau écoute le réseau d'une entreprise depuis un serveur Linux, dessine ses sites sur une carte, et localise une panne en 3D jusqu'au bâtiment, à l'étage, à la baie et au port en cause. Un Conseiller propose ensuite l'action adaptée : envoyer un technicien sur site si l'équipement est hors service, ou donner des directives IA s'il est seulement lent. L'incident n'est clos qu'après une vérification automatique.

## État du projet

**Phase 1 : socle et collecte des données**, terminée : toutes les briques sont validées sur un vrai réseau virtuel.

Le socle
- [x] Modèles partagés (`zeus_core`) : Emplacement, Equipement, Interface, Lien, Incident, Releve, Evenement, EtatReseau
- [x] Contrôles avant commit (pre-commit : ruff, mypy, pytest)
- [x] Intégration continue (GitHub Actions), avec les tests du labo snmpsim

Les briques
- [x] **B1 Découverte** des équipements, validée sur de vrais routeurs (SR Linux reconnu comme routeur)
- [x] **B13 Inventaire** des emplacements (lecture de sysLocation), validé sur de vrais routeurs
- [x] **B2 Topologie** (qui est branché à qui) : logique testée avec une fausse sonde
- [x] B2 : la sonde SNMP lit les voisins LLDP (LLDP-MIB), testée contre snmpsim et validée sur de vrais routeurs (un seul câble trouvé, `rt-dc` ↔ `rt-lil`)
- [x] **B3 Supervision** (état des ports, changements, seuils) : validée sur de vrais routeurs, une coupure donne exactement deux `port_down`, un par bout du câble, sans fausse alerte
- [ ] B3 : lire le CPU, mesurer la latence par un vrai ping, distinguer un port coupé par l'admin d'une panne

Le labo
- [x] Niveau 1 : fausses sondes, dans les tests
- [x] Niveau 2 : snmpsim, la vraie sonde SNMP face à un faux switch
- [x] Niveau 3 : Containerlab sous WSL2, validé avec deux routeurs Nokia SR Linux
- [x] Le labo à quatre équipements (datacenter → routeur → switch → borne) et la panne en cascade

**Phase 2 : l'application visible**, en cours.

- [x] **Le collecteur** (`zeus_app/collecte.py`) : `collecter()` enchaîne B1, B2 et B3, et renvoie la photo du réseau (`EtatReseau`) ; B1 garde le sysLocation brut et B13 le décode, pour que chaque équipement ait son emplacement (un sysLocation absent ou mal écrit ne bloque jamais la photo)
- [x] **B11 API** (`zeus_app/api.py`) : `/etat`, `/equipements` et `/liens` renvoient la dernière photo, reprise toutes les minutes ; une collecte qui échoue garde l'ancienne photo
- [x] **La corrélation** (`zeus_app/correlation.py`) : `correler()` regroupe les événements d'une même panne en un seul incident, en quatre règles (équipement hors ligne et sa cascade, câble coupé, port seul, lenteur)
- [x] **Le registre des incidents** : à chaque photo, l'API compare avec la précédente, corrèle, garde chaque panne tant qu'elle dure, et la ferme quand la photo la montre réparée ; `/incidents` (ouverts) et `/incidents/historique` (fermés, avec leur durée)
- [x] La route `/equipements/{nom}`, pour la fiche d'un seul équipement (404 si le nom est inconnu)
- [ ] **B12 Carte** 2D et 3D, branchée sur l'API. Choix retenus :
  - la carte se dessine seule à partir de la découverte, rien n'est placé à la main ;
  - les positions sont calculées en Python (`placer()`, à venir) et sont stables : le même réseau donne toujours la même carte ;
  - l'animation reprend le prototype : le scan qui construit la carte, un zoom 2D sur le bâtiment, puis un plan-séquence 3D en vue éclatée (jamais de départ depuis la France) ;
  - l'information d'abord : la fiche de localisation s'affiche tout de suite, l'animation peut être sautée ou accélérée (temps d'intervention, GTR)

Les phases suivantes : les alertes et la vérification avant clôture (phase 3), puis l'IA, dont B17 Classification des équipements inconnus (phase 4, idées dans `docs/b17-classification.md`).

## Technologies

- **Python 3.12** pour tout le moteur
- **Pydantic** pour les modèles de données partagés
- **pysnmp** pour interroger les équipements en SNMP
- **FastAPI** et **uvicorn** pour l'API web
- **pytest, ruff, mypy, pre-commit** pour les tests et la qualité du code
- **snmpsim** et **Containerlab** (avec Docker, sous WSL2) pour le labo
- Plus tard : networkx, Redis, Three.js

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

Sous Ubuntu (pour le labo Containerlab), c'est la même chose avec `python3 -m venv .venv` puis `source .venv/bin/activate`.

Refais `pip install -e ".[dev]"` chaque fois que `pyproject.toml` gagne une dépendance ou un nouveau dossier de code.

## Lancer l'API

Sous Ubuntu, avec le labo Containerlab lancé :

```bash
ZEUS_COMMUNAUTE=public uvicorn zeus_app.principal:app
```

Puis ouvrir http://localhost:8000/docs dans le navigateur. Les adresses :

| Adresse | Ce qu'elle renvoie |
| --- | --- |
| `/etat` | la photo complète du réseau |
| `/equipements` | les équipements |
| `/equipements/{nom}` | la fiche d'un équipement (404 s'il est inconnu) |
| `/liens` | les câbles |
| `/incidents` | les pannes en cours, de la plus ancienne à la plus récente |
| `/incidents/historique` | les pannes réparées, avec `ouvert_le` et `clos_le` |

Les réglages se donnent au lancement, jamais dans le code :
- `ZEUS_COMMUNAUTE` : la communauté SNMP, c'est-à-dire le mot de passe (obligatoire) ;
- `ZEUS_PLAGE` : la plage d'adresses à surveiller (par défaut, celle du labo) ;
- `ZEUS_RACINE` : le routeur central, d'où l'on regarde qui est derrière qui (par défaut `rt-dc`).

## Vérifier le code

```powershell
pytest          # les tests (sans le labo)
pytest -m labo  # les tests du labo snmpsim
ruff check .    # le style et les erreurs courantes
mypy            # les types
```

Ces contrôles tournent aussi automatiquement avant chaque commit, et dans la CI à chaque push.

## Le labo

Voir [`labo/README.md`](labo/README.md) : les trois niveaux de tests, le faux switch snmpsim et le réseau virtuel Containerlab.

## Travailler sur le projet

- Une petite correction se fait directement sur `main`. Une brique entière passe par une branche (`feat/…`, `fix/…`, `docs/…`) et une pull request.
- Un message de commit dit ce que fait le commit : `B1 : reconnaître SR Linux comme routeur`, et non `mise à jour`.
- Un test rouge se corrige dans le code, pas en supprimant le test.

## Arborescence

```
zeus_core/      modèles partagés par toutes les briques (Pydantic)
briques/        les briques du logiciel, une par sous-dossier (b01_decouverte…)
zeus_app/       l'application, qui assemble les briques : collecteur (collecte.py), API (api.py), point de départ (principal.py)
sondes/         le code qui parle au réseau (sonde SNMP)
labo/           snmpsim (faux switch) et Containerlab (routeurs virtuels)
tests/          les tests, un fichier par module
CLAUDE.md       règles du projet pour Claude Code
```

## Auteur

Elvis Noubissie (Levis), étudiant en Bachelor Informatique Data et IA à l'ECE Paris.

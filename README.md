# ZeusRéseau

Supervision réseau visuelle, pensée comme un jeu de gestion.

ZeusRéseau écoute le réseau d'une entreprise depuis un serveur Linux, dessine ses sites sur une carte, et localise une panne en 3D jusqu'au bâtiment, à l'étage, à la baie et au port en cause. Un Conseiller propose ensuite l'action adaptée : envoyer un technicien sur site si l'équipement est hors service, ou donner des directives IA s'il est seulement lent. L'incident n'est clos qu'après une vérification automatique.

## État du projet

**Phase 1 : socle et collecte des données**, presque terminée.

Le socle
- [x] Modèles partagés (`zeus_core`) : Emplacement, Equipement, Interface, Lien, Incident, Releve, Evenement
- [x] Contrôles avant commit (pre-commit : ruff, mypy, pytest)
- [x] Intégration continue (GitHub Actions), avec les tests du labo snmpsim

Les briques
- [x] **B1 Découverte** des équipements, validée sur de vrais routeurs (SR Linux reconnu comme routeur)
- [x] **B13 Inventaire** des emplacements (lecture de sysLocation), validé sur de vrais routeurs
- [x] **B2 Topologie** (qui est branché à qui) : logique testée avec une fausse sonde
- [x] B2 : la sonde SNMP lit les voisins LLDP (LLDP-MIB), testée contre snmpsim et validée sur de vrais routeurs (un seul câble trouvé, `rt-dc` ↔ `rt-lil`)
- [x] **B3 Supervision** (état des ports, changements, seuils) : logique testée, état réel des ports lu par la sonde
- [ ] B3 sur le labo : une vraie coupure passée par `relever()` et `comparer()`
- [ ] B3 : lire le CPU, mesurer la latence par un vrai ping, distinguer un port coupé par l'admin d'une panne

Le labo
- [x] Niveau 1 : fausses sondes, dans les tests
- [x] Niveau 2 : snmpsim, la vraie sonde SNMP face à un faux switch
- [x] Niveau 3 : Containerlab, deux routeurs Nokia SR Linux sous WSL2
- [ ] Un réseau plus grand pour tester la corrélation des pannes

Les phases suivantes : l'API et la carte 2D/3D sur les vraies données (phase 2), les alertes et la vérification avant clôture (phase 3), puis l'IA, dont B17 Classification des équipements inconnus (phase 4).

## Technologies

- **Python 3.12** pour tout le moteur
- **Pydantic** pour les modèles de données partagés
- **pysnmp** pour interroger les équipements en SNMP
- **pytest, ruff, mypy, pre-commit** pour les tests et la qualité du code
- **snmpsim** et **Containerlab** (avec Docker, sous WSL2) pour le labo
- Plus tard : networkx, FastAPI, Redis, Three.js

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
sondes/         le code qui parle au réseau (sonde SNMP)
labo/           snmpsim (faux switch) et Containerlab (routeurs virtuels)
tests/          les tests, un fichier par module
CLAUDE.md       règles du projet pour Claude Code
```

## Auteur

Elvis Noubissie (Levis), étudiant en Bachelor Informatique Data et IA à l'ECE Paris.

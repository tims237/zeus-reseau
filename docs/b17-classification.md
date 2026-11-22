# B17 Classification : idées retenues

Notes de conception, discutées avec Levis le 22 novembre 2026. À reprendre quand on attaquera B17, après l'API (B11), la corrélation et la carte (B12) : la validation par l'ingénieur a besoin d'un écran.

## Le but

Faire passer le savoir **du code vers les données**. Aujourd'hui, les types sont écrits à la main dans `MOTS_CLES` (B1) : chaque nouveau modèle demande de modifier le code. Demain, ZeusRéseau apprend sans qu'on le reprogramme.

- **Le code** dit *comment décider* : il change rarement.
- **Le catalogue** dit *ce qu'on sait* : « 6527 = Nokia », « Catalyst 9200 = switch, 1U ». Il grandit au fil des validations, rangé sur le serveur (fichier JSON au début, base de données ensuite). Mille modèles tiennent en moins de 100 Ko.

## Le pipeline

1. **Observer** : numéro de fabricant du sysObjectID, sysDescr, capacités LLDP, nombre de ports, voisins.
2. **Déduire** un type, avec une confiance (« borne Wi-Fi, 85 % »).
3. **Placer** dans l'armoire : le sysLocation (B13) quand il existe ; sinon, deviner le site et l'étage d'après les voisins LLDP.
4. **Faire valider** par l'ingénieur, seulement quand la confiance est faible.
5. **Apprendre** : chaque validation devient un exemple, pour un modèle de machine learning en phase 4.

## Le temps

- On identifie un équipement **une seule fois**, à sa découverte, et on range le résultat dans sa fiche. Les photos suivantes ne refont pas la recherche.
- On recommence seulement si quelque chose change : nouvel équipement, ou sysObjectID différent (remplacement).
- 3 ou 4 questions SNMP par équipement suffisent. Ce qui coûte, c'est de les poser l'un après l'autre : à faire **en parallèle** (asyncio) avant un vrai réseau d'entreprise.

## La place dans l'armoire

- Ajouter la **hauteur en U** à la fiche de l'équipement (au moins 1U), prise dans le catalogue des modèles ; sinon proposée selon le type, puis validée.
- Permettra : dessiner l'armoire à l'échelle en 3D, repérer deux équipements déclarés sur les mêmes U, calculer la place libre d'une baie.

## Comment l'entreprise complète le catalogue

1. **En validant** les propositions de ZeusRéseau : une validation sert pour tous les équipements du même modèle.
2. **À la main**, dans une page « Catalogue », avant même de brancher le matériel.
3. **Par import** d'un fichier CSV (Excel, GLPI, NetBox, liste d'achats).
4. **Par les mises à jour** du catalogue de départ livré avec ZeusRéseau (les mots-clés actuels de B1 en sont la première version).

Règles : seuls les ingénieurs autorisés valident ; chaque ligne garde qui l'a ajoutée, quand et d'où elle vient ; une correction remplace l'ancienne valeur, l'historique en garde la trace.

## Premier cas de test, déjà dans le labo

`sw-lil` est classé `routeur` par B1, puisque c'est un SR Linux, alors que c'est un switch.

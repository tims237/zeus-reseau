# Le labo de ZeusRéseau

Un réseau d'entraînement simulé, pour tester le vrai code sans vrai réseau d'entreprise.

## Les trois niveaux de tests

| Niveau | Outil | Ce qu'il vérifie | Quand il tourne |
| --- | --- | --- | --- |
| 1 | Fausses sondes (dans `tests/`) | La logique des briques | À chaque commit et dans la CI (`pytest`) |
| 2 | **snmpsim** (ce dossier) | La vraie sonde SNMP face à un faux switch | Dans la CI, et à la demande (`pytest -m labo`) |
| 3 | **Containerlab** (`containerlab/`) | ZeusRéseau face à un vrai réseau virtuel (3 SR Linux et une borne) | À la main, sous Ubuntu (WSL2), pour essayer et faire des démos |

## Niveau 2 : snmpsim, le faux switch

`snmpsim/sw-lil-02.snmprec` décrit les réponses SNMP d'un switch Cisco imaginaire, SW-LIL-02 :

- son nom, son modèle et son emplacement (`LIL/BatA/E2/SalleServeur/B2/U14`) ;
- trois ports : Gi1/0/1 et Gi1/0/11 up, **Gi1/0/12 down** ;
- ses voisins LLDP : `rt-lil` derrière Gi1/0/1, `AP-LIL-01` derrière Gi1/0/11 (qui annonce son port par adresse MAC, comme une vraie borne), et `rt-dc` derrière le port d'administration mgmt0 (que la sonde doit ignorer).

Les lignes sont rangées dans l'ordre des OID (snmpsim l'exige) : c'est pour ça que les lignes LLDP, en `1.0.8802…`, sont en haut.

Chaque ligne suit le format `OID|type|valeur` :
- l'**OID** est l'adresse de l'information dans l'équipement, par exemple `1.3.6.1.2.1.1.5.0` pour son nom ;
- le **type** vaut `4` pour du texte et `2` pour un nombre ;
- pour l'état d'un port, `1` veut dire up et `2` down.

### Lancer les tests du labo

```powershell
pytest -m labo
```

Le test démarre snmpsim tout seul, interroge le faux switch avec la vraie sonde (`sondes/sonde_snmp.py`), vérifie que B1, B13, B2 et B3 lisent bien ses réponses, puis arrête snmpsim.

### Interroger le faux switch à la main

Dans un premier terminal :
```powershell
snmpsim-command-responder --data-dir=labo/snmpsim --agent-udpv4-endpoint=127.0.0.1:1161
```

Dans un second terminal :
```powershell
python -c "from sondes.sonde_snmp import SondeSNMP; print(SondeSNMP('sw-lil-02', port=1161).lire_sysinfo('127.0.0.1'))"
```

La communauté `sw-lil-02` dit à snmpsim quel fichier `.snmprec` utiliser.

### Simuler une panne

Dans `sw-lil-02.snmprec`, passe la dernière ligne de `|2|2` à `|2|1` : le port 12 revient up. Relance `pytest -m labo` et regarde le test `test_b3_voit_le_port_12_down` échouer, puisque le port n'est plus down. Remets ensuite `|2|2`.

## Niveau 3 : Containerlab, de vrais routeurs virtuels

`containerlab/zeus.clab.yml` décrit une petite entreprise, du datacenter jusqu'à une borne Wi-Fi de l'agence de Lille :

```
rt-dc ──e1-1────e1-1── rt-lil ──e1-2────e1-1── sw-lil ──e1-2────eth1── ap-lil-01
(datacenter)        (routeur de Lille)       (switch de Lille)       (borne Wi-Fi)
```

- `rt-dc`, `rt-lil` et `sw-lil` sont des **Nokia SR Linux**, de vrais systèmes de routeur : ils parlent SNMP et LLDP comme en entreprise. Le switch est lui aussi un SR Linux : B1 le classe donc en `routeur`, un cas à garder pour B17.
- `ap-lil-01` est un petit **Alpine Linux** qui joue une borne : `lldpd` l'annonce en LLDP, `snmpd` répond en SNMP. La configuration SNMP est dans `containerlab/ap-lil-01/snmpd.conf`. Comme beaucoup de vraies bornes, elle annonce son port en LLDP par son adresse MAC. Sa description contient « access point », pour que B1 la classe en `borne-wifi`.

### Préparer le poste (une seule fois)

Containerlab demande Linux. Sous Windows :
1. **WSL2 et Ubuntu**, installés sur un disque qui a de la place (ici `B:\WSL\Ubuntu`, car `C:` était plein) : `wsl --install -d Ubuntu --location B:\WSL\Ubuntu`.
2. **Docker installé directement dans Ubuntu** (`curl -fsSL https://get.docker.com | sudo sh`), et **pas** l'intégration WSL de Docker Desktop : avec elle, Containerlab ne peut pas brancher les câbles virtuels (erreur `namespace path not available`).
3. **Containerlab** : `bash -c "$(curl -sL https://get.containerlab.dev)"`.
4. Les droits : `sudo usermod -aG docker,clab_admins $USER`, puis `wsl --shutdown` depuis Windows.
5. Les outils : `sudo apt install -y snmp python3-venv iptables`.

### Lancer le labo

Dans Ubuntu :
```bash
cd ~/zeus-reseau/labo/containerlab
containerlab deploy -t zeus.clab.yml
```
Le premier lancement télécharge l'image SR Linux (environ 2 Go) et, pour la borne, lldpd et snmpd : Ubuntu doit avoir accès à Internet. Comptez environ 2 Go de mémoire par SR Linux. Ensuite :

| Équipement | Entrer dans sa console |
| --- | --- |
| rt-dc | `docker exec -it clab-zeus-rt-dc sr_cli` |
| rt-lil | `docker exec -it clab-zeus-rt-lil sr_cli` |
| sw-lil | `docker exec -it clab-zeus-sw-lil sr_cli` |
| ap-lil-01 | `docker exec -it clab-zeus-ap-lil-01 sh` (un Linux : `lldpcli show neighbors`) |

Les adresses peuvent changer d'un lancement à l'autre (avec `--reconfigure`, `rt-dc` et `rt-lil` ont échangé leurs adresses) : le tableau affiché par `deploy` fait foi. Dans le code, ne les écris pas à la main : laisse B1 construire le carnet d'adresses.

```bash
python -c "
from briques.b01_decouverte import decouvrir
from briques.b02_topologie import construire_liens
from sondes.sonde_snmp import SondeSNMP
sonde = SondeSNMP('public', delai_s=0.5)
sonde.adresses = {e.id: str(e.ip) for e in decouvrir('172.20.20.0/28', sonde)}
for lien in construire_liens(list(sonde.adresses), sonde):
    print(lien)
"
```

SNMP v2c est actif d'origine sur les SR Linux, avec la communauté `public` ; la borne utilise la même.

Éteindre : `containerlab destroy -t zeus.clab.yml`. Repartir d'une configuration propre : `containerlab deploy -t zeus.clab.yml --reconfigure`.

### Ce qui a été vérifié sur le labo

- [x] SNMP : `snmpwalk -v2c -c public 172.20.20.3 1.3.6.1.2.1.1` renvoie le nom, le modèle et l'emplacement.
- [x] **B1 Découverte** : `decouvrir("172.20.20.0/28", SondeSNMP("public", delai_s=0.5))` trouve les deux routeurs, de type `routeur`.
- [x] **B13 Inventaire** : un `sysLocation` écrit sur le routeur est lu par la sonde et décodé par `lire_syslocation`.
- [x] **LLDP** : `show system lldp neighbor` montre `rt-lil` derrière le port `ethernet-1/1` de `rt-dc`.
- [x] **Coupure** : quand Lille coupe son port, celui de `rt-dc` passe down, et la sonde le voit (`etat_interfaces`).
- [x] **B3** : une coupure côté Lille, passée par `relever()` puis `comparer()`, donne exactement deux `port_down` (`rt-lil` et `rt-dc`, sur `ethernet-1/1`) et aucune alerte de seuil.
- [x] **B2** : `construire_liens` trouve un seul câble, `rt-dc ethernet-1/1` ↔ `rt-lil ethernet-1/1` ; le voisin vu par `mgmt0` est ignoré.
- [x] **Réseau à quatre équipements** : B1 trouve les quatre, dont `ap-lil-01` en `borne-wifi` ; B2 trouve trois câbles, le port de la borne lu `eth1`.
- [x] **Panne en cascade** : `rt-lil` en panne rend `sw-lil` et `ap-lil-01` injoignables ; `sw-lil` en panne, seulement `ap-lil-01`.

### Tester la panne en cascade

Quand le routeur de Lille tombe, tout ce qui est derrière lui est coupé du datacenter. ZeusRéseau doit envoyer **une** alerte, « Agence Lille hors ligne, cause : rt-lil », et non une alerte par équipement. C'est le rôle de `equipements_injoignables` (B2).

```bash
python -c "
from briques.b01_decouverte import decouvrir
from briques.b02_topologie import construire_liens, equipements_injoignables
from sondes.sonde_snmp import SondeSNMP
sonde = SondeSNMP('public', delai_s=0.5)
equipements = decouvrir('172.20.20.0/28', sonde)
sonde.adresses = {e.id: str(e.ip) for e in equipements}
for e in equipements:
    print(e.id, e.ip, e.type)
liens = construire_liens(list(sonde.adresses), sonde)
for lien in liens:
    print(lien)
print('Si rt-lil tombe :', equipements_injoignables('rt-dc', liens, en_panne={'rt-lil'}))
print('Si sw-lil tombe :', equipements_injoignables('rt-dc', liens, en_panne={'sw-lil'}))
"
```

On doit voir quatre équipements, trois câbles, puis `{'ap-lil-01', 'sw-lil'}` pour la panne de `rt-lil`, et `{'ap-lil-01'}` pour celle de `sw-lil`.

**Une limite du labo, à connaître** : dans Containerlab, chaque équipement a aussi un port d'administration (`mgmt0`), relié directement au PC. Si on coupe vraiment `rt-lil`, la sonde joint toujours `sw-lil` et la borne par ce chemin de secours : ils ne paraissent pas injoignables. C'est pourquoi on donne ici la panne à `equipements_injoignables` (`en_panne={'rt-lil'}`), sur la **vraie** topologie lue par B2. En entreprise, la supervision passe souvent par le réseau lui-même : derrière un routeur mort, tout devient vraiment muet, et c'est exactement ce cas que calcule la fonction.

### Si un câble ne monte pas

Si `show interface ethernet-1/2` affiche `down` sur `rt-lil` ou `sw-lil` alors que rien n'a été coupé, active le port :
```
enter candidate
set / interface ethernet-1/2 admin-state enable
commit now
```
Pour la borne, vérifie que lldpd et snmpd tournent : `docker exec clab-zeus-ap-lil-01 ps`. Sinon, relance le labo avec `--reconfigure`.

### Commandes utiles dans la console SR Linux

```
show interface ethernet-1/1          # état d'un port, et la raison s'il est down
show system lldp neighbor            # les voisins vus par LLDP
enter candidate                      # ouvrir un brouillon de configuration
set / interface ethernet-1/1 admin-state disable   # couper un port (enable pour rétablir)
set / system information location "LIL/BatA/E2/SalleServeur/B2/U14"
commit now                           # appliquer le brouillon
quit
```

### Ce que le labo a appris au projet

- Un port coupé par l'admin affiche la raison `port-admin-disabled` : ce n'est pas une panne, et ZeusRéseau devra le distinguer d'une vraie coupure.
- Un routeur a beaucoup de ports **normalement** down (57 sur 58 ici) : seule une détection des **changements**, comme `comparer()`, évite les fausses alertes.
- LLDP garde un voisin disparu en mémoire environ deux minutes.
- Une mesure peut mentir : `latence_ms` comptait le démarrage de pysnmp (500 ms) au lieu du réseau (quelques ms), et créait une fausse alerte sur chaque routeur.
- Les adresses IP changent : un nom d'équipement associé à la mauvaise IP fait croire à un routeur qu'il est son propre voisin. Seul B1, qui lit le vrai nom à chaque adresse, fait foi.
- Un identifiant de port LLDP n'est pas toujours un nom : la borne (lldpd) annonce son adresse MAC, dont les octets ressemblaient à du texte (`zØu`). Pire, SR Linux déclare le sous-type « nom de port » (5) même pour cette adresse MAC : un équipement de marque peut se tromper. La sonde vérifie donc elle-même qu'un nom de port est en ASCII, et sinon prend la description (`eth1`).
- snmpd lisait sa configuration deux fois (fichier à l'emplacement par défaut **et** option `-c`), ouvrait deux fois le port 161 et s'arrêtait (`Address in use`).
- Les mots-clés de B1 ne connaîtront jamais tous les modèles : c'est le rôle futur de B17 Classification.

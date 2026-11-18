# Le labo de ZeusRéseau

Un réseau d'entraînement simulé, pour tester le vrai code sans vrai réseau d'entreprise.

## Les trois niveaux de tests

| Niveau | Outil | Ce qu'il vérifie | Quand il tourne |
| --- | --- | --- | --- |
| 1 | Fausses sondes (dans `tests/`) | La logique des briques | À chaque commit et dans la CI (`pytest`) |
| 2 | **snmpsim** (ce dossier) | La vraie sonde SNMP face à un faux switch | Dans la CI, et à la demande (`pytest -m labo`) |
| 3 | **Containerlab** (`containerlab/`) | ZeusRéseau face à de vrais routeurs virtuels | À la main, sous Ubuntu (WSL2), pour essayer et faire des démos |

## Niveau 2 : snmpsim, le faux switch

`snmpsim/sw-lil-02.snmprec` décrit les réponses SNMP d'un switch Cisco imaginaire, SW-LIL-02 :

- son nom, son modèle et son emplacement (`LIL/BatA/E2/SalleServeur/B2/U14`) ;
- trois ports : Gi1/0/1 et Gi1/0/11 up, **Gi1/0/12 down**.

Chaque ligne suit le format `OID|type|valeur` :
- l'**OID** est l'adresse de l'information dans l'équipement, par exemple `1.3.6.1.2.1.1.5.0` pour son nom ;
- le **type** vaut `4` pour du texte et `2` pour un nombre ;
- pour l'état d'un port, `1` veut dire up et `2` down.

### Lancer les tests du labo

```powershell
pytest -m labo
```

Le test démarre snmpsim tout seul, interroge le faux switch avec la vraie sonde (`sondes/sonde_snmp.py`), vérifie que B1, B13 et B3 lisent bien ses réponses, puis arrête snmpsim.

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

`containerlab/zeus.clab.yml` décrit un petit réseau : deux routeurs **Nokia SR Linux**, `rt-dc` (le datacenter) et `rt-lil` (Lille), reliés par un câble entre leurs ports `ethernet-1/1`. Ce sont de vrais systèmes de routeur : ils parlent SNMP et LLDP comme en entreprise.

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
Le premier lancement télécharge l'image SR Linux (environ 2 Go). Ensuite :

| Routeur | Adresse | Entrer dans sa console |
| --- | --- | --- |
| rt-dc | 172.20.20.3 | `docker exec -it clab-zeus-rt-dc sr_cli` |
| rt-lil | 172.20.20.2 | `docker exec -it clab-zeus-rt-lil sr_cli` |

Les adresses peuvent changer d'un lancement à l'autre : le tableau affiché par `deploy` fait foi. SNMP v2c est actif d'origine, avec la communauté `public`.

Éteindre : `containerlab destroy -t zeus.clab.yml`. Repartir d'une configuration propre : `containerlab deploy -t zeus.clab.yml --reconfigure`.

### Ce qui a été vérifié sur le labo

- [x] SNMP : `snmpwalk -v2c -c public 172.20.20.3 1.3.6.1.2.1.1` renvoie le nom, le modèle et l'emplacement.
- [x] **B1 Découverte** : `decouvrir("172.20.20.0/28", SondeSNMP("public", delai_s=0.5))` trouve les deux routeurs, de type `routeur`.
- [x] **B13 Inventaire** : un `sysLocation` écrit sur le routeur est lu par la sonde et décodé par `lire_syslocation`.
- [x] **LLDP** : `show system lldp neighbor` montre `rt-lil` derrière le port `ethernet-1/1` de `rt-dc`.
- [x] **Coupure** : quand Lille coupe son port, celui de `rt-dc` passe down, et la sonde le voit (`etat_interfaces`).
- [ ] **B3** : faire passer une coupure par `relever()` puis `comparer()`.
- [ ] **B2** : la sonde ne lit pas encore les voisins LLDP en SNMP.
- [ ] Un réseau plus grand (datacenter, routeur, switch, borne) pour tester la corrélation des pannes.

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
- Les mots-clés de B1 ne connaîtront jamais tous les modèles : c'est le rôle futur de B17 Classification.

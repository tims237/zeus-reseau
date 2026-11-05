# Le labo de ZeusRéseau

Un réseau d'entraînement simulé, pour tester le vrai code sans vrai réseau d'entreprise.

## Les trois niveaux de tests

| Niveau | Outil | Ce qu'il vérifie | Quand il tourne |
| --- | --- | --- | --- |
| 1 | Fausses sondes (dans `tests/`) | La logique des briques | À chaque commit et dans la CI (`pytest`) |
| 2 | **snmpsim** (ce dossier) | La vraie sonde SNMP face à un faux switch | Dans la CI, et à la demande (`pytest -m labo`) |
| 3 | Containerlab (à venir) | Tout ZeusRéseau sur un réseau virtuel complet | À la main, pour essayer et faire des démos |

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

## Niveau 3 : Containerlab (à venir)

De vrais routeurs et switchs virtuels dans des conteneurs Docker, reliés par des câbles virtuels, avec LLDP et SNMP. On pourra couper un câble et regarder ZeusRéseau trouver la panne. Il demande Linux : sous Windows, il faudra installer WSL2 et Docker.
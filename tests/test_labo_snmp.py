"""Tests du labo : la vraie sonde SNMP face à un faux switch simulé par snmpsim.

Ces tests démarrent snmpsim, qui imite le switch SW-LIL-02 décrit dans
labo/snmpsim/sw-lil-02.snmprec, puis l'interrogent avec la vraie sonde.

Ils sont marqués « labo » et ne tournent pas avec un simple `pytest` (ils prennent
quelques secondes). Pour les lancer : `pytest -m labo`. La CI les lance à part.
"""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from briques.b01_decouverte import decouvrir
from briques.b02_topologie import construire_liens
from briques.b03_supervision import relever
from briques.b13_inventaire import lire_syslocation
from sondes.sonde_snmp import SondeSNMP
from zeus_core.modeles import Lien, TypeEquipement

DOSSIER_DONNEES = Path(__file__).parent.parent / "labo" / "snmpsim"
COMMUNAUTE = "sw-lil-02"  # snmpsim choisit le fichier d'après la communauté


def _port_libre() -> int:
    """Demande au système un port UDP libre."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _trouver_snmpsim() -> str | None:
    """Cherche le programme snmpsim, d'abord à côté du Python en cours (le .venv)."""
    dossier_python = str(Path(sys.executable).parent)
    return shutil.which("snmpsim-command-responder", path=dossier_python) or shutil.which(
        "snmpsim-command-responder"
    )


@pytest.fixture(scope="module")
def sonde() -> Iterator[SondeSNMP]:
    """Démarre snmpsim avant les tests du fichier, et l'arrête après."""
    programme = _trouver_snmpsim()
    if programme is None:
        pytest.skip('snmpsim n\'est pas installé (pip install -e ".[dev]")')

    port = _port_libre()
    cache = tempfile.mkdtemp(prefix="snmpsim-cache-")
    commande = [
        programme,
        f"--data-dir={DOSSIER_DONNEES}",
        f"--agent-udpv4-endpoint=127.0.0.1:{port}",
        f"--cache-dir={cache}",
    ]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        # snmpsim refuse de tourner en administrateur (root) : on lui donne un compte simple.
        os.chmod(cache, 0o777)
        commande += ["--process-user=nobody", "--process-group=nogroup"]

    processus = subprocess.Popen(commande, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sonde = SondeSNMP(communaute=COMMUNAUTE, port=port, adresses={"SW-LIL-02": "127.0.0.1"})
    try:
        # On attend que le faux switch réponde (au plus 20 secondes).
        limite = time.monotonic() + 20
        while not sonde.ping("127.0.0.1"):
            if time.monotonic() > limite:
                pytest.fail("snmpsim n'a pas démarré à temps")
            time.sleep(0.5)
        yield sonde
    finally:
        processus.terminate()
        processus.wait(timeout=10)
        shutil.rmtree(cache, ignore_errors=True)


@pytest.mark.labo
def test_sysinfo_du_faux_switch(sonde: SondeSNMP) -> None:
    info = sonde.lire_sysinfo("127.0.0.1")
    assert info is not None
    assert info["sysName"] == "SW-LIL-02"
    assert "C9200" in info["sysDescr"]


@pytest.mark.labo
def test_b1_decouvre_le_faux_switch(sonde: SondeSNMP) -> None:
    # B1, avec la VRAIE sonde : le même code que dans les tests à fausse sonde.
    trouves = decouvrir("127.0.0.1/32", sonde)
    assert [e.id for e in trouves] == ["SW-LIL-02"]
    assert trouves[0].type is TypeEquipement.SWITCH


@pytest.mark.labo
def test_b13_lit_l_emplacement_du_faux_switch(sonde: SondeSNMP) -> None:
    info = sonde.lire_sysinfo("127.0.0.1")
    assert info is not None
    emplacement = lire_syslocation(info["sysLocation"])
    assert (emplacement.site, emplacement.baie, emplacement.position_u) == ("LIL", "B2", 14)


@pytest.mark.labo
def test_b3_voit_le_port_12_down(sonde: SondeSNMP) -> None:
    releve = relever(["SW-LIL-02"], sonde, maintenant=datetime.now())[0]
    assert releve.repond
    assert releve.interfaces["Gi1/0/1"] is True
    assert releve.interfaces["Gi1/0/12"] is False


@pytest.mark.labo
def test_la_sonde_lit_les_voisins_lldp(sonde: SondeSNMP) -> None:
    voisins = sonde.voisins_lldp("SW-LIL-02")
    # Le voisin vu par le port d'administration (mgmt0) est ignoré.
    assert voisins == [
        {"port_local": "Gi1/0/1", "voisin": "rt-lil", "port_voisin": "ethernet-1/2"},
        {"port_local": "Gi1/0/11", "voisin": "AP-LIL-01", "port_voisin": "eth0"},
    ]


@pytest.mark.labo
def test_b2_construit_les_liens_du_faux_switch(sonde: SondeSNMP) -> None:
    # B2, avec la VRAIE sonde : le même code que dans les tests à fausse sonde.
    liens = construire_liens(["SW-LIL-02"], sonde)
    assert liens == [
        Lien(
            equipement_a="SW-LIL-02",
            interface_a="Gi1/0/1",
            equipement_b="rt-lil",
            interface_b="ethernet-1/2",
        ),
        Lien(
            equipement_a="SW-LIL-02",
            interface_a="Gi1/0/11",
            equipement_b="AP-LIL-01",
            interface_b="eth0",
        ),
    ]


@pytest.mark.labo
def test_equipement_muet_n_a_aucun_voisin(sonde: SondeSNMP) -> None:
    # Une mauvaise communauté : l'équipement ne répond pas, la sonde renvoie une liste vide.
    muette = SondeSNMP(communaute="inconnue", port=sonde.port, delai_s=0.5)
    assert muette.voisins_lldp("127.0.0.1") == []


@pytest.mark.labo
def test_latence_mesure_le_reseau_et_pas_le_demarrage_de_pysnmp(sonde: SondeSNMP) -> None:
    # snmpsim tourne sur ce même ordinateur : il répond en quelques millisecondes.
    # Une latence de plusieurs centaines de millisecondes voudrait dire que le chronomètre
    # compte aussi le démarrage de pysnmp (bug trouvé sur le labo Containerlab).
    latence = sonde.latence_ms("SW-LIL-02")
    assert latence is not None
    assert latence < 100

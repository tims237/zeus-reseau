"""Tests du labo : la vraie sondes SNMP face à un faux switch simulé par snmpsim.

Ces tests démarrent snmpsim, qui imite le switch SW-LIL-02 décrit dans
labo/snmpsim/sw-lil-02.snmprec, puis l'interrogent avec la vraie sondes.

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
from briques.b03_supervision import relever
from briques.b13_inventaire import lire_syslocation
from sondes.sonde_snmp import SondeSNMP
from zeus_core.modeles import TypeEquipement

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
    # B1, avec la VRAIE sondes : le même code que dans les tests à fausse sondes.
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

"""Un lock se da por huérfano por su dueño, no por el reloj de pared.

Hasta v41.6 `vault.kernel.bloqueo.adquirir` robaba el lock cuando
`time.time() - createdAt` pasaba de `CADUCA_TRAS`, y un salto del reloj se lo
robaba a un dueño vivo (deuda `lock_caduca_por_reloj_de_pared`, medida en
python:3.9-slim sobre Docker Desktop). El criterio pasa a ser el de py-filelock
(`SoftFileLock`): `owner.json` guarda la máquina y la hora de inicio del
proceso, y en la misma máquina el lock solo se rompe si el dueño murió o su pid
es ya de otro proceso. Un dueño de otra máquina —o un `owner.json` sin máquina,
de una versión anterior— sigue con la regla de edad, que es el límite que queda
declarado: entre máquinas no hay forma de preguntar si un proceso vive.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from vault.kernel import bloqueo  # noqa: E402


def _nota(tmp_path: Path) -> Path:
    nota = tmp_path / "nota.md"
    nota.write_text("x\n", encoding="utf-8")
    return nota


def _dueno(nota: Path) -> dict:
    _, lock_dir = bloqueo.rutas_de_lock(nota)
    return json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))


def _reescribir_dueno(nota: Path, **cambios) -> None:
    _, lock_dir = bloqueo.rutas_de_lock(nota)
    dueno = _dueno(nota)
    dueno.update(cambios)
    (lock_dir / "owner.json").write_text(json.dumps(dueno), encoding="utf-8")


def _pid_muerto() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def test_owner_json_declara_maquina_e_inicio_del_proceso(tmp_path):
    nota = _nota(tmp_path)
    token = bloqueo.adquirir(nota, timeout=1.0)
    try:
        dueno = _dueno(nota)
        assert dueno["maquina"] == bloqueo.maquina()
        assert "inicio" in dueno
    finally:
        bloqueo.soltar(nota, token)


def test_un_salto_del_reloj_no_roba_el_lock_a_un_dueno_vivo(tmp_path):
    """El caso medido: mismo host, dueño vivo, `createdAt` atrás por un salto."""
    nota = _nota(tmp_path)
    token = bloqueo.adquirir(nota, timeout=1.0)
    try:
        _reescribir_dueno(nota, createdAt=time.time() - bloqueo.CADUCA_TRAS - 3600)
        with pytest.raises(TimeoutError):
            bloqueo.adquirir(nota, timeout=0.5)
        assert _dueno(nota)["token"] == token
    finally:
        bloqueo.soltar(nota, token)


def test_un_dueno_muerto_de_la_misma_maquina_se_recupera_sin_esperar(tmp_path):
    nota = _nota(tmp_path)
    token = bloqueo.adquirir(nota, timeout=1.0)
    _reescribir_dueno(nota, pid=_pid_muerto(), inicio=None, createdAt=time.time())
    nuevo = bloqueo.adquirir(nota, timeout=2.0)
    try:
        assert nuevo != token
        assert _dueno(nota)["token"] == nuevo
    finally:
        bloqueo.soltar(nota, nuevo)


def test_un_pid_reutilizado_no_pasa_por_el_dueno(tmp_path):
    """Mismo pid, otra hora de inicio: el dueño murió y el pid es de otro."""
    if bloqueo.inicio_del_proceso(os.getpid()) is None:
        pytest.skip("esta plataforma no publica la hora de inicio de un proceso")
    nota = _nota(tmp_path)
    token = bloqueo.adquirir(nota, timeout=1.0)
    _reescribir_dueno(nota, inicio="otro-inicio", createdAt=time.time())
    nuevo = bloqueo.adquirir(nota, timeout=2.0)
    try:
        assert nuevo != token
    finally:
        bloqueo.soltar(nota, nuevo)


def test_un_dueno_de_otra_maquina_sigue_caducando_por_edad(tmp_path):
    """El límite declarado: entre máquinas solo queda la edad."""
    nota = _nota(tmp_path)
    token = bloqueo.adquirir(nota, timeout=1.0)
    _reescribir_dueno(nota, maquina="otra-maquina|linux")
    with pytest.raises(TimeoutError):
        bloqueo.adquirir(nota, timeout=0.3)
    _reescribir_dueno(nota, createdAt=time.time() - bloqueo.CADUCA_TRAS - 1)
    nuevo = bloqueo.adquirir(nota, timeout=2.0)
    try:
        assert nuevo != token
    finally:
        bloqueo.soltar(nota, nuevo)


def test_un_owner_json_de_una_version_anterior_sigue_la_regla_de_edad(tmp_path):
    nota = _nota(tmp_path)
    _, lock_dir = bloqueo.rutas_de_lock(nota)
    lock_dir.mkdir(parents=True)
    (lock_dir / "owner.json").write_text(json.dumps({
        "pid": os.getpid(), "createdAt": time.time() - bloqueo.CADUCA_TRAS - 1,
        "token": "viejo",
    }), encoding="utf-8")
    nuevo = bloqueo.adquirir(nota, timeout=2.0)
    try:
        assert nuevo != "viejo"
    finally:
        bloqueo.soltar(nota, nuevo)


def test_el_proceso_propio_vive(tmp_path):
    assert bloqueo.proceso_vivo(os.getpid()) is True
    assert bloqueo.proceso_vivo(_pid_muerto()) is False

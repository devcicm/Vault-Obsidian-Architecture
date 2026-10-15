"""Quien perdió el lock no escribe: la escritura relee `owner.json` antes del replace.

Con `3b8822a` el reloj ya no le roba el lock a un dueño vivo de la misma
máquina, pero el robo sigue siendo posible donde el límite está declarado: un
dueño de otra máquina, o un `owner.json` anterior sin `maquina`, caduca por
edad. Hasta aquí la víctima no se enteraba: seguía dentro de su `with`,
terminaba su `os.replace` sobre lo que el ladrón acababa de escribir y
devolvía ok:true. Es el caso de Kleppmann («How to do distributed locking»,
2016) y del `index.lock` de git: el lock no basta, quien escribe tiene que
comprobar que sigue siendo suyo.

`escritura_atomica` comprueba la toma justo antes de `os.replace`; si el token
de `owner.json` ya no es el de la toma de este hilo, no reemplaza y lanza
`LockPerdido`, que `wrap_main` traduce a NOTE_LOCKED. La comprobación y el
replace no son atómicos entre sí —el sistema de ficheros no acepta un token de
fencing—: estrecha la ventana a microsegundos, no la cierra.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

from vault.kernel import bloqueo  # noqa: E402
from vault.kernel.errores import MAPA_DE_FALLOS, traducir_fallo  # noqa: E402
from vault.kernel.escritura import escritura_atomica  # noqa: E402
from vault.kernel.fallos import CAUSAS  # noqa: E402


def _nota(tmp_path: Path) -> Path:
    nota = tmp_path / "nota.md"
    nota.write_text("original\n", encoding="utf-8")
    return nota


def _robar(nota: Path) -> None:
    """Lo que hace un ladrón que da el lock por caducado: su propio owner.json."""
    _, lock_dir = bloqueo.rutas_de_lock(nota)
    (lock_dir / "owner.json").write_text(
        json.dumps(bloqueo.ficha_del_dueno("ladron")), encoding="utf-8")


def _temporales(nota: Path) -> list:
    return [p.name for p in nota.parent.iterdir() if p.name.startswith(".tmp.")]


def test_la_victima_de_un_robo_no_reemplaza_la_nota(tmp_path):
    nota = _nota(tmp_path)
    token = bloqueo.adquirir(nota, timeout=1.0)
    try:
        _robar(nota)
        with pytest.raises(bloqueo.LockPerdido) as exc:
            escritura_atomica(nota, "de la victima\n")
        assert exc.value.causa == "LOCK_PERDIDO"
        assert nota.read_text(encoding="utf-8") == "original\n"
        assert _temporales(nota) == []
    finally:
        bloqueo.soltar(nota, token)


def test_un_lock_ya_retirado_tambien_es_un_lock_perdido(tmp_path):
    """El ladrón entró, escribió y soltó: `owner.json` ya no existe."""
    nota = _nota(tmp_path)
    token = bloqueo.adquirir(nota, timeout=1.0)
    _robar(nota)
    bloqueo.soltar(nota, "ladron")
    try:
        with pytest.raises(bloqueo.LockPerdido):
            escritura_atomica(nota, "de la victima\n")
        assert nota.read_text(encoding="utf-8") == "original\n"
    finally:
        bloqueo.soltar(nota, token)


def test_con_el_lock_en_regla_se_escribe(tmp_path):
    nota = _nota(tmp_path)
    token = bloqueo.adquirir(nota, timeout=1.0)
    try:
        escritura_atomica(nota, "nuevo\n")
    finally:
        bloqueo.soltar(nota, token)
    assert nota.read_text(encoding="utf-8") == "nuevo\n"


def test_sin_toma_no_hay_nada_que_comprobar(tmp_path):
    """Una escritura fuera de lock —o tras soltarlo— no se para por un lock ajeno."""
    nota = _nota(tmp_path)
    token = bloqueo.adquirir(nota, timeout=1.0)
    bloqueo.soltar(nota, token)
    escritura_atomica(nota, "despues\n")
    assert nota.read_text(encoding="utf-8") == "despues\n"


def test_por_la_politica_de_vault_io_tampoco_se_escribe(tmp_path):
    """El camino de las tools: `file_lock` + `atomic_write_text`."""
    import vault_fs
    import vault_io

    nota = _nota(tmp_path)
    with pytest.raises(bloqueo.LockPerdido):
        with vault_fs.file_lock(nota, timeout=1.0):
            _robar(nota)
            vault_io.atomic_write_text(nota, "de la victima\n")
    assert nota.read_text(encoding="utf-8") == "original\n"


SONDA = r"""
import json, runpy, sys
from pathlib import Path
scripts = sys.argv[1]
sys.path[:0] = [scripts, sys.argv[2]]
import vault_io
from vault.kernel import bloqueo

real = vault_io._record_write

def robar(path, text, encoding):
    # El ladrón entra entre la lectura y el replace de la víctima.
    _, lock_dir = bloqueo.rutas_de_lock(Path(path))
    (lock_dir / "owner.json").write_text(
        json.dumps(bloqueo.ficha_del_dueno("ladron")), encoding="utf-8")
    return real(path, text, encoding)

vault_io._record_write = robar
sys.argv = ["vault_append.py", "--path", "07_Knowledge/log.md",
            "--content", "DE_LA_VICTIMA", "--no-timestamp"]
runpy.run_path(str(Path(scripts) / "vault_append.py"), run_name="__main__")
"""


def test_la_tool_responde_note_locked_y_no_ok_true(tmp_path):
    """Lo que ve el consumidor: `vault_append` real, por `wrap_main`."""
    import os
    import subprocess

    from vault.kernel.errores import problemas_de_forma

    raiz = tmp_path / "vault"
    (raiz / "07_Knowledge").mkdir(parents=True)
    nota = raiz / "07_Knowledge" / "log.md"
    original = "---\ntitle: log\nstatus: draft\n---\n# log\n"
    nota.write_text(original, encoding="utf-8")
    p = subprocess.run(
        [sys.executable, "-c", SONDA, str(REPO_ROOT / "scripts"), str(REPO_ROOT)],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(REPO_ROOT / "scripts"), timeout=120,
    )
    env = json.loads(p.stdout[p.stdout.index("{"):])
    assert env["ok"] is False and env["error_code"] == "NOTE_LOCKED", env
    assert env.get("causa") == "LOCK_PERDIDO", env
    assert problemas_de_forma(env) == [], env
    assert nota.read_text(encoding="utf-8") == original


def test_el_consumidor_recibe_note_locked():
    assert "LOCK_PERDIDO" in CAUSAS
    assert MAPA_DE_FALLOS["LOCK_PERDIDO"] == "NOTE_LOCKED"
    codigo, _, campos = traducir_fallo(bloqueo.LockPerdido(Path("x/nota.md")))
    assert codigo == "NOTE_LOCKED" and campos["causa"] == "LOCK_PERDIDO"

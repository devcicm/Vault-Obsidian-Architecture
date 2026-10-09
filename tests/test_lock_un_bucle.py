"""AP-57 — el lock de una nota se adquiere con un solo bucle.

Medido en v41.2: `vault_fs.file_lock` y `_FileLock` de `vault.autoria.conocimiento`
compartían la ruta y el alta de `.locks/` (`vault.kernel.bloqueo`), pero cada uno
tenía su bucle de adquisición. El de `_FileLock` no recuperaba un lock huérfano
—el de un proceso que murió dentro— ni escribía `owner.json`: tras un corte,
`vault_knowledge_save` esperaba su timeout de 30 s y fallaba para siempre sobre
esa nota, mientras `vault_write` sobre la misma nota la recuperaba a los 120 s.
El bucle vive ahora en `vault.kernel.bloqueo.adquirir`, y los dos delegan.
"""

import ast
import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_fs  # noqa: E402
from vault.autoria.conocimiento import _FileLock  # noqa: E402
from vault.kernel.bloqueo import rutas_de_lock  # noqa: E402


def _huerfano(nota: Path, con_owner: bool) -> Path:
    """Un lock que dejó un proceso muerto hace una hora."""
    raiz, lock = rutas_de_lock(nota)
    lock.mkdir(parents=True)
    viejo = time.time() - 3600
    if con_owner:
        (lock / "owner.json").write_text(
            json.dumps({"pid": 999999, "createdAt": viejo, "token": "muerto"}),
            encoding="utf-8")
    os.utime(lock, (viejo, viejo))
    return lock


def _con_fs(nota):
    return vault_fs.file_lock(nota, timeout=2.0)


def _con_conocimiento(nota):
    return _FileLock(nota, timeout=2.0)


@pytest.mark.parametrize("tomar", [_con_fs, _con_conocimiento], ids=["vault_fs", "conocimiento"])
@pytest.mark.parametrize("con_owner", [True, False], ids=["owner-viejo", "sin-owner"])
def test_ap57_un_lock_huerfano_se_recupera_por_las_dos_vias(tmp_path, tomar, con_owner):
    nota = tmp_path / "jwt.md"
    lock = _huerfano(nota, con_owner)
    with tomar(nota):
        dueno = json.loads((lock / "owner.json").read_text(encoding="utf-8"))
        assert dueno["token"] != "muerto"
    assert not lock.exists()


def test_conocimiento_no_suelta_un_lock_que_ya_no_es_suyo(tmp_path):
    """Si se lo robaron por caducado, soltar no le quita el lock al ladrón."""
    nota = tmp_path / "jwt.md"
    lock = rutas_de_lock(nota)[1]
    tomado = _FileLock(nota, timeout=2.0)
    tomado.acquire()
    (lock / "owner.json").write_text(json.dumps({"token": "ladron"}), encoding="utf-8")
    tomado.release()
    assert lock.is_dir()


def test_ap57_ningun_tomador_tiene_su_propio_bucle():
    """El `os.mkdir` del lock solo lo llama el kernel."""
    for fichero in (SCRIPTS / "vault_fs.py", ROOT / "vault" / "autoria" / "conocimiento.py"):
        arbol = ast.parse(fichero.read_text(encoding="utf-8"))
        llamadas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute) and n.func.attr == "mkdir"
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == "os"]
        assert llamadas == [], fichero.name

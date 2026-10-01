"""CIA-A/F1 — `vault_undo --force` se puede deshacer y no pisa a otro escritor.

Medido en v40.34: `--restore <nota> --force` sobrescribía la nota con la
versión de `.history/` sin guardar antes la actual. La versión que se tapaba
—la más reciente, normalmente la buena— no quedaba en ninguna parte: un undo
equivocado era irreversible, justo en la tool cuyo contrato es deshacer.
Además escribía sin el lock de la nota, así que un `vault_append` concurrente
se perdía con los dos envelopes en `ok: true`.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.kernel.errores import problemas_de_forma  # noqa: E402


def _undo(raiz: Path, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_undo.py"), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="system"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=120,
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for d in ("00_System", "07_Knowledge", "99_Index", ".history"):
        (raiz / d).mkdir(parents=True)
    (raiz / "07_Knowledge" / "nota.md").write_text("actual\n", encoding="utf-8")
    viejo = raiz / ".history" / "07_Knowledge__nota-2026-09-01T00-00-00.md"
    viejo.write_text("anterior\n", encoding="utf-8")
    os.utime(viejo, (time.time() - 3600, time.time() - 3600))
    return raiz


def test_force_guarda_la_version_actual_y_se_puede_deshacer(vault):
    nota = vault / "07_Knowledge" / "nota.md"
    r = _undo(vault, "--restore", "07_Knowledge/nota.md", "--force")
    assert r["ok"], r
    assert nota.read_text(encoding="utf-8") == "anterior\n"
    guardada = vault / ".history" / r["previous_saved_as"]
    assert guardada.read_text(encoding="utf-8") == "actual\n"

    # El undo del undo: la versión más reciente del historial es la tapada.
    r2 = _undo(vault, "--restore", "07_Knowledge/nota.md", "--force")
    assert r2["ok"] and r2["restored_from"] == r["previous_saved_as"], r2
    assert nota.read_text(encoding="utf-8") == "actual\n"


def test_force_con_la_nota_tomada_no_escribe_y_lo_dice(vault):
    nota = vault / "07_Knowledge" / "nota.md"
    lock_dir = nota.parent / ".locks" / f"{nota.name}.lock"
    lock_dir.mkdir(parents=True)
    (lock_dir / "owner.json").write_text(
        json.dumps({"pid": 0, "createdAt": time.time(), "token": "otro"}), encoding="utf-8")
    historial = sorted(p.name for p in (vault / ".history").iterdir())

    r = _undo(vault, "--restore", "07_Knowledge/nota.md", "--force")
    assert r["ok"] is False and r["error_code"] == "NOTE_LOCKED", r
    assert problemas_de_forma(r) == [], r
    assert nota.read_text(encoding="utf-8") == "actual\n"
    assert sorted(p.name for p in (vault / ".history").iterdir()) == historial

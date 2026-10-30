"""D-03 -- un cambio de estado de un requisito deja una fila `transition` y un evento."""
import json
import os
import subprocess
import sys
from pathlib import Path

from vault_base import copiar_vault

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vault_requirement_save.py"


def _run(raiz, *argv):
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    p = subprocess.run([sys.executable, str(SCRIPT), *argv], env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=str(raiz.parent), timeout=300)
    return p.returncode, json.loads(p.stdout[p.stdout.index("{"):])


def _guardar(raiz, estado):
    return _run(raiz, "--project", "demo", "--title", "Login seguro", "--type", "functional",
                "--priority", "must-have", "--description", "Descripcion suficiente del requisito.",
                "--status", estado)


def test_cada_cambio_de_estado_deja_fila_y_evento(tmp_path):
    raiz = copiar_vault(tmp_path / "vault", "demo")
    assert _guardar(raiz, "draft")[1]["transition_logged"] is True
    assert _guardar(raiz, "approved")[1]["transition_logged"] is True
    # Mismo estado y mismo cuerpo: ni evento ni fila.
    assert _guardar(raiz, "approved")[1]["transition_logged"] is False

    indice = json.loads(next(raiz.rglob(".requirements-index.json")).read_text(encoding="utf-8"))
    ev = indice["requirements"][0]["events"]
    assert [(e["from"], e["to"]) for e in ev] == [(None, "draft"), ("draft", "approved")]

    log = json.loads((raiz / "00_System" / ".change-log.json").read_text(encoding="utf-8"))
    filas = [e for e in log if e["action"] == "transition"]
    assert [e["reason"] for e in filas] == ["REQ-001: (nuevo) -> draft", "REQ-001: draft -> approved"]

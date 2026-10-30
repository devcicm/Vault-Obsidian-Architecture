"""D-06 -- la identidad de un requisito es su REQ-NNN, y el contador no retrocede."""
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


def _guardar(raiz, titulo, *extra):
    return _run(raiz, "--project", "demo", "--title", titulo, "--type", "functional",
                "--priority", "must-have", "--description", "Descripcion suficiente del requisito.", *extra)


def test_renombrar_con_req_id_no_bifurca_el_objetivo(tmp_path):
    raiz = copiar_vault(tmp_path / "vault", "demo")
    rid = _guardar(raiz, "Login seguro")[1]["req_id"]
    rc, r = _guardar(raiz, "Autenticacion obligatoria", "--req-id", rid)
    assert rc == 0 and r["req_id"] == rid and r["action"] == "updated", r
    filas = _run(raiz, "--list", "--project", "demo")[1]["requirements"]
    assert [f["req_id"] for f in filas] == [rid] and filas[0]["title"] == "Autenticacion obligatoria"


def test_req_id_inexistente_no_crea(tmp_path):
    raiz = copiar_vault(tmp_path / "vault", "demo")
    rc, r = _guardar(raiz, "Algo", "--req-id", "REQ-099")
    assert rc == 1 and r["ok"] is False
    assert _run(raiz, "--list")[1]["count"] == 0


def test_el_contador_no_reusa_el_id_de_una_entrada_podada(tmp_path):
    raiz = copiar_vault(tmp_path / "vault", "demo")
    assert _guardar(raiz, "Primero")[1]["req_id"] == "REQ-001"
    assert _guardar(raiz, "Segundo")[1]["req_id"] == "REQ-002"
    indice = next(raiz.rglob(".requirements-index.json"))
    datos = json.loads(indice.read_text(encoding="utf-8"))
    datos["requirements"] = [r for r in datos["requirements"] if r["req_id"] != "REQ-002"]
    indice.write_text(json.dumps(datos), encoding="utf-8")
    assert _guardar(raiz, "Tercero")[1]["req_id"] == "REQ-003"

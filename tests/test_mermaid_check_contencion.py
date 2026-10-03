"""vault_mermaid_check --path no lee fuera del vault (AP-36).

Medido 2026-10-02: el catálogo declara `within_vault` sobre `--path`, pero la
CLI hacía `raiz / args.path` sin comprobar nada. `--path ../fuera.md` o una
ruta absoluta leían cualquier fichero del disco y devolvían su ruta absoluta y
los mensajes del validador sobre su contenido.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "vault_mermaid_check.py"
DIAGRAMA = "---\ntitle: d\n---\n```mermaid\nflowchart TD\n  A --> B\n```\n"


def _run(tmp_path, ruta):
    vault = tmp_path / "v"
    (vault / "00_System").mkdir(parents=True)
    (vault / "06_Diagrams").mkdir()
    (vault / "06_Diagrams" / "d.md").write_text(DIAGRAMA, encoding="utf-8")
    (tmp_path / "fuera.md").write_text(DIAGRAMA, encoding="utf-8")
    env = dict(os.environ, VAULT_ROOT=str(vault), PYTHONIOENCODING="utf-8")
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--path", ruta, "--json"],
        env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=str(tmp_path), timeout=60,
    )
    out = p.stdout
    return json.loads(out[out.index("{"):])


def test_ap36_mermaid_check_rechaza_ruta_relativa_de_fuera(tmp_path):
    r = _run(tmp_path, "../fuera.md")
    assert r.get("ok") is False and r["error_code"] == "INVALID_PATH"
    assert "blocks" not in r


def test_ap36_mermaid_check_rechaza_ruta_absoluta(tmp_path):
    r = _run(tmp_path, str(tmp_path / "fuera.md"))
    assert r.get("ok") is False and r["error_code"] == "INVALID_PATH"


def test_mermaid_check_dentro_del_vault_sigue_leyendo(tmp_path):
    r = _run(tmp_path, "06_Diagrams/d.md")
    assert r["valid"] is True and len(r["blocks"]) == 1

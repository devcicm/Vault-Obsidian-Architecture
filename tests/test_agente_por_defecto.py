"""AP-16 — quien firma una operación es `--agent`, y si falta, `VAULT_AGENT`.

Medido como consumidor el 2026-10-10 con `VAULT_AGENT=agente-consumidor`: las
notas de `vault_write` salían firmadas por él, pero el change-log de
`vault_delete` y `vault_undo` registraba `claude`, el `default` escrito a mano
en su argparse. Trece tools repetían ese literal: el registro de entorno ya
declaraba `VAULT_AGENT` como «quién firma cuando no se pasa `--agent`» y ellas
no lo leían (AP-57). El default tiene un dueño, `entorno.agente_por_defecto`.
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _defaults_literales_de_agent():
    sitios = []
    for raiz in (SCRIPTS, ROOT / "vault", ROOT / "cli"):
        for ruta in raiz.rglob("*.py"):
            if "_archived" in ruta.parts:
                continue
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if not (isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "add_argument"):
                    continue
                if not any(isinstance(a, ast.Constant) and a.value == "--agent" for a in nodo.args):
                    continue
                for kw in nodo.keywords:
                    if kw.arg == "default" and isinstance(kw.value, ast.Constant) and kw.value.value:
                        sitios.append(f"{ruta.relative_to(ROOT).as_posix()}:{nodo.lineno}")
    return sitios


def test_ningun_agent_tiene_un_default_escrito_a_mano():
    # AP-16 / AP-57: el default sale de `agente_por_defecto`, no de un literal.
    assert _defaults_literales_de_agent() == []


def test_delete_firma_el_change_log_con_vault_agent(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge").mkdir()
    (raiz / "07_Knowledge" / "n.md").write_text(
        "---\ntitle: n\nstatus: draft\ntype: knowledge\n---\n# n\n", encoding="utf-8")
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="agente-consumidor")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_delete.py"), "--path",
                        "07_Knowledge/n.md", "--reason", "prueba"],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    assert '"ok": true' in p.stdout, p.stdout + p.stderr
    log = json.loads((raiz / "00_System" / ".change-log.json").read_text(encoding="utf-8"))
    entradas = log if isinstance(log, list) else log.get("entries", [])
    assert [e.get("agent") for e in entradas] == ["agente-consumidor"], entradas


def test_sin_vault_agent_se_conserva_el_default_historico(monkeypatch):
    # No-derogación: sin `--agent` ni `VAULT_AGENT` sigue firmando `claude`.
    sys.path.insert(0, str(ROOT))
    from vault.kernel import entorno

    monkeypatch.delenv("VAULT_AGENT", raising=False)
    assert entorno.agente_por_defecto() == "claude"
    monkeypatch.setenv("VAULT_AGENT", "otro")
    assert entorno.agente_por_defecto() == "otro"

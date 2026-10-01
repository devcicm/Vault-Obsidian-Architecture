"""AP-52 — todo envelope de error sale en forma por la frontera de `wrap_main`.

Medido en v40.34: 82 sitios en 30 tools devolvían `{"ok": False,
"error_code": …, "error": …}` construido a mano, sin `category`, `severity`,
`recovery` ni `timestamp`. El servidor MCP y `cli/` deciden por
`recovery.action` y con esos envelopes no tenían por dónde. Convertir los 82
`return` uno a uno era la forma de que el 83 naciera igual: se canoniza en
`_inject_tool_envelope`, la salida por la que ya pasan todas, igual que allí
se completan los éxitos.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from vault.kernel.errores import ERROR_CATALOG, problemas_de_forma  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for s in ("00_System", "07_Knowledge", "17_Preferences"):
        (raiz / s).mkdir(parents=True)
    return raiz


def _corre(vault, tool, *argv):
    p = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / f"{tool}.py"), *argv],
        env=dict(os.environ, VAULT_ROOT=str(vault), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="system"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(RAIZ / "scripts"), timeout=180,
    )
    return json.loads(p.stdout[p.stdout.index("{"):])


@pytest.mark.parametrize("tool,argv,codigo", [
    ("vault_read", ["--path", "../fuera.md"], "INVALID_PATH"),
    ("vault_append", ["--path", "../fuera.md", "--content", "hola"], "INVALID_PATH"),
    ("vault_preferences", ["--set", "--category", "no-existe", "--title", "T",
                           "--statement", "algo"], "INVALID_CATEGORY"),
    ("vault_preferences", ["--revoke", "17_Preferences/no-existe.md",
                           "--reason", "ya no"], "PREFERENCE_NOT_FOUND"),
])
def test_el_error_hecho_a_mano_sale_en_forma(vault, tool, argv, codigo):
    env = _corre(vault, tool, *argv)
    assert env["error_code"] == codigo, env
    assert problemas_de_forma(env) == [], env
    assert env["tool"] == tool
    assert env["recovery"]["action"] == ERROR_CATALOG[codigo]["recovery"]["action"]
    # Lo propio del sitio no se pierde: el texto concreto del fallo sigue ahí.
    assert env["error"] and env["message"]


def test_la_frontera_canoniza_y_no_toca_lo_que_no_es_un_error():
    from vault_errors import _inject_tool_envelope

    salida = json.loads(_inject_tool_envelope(
        json.dumps({"ok": False, "error_code": "INVALID_PATH", "error": "fuera"}),
        "vault_x"))
    assert problemas_de_forma(salida) == []
    assert salida["message"] == "fuera"

    # Un informe con `ok: false` sin código no es un error que canonizar:
    # inventarle uno es lo que AP-52 persigue.
    informe = json.loads(_inject_tool_envelope(
        json.dumps({"ok": False, "stale": True}), "vault_x"))
    assert "error_code" not in informe and "recovery" not in informe


def test_un_error_ya_canonico_no_se_rehace_ni_se_registra_dos_veces(monkeypatch):
    import vault_errors

    canonico = vault_errors.construir_error("vault_x", "INVALID_PATH", "fuera")
    registros = []
    monkeypatch.setattr(vault_errors, "log_trace", registros.append)
    salida = json.loads(vault_errors._inject_tool_envelope(json.dumps(canonico), "vault_x"))
    assert salida["timestamp"] == canonico["timestamp"]
    assert registros == []

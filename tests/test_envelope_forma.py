"""D5 — los envelopes de error de las tools de escritura cumplen `ErrorEnvelope`.

Medido en v40.34: `vault_write` (content_too_short, missing_tags, …) y
`vault_ingest` (NO_SOURCE, NETWORK_DISABLED, SOURCE_NOT_FOUND, …) devolvían
`{"ok": False, "error_code": …, "error": …}` sin `tool`, `category`,
`severity`, `recovery` ni `timestamp`. El servidor MCP y `cli/` deciden por
`recovery.action`: con esos envelopes no tenían por dónde decidir (AP-52).
Se mide sobre la salida real del proceso, no sobre la función (AP-44).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from vault.kernel.errores import (  # noqa: E402
    ERROR_CATALOG, completar_envelope, problemas_de_forma,
)

CUERPO_LARGO = "palabra " * 80


def _vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    for s in ("00_System", "01_Projects", "07_Knowledge", "99_Index"):
        (raiz / s).mkdir(parents=True)
    return raiz


def _correr(raiz: Path, tool: str, *argv: str) -> dict:
    entorno = dict(os.environ, VAULT_ROOT=str(raiz), PYTHONIOENCODING="utf-8",
                   VAULT_AGENT="pytest")
    p = subprocess.run([sys.executable, str(RAIZ / "scripts" / f"{tool}.py"), *argv],
                       env=entorno, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(RAIZ / "scripts"), timeout=180)
    salida = p.stdout.strip()
    assert salida, p.stderr
    return json.loads(salida[salida.index("{"):])


CASOS = [
    ("vault_write", ["--folder", "07_Knowledge", "--title", "x", "--content", "corto", "--tags", "a"]),
    ("vault_write", ["--folder", "07_Knowledge", "--title", "x", "--content", CUERPO_LARGO]),
    ("vault_ingest", ["--text", "   ", "--section", "07_Knowledge"]),
    ("vault_ingest", ["--url", "http://example.com", "--section", "07_Knowledge"]),
    ("vault_ingest", ["--file", "no-existe.txt", "--section", "07_Knowledge"]),
    ("vault_ingest", ["--text", CUERPO_LARGO, "--section", "99_Index"]),
]


@pytest.mark.parametrize("tool,argv", CASOS, ids=[f"{t}-{i}" for i, (t, _) in enumerate(CASOS)])
def test_ap52_el_envelope_real_cumple_el_dto(tmp_path, tool, argv):
    env = _correr(_vault(tmp_path), tool, *argv)
    assert env["ok"] is False, env
    assert problemas_de_forma(env) == [], env
    assert env["tool"] == tool


def test_completar_conserva_lo_propio_y_no_pisa_lo_canonico():
    hecho_a_mano = {
        "ok": False, "error_code": "content_too_short", "error": "content_too_short",
        "norm_code": "AP-11", "message": "AP-11: demasiado corto",
        "category": "inventada", "tool": "otra",
    }
    env = completar_envelope("vault_write", hecho_a_mano)
    assert problemas_de_forma(env) == []
    assert env["norm_code"] == "AP-11" and env["error"] == "content_too_short"
    assert env["message"] == "AP-11: demasiado corto"
    assert env["category"] == ERROR_CATALOG["content_too_short"]["category"]
    assert env["tool"] == "vault_write"


def test_una_recuperacion_especifica_pasa_a_hint():
    env = completar_envelope("vault_ingest", {
        "ok": False, "error_code": "SOURCE_TOO_LARGE", "error": "grande",
        "recovery": "sube el tope con --max-chars",
    })
    assert problemas_de_forma(env) == []
    assert env["recovery"]["hint"] == "sube el tope con --max-chars"
    assert env["recovery"]["action"] == ERROR_CATALOG["SOURCE_TOO_LARGE"]["recovery"]["action"]
    assert env["message"] == "grande"


def test_un_exito_no_se_toca():
    ok = {"ok": True, "written": 1}
    assert completar_envelope("vault_write", ok) is ok

"""Vertical slice real: parseo instalado sin el checkout ni ``scripts/``."""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from vault.consulta.query_parse import vault_query_parse


ROOT = Path(__file__).resolve().parent.parent


def test_el_parser_estable_conserva_el_resultado_caracterizado():
    result = vault_query_parse(
        "que decidimos sobre el transporte MCP",
        now=datetime(2026, 1, 2, tzinfo=timezone.utc),
        available_sections=["03_Decisions", "07_Knowledge"],
    )
    assert result["ok"] is True
    assert result["structured"]["intent"] == "decision"
    assert result["structured"]["sections"] == ["03_Decisions"]
    assert result["plan"][0]["tool"] == "vault_search"


def test_el_modulo_estable_no_importa_el_adaptador_legacy():
    source = ROOT / "vault" / "consulta" / "query_parse.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any(name == "scripts" or name.startswith("scripts.") for name in imports)
    assert "sys.path" not in source.read_text(encoding="utf-8")


def test_el_modulo_estable_ejecuta_desde_una_copia_sin_checkout(tmp_path):
    """La implementación viaja sola: no necesita scripts ni la raíz fuente."""
    shutil.copytree(ROOT / "vault", tmp_path / "vault")
    env = {key: value for key, value in os.environ.items() if key.upper() != "PYTHONPATH"}
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vault.consulta.query_parse",
            "--query",
            "que decidimos sobre el transporte MCP",
            "--plan-only",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["plan"][0]["tool"] == "vault_search"

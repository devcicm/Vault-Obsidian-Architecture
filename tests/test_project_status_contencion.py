"""`vault_project_status`: el proyecto es un nombre, no una ruta ni YAML crudo.

Medido el 2026-10-01 en un vault del scratchpad, con el criterio del
consumidor (en otro proceso, como lo llama la CLI o el MCP).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _ejecutar(vault: Path, *args: str) -> dict:
    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_project_status.py"), *args],
        env=dict(os.environ, VAULT_ROOT=str(vault), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", cwd=str(vault.parent),
        timeout=120)
    salida = p.stdout + p.stderr
    return json.loads(salida[salida.index("{"):])


def _runtime(tmp_path: Path) -> Path:
    from vault.ciclo_de_vida import producto

    vault = tmp_path / "vault"
    assert producto.inicializar_runtime(vault)["ok"]
    return vault


def test_ap36_un_proyecto_con_traversal_no_crea_nada_fuera_del_vault(tmp_path):
    """`--project ../../fuera` lo rechazaba la escritura atómica, pero el
    `mkdir` previo ya había creado `fuera/` junto al vault: un side effect
    fuera de él (AP-36) en la rama que se declaraba fallida."""
    vault = _runtime(tmp_path)
    env = _ejecutar(vault, "--project", "../../fuera", "--status", "en_desarrollo",
                    "--summary", "prueba")
    assert env["ok"] is False
    assert env["error_code"] == "INVALID_PATH", env
    assert not (tmp_path / "fuera").exists(), "creó un directorio fuera del vault"

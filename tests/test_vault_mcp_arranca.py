"""vault_mcp.py arranca en todo Python que pyproject promete (AP-51).

Medido 2026-10-02 en 3.14: el subparser `folders` estaba declarado dos veces y
argparse, desde 3.11, lo rechaza al construir el parser. Toda orden —list,
show, validate, exec— salía como UNEXPECTED_ERROR «conflicting subparser»
antes de mirar su argumento, y el script viaja en la wheel.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _correr(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_mcp.py"), *args],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
    )


def test_ap51_vault_mcp_construye_su_parser():
    r = _correr("--help")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "conflicting subparser" not in r.stdout + r.stderr


def test_ap51_vault_mcp_show_responde():
    r = _correr("show", "vault_read")
    datos = json.loads(r.stdout)
    assert datos["ok"] is True and datos["name"] == "vault_read"

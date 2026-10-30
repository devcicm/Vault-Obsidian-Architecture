"""A-11 — limite declarado: `escritura_admitida` admite toda raiz EXPLICITA.

Es diseno (``--root``/``VAULT_ROOT`` a un vault real no paga por la
autodetección) pero tambien admite apuntar al propio repo del estandar, que la
regla 1 de AGENTS.md prohibe. Hoy ninguna puerta lo impide: una tool de solo
lectura corre con ``VAULT_ROOT=<repo>``. Este test fija el hueco y falla el dia
que se cierre, para que `vault_blueprint.DEUDA_DECLARADA` pase a `saldada`.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_limite_declarado_raiz_explicita_en_el_repo_no_se_rechaza():
    env = dict(os.environ, VAULT_ROOT=str(ROOT), PYTHONIOENCODING="utf-8")
    env.pop("VAULT_PERMISSIVE_ROOT", None)
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "vault_audit.py")],
                       env=env, capture_output=True, text=True, encoding="utf-8",
                       cwd=str(ROOT), timeout=120)
    salida = p.stdout.strip()
    assert salida, p.stderr[-500:]
    r = json.loads(salida[salida.index("{"):])
    assert r.get("error_code") != "VAULT_NOT_FOUND", "ya se rechaza: salda la deuda A-11"

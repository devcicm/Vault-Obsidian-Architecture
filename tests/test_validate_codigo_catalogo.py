"""AP-52 — `vault_validate` con problemas lleva su código del catálogo.

Medido en la comparativa v34/v40 (2026-10-01): con notas inválidas la tool
devolvía `ok: false` sin `error_code`, y el consumidor que decide por
`recovery.action` no tenía por dónde leerlo. El detalle de la medida
(`invalid`, `structure`, `indexes`) se conserva entero: es un campo estable
del contrato con los repos consumidores.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.kernel.errores import ERROR_CATALOG  # noqa: E402


def _validate(raiz: Path, *argv: str):
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_validate.py"), *argv],
        env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=str(SCRIPTS))
    salida = p.stdout.strip()
    assert salida, p.stderr
    return p.returncode, json.loads(salida[salida.index("{"):])


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / seccion).mkdir(parents=True)
    return raiz


def test_ap52_validacion_con_notas_invalidas_lleva_codigo(vault):
    (vault / "07_Knowledge" / "rota.md").write_text(
        "---\ntitle: [sin cerrar\n---\n\ncuerpo\n", encoding="utf-8")
    rc, r = _validate(vault, "--folder", "07_Knowledge", "--check", "frontmatter")
    assert rc == 1
    assert r["ok"] is False
    assert r["error_code"] == "VALIDATION_FAILED", r
    assert r["invalid"], "el detalle de la medida tiene que seguir ahí"
    assert r["recovery"]["action"] == ERROR_CATALOG["VALIDATION_FAILED"]["recovery"]["action"]
    assert "1 nota(s)" in r["message"]


def test_ap52_validacion_limpia_no_inventa_codigo(vault):
    (vault / "07_Knowledge" / "buena.md").write_text(
        "---\nid: buena\ntitle: Buena\ncreatedAt: 2026-10-01T00:00:00Z\n"
        "updatedAt: 2026-10-01T00:00:00Z\ncia_integrity: medium\n"
        "cia_availability: medium\ncia_sensitivity: internal\nagent: test\n"
        "tags: [demo]\n---\n\ncuerpo\n", encoding="utf-8")
    rc, r = _validate(vault, "--folder", "07_Knowledge", "--check", "frontmatter")
    assert rc == 0 and r["ok"] is True, r
    assert "error_code" not in r and "recovery" not in r

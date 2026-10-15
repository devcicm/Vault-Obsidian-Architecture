"""AP-36/F1 — `vault_propagate --clear` no escribe fuera del vault ni pisa a otro escritor.

Medido en v40.34: `--clear ../canario.md` reescribió un fichero de FUERA del
vault y devolvió `ok: true`. La tool unía la ruta del agente a la raíz sin
contenerla y escribía con `Path.write_text` en crudo, que se salta el guard de
`atomic_write_text` —el que paró el mismo intento en `vault_runbook_log` y
`vault_norms --apply`—. Tampoco tomaba el lock de la nota: reescribía entera
una lectura que un `vault_append` concurrente ya había dejado vieja.
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

from vault.kernel.errores import problemas_de_forma  # noqa: E402
from vault.kernel import bloqueo  # noqa: E402

PENDIENTE = "---\ntitle: n\npropagation_pending: \"2026-09-01\"\n---\n# n\n"


def _propagar(raiz: Path, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_propagate.py"), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=120,
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.fixture
def entorno(tmp_path):
    raiz = tmp_path / "vault"
    for d in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / d).mkdir(parents=True)
    (raiz / "07_Knowledge" / "n.md").write_text(PENDIENTE, encoding="utf-8")
    canario = tmp_path / "canario.md"
    canario.write_text(PENDIENTE, encoding="utf-8")
    return raiz, canario


@pytest.mark.parametrize("ruta", ["../canario.md", "07_Knowledge/../../canario.md"])
def test_clear_fuera_del_vault_no_escribe(entorno, ruta):
    raiz, canario = entorno
    r = _propagar(raiz, "--clear", ruta)
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH", r
    assert problemas_de_forma(r) == [], r
    assert canario.read_text(encoding="utf-8") == PENDIENTE


def test_clear_con_la_nota_tomada_no_escribe_y_lo_dice(entorno):
    raiz, _ = entorno
    nota = raiz / "07_Knowledge" / "n.md"
    ocupado = nota.parent / ".locks" / f"{nota.name}.lock"
    ocupado.mkdir(parents=True)
    (ocupado / "owner.json").write_text(
        json.dumps(bloqueo.ficha_del_dueno("otro")), encoding="utf-8")
    r = _propagar(raiz, "--clear", "07_Knowledge/n.md")
    assert r["ok"] is False and r["error_code"] == "NOTE_LOCKED", r
    assert problemas_de_forma(r) == [], r
    assert nota.read_text(encoding="utf-8") == PENDIENTE


def test_clear_legitimo_quita_el_campo(entorno):
    raiz, _ = entorno
    r = _propagar(raiz, "--clear", "07_Knowledge/n.md")
    assert r["ok"] and r["cleared_frontmatter"], r
    texto = (raiz / "07_Knowledge" / "n.md").read_text(encoding="utf-8")
    assert "propagation_pending" not in texto and texto.endswith("# n\n")

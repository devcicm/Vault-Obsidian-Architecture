"""AP-36 — `vault_diagram_export` no lee ni escribe fuera del vault.

Medido en v40.34: `--output` se tomaba con `Path(args.output)` —relativo al
CWD del proceso o absoluto— y se escribía con `Path.write_text` en crudo. Por
MCP el parámetro `output` era una escritura arbitraria en el disco de quien
instala esto: pisaba el fichero que se le nombrase con `ok: true`. `--path` se
unía a la raíz sin contenerse y leía los bloques mermaid de cualquier fichero.
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

NOTA = "---\ntitle: d\n---\n# d\n\n```mermaid\ngraph TD\nA-->B\n```\n"


def _exportar(raiz: Path, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_diagram_export.py"), *argv, "--json"],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        # CWD hermano del vault: si una regresión vuelve a resolver `--output`
        # contra el CWD, `../canario.md` cae sobre el canario y no en el repo
        # (contra el código de v40.34, con cwd=scripts/, lo escribió en la raíz).
        cwd=str(raiz.parent / "cwd"), timeout=120,
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.fixture
def entorno(tmp_path):
    raiz = tmp_path / "vault"
    (tmp_path / "cwd").mkdir()
    # `01_Projects/p` registra el proyecto `p` (AP-63): sin él, `--project p`
    # no llegaría a la tool y el rechazo de `--output` no se mediría.
    for d in ("00_System", "06_Diagrams", "99_Index", "01_Projects/p"):
        (raiz / d).mkdir(parents=True)
    (raiz / "06_Diagrams" / "d.md").write_text(NOTA, encoding="utf-8")
    canario = tmp_path / "canario.md"
    canario.write_text("no tocar\n", encoding="utf-8")
    ajeno = tmp_path / "ajeno.md"
    ajeno.write_text("```mermaid\ngraph TD\nSECRETO-->X\n```\n", encoding="utf-8")
    return raiz, canario, ajeno


@pytest.mark.parametrize("salida", ["../canario.md", "ABS"])
def test_output_fuera_del_vault_no_escribe(entorno, salida):
    raiz, canario, _ = entorno
    destino = str(canario) if salida == "ABS" else salida
    r = _exportar(raiz, "--path", "06_Diagrams/d.md", "--output", destino)
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH", r
    assert problemas_de_forma(r) == [], r
    assert canario.read_text(encoding="utf-8") == "no tocar\n"


def test_output_de_proyecto_fuera_del_vault_no_escribe(entorno, tmp_path):
    raiz, _, _ = entorno
    r = _exportar(raiz, "--project", "p", "--output", "../fuera")
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH", r
    assert not (tmp_path / "fuera").exists()


def test_path_fuera_del_vault_no_se_lee(entorno):
    raiz, _, _ = entorno
    r = _exportar(raiz, "--path", "../ajeno.md")
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH", r
    assert "SECRETO" not in json.dumps(r)


def test_output_dentro_del_vault_escribe_y_devuelve_ruta_relativa(entorno):
    raiz, _, _ = entorno
    r = _exportar(raiz, "--path", "06_Diagrams/d.md", "--output", "06_Diagrams/export/d.mmd")
    assert r["ok"], r
    assert (raiz / "06_Diagrams" / "export" / "d.mmd").read_text(encoding="utf-8").startswith("```mermaid")
    assert r["output"] == "06_Diagrams/export/d.mmd", r


def test_no_exporta_los_diagramas_de_una_instantanea(entorno):
    """`.trash/` y `vault-backups/` son instantáneas, como `.history` (vault_io).

    Auditoría del 2026-10-15: el filtro era `".history" in str(md)`, así que una
    nota tirada a `.trash/` dentro del proyecto seguía exportando sus diagramas.
    """
    raiz, _, _ = entorno
    proyecto = raiz / "01_Projects" / "p"
    (proyecto / "vivo.md").write_text(NOTA, encoding="utf-8")
    (proyecto / ".trash").mkdir()
    (proyecto / ".trash" / "tirada.md").write_text(NOTA, encoding="utf-8")
    r = _exportar(raiz, "--project", "p", "--output", "salida")
    assert r["ok"] is True, r
    assert r["files"] == ["salida/vivo-0.mmd"], r

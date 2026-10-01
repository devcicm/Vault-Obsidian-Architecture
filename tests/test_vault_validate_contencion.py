"""AP-36 — `vault_validate` no mide ficheros fuera del vault.

Medido antes del arreglo: `--path "../x.md"` validaba un fichero ajeno y
`--folder ..` recorría el disco fuera del vault. No devolvía el contenido,
pero sí que el fichero existe y qué campos del frontmatter le faltan, por MCP
y con la misma ruta que `vault_read` ya rechazaba.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _ejecutar(raiz: Path, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_validate.py"), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.fixture
def entorno(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "07_Knowledge").mkdir(parents=True)
    (raiz / "07_Knowledge" / "nota.md").write_text("# nota\n", encoding="utf-8")
    fuera = tmp_path / "fuera.md"
    fuera.write_text("---\ntitle: fuera\n---\nsecreto\n", encoding="utf-8")
    return raiz, fuera


@pytest.mark.parametrize("argv", [
    ["--path", "../fuera.md"],
    ["--folder", ".."],
])
def test_una_ruta_con_punto_punto_es_invalid_path(entorno, argv):
    raiz, _ = entorno
    r = _ejecutar(raiz, *argv, "--check", "frontmatter")
    assert not r["ok"] and r["error_code"] == "INVALID_PATH", r
    assert "fuera.md" not in json.dumps(r.get("invalid", []))


def test_una_ruta_absoluta_es_invalid_path(entorno):
    raiz, fuera = entorno
    r = _ejecutar(raiz, "--path", str(fuera), "--check", "frontmatter")
    assert not r["ok"] and r["error_code"] == "INVALID_PATH", r


def test_una_carpeta_del_vault_se_sigue_validando(entorno):
    raiz, _ = entorno
    r = _ejecutar(raiz, "--folder", "07_Knowledge", "--check", "frontmatter")
    # Desde 2026-10-01 una medida con notas inválidas lleva VALIDATION_FAILED
    # (AP-52); lo que este test protege es que la carpeta no se rechace.
    assert r.get("error_code") in (None, "VALIDATION_FAILED"), r
    assert len(r["invalid"]) == 1  # la nota sin frontmatter


def test_folder_publica_las_rutas_con_barra_en_todas_las_plataformas(entorno):
    """`--path` devolvía `07_Knowledge/x.md` y `--folder`, en Windows,
    la misma ruta con barra invertida: la misma nota con dos claves distintas según cómo se
    pidiera, y una ruta que ninguna otra tool del vault acepta de vuelta."""
    raiz, _ = entorno
    sub = raiz / "07_Knowledge" / "sub"
    sub.mkdir()
    (sub / "otra.md").write_text("# otra\n", encoding="utf-8")
    r = _ejecutar(raiz, "--folder", "07_Knowledge", "--check", "frontmatter")
    rutas = sorted(x["path"] for x in r["invalid"])
    assert rutas == ["07_Knowledge/nota.md", "07_Knowledge/sub/otra.md"], r

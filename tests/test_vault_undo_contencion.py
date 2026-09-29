"""AP-36 — `vault_undo` no resuelve rutas fuera del vault.

Medido antes del arreglo: `--list <ruta absoluta>` terminaba en
`UNEXPECTED_ERROR` con severidad `critical`, y `--restore "../x.md" --force`
buscaba en `.history/` una nota que no es del vault antes de sobrescribirla.
Hoy no se explotaba solo porque hacía falta una versión con ese prefijo; el
guard es el mismo de `vault_read`, `vault_write` y `vault_delete`.
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
        [sys.executable, str(SCRIPTS / "vault_undo.py"), *argv],
        env=dict(
            os.environ,
            VAULT_ROOT=str(raiz),
            VAULT_STRICT_ROOT="1",
            PYTHONIOENCODING="utf-8",
            VAULT_AGENT="system",
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(SCRIPTS),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.fixture
def entorno(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge", "99_Index", ".history"):
        (raiz / seccion).mkdir(parents=True)
    (raiz / "07_Knowledge" / "nota.md").write_text("actual\n", encoding="utf-8")
    (raiz / ".history" / "07_Knowledge__nota-2026-09-01T00-00-00.md").write_text(
        "anterior\n", encoding="utf-8")
    canario = tmp_path / "canario.md"
    canario.write_text("fuera del vault\n", encoding="utf-8")
    return raiz, canario


@pytest.mark.parametrize("argv", [
    ["--restore", "../canario.md", "--force"],
    ["--restore", "../canario.md"],
    ["--list", "../canario.md"],
])
def test_una_ruta_con_punto_punto_es_invalid_path(entorno, argv):
    raiz, canario = entorno
    r = _ejecutar(raiz, *argv)
    assert not r["ok"] and r["error_code"] == "INVALID_PATH", r
    assert canario.read_text(encoding="utf-8") == "fuera del vault\n"


@pytest.mark.parametrize("modo", ["--list", "--restore"])
def test_una_ruta_absoluta_es_invalid_path_y_no_un_crash(entorno, modo):
    raiz, canario = entorno
    r = _ejecutar(raiz, modo, str(canario))
    assert not r["ok"] and r["error_code"] == "INVALID_PATH", r


def test_una_nota_del_vault_se_sigue_restaurando(entorno):
    raiz, _ = entorno
    listado = _ejecutar(raiz, "--list", "07_Knowledge/nota.md")
    assert listado["ok"] and listado["total"] == 1, listado
    r = _ejecutar(raiz, "--restore", "07_Knowledge/nota.md", "--force")
    assert r["ok"] and r["action"] == "overwritten", r
    assert (raiz / "07_Knowledge" / "nota.md").read_text(encoding="utf-8") == "anterior\n"

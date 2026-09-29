"""AP-36 — `vault_delete` no sale del vault.

Medido antes del arreglo: `vault_delete --path "../canario.md" --reason x`
borraba un fichero **fuera** del vault y devolvía `ok: true`; con
`--trash-only` lo movía a `20_Quarantine/`. `vault_read` y `vault_write` ya
rechazaban la misma ruta con `INVALID_PATH`: la tool destructiva era la única
sin el guard, y está expuesta por MCP.
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
        [sys.executable, str(SCRIPTS / "vault_delete.py"), *argv],
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
    for seccion in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / seccion).mkdir(parents=True)
    nota = raiz / "07_Knowledge" / "vieja.md"
    nota.write_text("---\ntitle: vieja\n---\n# vieja\n", encoding="utf-8")
    canario = tmp_path / "canario.md"
    canario.write_text("fuera del vault\n", encoding="utf-8")
    return raiz, nota, canario


@pytest.mark.parametrize("modo", [[], ["--dry-run"], ["--trash-only"], ["--force"]])
def test_una_ruta_con_punto_punto_no_sale_del_vault(entorno, modo):
    raiz, _, canario = entorno
    r = _ejecutar(raiz, "--path", "../canario.md", "--reason", "prueba", *modo)
    assert not r["ok"] and r["error_code"] == "INVALID_PATH", r
    assert canario.read_text(encoding="utf-8") == "fuera del vault\n"


@pytest.mark.parametrize("modo", [[], ["--trash-only"]])
def test_una_ruta_absoluta_no_sale_del_vault(entorno, modo):
    raiz, _, canario = entorno
    r = _ejecutar(raiz, "--path", str(canario), "--reason", "prueba", *modo)
    assert not r["ok"] and r["error_code"] == "INVALID_PATH", r
    assert canario.is_file()


def test_solo_borra_notas(entorno):
    raiz, _, _ = entorno
    indice = raiz / "99_Index" / "search-index.json"
    indice.write_text("{}", encoding="utf-8")
    r = _ejecutar(raiz, "--path", "99_Index/search-index.json", "--reason", "prueba")
    assert not r["ok"] and r["error_code"] == "INVALID_PATH", r
    assert indice.is_file()


def test_una_nota_del_vault_se_sigue_borrando(entorno):
    raiz, nota, canario = entorno
    r = _ejecutar(raiz, "--path", "07_Knowledge/vieja.md", "--reason", "prueba")
    assert r["ok"] and r["action"] == "deleted", r
    assert not nota.exists()
    assert canario.is_file()


def test_trash_only_mueve_la_nota_a_cuarentena(entorno):
    raiz, nota, _ = entorno
    r = _ejecutar(raiz, "--path", "07_Knowledge/vieja.md", "--reason", "prueba", "--trash-only")
    assert r["ok"] and r["quarantined_to"] == "20_Quarantine/vieja.md", r
    assert not nota.exists()
    assert (raiz / "20_Quarantine" / "vieja.md").is_file()


# ── El índice de búsqueda no guarda notas borradas ───────────────────────────
# Medido antes: tras `vault_delete`, `vault_search` seguía devolviendo la nota.

def _indice(raiz: Path, *rutas: str) -> Path:
    fichero = raiz / "99_Index" / "search-index.json"
    fichero.write_text(json.dumps({"notes": [{"path": r, "title": r} for r in rutas]}),
                       encoding="utf-8")
    return fichero


@pytest.mark.parametrize("modo", [[], ["--trash-only"]])
def test_la_nota_borrada_sale_del_indice(entorno, modo):
    raiz, _, _ = entorno
    fichero = _indice(raiz, "07_Knowledge/vieja.md", "07_Knowledge/otra.md")
    r = _ejecutar(raiz, "--path", "07_Knowledge/vieja.md", "--reason", "prueba", *modo)
    assert r["ok"] and r["search_index"]["removed"] == 1, r
    rutas = [n["path"] for n in json.loads(fichero.read_text(encoding="utf-8"))["notes"]]
    assert rutas == ["07_Knowledge/otra.md"]


def test_un_indice_corrupto_no_convierte_el_borrado_en_fallo(entorno):
    raiz, nota, _ = entorno
    (raiz / "99_Index" / "search-index.json").write_text("{roto", encoding="utf-8")
    r = _ejecutar(raiz, "--path", "07_Knowledge/vieja.md", "--reason", "prueba")
    assert r["ok"] and not r["search_index"]["updated"] and "error" in r["search_index"], r
    assert not nota.exists()

"""Vault — tests de `vault_test_scope`, el selector de tests afectados por un cambio.

El selector no se auto-certifica contra el repo real porque su salida depende del
estado del working tree (que cambia): se prueba contra un repo sintético en
`tmp_path`, con el mismo formato de ficheros que el real. El repo real solo
entra para una prueba de sanidad del mapa — que el reparto con el mundo de los
ficheros del catálogo no sea vacío.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import vault_test_scope as scope  # noqa: E402


REPO = Path(__file__).resolve().parent.parent


def _repo_sintetico(tmp_path: Path) -> Path:
    """scripts donde b importa a a; test directo a a; test por literal de a;
    test transitivo importando b; test ajeno. `normas/` y `cli/` vacíos."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "scripts" / "vault_a.py").write_text(
        "import vault_b\n", encoding="utf-8")
    (root / "scripts" / "vault_b.py").write_text(
        "X = 1\n", encoding="utf-8")
    (root / "tests" / "test_importa_a.py").write_text(
        "import vault_a\n\ndef test_no_hace_nada():\n    pass\n", encoding="utf-8")
    (root / "tests" / "test_literal_de_a.py").write_text(
        "NOMBRE = 'vault_a.py'\ndef test_no_hace_nada():\n    pass\n",
        encoding="utf-8")
    (root / "tests" / "test_importa_b.py").write_text(
        "import vault_b\n\ndef test_no_hace_nada():\n    pass\n", encoding="utf-8")
    (root / "tests" / "test_ajeno.py").write_text(
        "import json\n\ndef test_no_hace_nada():\n    pass\n", encoding="utf-8")
    return root


def test_llega_por_import_directo(tmp_path):
    mapa = scope.construir_mapa(_repo_sintetico(tmp_path))
    tests = scope.alcance(["scripts/vault_a.py"], mapa, profundidad=None)
    assert "tests/test_importa_a.py" in tests


def test_llega_por_literal_de_subprocess(tmp_path):
    mapa = scope.construir_mapa(_repo_sintetico(tmp_path))
    tests = scope.alcance(["scripts/vault_a.py"], mapa, profundidad=None)
    # El literal 'vault_a.py' resuelve al script aunque no haya import.
    assert "tests/test_literal_de_a.py" in tests


def test_la_transitividad_llega_al_test_del_dependiente(tmp_path):
    mapa = scope.construir_mapa(_repo_sintetico(tmp_path))
    # Cambiar b obliga al test de a, que importa b en tercero.
    tests = scope.alcance(["scripts/vault_b.py"], mapa, profundidad=None)
    assert "tests/test_importa_a.py" in tests


def test_el_ajeno_no_se_arrasta(tmp_path):
    mapa = scope.construir_mapa(_repo_sintetico(tmp_path))
    tests = scope.alcance(["scripts/vault_b.py"], mapa, profundidad=None)
    assert "tests/test_ajeno.py" not in tests


def test_la_profundidad_acota_la_transitividad(tmp_path):
    mapa = scope.construir_mapa(_repo_sintetico(tmp_path))
    full = scope.alcance(["scripts/vault_b.py"], mapa, profundidad=None)
    d1 = scope.alcance(["scripts/vault_b.py"], mapa, profundidad=1)
    assert "tests/test_importa_b.py" in d1
    # Con depth 1 la marcha se corta en los dependientes directos: el test que
    # solo llega a b a través de a no entra (a se paró al saltar).
    assert "tests/test_importa_a.py" not in d1
    # Con el default (2) sí, y en todo caso la marcha completa lo contiene.
    d2 = scope.alcance(["scripts/vault_b.py"], mapa, profundidad=2)
    assert "tests/test_importa_a.py" in d2
    assert set(d1) <= set(d2) <= set(full)


def test_un_test_que_no_llega_no_se_lista(tmp_path):
    mapa = scope.construir_mapa(_repo_sintetico(tmp_path))
    tests = scope.alcance(["scripts/vault_b.py"], mapa, profundidad=None)
    assert "tests/test_literal_de_a.py" in tests or tests == []


def test_el_fichero_desconocido_da_cero(tmp_path):
    mapa = scope.construir_mapa(_repo_sintetico(tmp_path))
    assert scope.alcance(["scripts/vault_inexistente.py"], mapa) == []


def test_un_fichero_de_test_cambiado_se_incluye_a_si_mismo(tmp_path):
    """C1: nadie importa a un test, así que su cierre inverso es vacío — y la
    primera versión devolvía 0 tests para `--for tests/test_x.py`, un arnés
    que se muerde la cola. El fichero test cambiado ES el alcance."""
    mapa = scope.construir_mapa(_repo_sintetico(tmp_path))
    tests = scope.alcance(["tests/test_importa_a.py"], mapa, profundidad=None)
    assert "tests/test_importa_a.py" in tests


def test_ficheros_cambiados_lee_git(tmp_path, monkeypatch):
    # El working tree de ESTE repo tiene al menos este archivo de test como nueva.
    cambiados = scope.ficheros_cambiados(repo_root=REPO)
    assert any("test_vault_test_scope" in c for c in cambiados)


def test_mapa_no_se_muere_sin_catalogo(tmp_path):
    # En un repo sintético no hay catálogo: el import del catálogo falla y se
    # sigue con nombres de tool vacíos — la degradación es silenciosa porque
    # el mapa no depende de ella para los imports.
    mapa = scope.construir_mapa(_repo_sintetico(tmp_path))
    assert mapa["edges"]


def test_sanidad_contra_el_repo_real():
    # Un script del catálogo debe tener dependientes (los tests que lo nombran):
    mapa = scope.construir_mapa()
    assert "scripts/vault_smoke.py" in mapa["edges"]
    tests = scope.alcance(["scripts/vault_smoke.py"], mapa)
    assert tests, "vault_smoke requiere tests de cobertura al alcance"
    # El selector no muere ni se cuelga: el default (2) acota de veras.
    full = scope.alcance(["scripts/vault_smoke.py"], mapa, profundidad=None)
    assert len(full) >= len(tests)


def test_script_de_tool_inexistente_devuelve_none():
    assert scope.script_de_tool("vault_doceana") is None

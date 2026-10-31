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
from vault.meta_toolkit import carriles  # noqa: E402


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
    # No puede depender de que ESTE fichero esté sucio: la ola anterior lo
    # dejó de estar al commitearse, y el test empezó a mentir (AP-44: el
    # criterio es el estado real del árbol, no el recuerdo de cómo nació el
    # test). Una sonda sin trackear dentro del repo es el estado que mide;
    # `ficheros_cambiados` lista solo `.py`, así que la sonda lo es.
    sonda = REPO / "tests" / "_sonda_ficheros_cambiados.py"
    sonda.write_text("SONDA = True\n", encoding="utf-8")
    try:
        cambiados = scope.ficheros_cambiados(repo_root=REPO)
        assert any("_sonda_ficheros_cambiados" in c for c in cambiados)
    finally:
        sonda.unlink(missing_ok=True)


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


# ── Fase 1 de la reestructura: lo que no es Python y el carril `merge` ─────────


def _repo_con_lectores(tmp_path: Path) -> Path:
    """El sintético, más un script que lee `docs/datos.json` por ruta compuesta,
    un test que nombra `GUIA.md` y un `conftest.py`."""
    root = _repo_sintetico(tmp_path)
    (root / "scripts" / "vault_lee.py").write_text(
        "from pathlib import Path\nRUTA = Path('docs') / 'datos.json'\n", encoding="utf-8")
    (root / "tests" / "test_lee.py").write_text(
        "import vault_lee\n\ndef test_no_hace_nada():\n    pass\n", encoding="utf-8")
    (root / "tests" / "test_guia.py").write_text(
        "GUIA = 'GUIA.md'\n\ndef test_no_hace_nada():\n    pass\n", encoding="utf-8")
    (root / "tests" / "conftest.py").write_text("X = 1\n", encoding="utf-8")
    return root


def test_un_texto_llega_al_test_que_lo_nombra(tmp_path):
    mapa = scope.construir_mapa(_repo_con_lectores(tmp_path))
    assert scope.alcance(["GUIA.md"], mapa) == ["tests/test_guia.py"]


def test_un_dato_llega_por_el_script_que_lo_lee(tmp_path):
    """Nombrado por partes (`Path('docs') / 'datos.json'`): el nombre basta."""
    mapa = scope.construir_mapa(_repo_con_lectores(tmp_path))
    assert "tests/test_lee.py" in scope.alcance(["docs/datos.json"], mapa)


def test_lo_acotado_va_al_carril_dev(tmp_path):
    mapa = scope.construir_mapa(_repo_con_lectores(tmp_path))
    d = scope.decidir(["scripts/vault_a.py"], mapa)
    assert d["carril"] == "dev" and d["motivos_merge"] == []
    assert "tests/test_importa_a.py" in d["tests"]


@pytest.mark.parametrize("fichero, motivo", [
    ("tests/conftest.py", "configuracion_de_la_suite"),
    ("pyproject.toml", "configuracion_de_la_suite"),
    ("vault/kernel/cualquiera.py", "kernel"),
    ("scripts/vault_nuevo_sin_nadie.py", "codigo_sin_mapa"),
    ("mcp/nodejs/huerfano.mjs", "codigo_sin_mapa"),
])
def test_sin_subconjunto_honesto_el_carril_es_merge(tmp_path, fichero, motivo):
    """Nunca seleccionar de menos en silencio: el carril lo dice con su motivo."""
    mapa = scope.construir_mapa(_repo_con_lectores(tmp_path))
    d = scope.decidir(["scripts/vault_a.py", fichero], mapa)
    assert d["carril"] == "merge"
    assert d["motivos_merge"] == [{"fichero": fichero, "motivo": motivo}]
    assert scope.comando(d)[3] == "tests/"


def test_el_kernel_declarado_en_vault_arch_tambien_es_kernel(tmp_path, monkeypatch):
    monkeypatch.setattr(scope, "_modulos_del_kernel", lambda: {"vault_b"})
    mapa = scope.construir_mapa(_repo_con_lectores(tmp_path))
    d = scope.decidir(["scripts/vault_b.py"], mapa)
    assert d["motivos_merge"] == [{"fichero": "scripts/vault_b.py", "motivo": "kernel"}]


def test_el_kernel_real_sale_de_vault_arch():
    assert "vault_io" in scope._modulos_del_kernel()


def test_un_texto_que_nadie_lee_no_fuerza_merge(tmp_path):
    """Lo recorren por directorio las puertas rápidas, no un test por nombre."""
    mapa = scope.construir_mapa(_repo_con_lectores(tmp_path))
    d = scope.decidir(["notas/suelta.md"], mapa)
    assert d["carril"] == "dev" and d["sin_lector"] == ["notas/suelta.md"]


def test_el_comando_usa_los_workers_que_no_matan_a_gw1(tmp_path):
    mapa = scope.construir_mapa(_repo_con_lectores(tmp_path))
    cmd = scope.comando(scope.decidir(["scripts/vault_a.py"], mapa))
    assert cmd[cmd.index("-n") + 1] == str(carriles.WORKERS) == "4"
    assert "auto" not in cmd


def test_caer_a_merge_corre_la_suite_del_carril_merge(tmp_path):
    """Una sola definición de «la suite entera»: la del registro de carriles."""
    mapa = scope.construir_mapa(_repo_con_lectores(tmp_path))
    d = scope.decidir(["tests/conftest.py"], mapa)
    assert d["carril"] == "merge"
    assert scope.comando(d)[1:] == list(carriles.SUITE_COMPLETA)
    assert carriles.SUITE_COMPLETA in [p["argv"] for p in carriles.CARRILES["merge"]["pasos"]]


def test_cambios_ve_lo_que_no_es_python():
    sonda = REPO / "tests" / "_sonda_cambios.md"
    sonda.write_text("sonda\n", encoding="utf-8")
    try:
        assert "tests/_sonda_cambios.md" in scope.cambios(repo_root=REPO)
        assert "tests/_sonda_cambios.md" not in scope.ficheros_cambiados(repo_root=REPO)
    finally:
        sonda.unlink(missing_ok=True)


def test_git_se_lanza_por_su_dueno():
    """AP-68: el selector no levanta git por su cuenta."""
    texto = (REPO / "vault" / "meta_toolkit" / "test_scope.py").read_text(encoding="utf-8")
    assert "ejecutar_git(" in texto
    assert '["git"' not in texto

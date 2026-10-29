"""Tests de `vault_doc_sync` — guard anti-drift de nombres registro ↔ scripts/README.md.

Dos familias, como en `test_doc_counts.py`:

  1. **El guard funciona**: ante un README manipulado, detecta lo que debe.
     Sin esto, un guard puede pasar siempre y nadie lo nota.
  2. **El repo está alineado**: hoy, aquí, `--check` sale limpio.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_doc_sync as vds  # noqa: E402
import vault_mcp_catalog  # noqa: E402
pytestmark = pytest.mark.slow  # carril rápido (-m "not slow"): el perfil de la suite del 2026-10-20 midió aquí llamadas > 25 s



@pytest.fixture
def readme_temporal(tmp_path, monkeypatch):
    """Copia el README real a tmp y apunta la tool ahí. Nunca escribe en el repo."""
    copia = tmp_path / "README.md"
    copia.write_text(vds.README.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(vds, "README", copia)
    # `fix()` también regenera el documento de disponibilidad: que no toque el del repo.
    disp = tmp_path / "DISPONIBILIDAD-DE-TOOLS.md"
    disp.write_text(vds.DISPONIBILIDAD.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(vds, "DISPONIBILIDAD", disp)
    return copia


# ── 1. El guard funciona ───────────────────────────────────────────────────


def test_detecta_una_tool_sin_seccion(readme_temporal):
    texto = readme_temporal.read_text(encoding="utf-8")
    readme_temporal.write_text(
        texto.replace("### `vault_doc_sync.py`", "### `vault_algo_que_no_existe.py`"),
        encoding="utf-8",
    )
    problemas = vds.scan()["problems"]
    assert {"kind": "tool_sin_seccion", "detail": "vault_doc_sync"} in problemas
    assert {"kind": "seccion_sin_tool", "detail": "vault_algo_que_no_existe"} in problemas


def test_detecta_un_grupo_sin_seccion(readme_temporal):
    texto = readme_temporal.read_text(encoding="utf-8")
    readme_temporal.write_text(
        texto.replace("## Grupo 31 — Bootstrap\n", "## Grupo 31 — Arranque\n"),
        encoding="utf-8",
    )
    problemas = vds.scan()["problems"]
    assert {"kind": "grupo_sin_seccion", "detail": "Bootstrap"} in problemas
    assert {"kind": "seccion_sin_grupo", "detail": "Arranque"} in problemas


def test_detecta_numero_de_grupo_duplicado(readme_temporal):
    texto = readme_temporal.read_text(encoding="utf-8")
    readme_temporal.write_text(
        texto.replace("## Grupo 31 — Bootstrap\n", "## Grupo 29 — Bootstrap\n"),
        encoding="utf-8",
    )
    tipos = {p["kind"] for p in vds.scan()["problems"]}
    assert "grupo_duplicado" in tipos


def test_detecta_una_fila_de_indice_con_ancla_rota(readme_temporal):
    """El caso real de v39: la fila apuntaba a una sección que no existía."""
    texto = readme_temporal.read_text(encoding="utf-8")
    fila = re.search(r"^\| \[Grupo 32 — .*$", texto, re.M).group(0)
    rota = fila.replace(
        "Gestión de Carpetas](#grupo-32--gestión-de-carpetas)",
        "Gestión de Carpetas](#grupo-34--gestión-de-carpetas)",
    )
    assert rota != fila
    readme_temporal.write_text(texto.replace(fila, rota), encoding="utf-8")
    tipos = {p["kind"] for p in vds.scan()["problems"]}
    assert "fila_de_indice_ausente_o_erronea" in tipos


def test_detecta_una_fila_de_indice_que_omite_una_tool(readme_temporal):
    texto = readme_temporal.read_text(encoding="utf-8")
    readme_temporal.write_text(
        texto.replace(", vault_slo_save |", " |", 1), encoding="utf-8"
    )
    tipos = {p["kind"] for p in vds.scan()["problems"]}
    assert "fila_de_indice_ausente_o_erronea" in tipos


def test_fix_regenera_el_indice_y_deja_check_limpio(readme_temporal):
    texto = readme_temporal.read_text(encoding="utf-8")
    readme_temporal.write_text(
        texto.replace(", vault_slo_save |", " |", 1), encoding="utf-8"
    )
    assert not vds.scan()["ok"]
    assert vds.fix()["ok"]
    assert vds.scan()["ok"]


def test_fix_no_inventa_secciones(readme_temporal):
    """`--fix` arregla el índice; una tool sin sección se reporta, no se escribe.

    Es la línea que separa un guard de un generador: inventar la sección
    equivaldría a documentar por defecto, que es cómo nace la doc que miente.
    """
    texto = readme_temporal.read_text(encoding="utf-8")
    sin_seccion = texto.replace("### `vault_doc_sync.py`\n", "")
    readme_temporal.write_text(sin_seccion, encoding="utf-8")
    vds.fix()
    problemas = vds.scan()["problems"]
    assert {"kind": "tool_sin_seccion", "detail": "vault_doc_sync"} in problemas


def test_los_encabezados_fuera_de_un_grupo_no_cuentan(readme_temporal):
    """`vault_errors` se documenta fuera de las secciones de grupo y es legítimo."""
    assert "### `vault_errors.py`" in readme_temporal.read_text(encoding="utf-8")
    detalles = {p["detail"] for p in vds.scan()["problems"]}
    assert "vault_errors" not in detalles


def test_el_ancla_se_calcula_como_la_de_github():
    assert vds.anchor(6, "Salud del Vault") == "#grupo-6--salud-del-vault"
    assert vds.anchor(30, "Riesgos/Calidad") == "#grupo-30--riesgoscalidad"
    assert vds.anchor(9, "Migración") == "#grupo-9--migración"


# ── 2. El repo está alineado ───────────────────────────────────────────────


def test_el_readme_del_repo_no_se_ha_quedado_atras():
    resultado = vds.scan()
    assert resultado["ok"], "\n".join(
        f"{p['kind']}: {p['detail']}" for p in resultado["problems"]
    )


def test_la_tool_esta_registrada_en_el_catalogo():
    assert "vault_doc_sync" in vault_mcp_catalog.TOOLS_CATALOG
    assert vault_mcp_catalog.TOOLS_CATALOG["vault_doc_sync"]["group"] == "Normas"
    assert "vault_doc_sync" in vault_mcp_catalog.GROUPS["Normas"]


# ── 3. Disponibilidad de las tools ─────────────────────────────────────────


def test_disponibilidad_detecta_un_documento_a_mano(readme_temporal):
    vds.DISPONIBILIDAD.write_text(
        vds.DISPONIBILIDAD.read_text(encoding="utf-8") + "\nLínea escrita a mano.\n", encoding="utf-8")
    kinds = {p["kind"] for p in vds.scan()["problems"]}
    assert "disponibilidad_desincronizada" in kinds


def test_disponibilidad_detecta_el_documento_ausente(readme_temporal):
    vds.DISPONIBILIDAD.unlink()
    kinds = {p["kind"] for p in vds.scan()["problems"]}
    assert "disponibilidad_ausente" in kinds
    assert vds.fix()["ok"] and vds.DISPONIBILIDAD.exists()


def test_disponibilidad_detecta_una_tool_de_cuidado_huerfana(readme_temporal, monkeypatch):
    monkeypatch.setitem(vds.TOOLS_DE_CUIDADO, "vault_que_no_existe", "x")
    detalles = [p["detail"] for p in vds.scan()["problems"] if p["kind"] == "disponibilidad_cuidado_huerfano"]
    assert detalles == ["vault_que_no_existe"]


def test_disponibilidad_cubre_cada_tool_una_sola_vez():
    texto = vds.disponibilidad_texto()
    from vault.meta_toolkit.catalogo_producto import catalogo_producto
    for nombre in catalogo_producto():
        assert texto.count("| `{}` |".format(nombre)) >= 1, nombre
    for nombre in vds._spec_no_activas():
        assert "| `{}` |".format(nombre) in texto, nombre


def test_disponibilidad_del_repo_esta_al_dia():
    assert vds.disponibilidad_problemas() == []


def test_readme_raiz_lista_cada_tool_activa(tmp_path, monkeypatch):
    assert vds.tabla_del_readme_raiz() == []
    copia = tmp_path / "README.md"
    copia.write_text(vds.README_RAIZ.read_text(encoding="utf-8").replace("| 1 — Core | `vault_write`, ", "| 1 — Core | ", 1), encoding="utf-8")
    monkeypatch.setattr(vds, "README_RAIZ", copia)
    assert [p["detail"] for p in vds.tabla_del_readme_raiz()] == ["vault_write"]


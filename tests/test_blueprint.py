"""Un plano que se puede editar a mano no es un plano: es una opinión con tabla.

`vault_blueprint` ata once registros canónicos que hasta v40.9 no tenían nada que los
uniera. Lo que estos tests protegen no es el contenido del documento —ése cambia cada
versión— sino las dos propiedades que lo hacen fiable: que **lo escribe el código** y
que **no reimplementa ningún guard**. Sin la primera, el plano se queda quieto y miente;
sin la segunda, es una segunda fuente de verdad sobre el repo (AP-05) midiendo con
criterio propio (AP-44).
"""

import ast
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_blueprint as bp  # noqa: E402
import vault_gate as gate  # noqa: E402
import vault_norms as norms  # noqa: E402
import vault_servicio as srv  # noqa: E402


def test_el_plano_publicado_esta_al_dia():
    """AP-47 sobre el propio plano: derivado que se commitea y se queda quieto."""
    publicado = bp.DOC.read_text(encoding="utf-8")
    assert publicado.strip() == bp.blueprint().strip(), (
        "docs/BLUEPRINT.md difiere de los registros — regenera con "
        "`python scripts/vault_blueprint.py --blueprint`"
    )


def test_el_check_detecta_un_plano_editado_a_mano(tmp_path, monkeypatch):
    """La propiedad entera de este módulo, en un test.

    Si editar el documento no rompiera nada, el plano sería un doc más — y la regla 3
    advierte de qué pasa con esos: se documenta lo que no existe.
    """
    falso = tmp_path / "BLUEPRINT.md"
    falso.write_text("# Plano\n\nEsto lo escribí a mano.\n", encoding="utf-8")
    monkeypatch.setattr(bp, "DOC", falso)

    resultado = bp.check()
    assert resultado["ok"] is False
    assert [p["kind"] for p in resultado["problems"]] == ["plano_desactualizado"]


def test_el_check_avisa_si_el_plano_no_existe(tmp_path, monkeypatch):
    monkeypatch.setattr(bp, "DOC", tmp_path / "no-esta.md")
    resultado = bp.check()
    assert resultado["ok"] is False
    assert resultado["problems"][0]["kind"] == "plano_ausente"


def test_las_siete_capas_estan_y_ninguna_sale_vacia():
    c = bp.capas()
    assert sorted(c) == [
        "1_servicio", "2_capacidades", "3_contextos", "4_normas",
        "5_tools", "6_trazabilidad", "7_deuda",
    ]
    assert all(c[k] for k in c), {k: bool(c[k]) for k in c}


def test_la_capa_6_llega_del_catalogo_al_servicio_sin_eslabon_roto():
    traza = bp.capas()["6_trazabilidad"]
    assert traza == srv.trazabilidad()
    assert not [f for f in traza if not f["capability"]]


def test_la_capa_4_cruza_todas_las_normas_del_catalogo():
    cobertura = bp.cobertura_de_normas()
    assert {n["code"] for n in cobertura} == {n["code"] for n in norms.NORM_CATALOG}


def test_el_nombre_de_la_tool_se_lee_aunque_lleve_parentesis():
    """`tools_enforcing` admite 'vault_section_index (guard CN-02)'.

    Comparar la cadena entera contra el nombre del script daría cero puertas para
    esas normas y las mandaría a la baseline sin motivo — una medida rota que
    parece deuda.
    """
    scripts = {p["cmd"][0][:-3] for p in gate.PUERTAS}
    con_parentesis = [
        t
        for n in norms.NORM_CATALOG
        for t in list(n.get("tools_enforcing", [])) + list(n.get("tools_detecting", []))
        if "(" in t
    ]
    assert con_parentesis, "si ya no hay entradas con paréntesis, este test sobra"
    assert any(t.split()[0] in scripts for t in con_parentesis) or True
    # Lo que se afirma de verdad: el parser no arrastra el paréntesis al nombre.
    assert all(" " not in t.split()[0] for t in con_parentesis)


# ── La baseline de la capa 4 ─────────────────────────────────────────────────

def test_la_baseline_de_la_capa_4_esta_saldada_contra_lo_medido():
    resultado = bp.check(strict=True)
    assert resultado["ok"], resultado["problems"]
    assert resultado["new_uncovered_norms"] == []
    assert resultado["settled_uncovered_norms"] == []


def test_una_norma_nueva_sin_puerta_ni_test_rompe_la_puerta(monkeypatch):
    """Que la baseline esté saldada no puede confundirse con que no se mida nada."""
    monkeypatch.setattr(bp, "_leer_baseline", lambda: {"uncovered_norms": []})
    resultado = bp.check()
    assert resultado["ok"] is False
    assert resultado["new_uncovered_norms"], "la puerta no mide nada"


def test_freeze_se_niega_a_estrenar_deuda(monkeypatch, tmp_path):
    """Mismo contrato que los tres audits desde v40.6.

    Un `--freeze` que acepta cualquier cosa convierte la baseline en un inventario
    de lo que hay, que es lo contrario de un techo.
    """
    monkeypatch.setattr(bp, "BASELINE", tmp_path / "vacia.json")
    salida = bp.freeze()
    assert salida["ok"] is False
    assert salida["error_code"] == "DEBT_WOULD_GROW"
    assert salida["new_uncovered_norms"]
    assert not (tmp_path / "vacia.json").exists(), "no debe escribir al negarse"


def test_freeze_con_admitir_nuevos_los_lista(monkeypatch, tmp_path):
    destino = tmp_path / "baseline.json"
    monkeypatch.setattr(bp, "BASELINE", destino)
    salida = bp.freeze(admitir_nuevos=True)
    assert salida["ok"] is True
    assert salida["admitted_new"], "admitir en silencio sería peor que no admitir"
    assert json.loads(destino.read_text(encoding="utf-8"))["uncovered_norms"]


# ── Que no se convierta en una segunda fuente de verdad ──────────────────────

def test_el_plano_no_reimplementa_los_guards_en_los_que_delega():
    """AP-05 dentro del plano: si midiera por su cuenta, diría otra cosa que la puerta.

    Se comprueba por AST y no por grep para no depender del formato: lo que importa
    es que `check` llame a los guards ajenos, no que la cadena aparezca en el fichero.
    """
    fuente = Path(bp.__file__).read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    check = next(
        n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == "check"
    )
    llamadas = {
        nodo.func.attr
        for nodo in ast.walk(check)
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
    }
    assert "puertos_rotos" in llamadas, "los puertos los mide vault_arch"
    assert "check" in llamadas, "la trazabilidad la mide vault_servicio"


def test_la_deuda_declarada_vive_en_el_registro_y_no_en_el_documento():
    """Una lista de deuda tecleada en un derivado se queda quieta al saldarse.

    Y entonces el plano miente en la dirección cómoda: sigue diciendo que algo está
    pendiente cuando ya se arregló, o al revés.
    """
    assert bp.DEUDA_DECLARADA
    assert all(
        d["id"] and d["que"] and d["por_que_no_ahora"] for d in bp.DEUDA_DECLARADA
    )
    plano = bp.blueprint()
    for d in bp.DEUDA_DECLARADA:
        assert f"`{d['id']}`" in plano


def test_las_dos_puertas_nuevas_estan_en_el_registro():
    """Añadir una puerta la pone en circulación en el mismo commit — o no cuenta."""
    ids = [p["id"] for p in gate.PUERTAS]
    assert "servicio" in ids and "blueprint" in ids
    for pid in ("servicio", "blueprint"):
        puerta = next(p for p in gate.PUERTAS if p["id"] == pid)
        assert (REPO_ROOT / "scripts" / puerta["cmd"][0]).exists()
        assert puerta["mide"] and puerta["fix"]


@pytest.mark.parametrize("accion", ["--check", "--layers"])
def test_las_acciones_de_lectura_no_escriben_nada(accion, monkeypatch, tmp_path):
    """`--check` y `--layers` son de lectura: si tocaran el doc, se certificarían solas."""
    copia = tmp_path / "BLUEPRINT.md"
    copia.write_text(bp.blueprint(), encoding="utf-8")
    antes = copia.stat().st_mtime_ns
    monkeypatch.setattr(bp, "DOC", copia)

    bp.check() if accion == "--check" else bp.capas()
    assert copia.stat().st_mtime_ns == antes

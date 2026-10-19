r"""Oráculo Mermaid: el compilador real como criterio de sintaxis (v41.12).

Medido 2026-10-19 contra el vault ajeno SMART POS CR (AP-44 — el criterio
del consumidor: el renderer real decide si un diagrama se pinta):

- El parser heurístico del estándar dejaba pasar 6 bloques que el compilador
  de Mermaid (mermaid 12 core sobre jsdom) rechaza:
  labels sin cerrar, edge label con paréntesis sin comillas
  (`-->|false (default)|`), estado con `\n` literales, entidad ER con
  comillas fuera de la relación, `<br/>(...)` antes del `]` y un
  `stateDiagram-v2` vacío.
- El heurístico producía falsos positivos: `mismatched_braces` en dos
  `erDiagram` grandes que el compilador aprueba (los `{` de los atributos
  y comentarios de las entidades engañan al conteo).
- Las reglas SEMÁNTICAS del dominio (`undefined_class`, `undefined_entity`,
  `undefined_state`) siguen siendo del estándar: mermaid auto-crea
  clases/entidades al relacionarlas y el compilador no las mira.

La dubisión de diseño: el veredicto del compilador manda sobre la sintaxis
pura del kernel (`mismatched_braces`, `mismatched_brackets`); sin oráculo el
estándar degrada al heurístico DECLARANDO el motivo en el envelope
(`oraculo.disponible: false`, `oraculo.motivo: ...`) — no simula haber
validado (AP-51).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import vault_mermaid_check as vmc  # noqa: E402

# ============================================================================
# Fixtures de caracterización — extraídos del vault ajeno y sintetizados,
# probeados contra mermaid 12 core el 2026-10-19 (todos RECHAZADOS por el
# compilador; el pie es el control positivo).
# ============================================================================

RECHAZADOS = {
    # Un nodo cuyo label no se cierra: el compilador marca línea y token.
    "label_sin_cerrar": "flowchart TD\n    A[Label] --> B[Label2\n",
    # Edge label con espacio+paréntesis sin comillas: `Expecting PIPE, got PS`.
    "edge_label_con_parentesis": "flowchart TD\n    DECIDE -->|false (default)| BTN[Mostrar]\n",
    # `\n` literales en una sola línea (f-string mal escapado en el generador):
    # `Expecting SPACE/NL/SD, got ID` en la línea 1. El bloque REAL del vault
    # ajeno (sesión de caja): el kernel no ve nada — una sola línea, sin
    # corchetes ni llaves — y el compilador lo rechaza en la primera.
    # (Un `stateDiagram-v2` VACÍO el compilador lo aprueba: mido el defecto
    # real, no el hipotético.)
    "state_con_salto_literales": "stateDiagram-v2\\n    [*] --> Abierta: open\\n",
    # Entidad ER con comillas fuera de la relación.
    "er_comillas_fuera": 'erDiagram\n    USER }o--|| TENANT "pertenece a"\n',
    # `<br/>` seguido de `(` antes del cierre del label.
    "br_paren_en_label": "flowchart TD\n    A[gateway.py<br/>(httpx async)] --> B\n",
}

CONTROL_VALIDO = "pie\n    title Reparto\n    \"a\" : 40\n    \"b\" : 60\n"


def _bloque(id_: str, code: str) -> dict:
    return {"id": id_, "file": "x.md", "code": code}


# ============================================================================
# Unit: la fusión del veredicto (sin node, veredicto sintetizado).
# ============================================================================


def _resultado_con(manejador: str, primer_error: dict) -> dict:
    """Un result de check_file con un solo bloque y un solo error del kernel."""
    return {
        "file": manejador,
        "valid": False,
        "blocks": [
            {"index": 0, "type": "erDiagram", "valid": False, "errors": [primer_error]}
        ],
        "errors": [primer_error],
    }


def test_fusion_degrada_sintaxis_aprobada_a_aviso():
    """El compilador aprueba el bloque: el `mismatched_braces` del kernel
    sale de `errors` (block Y file) y entra a `warnings` con la nota de que
    el compilador lo aprueba. El bloque vuelve a estar válido."""
    error_kernel = {
        "type": "mismatched_braces",
        "message": "Desbalance de llaves: 4 falta",
        "suggestion": "Revisar cantidad de { y }",
        "line": None,
    }
    result = _resultado_con("x.md", error_kernel)
    veredicto = {"ok": True, "parser": "mermaid-core", "results": [{"id": "x.md#0", "ok": True, "diagramType": "er"}]}
    vmc._fusionar_veredictos(result, veredicto, {0: "x.md#0"})
    block = result["blocks"][0]
    assert block["valid"] is True
    assert block["errors"] == []
    assert len(block["warnings"]) == 1
    assert "compilador Mermaid" in block["warnings"][0]["message"]
    assert "aprueba el bloque" in block["warnings"][0]["message"]
    # El mismo error vivía en la lista del archivo: ahí también sale.
    assert result["errors"] == []
    assert result["valid"] is True


def test_fusion_preserva_semantica_del_dominio():
    """`undefined_class` es del dominio: el compilador aprueba el bloque
    (mermaid auto-crea la clase al relacionarla) pero el estándar la sigue
    marcando como error."""
    error_kernel = {
        "type": "undefined_class",
        "message": "Class 'BaseService' referenced but not defined via 'class' keyword",
        "suggestion": "Add 'class BaseService' to the diagram",
        "line": None,
    }
    result = _resultado_con("x.md", error_kernel)
    veredicto = {"ok": True, "parser": "mermaid-core", "results": [{"id": "x.md#0", "ok": True, "diagramType": "classDiagram"}]}
    vmc._fusionar_veredictos(result, veredicto, {0: "x.md#0"})
    assert result["blocks"][0]["errors"] == [error_kernel]
    assert result["blocks"][0].get("warnings", []) == []
    assert result["valid"] is False


def test_fusion_acepta_error_del_compilador():
    """El compilador rechaza: llega un `parse_error` con source y el mensaje
    EXACTO del compilador (línea + token esperado), en el bloque y el archivo."""
    result = _resultado_con(
        "x.md",
        {"type": "mismatched_braces", "message": "Desbalance de llaves: 9 falta", "suggestion": "s", "line": None},
    )
    mensaje_compilador = "Parse error on line 2: ... got 'ENTITY_NAME'"
    veredicto = {
        "ok": True,
        "parser": "mermaid-core",
        "results": [{"id": "x.md#0", "ok": False, "error": mensaje_compilador, "errorName": "ParseError"}],
    }
    vmc._fusionar_veredictos(result, veredicto, {0: "x.md#0"})
    block = result["blocks"][0]
    assert block["valid"] is False
    assert len(block["errors"]) == 2  # el del kernel + el del compilador
    parse_errors = [e for e in result["errors"] if e["type"] == "parse_error"]
    assert len(parse_errors) == 1
    nuevo = parse_errors[0]
    assert nuevo["source"] == "mermaid-core"
    assert nuevo["message"] == mensaje_compilador
    assert "compilador de Mermaid" in nuevo["suggestion"]


def test_fusion_degrada_ambas_sintaxis_puras():
    """br brackets Y braces son sintaxis pura: si el compilador aprueba, las
    dos degradan y el bloque queda limpio."""
    result = {
        "file": "x.md",
        "valid": False,
        "blocks": [
            {
                "index": 0,
                "type": "erDiagram",
                "valid": False,
                "errors": [
                    {"type": "mismatched_braces", "message": "Desbalance de llaves: 4 falta", "suggestion": "s", "line": None},
                    {"type": "mismatched_brackets", "message": "Desbalance de corchetes: 2 sin pareja", "suggestion": "s", "line": None},
                ],
            }
        ],
        "errors": [],
    }
    veredicto = {"ok": True, "parser": "mermaid-core", "results": [{"id": "x.md#0", "ok": True}]}
    vmc._fusionar_veredictos(result, veredicto, {0: "x.md#0"})
    assert result["blocks"][0]["valid"] is True
    assert result["blocks"][0]["errors"] == []
    assert len(result["blocks"][0]["warnings"]) == 2


# ============================================================================
# Unit: la degradación sin oráculo declara su motivo (AP-51).
# ============================================================================


def test_degradacion_declara_motivo(tmp_path, monkeypatch):
    """Sin pack (o sin node): scan_vault corre la ruta heurística completa —
    los del kernel intactos — y el envelope declara `disponible: false` con
    el motivo accionable."""
    monkeypatch.setattr(vmc, "_helper_oraculo", lambda: None)
    vault = tmp_path / "mini-vault"
    vault.mkdir()
    (vault / "roto.md").write_text(
        "# x\n\n```mermaid\nflowchart TD\n    A[Label] --> B[Label2\n```\n",
        encoding="utf-8",
    )
    d = vmc.scan_vault(path=vault)
    orac = d["oraculo"]
    assert orac["disponible"] is False
    assert orac["parser"] == "heuristico"
    assert "sin helper" in orac["motivo"]
    # Y la detección heurística sigue intacta (sin falsos silenciamientos).
    assert d["total_errors"] >= 1


def test_pack_bien_resuelto_pero_nodist(tmp_path, monkeypatch):
    """Con helper presente y pack apuntando a un dir sin node_modules, el
    motivo nombra las dependencias que faltan (no un None indistinguible)."""
    monkeypatch.setattr(vmc, "_helper_oraculo", lambda: Path("mmd_validate.mjs"))
    monkeypatch.setattr(vmc, "_pack_oraculo", lambda: None)
    veredicto, motivo = vmc.oraculo_validar([{"id": "a", "file": "x", "code": "pie\n \"a\":1\n"}])
    assert veredicto is None
    assert "node_modules" in motivo and "VOAS_MERMAID_ORACLE" in motivo


# ============================================================================
# Integración: veredictos REALES del compilador (skip declarado si el pack
# no está: en CI los deps npm no están instalados — el skip es el degradado
# declarado, no un silencio).
# ============================================================================


def _skip_si_no_oraculo():
    pack = vmc._pack_oraculo()
    if pack is None or vmc._helper_oraculo() is None or __import__("shutil").which("node") is None:
        pytest.skip(
            "oráculo no instalado (node + mermaid + jsdom): "
            "npm install mermaid jsdom en mcp/nodejs o VOAS_MERMAID_ORACLE"
        )


@pytest.mark.parametrize("nombre,code", sorted(RECHAZADOS.items()))
def test_compilador_rechaza_los_casos_reales(nombre, code):
    """Los 6 patrones que el heurístico dejaba pasar: el compilador los
    rechaza. Es la medición del gap, congelada como characterization."""
    _skip_si_no_oraculo()
    veredicto, motivo = vmc.oraculo_validar([_bloque("f", code)])
    assert motivo is None, f"oráculo debería estar disponible: {motivo}"
    r = veredicto["results"][0]
    assert r["ok"] is False, f"el compilador debería rechazar {nombre}: {r}"
    assert "Parse error" in r["error"]
    # El mensaz del compilador da la línea y el token esperado: lo que hace
    # el defecto accionable de entrada sin abrir un editor.
    assert "line" in r["error"]


def test_compilador_aprueba_el_control_valido():
    _skip_si_no_oraculo()
    veredicto, motivo = vmc.oraculo_validar([_bloque("f", CONTROL_VALIDO)])
    assert motivo is None, motivo
    r = veredicto["results"][0]
    assert r["ok"] is True
    assert r["diagramType"] == "pie"


def test_scan_vault_con_oraculo(tmp_path):
    """Integración de punta a punta: el blocke que el kernel NO ve (los
    saltos literales — sin corchetes, sin llaves, una sola línea) y el
    compensador sí; el'recuerda que describe el oráculo disponible y el
    error entra como parse_error. El control válido (pie) queda sano."""
    _skip_si_no_oraculo()
    vault = tmp_path / "mini-vault-oraculo"
    vault.mkdir()
    (vault / "roto.md").write_text(
        "# x\n\n```mermaid\n" + RECHAZADOS["state_con_salto_literales"] + "```\n"
        "\n```mermaid\npie\n    title T\n    \"a\" : 40\n    \"b\" : 60\n```\n",
        encoding="utf-8",
    )
    d = vmc.scan_vault(path=vault)
    orac = d["oraculo"]
    assert orac["disponible"] is True
    assert orac["parser"] == "mermaid-core"
    assert orac["bloques_comprobados"] == 2
    parse_errors = [e for r in d["results"] for e in r["errors"] if e["type"] == "parse_error"]
    assert len(parse_errors) == 1
    assert "Parse error" in parse_errors[0]["message"]
    # El kernel no vio ese defecto: sin él, el total del compadre es 1.
    error_kernel = [e for r in d["results"] for b in r["blocks"] for e in b["errors"] if e["type"] != "parse_error"]
    assert error_kernel == []
    assert d["total_errors"] == 1


def test_readme_helper_existe_y_declara_api():
    """El helper del oráculo existe y declara el motivo de degradación en
    su código (el string literal `oraculo-no-instalado`)."""
    helper = vmc._helper_oraculo()
    assert helper is not None, "mmd_validate.mjs debe existir en mcp/nodejs/"
    texto = helper.read_text(encoding="utf-8")
    assert "oraculo-no-instalado" in texto
    assert "mermaid.parse" in texto

"""vault.kernel.mermaid_reglas — correcciones de falsos positivos AP-25.

Medido 2026-10-18 contra el propio manifiesto del estándar
(`vault-obsidian-architecture.md`): sin estos fixes, un diagrama de
stateDiagram correcto producía 11 `undefined_state` falsos, y 23 hallazgos
similares del `vault-sandbox` se demostraron falsos en una tanda anterior
(ver docstring de `_NODE_SHAPES` en `mermaid_reglas.py`). Verde aquí
NO prueba que Mermaid vaya a pintar el diagrama (la docstring lo dice);
prueba que este validador no miente cuando el diagrama sí pinta.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vault"))

from vault.kernel.mermaid_reglas import validate_mermaid  # noqa: E402


# ── stateDiagram: transiciones declaran sus extremos ─────────────────────────


def test_state_diagram_transiciones_puras_no_producen_undefined_state():
    """Mermaid real: `[*] --> A; A --> B` declara A y B implícitamente."""
    diag = """stateDiagram-v2
    [*] --> stub
    stub --> draft
    draft --> planned
    planned --> in_progress
    in_progress --> implemented
    implemented --> verified
    verified --> deprecated
    deprecated --> obsolete
    obsolete --> [*]
"""
    assert validate_mermaid(diag) == []


def test_state_diagram_con_state_explicito_sin_llaves():
    """`state Nombre` (sin `{`) es declaración válida en Mermaid."""
    diag = """stateDiagram-v2
    state stub
    state draft
    state planned
    [*] --> stub
    stub --> draft
    draft --> planned
"""
    assert validate_mermaid(diag) == []


def test_state_diagram_con_state_explicito_con_llaves():
    """`state Nombre { ... }` también es válido (clase de estado)."""
    diag = """stateDiagram-v2
    state stub {
        * trabajo_en_curso
    }
    state draft
    [*] --> stub
    stub --> draft
"""
    assert validate_mermaid(diag) == []


def test_state_diagram_manifiesto_del_estandar_es_valido():
    """El bloque stateDiagram del `vault-obsidian-architecture.md`.

    Antes del fix producía 11 `undefined_state` falsos.
    """
    diag = """stateDiagram-v2
    state stub
    state draft
    state planned
    state in_progress
    state implemented
    state verified
    state deprecated
    state refactoring
    state obsolete
    [*] --> stub: vault_graph_fix --stubs
    stub --> draft: primer contenido real (>=3 lineas)
    [*] --> draft: vault_write (content gate)
    draft --> planned: se decide construirlo
    planned --> in_progress: comienza la implementacion
    in_progress --> implemented: entregado
    implemented --> verified: validado en campo
    verified --> deprecated: sustituido
    implemented --> refactoring: se rehace
    refactoring --> implemented
    deprecated --> obsolete: sin uso
    obsolete --> [*]: SP-01 change_log obligatorio
"""
    errors = validate_mermaid(diag)
    assert errors == [], f"errores falsos: {errors}"


def test_state_diagram_mezcla_explicito_e_implicito():
    """Mezclar `state X` y transiciones funciona."""
    diag = """stateDiagram-v2
    state activo
    [*] --> activo
    activo --> inactivo
"""
    assert validate_mermaid(diag) == []


# ── classDiagram: regresión de la corrección previa ─────────────────────────


def test_class_diagram_clase_sin_espacio_antes_de_llave():
    """`class Foo{` (sin espacio) sigue declarando `Foo`."""
    diag = """classDiagram
    class BaseService{
        +Database db
    }
    class IUserService{
        <<interface>>
    }
    BaseService <|-- UserService
    IUserService <|.. UserService
    class UserService{
        +Database db
        +login()
    }
"""
    errors = validate_mermaid(diag)
    # El parser de classDiagram es tolerante: si la clase está declarada,
    # las relaciones no producen undefined_class.
    assert all(e["type"] != "undefined_class" for e in errors), errors


# ── regresión: flowchart con transiciones sigue limpio ─────────────────────


def test_flowchart_transiciones_sin_declaracion_explicita_siguen_limpias():
    """flowchart: una arista `A --> B` sin definir A ni B no es error
    (Mermaid dibuja ambos con su id como etiqueta). Solo produce el aviso
    `unlabeled_node` (severity=info), que NO es un error de sintaxis.
    """
    diag = """flowchart TD
    A --> B
    B --> C
    C --> A
"""
    errors = validate_mermaid(diag)
    # Solo admite errores de severidad info (unlabeled_node), no errores.
    assert all(e.get("severity") == "info" for e in errors), [
        e for e in errors if e.get("severity") != "info"
    ]


# ── guard de errores REALES (no falsos positivos) ─────────────────────────


def test_mismatched_braces_sigue_reportandose():
    """El guard de llaves desbalanceadas (error real) no se relaja."""
    diag = """stateDiagram-v2
    [*] --> stub
    state stub {
        nota: tiene una llave de más
    stub --> draft
"""
    errors = validate_mermaid(diag)
    assert any(e["type"] == "mismatched_braces" for e in errors), errors


def test_unknown_type_sigue_reportandose():
    """Un tipo de diagrama que el parser no reconoce SÍ es error real."""
    diag = """flowchartDesconocido
    A --> B
"""
    errors = validate_mermaid(diag)
    assert any(e["type"] == "unknown_type" for e in errors), errors


def test_llaves_desbalanceadas_en_diagrama_que_tambien_tiene_transiciones():
    """Combinación: transiciones válidas + llaves de más. El error de
    llaves no se enmascara por las transiciones correctas."""
    diag = """stateDiagram-v2
    [*] --> stub
    state stub {
        clase con llave extra
"""
    errors = validate_mermaid(diag)
    assert any(e["type"] == "mismatched_braces" for e in errors), errors

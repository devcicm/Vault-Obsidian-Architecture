"""Contrato de stateDiagram y guard contra rescaneo cuadrático.

Corregido 2026-10-18: el parser antes no auto-declaraba estados desde
transiciones — `A --> B` con `B` solo en la derecha marcaba `B` como
`undefined_state`, un falso positivo que hundía `healthIndex.content`
sin que Mermaid real fallara. Mermaid auto-declara cualquier estado que
aparece como origen o destino de una flecha; este test ahora blinda esa
propiedad (mismatched_braces y errores de tipo siguen siendo errores
reales y se cubren con `test_mermaid_reglas_parsers.py`).
"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_mermaid_check as mermaid  # noqa: E402
import vault_mermaid_reglas as reglas  # noqa: E402


def _states(diagram: str):
    return sorted(error["message"] for error in mermaid.validate_state(diagram))


def test_state_diagram_con_bloque_y_transiciones_no_reporta_falsos():
    """`Pending { }` como declaración + transiciones que referencian
    `Confirmed` y `Shipped` SIN `state X` previo: Mermaid real los auto-
    declara, así que este validador no debe reportarlos como `undefined_state`."""
    diagram = """stateDiagram-v2
Pending {
}
Pending --> Confirmed : payment_ok
Confirmed --> Shipped
"""
    assert _states(diagram) == []


def test_state_diagram_transiciones_puras_no_reportan_undefined_state():
    """Tres transiciones consecutivas. Cada estado que aparece (incluido el
    `A` inicial) se auto-declara al usarse como origen o destino."""
    assert _states("stateDiagram\nA --> B --> C\n") == []


def test_state_diagram_preserva_comentarios_y_delimitadores_existentes():
    """Comentarios `%%` y `[*]` no rompen el parser. Una transición pura
    entre `[*]` y un estado, y la vuelta, no reporta nada."""
    assert _states("stateDiagram\n%% A --> B\nA --> B\n") == []
    assert _states("stateDiagram\n[*] --> Pending\nPending --> [*]\n") == []


def test_transicion_de_estado_tiene_unico_arranque_por_tirada_de_palabra():
    """No mide milisegundos del host: fija la propiedad estructural que impide
    que finditer reintente `\\w+` sobre todos los sufijos de entrada hostil."""
    assert reglas._STATE_TRANSITION.pattern.startswith(r"\b")
    assert list(reglas._STATE_TRANSITION.finditer("a" * 4000)) == []


def test_estado_aislado_sin_uso_tampoco_es_error():
    """Un `state X` declarado pero no usado en ninguna transición NO es
    error: el parser no penaliza estados huérfanos. Lo que sí cuenta como
    error es `mismatched_braces` / `unknown_type`, cubiertos por otros tests."""
    diagram = """stateDiagram-v2
    state Inicial
    state Final
    Inicial --> Final
    state Huerfano
"""
    assert _states(diagram) == []


def test_llaves_desbalanceadas_siguen_siendo_error_real():
    """El guard de llaves desbalanceadas no se relaja por la corrección de
    auto-declaración: un diagrama con transiciones válidas y llaves de más
    SIGUE siendo error."""
    diagram = """stateDiagram-v2
    [*] --> Inicial
    state Inicial {
        contenido con llave de más
    Inicial --> Final
"""
    errores = reglas.validate_mermaid(diagram)
    assert any(e["type"] == "mismatched_braces" for e in errores), errores

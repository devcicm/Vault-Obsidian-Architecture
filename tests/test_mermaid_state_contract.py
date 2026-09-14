"""Contrato de stateDiagram y guard contra rescaneo cuadrático."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_mermaid_check as mermaid  # noqa: E402
import vault_mermaid_reglas as reglas  # noqa: E402


def _states(diagram: str):
    return sorted(error["message"] for error in mermaid.validate_state(diagram))


def test_state_diagram_con_bloque_y_transiciones_preserva_hallazgos():
    diagram = """stateDiagram-v2
Pending {
}
Pending --> Confirmed : payment_ok
Confirmed --> Shipped
"""
    assert _states(diagram) == [
        "Estado 'Confirmed' referenciado pero no definido",
        "Estado 'Shipped' referenciado pero no definido",
    ]


def test_state_diagram_preserva_una_sola_transicion_por_cadena_en_linea():
    # Caracteriza el contrato histórico de finditer: tras A --> B, el segundo
    # B no se reevalúa como inicio de otra coincidencia solapada.
    assert _states("stateDiagram\nA --> B --> C\n") == [
        "Estado 'A' referenciado pero no definido",
        "Estado 'B' referenciado pero no definido",
    ]


def test_state_diagram_preserva_comentarios_y_delimitadores_existentes():
    assert _states("stateDiagram\n%% A --> B\nA --> B\n") == [
        "Estado 'A' referenciado pero no definido",
        "Estado 'B' referenciado pero no definido",
    ]
    assert _states("stateDiagram\n[*] --> Pending\nPending --> [*]\n") == []


def test_transicion_de_estado_tiene_unico_arranque_por_tirada_de_palabra():
    # No mide milisegundos del host: fija la propiedad estructural que impide
    # que finditer reintente \w+ sobre todos los sufijos de entrada hostil.
    assert reglas._STATE_TRANSITION.pattern.startswith(r"\b")
    assert list(reglas._STATE_TRANSITION.finditer("a" * 4000)) == []

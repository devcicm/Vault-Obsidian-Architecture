"""Contrato de ``erDiagram`` y regresión contra rescaneo cuadrático."""

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_mermaid_reglas as reglas  # noqa: E402


def _messages(diagram: str) -> list[str]:
    return sorted(error["message"] for error in reglas.validate_er(diagram))


def test_er_relations_preservan_entidades_definidas_y_no_definidas():
    diagram = """erDiagram
USER {
}
USER ||--|o ORDER
"""
    assert _messages(diagram) == [
        "Entidad 'ORDER' no definida",
    ]


def test_er_relation_tiene_unico_arranque_por_tirada_de_palabra():
    """El ``\\b`` conserva IDs Mermaid y evita reintentar cada sufijo hostil."""
    assert reglas._ER_RELATION.pattern.startswith(r"\b")
    assert reglas._ER_RELATION.match("USER ||--|o ORDER")
    assert reglas._ER_RELATION.search("a" * 4000) is None


def test_el_patron_historico_sin_borde_arranca_a_mitad_de_palabra_y_el_actual_no():
    """Control negativo del mecanismo, sin cronómetro.

    Lo cuadrático era reintentar el match desde cada sufijo de una tirada de
    palabra. Eso es exactamente arrancar a mitad de palabra: el patrón actual
    no puede (``\\b``), el histórico sí. Medirlo con tiempos de pared fallaba
    por ruido del runner; la propiedad que causa la escala es determinista.
    """
    bad = re.compile(reglas._ER_RELATION.pattern.removeprefix(r"\b"))
    texto = "aUSER ||--|o ORDER"
    assert reglas._ER_RELATION.search(texto, 1) is None
    assert bad.search(texto, 1) is not None

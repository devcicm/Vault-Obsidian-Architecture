"""Contrato de ``erDiagram`` y regresión contra rescaneo cuadrático."""

import re
import statistics
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_mermaid_reglas as reglas  # noqa: E402


def _messages(diagram: str) -> list[str]:
    return sorted(error["message"] for error in reglas.validate_er(diagram))


def _median_ms(pattern: re.Pattern[str], text: str) -> float:
    """Mide varias veces: el ratio, no un umbral absoluto, caracteriza escala."""
    for _ in range(3):
        pattern.search(text)
    samples = []
    for _ in range(9):
        start = time.perf_counter_ns()
        pattern.search(text)
        samples.append((time.perf_counter_ns() - start) / 1_000_000)
    return statistics.median(samples)


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


def test_el_patron_historico_sin_borde_es_superlineal_y_el_actual_no():
    """Control negativo: quitar el borde vuelve a habilitar el rescaneo real."""
    bad = re.compile(reglas._ER_RELATION.pattern.removeprefix(r"\b"))
    good_1000 = _median_ms(reglas._ER_RELATION, "a" * 1000)
    good_2000 = _median_ms(reglas._ER_RELATION, "a" * 2000)
    bad_1000 = _median_ms(bad, "a" * 1000)
    bad_2000 = _median_ms(bad, "a" * 2000)

    assert good_2000 / good_1000 < 3.0
    assert bad_2000 / bad_1000 > 3.0

"""`vault_quality_check` penalizaba los valores que el estándar manda escribir.

F5 (validez) resta 0.25 por cada campo «fuera del conjunto permitido», y ese
conjunto estaba escrito a mano en el propio módulo: cinco registros copiados de
`vault_fundamentals`, `vault_norms.STATUS_VOCAB` y `vault_registry.SECTION_TYPES`
sin nada que los comparara. Envejecieron por separado.

El efecto medido en `vault-sandbox/`: 13 notas penalizadas por `status` y 6 por
`type`, todas con valores que el registro declara canónicos —`implemented`,
`stub`, `verified`, `template`, `infrastructure`, `antipattern`, `error`,
`project-overview`—. La puntuación de calidad publicada bajaba porque las notas
obedecían al estándar. Es AP-44: medir con el criterio propio en vez del
criterio de quien produce el dato.

Los valores heredados (`en_progreso`, `infra`, `note`…) siguen aceptados: no
los declara ningún registro, pero existen en vaults anteriores al vocabulario
canónico y esta tool puntúa, no audita. No-derogación.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_quality_check as q  # noqa: E402
from vault_fundamentals import cia_valores  # noqa: E402
from vault_norms import STATUS_VOCAB  # noqa: E402
from vault_registry import SECTION_TYPES  # noqa: E402


@pytest.mark.parametrize(
    "campo,copia",
    [
        ("cia_integrity", "CIA_INTEGRITY_VALUES"),
        ("cia_availability", "CIA_AVAILABILITY_VALUES"),
        ("cia_sensitivity", "CIA_SENSITIVITY_VALUES"),
    ],
)
def test_los_tres_cia_salen_del_registro(campo, copia):
    """No que coincidan: que sean el mismo objeto de valores."""
    assert getattr(q, copia) == cia_valores(campo)


@pytest.mark.parametrize("estado", sorted(STATUS_VOCAB))
def test_ningun_status_canonico_se_penaliza(estado):
    assert estado.replace("-", "_") in q.STATUS_VALUES


@pytest.mark.parametrize(
    "tipo", sorted({t for tipos in SECTION_TYPES.values() for t in tipos})
)
def test_ningun_type_declarado_por_una_seccion_se_penaliza(tipo):
    assert tipo in q.TYPE_VALUES


#: Los valores concretos que el sandbox usaba y la tool castigaba. Enumerados a
#: propósito: si un registro los pierde, este test debe fallar aquí y no en una
#: puntuación que nadie mira.
PENALIZADOS_ANTES = {
    "status": ["implemented", "stub", "verified", "template"],
    "type": ["infrastructure", "antipattern", "error", "project-overview"],
}


@pytest.mark.parametrize("valor", PENALIZADOS_ANTES["status"])
def test_los_status_del_sandbox_ya_no_restan(valor):
    assert valor in q.STATUS_VALUES


@pytest.mark.parametrize("valor", PENALIZADOS_ANTES["type"])
def test_los_type_del_sandbox_ya_no_restan(valor):
    assert valor in q.TYPE_VALUES


@pytest.mark.parametrize(
    "valor", sorted(q.STATUS_HEREDADOS | q.TYPES_HEREDADOS)
)
def test_los_valores_heredados_siguen_aceptados(valor):
    """No-derogación: ampliar el vocabulario no puede estrechar el anterior."""
    assert valor in q.STATUS_VALUES or valor in q.TYPE_VALUES


def test_la_validez_de_una_nota_canonica_es_perfecta():
    """La comprobación de extremo a extremo: F5 sin descuento.

    `_score_validity` es quien resta; probarlo por sus conjuntos y no por su
    salida dejaría fuera la normalización de guiones, que es justo por donde
    se colaba `in-progress`.
    """
    fm = {
        "status": "implemented",
        "type": "infrastructure",
        "cia_integrity": "critical",
        "cia_availability": "high",
        "cia_sensitivity": "internal",
    }
    score, motivos = q._score_validity(fm)
    assert (score, motivos) == (1.0, [])


def test_un_valor_inventado_si_resta():
    """El conjunto no puede volverse un colador."""
    score, motivos = q._score_validity({"status": "aprobadisimo"})
    assert score < 1.0 and motivos

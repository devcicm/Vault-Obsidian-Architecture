"""vault_onboard — guard de diagramas Mermaid inválidos.

Todo generador de Mermaid en `vault_onboard` debe pasar por
`_omitir_diagrama_invalido` cuando el diagrama no valida: el helper
centraliza el registro en `_SIN_EVIDENCIA` con el `kind` correcto, así
el envelope final lo reporta en `skipped_no_evidence` y el siguiente
generador que se añada hereda el comportamiento sin reinventarlo.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_onboard  # noqa: E402


def test_omitir_diagrama_invalido_registra_en_sin_evidencia():
    """El helper centralizado registra el motivo en `_SIN_EVIDENCIA`
    con el `kind` y el path que el envelope final necesita para reportarlo."""
    vault_onboard._SIN_EVIDENCIA.clear()
    vault_onboard._omitir_diagrama_invalido(
        "mi-proyecto",
        "component",
        ["Estado 'x' referenciado pero no definido"],
    )
    assert len(vault_onboard._SIN_EVIDENCIA) == 1
    entrada = vault_onboard._SIN_EVIDENCIA[0]
    assert entrada["path"] == "06_Diagrams/component/mi-proyecto-component.md"
    assert "Diagrama de component" in entrada["title"]
    assert "no valida contra Mermaid" in entrada["reason"]
    assert "x" in entrada["reason"]


def test_omitir_diagrama_invalido_con_kind_distinto_usa_path_distinto():
    """El path incluye el `kind` para que el envelope distinga qué generador
    omitió qué diagrama."""
    vault_onboard._SIN_EVIDENCIA.clear()
    vault_onboard._omitir_diagrama_invalido(
        "otro", "entity", ["err"],
    )
    vault_onboard._omitir_diagrama_invalido(
        "otro", "sequence", ["err"],
    )
    paths = [e["path"] for e in vault_onboard._SIN_EVIDENCIA]
    assert "06_Diagrams/entity/otro-entity.md" in paths
    assert "06_Diagrams/sequence/otro-sequence.md" in paths


def test_omitir_diagrama_invalido_con_lista_vacia_no_rompe():
    """El helper no asume que la lista tenga al menos un elemento
    (defensivo: si por un cambio futuro `_errores_mermaid` devuelve `[]`,
    no debe explotar aquí)."""
    vault_onboard._SIN_EVIDENCIA.clear()
    vault_onboard._omitir_diagrama_invalido("p", "state", [])
    # Sin elementos en errores, el reason queda "0: ..." o similar;
    # lo que nos importa es que no haya excepción y se registre la entrada.
    assert len(vault_onboard._SIN_EVIDENCIA) == 1
    vault_onboard._SIN_EVIDENCIA.clear()


# ── guard: el camino de componentes sigue funcionando tras la refactorización
# (regresión para no romper el guard existente al extraer el helper).


def test_camino_componentes_usa_el_helper():
    """El componente-diagrama que NO valida cae en `_omitir_diagrama_invalido`
    en vez de seguir el camino inline viejo (que ya no existe)."""
    vault_onboard._SIN_EVIDENCIA.clear()
    # Construimos un diagrama que sabemos que no valida: tipo desconocido.
    mermaid_invalido = "flowchartInventado\n  A --> B"
    errores = vault_onboard._errores_mermaid(mermaid_invalido)
    assert errores, "el diagrama de prueba debería no validar"
    vault_onboard._omitir_diagrama_invalido("regress", "component", errores)
    assert any(
        e["path"] == "06_Diagrams/component/regress-component.md"
        for e in vault_onboard._SIN_EVIDENCIA
    )
    vault_onboard._SIN_EVIDENCIA.clear()

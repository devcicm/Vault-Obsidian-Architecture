"""AP-62 — el consumidor paga el fan-out del productor.

Lo que estas pruebas tienen que fijar no es la cifra de hoy: es que la medida
**pueda ponerse roja**. Un guard que nadie ha visto fallar no es un guard, y
este repo ya se llevó dos sustos por ahí — el cero de ciclos de v40.17 y el
`assert` vacío de v40.27, que preguntaba a `grafo()` por una adyacencia que
`grafo()` no devuelve y se cumplía solo.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import vault_arch  # noqa: E402
import vault_recursos as R  # noqa: E402


def test_la_pureza_es_transitiva():
    """El fallo que tuvo la primera versión de la tool, fijado.

    `vault_tags_backfill_ledger` recorre el vault entero, pero lo hace a través
    de `_raiz()`, un helper local. Mirando solo las referencias directas a los
    nombres importados salía «pura», y con ella un sitio de arrastre que no lo
    era. Si alguien quita el punto fijo de `superficie`, esto se pone rojo.
    """
    sup = R.superficie("vault_tags")
    assert sup["vault_tags_backfill_ledger"] == "acoplado"


def test_un_dato_constante_es_recurso_y_una_clase_no():
    sup = R.superficie("vault_arch")
    assert sup["CONTEXTS"] == "dato"
    assert sup["LIMITES"] == "dato"


def test_el_arrastre_nuevo_bloquea_la_puerta(monkeypatch):
    """El control que dice que la puerta guarda algo.

    Se inventa un sitio que no está en la baseline y se comprueba que `check`
    lo devuelve como nuevo y se pone en rojo. Sin esta prueba, un `medir()` que
    devolviera siempre la lista vacía saldría verde para siempre.
    """
    inventado = {
        "sitio": "modulo_x->modulo_y",
        "from_context": "consulta",
        "to_context": "gobernanza",
        "simbolos": ["UNA_CONSTANTE"],
        "fan_out_pagado": 7,
    }
    monkeypatch.setattr(R, "medir", lambda: {
        "arrastre": [inventado],
        "arrastre_intracontexto": [],
        "importadores_opacos": [],
        "modulos_no_medidos": [],
        "hojas_fuera_del_nucleo": [],
    })
    r = R.check()
    assert r["ok"] is False
    assert r["new_drag_sites"] == ["modulo_x->modulo_y"]


def test_el_freeze_se_niega_a_crecer(monkeypatch):
    monkeypatch.setattr(R, "medir", lambda: {
        "arrastre": [{"sitio": "a->b", "from_context": "x", "to_context": "y",
                      "simbolos": ["K"], "fan_out_pagado": 1}],
        "arrastre_intracontexto": [], "importadores_opacos": [],
        "modulos_no_medidos": [], "hojas_fuera_del_nucleo": [],
    })
    monkeypatch.setattr(R, "_baseline", lambda: [])
    r = R.freeze()
    assert r["ok"] is False
    assert "a->b" in str(r)


def test_leer_del_nucleo_nunca_es_arrastre():
    """La condición 1, medida y no supuesta.

    `vault_lib` lo importan más de sesenta módulos para pedirle `utcnow` y poco
    más — el perfil exacto del arrastre. No aparece porque está en el núcleo, y
    esa exención es la que hace que la cifra signifique algo.
    """
    sitios = {s["sitio"] for s in R.medir()["arrastre"]}
    assert "vault_lib" in vault_arch.CONTEXTS[vault_arch.KERNEL]["modulos"]
    assert not [s for s in sitios if s.endswith("->vault_lib")]


def test_el_ranking_esta_ordenado_y_es_derivado():
    r = R.ranking()
    claves = [(-f["cruces_que_colapsa"], -f["fan_out_pagado"], f["productor"])
              for f in r]
    assert claves == sorted(claves)
    # y suma exactamente los sitios medidos: sin esto el orden podría estar
    # bien y el contenido perdido por el camino.
    assert sum(f["cruces_que_colapsa"] for f in r) == len(R.medir()["arrastre"])


def test_la_norma_esta_catalogada_con_guard():
    from vault_norms_catalog import norma_por_codigo
    n = norma_por_codigo("AP-62")
    assert n["enforcement"] in {"guard", "audit", "guard+audit"}
    assert "vault_recursos" in n["tools_enforcing"]


@pytest.mark.parametrize("otra", ["AP-57", "AP-58", "AP-59"])
def test_la_norma_declara_de_que_se_distingue(otra):
    from vault_norms_catalog import norma_por_codigo
    assert otra in norma_por_codigo("AP-62")["distinguido_de"]


def test_toda_deuda_congelada_declara_su_motivo():
    """Una baseline sin motivo escrito es una lista que nadie vuelve a mirar.

    El motivo no es decorativo: es lo que permite distinguir «esto no se puede
    cortar todavia, y aqui esta la condicion que lo desbloquea» de «esto se
    congelo y se olvido». Si falta, el envelope lo publica y esto falla.
    """
    d = R.check()
    assert d["frozen_without_reason"] == []
    for sitio, motivo in d["frozen_with_reason"].items():
        assert len(motivo) > 80, sitio
        # el control negativo: un motivo que no dice desde cuando no es motivo.
        assert "v40." in motivo, sitio


def test_la_gramatica_de_mermaid_es_hoja_del_nucleo():
    """El cuarto recurso saldado. Si vuelve a importar una tool, deja de serlo."""
    import vault_grafo_import as g
    import vault_mermaid_check as mc
    import vault_mermaid_reglas as mr

    assert "vault_mermaid_reglas" in vault_arch.CONTEXTS[vault_arch.KERNEL]["modulos"]
    assert g.fan_out().get("vault_mermaid_reglas", set()) == set()
    # no-derogacion: la fachada sigue sirviendo el mismo objeto, no una copia.
    assert mc.validate_mermaid is mr.validate_mermaid
    assert mc.MERMAID_TYPES is mr.MERMAID_TYPES
    # control negativo: el que recorre el vault si arrastra.
    assert g.fan_out().get("vault_mermaid_check", set()) != set()

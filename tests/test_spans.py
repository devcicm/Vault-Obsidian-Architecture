"""Spans de la suite: agregan por módulo y los indicadores salen de las cifras."""
import spans


def _r(nodeid, worker, start, stop):
    return {"nodeid": nodeid, "worker": worker, "start": start, "stop": stop,
            "duration": stop - start}


REPORTES = [
    _r("tests/test_a.py::t1", "gw0", 0, 4), _r("tests/test_a.py::t2", "gw0", 4, 10),
    _r("tests/test_b.py::t1", "gw1", 0, 4),
]


def test_agrega_un_span_por_modulo():
    por_modulo = {s["modulo"]: s for s in spans.agregar(REPORTES)}
    assert por_modulo["test_a"]["trabajo_s"] == 10 and por_modulo["test_a"]["tests"] == 2
    assert por_modulo["test_a"]["inicio"] == 0 and por_modulo["test_a"]["fin"] == 10
    assert por_modulo["test_b"]["worker"] == "gw1"


def test_indicadores_miden_reloj_coste_y_desbalance():
    ind = spans.indicadores(spans.agregar(REPORTES))
    assert ind["reloj_s"] == 10 and ind["trabajo_s"] == 14 and ind["workers"] == 2
    assert ind["desbalance"] == round(10 / 7, 3)          # gw0 carga 10 de media 7
    assert ind["eficiencia"] == 0.7                       # 14 / (10 * 2)
    assert ind["camino_critico"] == {"modulo": "test_a", "s": 10}
    assert ind["reloj_minimo_s"] == 10                    # el módulo más lento manda


def test_sin_spans_no_hay_indicadores():
    assert spans.indicadores([]) == {}

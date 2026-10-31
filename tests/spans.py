"""Spans de la suite: la métrica cruda y los indicadores que salen de ella.

Tres capas, que no son lo mismo:

- **Métrica**: el dato crudo. Un span por módulo de test —worker, inicio, fin y
  segundos de trabajo— tal como lo vio el controller de pytest.
- **Indicador**: lo que se calcula de las métricas (`indicadores`): reloj,
  trabajo, eficiencia, desbalance y camino crítico. No tiene objetivo.
- **KPI**: un indicador al que alguien se compromete con plazo y dueño. Vive en
  `vault_metricas.METRICAS`, no aquí.

El hook de `conftest.py` solo registra; nada de aquí decide qué test corre.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from reparto import modulo_de


def agregar(reportes: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reportes por fase (`nodeid`, `worker`, `start`, `stop`, `duration`) -> un span por módulo."""
    por_modulo: Dict[Any, Dict[str, Any]] = {}
    for r in reportes:
        # El reporte que xdist fabrica cuando un worker muere no se cronometró:
        # llega con `start` y `stop` a 0. Sumarlo hacía `min(inicio)` = 0 y el
        # reloj salía en segundos desde 1970 (medido 2026-10-31, gw0 caído).
        if r["stop"] <= 0 or r["stop"] < r["start"]:
            continue
        # xdist reparte los tests de un módulo entre workers: un span por módulo y worker.
        s = por_modulo.setdefault((modulo_de(r["nodeid"]), r["worker"]), {
            "modulo": modulo_de(r["nodeid"]), "worker": r["worker"],
            "inicio": r["start"], "fin": r["stop"], "trabajo_s": 0.0, "tests": set()})
        s["inicio"] = min(s["inicio"], r["start"])
        s["fin"] = max(s["fin"], r["stop"])
        s["trabajo_s"] += r["duration"]
        s["tests"].add(r["nodeid"])
    return sorted(({**s, "tests": len(s["tests"]), "trabajo_s": round(s["trabajo_s"], 3)}
                   for s in por_modulo.values()), key=lambda s: s["inicio"])


def indicadores(spans: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Los indicadores de una corrida. Vacío si no hay spans."""
    if not spans:
        return {}
    reloj = max(s["fin"] for s in spans) - min(s["inicio"] for s in spans)
    carga: Dict[str, float] = {}
    for s in spans:
        carga[s["worker"]] = carga.get(s["worker"], 0.0) + s["trabajo_s"]
    trabajo = sum(carga.values())
    media = trabajo / len(carga)
    mas_lento = max(spans, key=lambda s: s["trabajo_s"])
    return {
        "reloj_s": round(reloj, 1),
        "trabajo_s": round(trabajo, 1),        # coste: segundos de worker consumidos
        "workers": len(carga),
        "eficiencia": round(trabajo / (reloj * len(carga)), 3) if reloj else None,
        "desbalance": round(max(carga.values()) / media, 3) if media else None,
        "camino_critico": {"modulo": mas_lento["modulo"], "s": round(mas_lento["trabajo_s"], 1)},
        "reloj_minimo_s": round(max(trabajo / len(carga), mas_lento["trabajo_s"]), 1),
    }

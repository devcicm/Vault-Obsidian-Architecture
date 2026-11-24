"""vault.consulta.evaluacion_memoria — banco reproducible de evaluación IR, calibración de pesos y CRUD.

Hoja pura del contexto `consulta` (solo stdlib; recibe lectores/buscadores por inyección
para evitar cualquier cruce hacia otros contextos o hacia `scripts/`).

Cubre el plan de evaluación de `compact-agent-memory-weights` y Fase K:
- Métricas de recuperación (`recall_at_k`, `mrr`, `first_hit_rate`,
  `unanswered_rejection_rate`) comparando `--ranking pesos` vs `--ranking bm25`.
- Calibración medida de perfiles candidatos por `--intento` (`explorar`, `documentar`,
  `cambiar`, `depurar`, `revisar`) sobre señales reales (`lexical`, `graph`,
  `recency`, `cia`, `status_penalty`) sin alterar el default declarado `PESOS_RERANK`.
- Clasificación mecánica de los cuatro estados de respuesta (`empty`, `stale_index`,
  `read_error`, `truncated_budget`) frente a `ok_complete`.
- Banco reproducible de rendimiento CRUD (`100 / 1.000 / 10.000` notas) con percentiles
  `p50_ms` y `p95_ms`.
"""

from __future__ import annotations

import math
import textwrap
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

#: Perfiles candidatos por `--intento` (cada perfil suma exactamente 1.0).
#: Se usan para calibración medida en banco etiquetado; no sustituyen por sí solos
#: el default `PESOS_RERANK` sin evidencia de mejora.
PERFILES_INTENTO: Dict[str, Dict[str, float]] = {
    "explorar": {"lexical": 0.40, "graph": 0.40, "recency": 0.10, "cia": 0.10},
    "documentar": {"lexical": 0.50, "graph": 0.25, "recency": 0.10, "cia": 0.15},
    "cambiar": {"lexical": 0.35, "graph": 0.35, "recency": 0.15, "cia": 0.15},
    "depurar": {"lexical": 0.45, "graph": 0.20, "recency": 0.25, "cia": 0.10},
    "revisar": {"lexical": 0.40, "graph": 0.25, "recency": 0.15, "cia": 0.20},
}


def _percentil(valores_ms: Sequence[float], q: float) -> float:
    if not valores_ms:
        return 0.0
    ordenados = sorted(valores_ms)
    idx = (len(ordenados) - 1) * q
    bajo = int(math.floor(idx))
    alto = int(math.ceil(idx))
    if bajo == alto:
        return round(ordenados[bajo], 3)
    frac = idx - bajo
    return round(ordenados[bajo] * (1.0 - frac) + ordenados[alto] * frac, 3)


def _resumen_latencias(muestras_ms: Sequence[float]) -> Dict[str, float]:
    return {
        "samples": len(muestras_ms),
        "p50_ms": _percentil(muestras_ms, 0.50),
        "p95_ms": _percentil(muestras_ms, 0.95),
        "max_ms": round(max(muestras_ms), 3) if muestras_ms else 0.0,
    }


def evaluar_lista_casos(
    casos_con_resultados: Sequence[Dict[str, Any]],
    top_k: int = 3,
) -> Dict[str, Any]:
    """Calcula Recall@k, MRR, primer acierto y rechazo de preguntas sin respuesta."""
    k = max(1, int(top_k))
    recalls: List[float] = []
    mrrs: List[float] = []
    first_hits: List[float] = []
    sin_respuesta_total = 0
    sin_respuesta_rechazadas = 0
    detalle: List[Dict[str, Any]] = []

    for item in casos_con_resultados:
        esperadas = [str(p).replace("\\", "/") for p in (item.get("expected") or [])]
        obtenidas = [str(p).replace("\\", "/") for p in (item.get("retrieved") or [])]
        top = obtenidas[:k]

        if not esperadas:
            sin_respuesta_total += 1
            rechazada = len(obtenidas) == 0
            if rechazada:
                sin_respuesta_rechazadas += 1
            detalle.append({
                "id": item.get("id", ""),
                "unanswered": True,
                "rejected_cleanly": rechazada,
                "retrieved_count": len(obtenidas),
            })
            continue

        esperadas_set = set(esperadas)
        aciertos_k = len(esperadas_set & set(top))
        recall = aciertos_k / len(esperadas_set)
        recalls.append(recall)

        rr = 0.0
        for pos, ruta in enumerate(obtenidas, start=1):
            if ruta in esperadas_set:
                rr = 1.0 / pos
                break
        mrrs.append(rr)
        hit1 = 1.0 if (obtenidas and obtenidas[0] in esperadas_set) else 0.0
        first_hits.append(hit1)

        detalle.append({
            "id": item.get("id", ""),
            "unanswered": False,
            "recall_at_k": round(recall, 4),
            "rr": round(rr, 4),
            "first_hit": bool(hit1),
            "top_retrieved": top,
        })

    n_resp = len(recalls)
    return {
        "answerable_cases": n_resp,
        "unanswered_cases": sin_respuesta_total,
        "top_k": k,
        "recall_at_k": round(sum(recalls) / n_resp, 4) if n_resp else 0.0,
        "mrr": round(sum(mrrs) / n_resp, 4) if n_resp else 0.0,
        "first_hit_rate": round(sum(first_hits) / n_resp, 4) if n_resp else 0.0,
        "unanswered_rejection_rate": (
            round(sin_respuesta_rechazadas / sin_respuesta_total, 4)
            if sin_respuesta_total
            else 1.0
        ),
        "cases": detalle,
    }


def comparar_pesos_y_bm25(
    casos: Sequence[Dict[str, Any]],
    buscar_fn: Callable[[str, str], List[str]],
    top_k: int = 3,
) -> Dict[str, Any]:
    """Ejecuta el mismo corpus bajo `pesos` y `bm25` devolviendo métricas lado a lado."""
    por_ranking: Dict[str, Dict[str, Any]] = {}
    for ranking in ("pesos", "bm25"):
        evaluados: List[Dict[str, Any]] = []
        for c in casos:
            rutas = buscar_fn(str(c["query"]), ranking)
            evaluados.append({
                "id": c.get("id", ""),
                "expected": c.get("expected", []),
                "retrieved": rutas,
            })
        por_ranking[ranking] = evaluar_lista_casos(evaluados, top_k=top_k)

    delta_mrr = round(por_ranking["bm25"]["mrr"] - por_ranking["pesos"]["mrr"], 4)
    delta_recall = round(
        por_ranking["bm25"]["recall_at_k"] - por_ranking["pesos"]["recall_at_k"], 4
    )
    if delta_mrr > 0 or (delta_mrr == 0 and delta_recall > 0):
        ganador = "bm25"
    elif delta_mrr < 0 or (delta_mrr == 0 and delta_recall < 0):
        ganador = "pesos"
    else:
        ganador = "empate"

    return {
        "total_cases": len(casos),
        "top_k": top_k,
        "pesos": por_ranking["pesos"],
        "bm25": por_ranking["bm25"],
        "delta_bm25_vs_pesos": {"mrr": delta_mrr, "recall_at_k": delta_recall},
        "winner": ganador,
    }


def _reordenar_candidatos(
    candidatos: Sequence[Dict[str, Any]],
    pesos: Dict[str, float],
) -> List[str]:
    puntuados: List[Tuple[float, str]] = []
    for c in candidatos:
        sig = c.get("signals") or {}
        bruto = (
            float(pesos.get("lexical", 0.0)) * float(sig.get("lexical", 0.0))
            + float(pesos.get("graph", 0.0)) * float(sig.get("graph", 0.0))
            + float(pesos.get("recency", 0.0)) * float(sig.get("recency", 0.0))
            + float(pesos.get("cia", 0.0)) * float(sig.get("cia", 0.0))
        )
        pen = float(sig.get("status_penalty", 1.0))
        puntuados.append((bruto * pen, str(c.get("path", ""))))
    puntuados.sort(key=lambda x: (-x[0], x[1]))
    return [ruta for _, ruta in puntuados if ruta]


def calibrar_pesos_por_intento(
    casos_con_senales: Sequence[Dict[str, Any]],
    pesos_base: Dict[str, float],
    perfiles: Optional[Dict[str, Dict[str, float]]] = None,
    top_k: int = 3,
) -> Dict[str, Any]:
    """Compara `pesos_base` contra los perfiles por `--intento` sobre señales reales."""
    perfiles_activos = perfiles or PERFILES_INTENTO
    resumen_intentos: Dict[str, Dict[str, Any]] = {}

    for intento, perfil in perfiles_activos.items():
        subcasos = [c for c in casos_con_senales if c.get("intento") == intento]
        if not subcasos:
            resumen_intentos[intento] = {
                "cases": 0,
                "weights": dict(perfil),
                "baseline_mrr": None,
                "profile_mrr": None,
                "delta_mrr": 0.0,
                "recommendation": "sin_casos",
            }
            continue
        base_eval = evaluar_lista_casos(
            [
                {
                    "id": c.get("id", ""),
                    "expected": c.get("expected", []),
                    "retrieved": _reordenar_candidatos(c.get("candidates", []), pesos_base),
                }
                for c in subcasos
            ],
            top_k=top_k,
        )
        prof_eval = evaluar_lista_casos(
            [
                {
                    "id": c.get("id", ""),
                    "expected": c.get("expected", []),
                    "retrieved": _reordenar_candidatos(c.get("candidates", []), perfil),
                }
                for c in subcasos
            ],
            top_k=top_k,
        )
        delta = round(prof_eval["mrr"] - base_eval["mrr"], 4)
        rec = "adoptar_perfil" if delta > 0 else ("mantener_base" if delta < 0 else "empate")
        resumen_intentos[intento] = {
            "cases": len(subcasos),
            "weights": dict(perfil),
            "baseline_mrr": base_eval["mrr"],
            "profile_mrr": prof_eval["mrr"],
            "baseline_recall_at_k": base_eval["recall_at_k"],
            "profile_recall_at_k": prof_eval["recall_at_k"],
            "delta_mrr": delta,
            "recommendation": rec,
        }

    return {
        "baseline_weights": dict(pesos_base),
        "perfiles_evaluados": resumen_intentos,
    }


def clasificar_estado_respuesta(envelope: Dict[str, Any]) -> str:
    """Distingue los 4 estados de fallo/degradación de una consulta de memoria.

    Estados posibles:
    - `read_error`: `ok` es False o hay error explícito de lectura/sistema.
    - `stale_index`: avisos indican índice obsoleto/desfasado (`stale` / `obsoleto`).
    - `truncated_budget`: hay notas devueltas pero al menos una fue recortada (`truncated`).
    - `empty`: respuesta válida sin notas ni resultados (y sin índice obsoleto).
    - `ok_complete`: respuesta válida con resultados completos sin recorte.
    """
    if not isinstance(envelope, dict) or envelope.get("ok") is False or envelope.get("error_code"):
        return "read_error"

    warnings = envelope.get("warnings") or envelope.get("avisos") or []
    if isinstance(warnings, list):
        for w in warnings:
            txt = str(w).lower()
            if "stale" in txt or "obsoleto" in txt or "desfasado" in txt or "sin estadísticas" in txt:
                return "stale_index"
    if envelope.get("index_stale") is True:
        return "stale_index"

    incluidas = envelope.get("included")
    notas = envelope.get("notes")
    resultados = envelope.get("results")
    if isinstance(incluidas, list) and incluidas:
        items = incluidas
    elif isinstance(notas, list) and notas:
        items = notas
    elif isinstance(resultados, list):
        items = resultados
    else:
        items = []
    if not items:
        return "empty"

    if (
        envelope.get("truncated") is True
        or bool(envelope.get("excluded"))
        or any(isinstance(n, dict) and n.get("truncated") is True for n in items)
    ):
        return "truncated_budget"
    return "ok_complete"


def banco_crud_escalado(
    raiz_base: Path,
    escalas: Iterable[int] = (100,),
    muestras_lectura: int = 20,
    escribir_fn: Optional[Callable[[Path, str, str], None]] = None,
    leer_fn: Optional[Callable[[Path, str], str]] = None,
    reindexar_fn: Optional[Callable[[Path], None]] = None,
    buscar_fn: Optional[Callable[[Path, str, str], int]] = None,
) -> Dict[str, Any]:
    """Mide p50/p95 ms de create, read, update, reindex y search (`pesos`/`bm25`) por escala."""
    raiz_base = Path(raiz_base)
    resultados: List[Dict[str, Any]] = []

    for total in escalas:
        n = max(1, int(total))
        vdir = raiz_base / f"scale-{n}"
        for carpeta in ("00_System", "07_Knowledge", "99_Index"):
            (vdir / carpeta).mkdir(parents=True, exist_ok=True)

        m_create: List[float] = []
        rutas_creadas: List[str] = []
        t_creacion_ini = time.perf_counter()
        for i in range(n):
            rel = f"07_Knowledge/nota-{i:05d}.md"
            tema = f"modulo-{i % 25}"
            contenido = textwrap.dedent(
                f"""\
                ---
                title: Nota sintetica {i:05d} {tema}
                type: knowledge
                status: active
                tags: [{tema}, escala-{n}]
                cia_integrity: medium
                updatedAt: 2026-11-23T12:00:00Z
                ---

                # Nota sintetica {i:05d} {tema}

                Documento reproducible del banco CRUD para {tema} con clave unica token_{i:05d}.
                """
            )
            t0 = time.perf_counter()
            if escribir_fn is not None:
                escribir_fn(vdir, rel, contenido)
            else:
                (vdir / rel).write_text(contenido, encoding="utf-8")
            m_create.append((time.perf_counter() - t0) * 1000.0)
            rutas_creadas.append(rel)
        creacion_total_ms = round((time.perf_counter() - t_creacion_ini) * 1000.0, 2)

        t_idx0 = time.perf_counter()
        if reindexar_fn is not None:
            reindexar_fn(vdir)
        reindex_ms = round((time.perf_counter() - t_idx0) * 1000.0, 2)

        paso = max(1, n // max(1, int(muestras_lectura)))
        muestra_indices = list(range(0, n, paso))[: max(1, int(muestras_lectura))]

        m_read: List[float] = []
        for idx in muestra_indices:
            t0 = time.perf_counter()
            if leer_fn is not None:
                leer_fn(vdir, rutas_creadas[idx])
            else:
                (vdir / rutas_creadas[idx]).read_text(encoding="utf-8")
            m_read.append((time.perf_counter() - t0) * 1000.0)

        m_update: List[float] = []
        for idx in muestra_indices:
            rel = rutas_creadas[idx]
            texto_upd = (vdir / rel).read_text(encoding="utf-8") + "\nActualizacion verificada.\n"
            t0 = time.perf_counter()
            if escribir_fn is not None:
                escribir_fn(vdir, rel, texto_upd)
            else:
                (vdir / rel).write_text(texto_upd, encoding="utf-8")
            m_update.append((time.perf_counter() - t0) * 1000.0)

        m_pesos: List[float] = []
        m_bm25: List[float] = []
        if buscar_fn is not None:
            for idx in muestra_indices[:10]:
                q = f"token_{idx:05d} modulo-{idx % 25}"
                t0 = time.perf_counter()
                buscar_fn(vdir, q, "pesos")
                m_pesos.append((time.perf_counter() - t0) * 1000.0)
                t1 = time.perf_counter()
                buscar_fn(vdir, q, "bm25")
                m_bm25.append((time.perf_counter() - t1) * 1000.0)

        idx_file = vdir / "99_Index" / "search-index.json"
        index_bytes = idx_file.stat().st_size if idx_file.is_file() else 0

        resultados.append({
            "notes": n,
            "create_total_ms": creacion_total_ms,
            "reindex_ms": reindex_ms,
            "search_index_bytes": index_bytes,
            "create": _resumen_latencias(m_create),
            "read": _resumen_latencias(m_read),
            "update": _resumen_latencias(m_update),
            "search_pesos": _resumen_latencias(m_pesos),
            "search_bm25": _resumen_latencias(m_bm25),
        })

    return {"scales": resultados}


__all__ = [
    "PERFILES_INTENTO",
    "evaluar_lista_casos",
    "comparar_pesos_y_bm25",
    "calibrar_pesos_por_intento",
    "clasificar_estado_respuesta",
    "banco_crud_escalado",
]

"""Motor de Ingeniería de Contexto, Compactación Adaptativa y Recordatorios JIT (SPEC-06).

Hoja pura del núcleo (`vault.kernel`, 0 dependencias de dominio, 0 BD, 0 terceros).
Sirve ambos modos de integración sin acoplar el estándar a un cliente único:

- **Modo A — Harness Nativo:** el loop de un agente importa directamente
  `evaluar_presion_contexto`, `compactar_observaciones` y `evaluar_triggers_jit`
  para administrar la ventana de tokens como memoria finita de SO e inyectar
  recordatorios breves con `role="user"` antes de cada inferencia.
- **Modo B — Standalone (CLI / MCP):** las tools de consulta y la voz del vault
  usan estas mismas primitivas para externalizar (*offload*) respuestas pesadas
  a punteros compactos `~15 tokens` bajo `00_System/context-offload/` (AP-36) y
  emitir recordatorios JIT por eventos en `vault_says`.

Enforcea de forma determinista las normas **AP-81** (saturación de contexto sin
presupuesto ni offloading) y **SP-07** (compactación adaptativa en 5 umbrales y
recordatorios JIT acotados).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "HARD_CAPS_CONTEXTO",
    "NIVELES_COMPACTACION",
    "UMBRALES_COMPACTACION",
    "compactar_observaciones",
    "estimar_tokens",
    "evaluar_presion_contexto",
    "evaluar_triggers_jit",
    "offload_texto_a_puntero",
]

#: Escalera de 5 umbrales de presión de ventana (SPEC-06 / OpenDev).
UMBRALES_COMPACTACION: Tuple[Tuple[int, float, str], ...] = (
    (1, 0.70, "telemetria"),
    (2, 0.80, "enmascarado"),
    (3, 0.85, "poda_rapida"),
    (4, 0.90, "enmascarado_agresivo"),
    (5, 0.99, "compactacion_completa"),
)

NIVELES_COMPACTACION: Dict[int, str] = {
    0: "normal",
    **{nivel: nombre for nivel, _, nombre in UMBRALES_COMPACTACION},
}

#: Topes estrictos sobre toda estructura que crece con la duración de la sesión (SP-07 / AP-81).
HARD_CAPS_CONTEXTO: Dict[str, int] = {
    "max_inline_tool_tokens": 1200,
    "max_retained_observations": 24,
    "max_active_jit_reminders": 3,
    "max_undo_stack": 50,
    "max_parallel_tool_results": 8,
    "keep_recent_level_2": 6,
    "keep_recent_level_3": 4,
    "keep_recent_level_4": 2,
    "keep_recent_level_5": 4,
}


def estimar_tokens(texto: str) -> int:
    """Estimación determinista y conservadora (~4 chars/token) sin dependencias externas."""
    if not texto:
        return 0
    return max(1, (len(texto) + 3) // 4)


def evaluar_presion_contexto(
    tokens_usados: int,
    ventana_maxima: int,
    historial_tokens: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """Calcula ocupación, nivel de compactación (0..5) y tasa de crecimiento por turno.

    AP-81 / SP-07: el contexto se evalúa como presupuesto finito en cada turno,
    no solo cuando la ventana ya colapsó.
    """
    if ventana_maxima <= 0:
        raise ValueError("ventana_maxima debe ser > 0")
    usados = max(0, int(tokens_usados))
    ratio = usados / float(ventana_maxima)

    nivel = 0
    estrategia = "normal"
    for n, umbral, nombre in UMBRALES_COMPACTACION:
        if ratio >= umbral:
            nivel = n
            estrategia = nombre

    tasa_crecimiento = 0.0
    if historial_tokens and len(historial_tokens) >= 2:
        deltas = [
            int(historial_tokens[i]) - int(historial_tokens[i - 1])
            for i in range(1, len(historial_tokens))
        ]
        tasa_crecimiento = round(sum(deltas) / len(deltas), 2)

    return {
        "tokens_used": usados,
        "window_max": int(ventana_maxima),
        "occupancy_ratio": round(ratio, 4),
        "occupancy_pct": round(ratio * 100.0, 2),
        "level": nivel,
        "strategy": estrategia,
        "growth_tokens_per_turn": tasa_crecimiento,
        "norm_refs": ["AP-81", "SP-07"],
    }


def offload_texto_a_puntero(
    contenido: str,
    *,
    etiqueta: str = "tool_output",
    offload_dir: Optional[Path] = None,
    vault_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Externaliza una observación pesada a disco y devuelve un puntero compacto (~15 tokens).

    Cumple AP-36: si se entrega `offload_dir` y `vault_root`, valida que el
    destino permanezca estrictamente dentro del vault antes de escribir.
    """
    digest = hashlib.sha256(contenido.encode("utf-8", errors="replace")).hexdigest()[:12]
    tokens_orig = estimar_tokens(contenido)
    ref_rel = f"00_System/context-offload/{etiqueta}-{digest}.txt"
    escrito = False

    if offload_dir is not None:
        destino_dir = Path(offload_dir).resolve()
        if vault_root is not None:
            raiz = Path(vault_root).resolve()
            if not destino_dir.is_relative_to(raiz):
                raise ValueError(f"AP-36: offload_dir fuera del vault: {destino_dir}")
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / f"{etiqueta}-{digest}.txt"
        tmp = destino.with_suffix(".txt.tmp")
        tmp.write_text(contenido, encoding="utf-8")
        tmp.replace(destino)
        escrito = True
        if vault_root is not None:
            ref_rel = destino.relative_to(Path(vault_root).resolve()).as_posix()
        else:
            ref_rel = destino.name

    puntero = f"[offload:{digest} {tokens_orig}t -> {ref_rel}]"
    return {
        "offload_id": digest,
        "pointer": puntero,
        "pointer_tokens": estimar_tokens(puntero),
        "original_tokens": tokens_orig,
        "saved_tokens": max(0, tokens_orig - estimar_tokens(puntero)),
        "ref": ref_rel,
        "written": escrito,
    }


def compactar_observaciones(
    observaciones: Sequence[Dict[str, Any]],
    *,
    tokens_usados: int,
    ventana_maxima: int,
    offload_dir: Optional[Path] = None,
    vault_root: Optional[Path] = None,
    historial_tokens: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """Aplica la escalera adaptativa de 5 umbrales sobre las observaciones de sesión.

    Cada observación es un dict `{id, tool, content}` (opcionalmente ya marcada
    con `masked: True`). Aplica AP-81 / SP-07 de forma determinista y sin LLM:
    - Nivel 0 (<70%) y Nivel 1 (70%): sin mutar contenido (solo telemetría).
    - Nivel 2 (80%): enmascara salidas antiguas fuera de los últimos 6 turnos
      con punteros compactos ~15 tokens (con offloading en disco si se provee dir).
    - Nivel 3 (85%): poda rápida (elimina observaciones antiguas fuera de los
      últimos 4 turnos sin llamada a LLM).
    - Nivel 4 (90%): enmascarado agresivo reteniendo solo los últimos 2 turnos.
    - Nivel 5 (99%): vuelca el historial íntegro a archivo externo, sintetiza
      el tramo central en un bloque determinista y preserva literales los
      últimos 4 turnos.
    """
    presion = evaluar_presion_contexto(tokens_usados, ventana_maxima, historial_tokens)
    nivel = presion["level"]
    items = [dict(o) for o in observaciones]

    # Hard cap de observaciones retenidas en ventana (AP-81)
    cap = HARD_CAPS_CONTEXTO["max_retained_observations"]
    if len(items) > cap and nivel < 3:
        items = items[-cap:]

    if nivel <= 1:
        return {
            "ok": True,
            "pressure": presion,
            "observations": items,
            "masked_count": 0,
            "pruned_count": 0,
            "full_dump_ref": None,
            "tokens_saved": 0,
        }

    masked_count = 0
    pruned_count = 0
    tokens_saved = 0
    full_dump_ref: Optional[str] = None

    if nivel == 2:
        keep = HARD_CAPS_CONTEXTO["keep_recent_level_2"]
        corte = max(0, len(items) - keep)
        salida: List[Dict[str, Any]] = []
        for idx, item in enumerate(items):
            if idx < corte and not item.get("masked"):
                texto = str(item.get("content", ""))
                off = offload_texto_a_puntero(
                    texto,
                    etiqueta=str(item.get("tool", "obs")),
                    offload_dir=offload_dir,
                    vault_root=vault_root,
                )
                salida.append({
                    **item,
                    "content": off["pointer"],
                    "masked": True,
                    "offload_ref": off["ref"],
                })
                masked_count += 1
                tokens_saved += off["saved_tokens"]
            else:
                salida.append(item)
        items = salida

    elif nivel == 3:
        keep = HARD_CAPS_CONTEXTO["keep_recent_level_3"]
        corte = max(0, len(items) - keep)
        for item in items[:corte]:
            tokens_saved += estimar_tokens(str(item.get("content", "")))
        pruned_count = corte
        items = items[corte:]

    elif nivel == 4:
        keep = HARD_CAPS_CONTEXTO["keep_recent_level_4"]
        corte = max(0, len(items) - keep)
        salida = []
        for idx, item in enumerate(items):
            if idx < corte:
                texto = str(item.get("content", ""))
                off = offload_texto_a_puntero(
                    texto,
                    etiqueta=str(item.get("tool", "obs")),
                    offload_dir=offload_dir,
                    vault_root=vault_root,
                )
                salida.append({
                    "id": item.get("id", f"obs-{idx}"),
                    "tool": item.get("tool", "obs"),
                    "content": off["pointer"],
                    "masked": True,
                    "offload_ref": off["ref"],
                })
                masked_count += 1
                tokens_saved += off["saved_tokens"]
            else:
                salida.append(item)
        items = salida

    else:  # nivel == 5 (>= 99%)
        bruto_json = json.dumps(items, ensure_ascii=False, indent=2)
        dump = offload_texto_a_puntero(
            bruto_json,
            etiqueta="session-full-dump",
            offload_dir=offload_dir,
            vault_root=vault_root,
        )
        full_dump_ref = dump["ref"]
        keep = HARD_CAPS_CONTEXTO["keep_recent_level_5"]
        corte = max(0, len(items) - keep)
        antiguos = items[:corte]
        recientes = items[corte:]
        herramientas = sorted({str(o.get("tool", "obs")) for o in antiguos})
        resumen_central = (
            f"[compactacion_completa: {len(antiguos)} observaciones resumidas; "
            f"tools={','.join(herramientas) or 'none'}; "
            f"historial_integro={full_dump_ref}]"
        )
        tokens_antiguos = sum(estimar_tokens(str(o.get("content", ""))) for o in antiguos)
        tokens_saved = max(0, tokens_antiguos - estimar_tokens(resumen_central))
        pruned_count = len(antiguos)
        items = (
            [{"id": "compaction-summary", "tool": "context_engine", "content": resumen_central, "masked": True}]
            if antiguos
            else []
        ) + recientes

    return {
        "ok": True,
        "pressure": presion,
        "observations": items,
        "masked_count": masked_count,
        "pruned_count": pruned_count,
        "full_dump_ref": full_dump_ref,
        "tokens_saved": tokens_saved,
    }


def evaluar_triggers_jit(
    eventos: Iterable[Dict[str, Any]],
    *,
    max_activos: Optional[int] = None,
) -> Dict[str, Any]:
    """Evalúa disparadores de sesión y genera recordatorios JIT deduplicados (SP-07).

    Detecta tres estados críticos en tiempo de ejecución:
    - `tool_error`: fallo reciente de herramienta → comprobar contrato/rollback.
    - `consecutive_reads >= 5`: ráfaga de lecturas sin escritura → consolidar o pasar a acción.
    - `post_code_edit`: edición de código pendiente de verificación → ejecutar tests.

    Emite cada directiva con `role="user"` (Modo A Harness Nativo) y texto
    compacto compatible con `vault_says` (Modo B Standalone), acotado a
    `max_activos` para evitar saturar el presupuesto de contexto (AP-81).
    """
    tope = int(max_activos if max_activos is not None else HARD_CAPS_CONTEXTO["max_active_jit_reminders"])
    lista = [dict(e) for e in eventos]
    lecturas_seguidas = 0
    hubo_error = False
    hubo_edit_sin_test = False

    for ev in lista:
        tipo = str(ev.get("type") or ev.get("kind") or "").lower()
        if tipo in ("tool_error", "error"):
            hubo_error = True
        elif tipo in ("read", "search", "grep", "glob"):
            lecturas_seguidas += 1
        elif tipo in ("code_edit", "write", "edit"):
            lecturas_seguidas = 0
            hubo_edit_sin_test = True
        elif tipo in ("test_pass", "tests_run", "verify"):
            lecturas_seguidas = 0
            hubo_edit_sin_test = False

    candidatos: List[Dict[str, str]] = []
    if hubo_error:
        candidatos.append({
            "trigger": "tool_error",
            "role": "user",
            "message": "[Recordatorio operativo: una herramienta falló; verifica el error_code y el estado antes de reintentar.]",
        })
    if hubo_edit_sin_test:
        candidatos.append({
            "trigger": "post_code_edit",
            "role": "user",
            "message": "[Recordatorio operativo: acabas de editar código; ejecuta la suite de tests afectada y las puertas rápidas antes de cerrar.]",
        })
    if lecturas_seguidas >= 5:
        candidatos.append({
            "trigger": "consecutive_reads",
            "role": "user",
            "message": f"[Recordatorio operativo: llevas {lecturas_seguidas} lecturas seguidas sin avanzar; consolida hallazgos o usa vault_subgraph --report/--explain.]",
        })

    # Deduplicar por trigger y aplicar hard cap
    vistos = set()
    finales: List[Dict[str, str]] = []
    for item in candidatos:
        if item["trigger"] in vistos:
            continue
        vistos.add(item["trigger"])
        finales.append(item)
        if len(finales) >= max(0, tope):
            break

    return {
        "ok": True,
        "reminders": finales,
        "active_count": len(finales),
        "cap": max(0, tope),
        "consecutive_reads": lecturas_seguidas,
        "norm_refs": ["SP-07", "AP-81"],
    }

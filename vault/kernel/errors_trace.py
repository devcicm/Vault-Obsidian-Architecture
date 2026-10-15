#!/usr/bin/env python3
"""vault_errors_trace — Trace log + token usage logging for vault tools.

Importado por vault_errors.py. No debe importar vault_errors (circular).
"""

import contextvars
import json
import re as _re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

# v40.17 — se pide el mecanismo a las hojas, no el módulo de IO entero.
#
# Este fichero declara desde siempre «no debe importar vault_errors (circular)»,
# y sin embargo cerraba el ciclo por el otro lado: `vault_io` importa
# `vault_encoding`, que llama a `vault_errors.log_trace`, que importa este
# módulo. El aviso del docstring señalaba la arista visible y no la que había.
#
# `escritura_atomica` con `guarda_secretos` conserva exactamente lo que hacía
# `atomic_write_text(..., sanitize=False)` sobre este fichero: el escaneo de
# secretos sigue corriendo. Lo que se deja fuera —saneado de codificación,
# ledger, índice de sección, vocabulario de tags— no aplicaba a un JSON generado
# aquí mismo dentro de `00_System/`, y era justamente lo que arrastraba el ciclo.
from vault_fs import escritura_atomica, file_lock, guarda_secretos
from vault_raiz import escritura_admitida, get_vault_root


# AP-36: los paths se resuelven LAZY vía get_vault_root() en cada llamada, para
# que un tool ejecutado con --root (que llama vault_io.set_vault_root) escriba
# sus traces en el vault objetivo y no en el VAULT_ROOT detectado en import.
def trace_file() -> Path:
    return get_vault_root() / "00_System" / ".tool-trace.json"


#: El contador de tokens es del kernel: aquí se anota y aquí se reinicia (deuda
#: #3, residuo, 2026-10-08). Hasta esa fecha lo declaraba Consulta, que solo lo
#: lee y lo reiniciaba; `vault.consulta.repositorio.FICHERO_TOKENS` lo reexporta.
FICHERO_TOKENS = ".tool-tokens.json"


def tokens_file() -> Path:
    return get_vault_root() / "00_System" / FICHERO_TOKENS


def reiniciar_tokens() -> bool:
    """Borra el contador; True si había uno. Lo pide `vault_tokens --reset`."""
    tkf = tokens_file()
    if not tkf.exists():
        return False
    tkf.unlink()
    return True


TRACE_MAX_ENTRIES = 500
TOKENS_MAX_ENTRIES = 2000


#: Entradas acumuladas dentro de `trazas_en_lote`; `None` fuera de un lote.
_LOTE: "contextvars.ContextVar[Optional[List[Dict[str, Any]]]]" = contextvars.ContextVar(
    "errors_trace_lote", default=None)


@contextmanager
def trazas_en_lote() -> Iterator[None]:
    """Acumula las entradas de `log_trace` y las escribe una vez al salir (AP-47).

    Medido el 2026-10-14 con cProfile en una copia de /ans: tras poner en lote
    el índice de sección y el grafo, 47,6 de los 103 s de
    `vault_frontmatter_completar --apply` eran 191 llamadas a `log_trace`
    —las de `log_encoding_fixes`—: cada una relee hasta `TRACE_MAX_ENTRIES`,
    reescribe el fichero entero y le pasa el escáner de secretos. Al salir
    —también por excepción— las entradas se añaden en una sola escritura con
    la misma rotación. Mientras dura el lote, `query_trace` no las ve todavía.

    Un lote anidado no escribe nada: lo cierra el de fuera.
    """
    if _LOTE.get() is not None:
        yield
        return
    pendientes: List[Dict[str, Any]] = []
    token = _LOTE.set(pendientes)
    try:
        yield
    finally:
        _LOTE.reset(token)
        if pendientes:
            log_trace(*pendientes)


def _append_trace_entry(nuevas: List[Dict[str, Any]], use_atomic: bool) -> None:
    """Lee, rota y escribe el trace file con `nuevas` añadidas: una escritura.

    Recibe una lista desde `trazas_en_lote`: fuera de un lote es de una entrada.
    """
    tf = trace_file()
    if tf.exists():
        try:
            entries: List[Dict] = json.loads(tf.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except Exception:
            # AP-37 fail-safe: corrupt trace file — start fresh.
            # Cannot call emit_error here (circular import with vault_errors).
            entries = []
    else:
        entries = []

    entries.extend(nuevas)
    if len(entries) > TRACE_MAX_ENTRIES:
        entries = entries[-TRACE_MAX_ENTRIES:]

    text = json.dumps(entries, indent=2, ensure_ascii=False)
    if use_atomic:
        # `sanitize=False` NO es una optimización: es lo que corta un bucle que
        # se alimenta solo. El saneado de `atomic_write_text` llama a
        # `log_encoding_fixes` cuando aplica algún arreglo, y eso llama a
        # `log_trace`, que vuelve a escribir ESTE fichero, que vuelve a
        # sanearse. Medido en un solo `vault_risk_save`: 196 escrituras del
        # trace donde debía haber una.
        #
        # Estuvo latente porque el camino que lo dispara —el lock reentrante—
        # antes fallaba y caía a la rama sin saneado, que rompía el ciclo por
        # accidente. Al arreglar la reentrancia (v40.7) el bucle quedó al
        # descubierto. Además el trace es JSON generado aquí mismo: no hay
        # nada que sanear que no hayamos escrito nosotros.
        escritura_atomica(tf, text, guardas=(guarda_secretos,))
    else:
        tf.write_text(text, encoding="utf-8")


def log_trace(entry: Dict[str, Any], *mas: Dict[str, Any]) -> None:
    """Añade entrada al trace log con rotación a TRACE_MAX_ENTRIES.

    `mas` son entradas que van en la misma escritura: las pasa el cierre de
    `trazas_en_lote`. Dentro de un lote solo se apuntan; las escribe el cierre.
    """
    pendientes = _LOTE.get()
    if pendientes is not None:
        pendientes.extend((entry, *mas))
        return
    entradas = [entry, *mas]
    try:
        tf = trace_file()
        # AP-36: con la raíz adivinada la traza no se deposita. Es observabilidad
        # best-effort y su destino sería el propio paquete instalado.
        if not escritura_admitida(tf):
            return
        tf.parent.mkdir(parents=True, exist_ok=True)
        try:
            with file_lock(tf, timeout=5):
                _append_trace_entry(entradas, use_atomic=True)
        except TimeoutError:
            # Se DESCARTA la entrada. Antes caía a
            # `_append_trace_entry(use_atomic=False)`, que escribe el fichero de
            # trazas sin lock — precisamente mientras quien sí lo tiene lo está
            # reemplazando. Perder una línea de observabilidad best-effort es
            # barato; corromper el fichero donde se investigan los fallos, no.
            #
            # El caso que lo disparaba en masa era la reentrancia del mismo
            # hilo, ya resuelta en `vault_io.file_lock`. Lo que queda aquí es
            # contención real entre hilos, donde descartar es la respuesta
            # correcta y no un parche.
            pass
    except Exception:
        pass  # AP-37: fail-safe — thread contention, discard is correct


def query_trace(
    tool: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    last: int = 20,
) -> List[Dict[str, Any]]:
    """Consulta el trace log."""
    tf = trace_file()
    if not tf.exists():
        return []
    try:
        entries: List[Dict] = json.loads(tf.read_text(encoding="utf-8"))
    except Exception:
        # AP-51: caller cannot distinguish corrupt file from empty.
        # Cannot call emit_error here due to circular import with vault_errors.
        # The degradation is logged via stderr as last resort.
        return []
    if tool:
        entries = [e for e in entries if e.get("tool") == tool]
    if severity:
        entries = [e for e in entries if e.get("severity") == severity]
    if category:
        entries = [e for e in entries if e.get("category") == category]
    return list(reversed(entries))[:last]


def _count_tokens(text: str) -> Tuple[int, str]:
    """Count tokens using best available tokenizer (anthropic → tiktoken → heuristic)."""
    if not text:
        return 0, "heuristic"

    try:
        import anthropic

        client = anthropic.Anthropic(api_key="dummy")
        count = client.count_tokens(text)
        return count, "anthropic"
    except Exception:
        pass  # AP-37: fallback chain — try next tokenizer

    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text)), "tiktoken"
    except Exception:
        pass  # AP-37: fallback chain — try heuristic

    pieces = _re.findall(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", text)
    total = sum(
        max(1, (len(p) + 3) // 4) if _re.match(r"^[A-Za-z0-9_]+$", p) else 1
        for p in pieces
    )
    return max(1, total), "heuristic"


def log_token_usage(tool: str, input_text: str, output_text: str) -> None:
    """Record token usage to .tool-tokens.json."""
    try:
        in_tokens, provider = _count_tokens(input_text)
        out_tokens, _ = _count_tokens(output_text)
        entry = {
            "tool": tool,
            "timestamp": datetime.now(timezone.utc).isoformat()[:19] + "Z",
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "total_tokens": in_tokens + out_tokens,
            "provider": provider,
        }
        tkf = tokens_file()
        tkf.parent.mkdir(parents=True, exist_ok=True)
        if tkf.exists():
            try:
                entries: List[Dict] = json.loads(tkf.read_text(encoding="utf-8"))
                if not isinstance(entries, list):
                    entries = []
            except Exception:
                # AP-37 fail-safe: corrupt token log — start fresh, preserve new entry.
                entries = []
        else:
            entries = []
        entries.append(entry)
        if len(entries) > TOKENS_MAX_ENTRIES:
            entries = entries[-TOKENS_MAX_ENTRIES:]
        tkf.write_text(
            json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass  # AP-37: fail-safe — never crash caller on token log write failure

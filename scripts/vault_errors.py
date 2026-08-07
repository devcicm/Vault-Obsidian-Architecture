#!/usr/bin/env python3
"""
vault_errors.py — Observabilidad y trazabilidad centralizada para vault tools.

Uso en cualquier tool:
    from vault_errors import wrap_main, emit_error

    def main():
        # ... lógica ...
        if algo_falla:
            print(json.dumps(emit_error("vault_write", "VAULT_NOT_FOUND",
                                         "Vault root no existe")))
            sys.exit(1)

    if __name__ == "__main__":
        sys.exit(wrap_main(main, "vault_write"))

Componentes (split D2):
  vault_errors_catalog.py — ERROR_CATALOG con metadata + recovery hints
  vault_errors_trace.py   — log_trace, query_trace, log_token_usage
"""

import io
import json
import os
import queue
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

# La configuración se lee del registro único, no con un default por punto
# de uso. Ver `vault_entorno.py`.
from vault_entorno import leer as _env
from typing import Any, Callable, Dict, List, Optional

from vault_errors_catalog import ERROR_CATALOG, get_error
from vault_errors_trace import log_trace, log_token_usage

TOOL_TIMEOUT_SECONDS: int = _env("VAULT_TOOL_TIMEOUT")


def emit_error(
    tool: str,
    code: str,
    message: str = None,
    args: Dict[str, Any] = None,
    exception: Exception = None,
) -> Dict[str, Any]:
    """Construye error estructurado y lo registra en el trace log."""
    catalog_entry = get_error(code)
    entry = {
        "ok": False,
        "tool": tool,
        "error_code": code,
        "category": catalog_entry["category"],
        "severity": catalog_entry["severity"],
        "message": message or catalog_entry["message"],
        "recovery": catalog_entry["recovery"],
        "timestamp": datetime.now(timezone.utc).isoformat()[:19] + "Z",
    }
    if args:
        entry["args"] = args
    if exception:
        entry["traceback"] = traceback.format_exc()
    log_trace(entry)
    return entry


def emit_ok(tool: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Produce envelope de éxito uniforme y registra en trace log."""
    result = {
        "ok": True,
        "tool": tool,
        "timestamp": datetime.now(timezone.utc).isoformat()[:19] + "Z",
        **data,
    }
    log_trace(result)
    return result


def _inject_voice(data: Any, tool_name: str, writes: Optional[Dict[str, int]]) -> None:
    """AP-43 — añade `vault_says` al resultado. Nunca puede romper la tool.

    Se hace aquí y no en cada tool porque este es el único punto por el que ya
    pasa la salida de las 97 tools: una capa de refuerzo que hubiera que
    invocar tool por tool sería exactamente el registro-que-nadie-consume que
    esta norma existe para evitar.
    """
    if not isinstance(data, dict) or "vault_says" in data:
        return
    try:
        from vault_voice import speak

        bloque = speak(tool_name, data, writes)
        if bloque:
            data["vault_says"] = bloque
    except Exception:
        pass


def _inject_tool_envelope(
    text: str, tool_name: str, writes: Optional[Dict[str, int]] = None
) -> str:
    """Inyecta tool+timestamp en el JSON de salida si aún no los tiene."""
    text = text.strip()
    if not text:
        return text
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("ok") is True and "tool" not in data:
            data["tool"] = tool_name
            data["timestamp"] = datetime.now(timezone.utc).isoformat()[:19] + "Z"
            log_trace(data)
        _inject_voice(data, tool_name, writes)
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return text


def _write_output(text: str, stdout_ref=None) -> None:
    """Escribe texto a stdout con soporte de buffer para UTF-8."""
    target = stdout_ref or sys.stdout
    try:
        buf = getattr(target, "buffer", None)
        if buf:
            buf.write((text + "\n").encode("utf-8"))
            buf.flush()
        else:
            print(text, file=target)
    except Exception:
        try:
            print(text)
        except Exception:
            pass


def wrap_main(fn: Callable, tool_name: str, timeout: int = None) -> int:
    """Envuelve main() con timeout, captura de excepciones, y trace log.

    Args:
        fn: Función main() a ejecutar
        tool_name: Nombre de la tool (para logs)
        timeout: Segundos máximo (default: TOOL_TIMEOUT_SECONDS)

    Returns: exit code (0 = éxito, 1 = error)
    """
    limit = timeout if timeout is not None else TOOL_TIMEOUT_SECONDS

    def _run():
        try:
            result = fn()
            if result is None:
                return 0
            return int(result)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (1 if e.code else 0)
            return code

    _real_stdout = sys.stdout
    result_q: queue.Queue = queue.Queue()

    def _writes() -> Dict[str, int]:
        """El ledger AP-37 es thread-local: hay que leerlo en ESTE hilo."""
        try:
            from vault_io import write_report

            return write_report()
        except Exception:
            return {}

    def _target():
        captured = io.StringIO()
        sys.stdout = captured
        # AP-37: el contador de escrituras es thread-local y la tool corre en
        # ESTE hilo, así que se pone a cero aquí — no en wrap_main, que se
        # ejecuta en el hilo principal y no vería el mismo ledger.
        try:
            from vault_io import write_ledger_reset

            write_ledger_reset()
        except Exception:
            pass
        try:
            exit_code = _run()
            result_q.put(("ok", exit_code, captured.getvalue(), _writes()))
        except Exception as exc:
            result_q.put(("exc", exc, captured.getvalue(), _writes()))
        finally:
            sys.stdout = _real_stdout

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout=limit)

    if t.is_alive():
        err = emit_error(
            tool=tool_name,
            code="TOOL_TIMEOUT",
            message=f"La tool '{tool_name}' excedio el limite de {limit}s y fue terminada.",
        )
        _write_output(json.dumps(err, ensure_ascii=False), _real_stdout)
        return 1

    try:
        kind, value, captured_text, writes = result_q.get_nowait()
    except queue.Empty:
        return 1

    if kind == "exc":
        err = emit_error(
            tool=tool_name,
            code="UNEXPECTED_ERROR",
            message=f"{type(value).__name__}: {value}",
            exception=value,
        )
        _inject_voice(err, tool_name, writes)
        _write_output(json.dumps(err, ensure_ascii=False), _real_stdout)
        return 1

    output = _inject_tool_envelope(captured_text, tool_name, writes)
    if output:
        _write_output(output, _real_stdout)

    if _env("VAULT_COUNT_TOKENS"):
        input_text = " ".join(sys.argv)
        log_token_usage(tool_name, input_text, captured_text)

    return value


def _main():
    """CLI standalone: consulta trace log y catálogo de errores."""
    import argparse

    parser = argparse.ArgumentParser(
        description="vault_errors — Consulta el trace log y el catálogo de errores",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_errors.py query --last 10
  python vault_errors.py query --tool vault_write --severity error
  python vault_errors.py query --category governance
  python vault_errors.py catalog
  python vault_errors.py catalog --code AP21_PATH_WIKILINKS
""",
    )
    parser.add_argument("command", choices=["query", "catalog"], help="Comando")
    parser.add_argument("--tool", "-t", help="Filtrar por tool")
    parser.add_argument(
        "--severity",
        "-s",
        choices=["critical", "error", "warning"],
        help="Filtrar por severity",
    )
    parser.add_argument("--category", "-c", help="Filtrar por categoría")
    parser.add_argument("--last", "-l", type=int, default=20, help="Últimas N entradas")
    parser.add_argument(
        "--code", "-k", help="Código de error específico (para catalog)"
    )
    args = parser.parse_args()

    if args.command == "query":
        from vault_errors_trace import query_trace

        results = query_trace(
            tool=args.tool,
            severity=args.severity,
            category=args.category,
            last=args.last,
        )
        print(
            json.dumps(
                {"ok": True, "count": len(results), "entries": results},
                indent=2,
                ensure_ascii=False,
            )
        )
    elif args.command == "catalog":
        if args.code:
            entry = ERROR_CATALOG.get(args.code)
            if entry:
                print(
                    json.dumps(
                        {"ok": True, "code": args.code, **entry},
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            else:
                print(
                    json.dumps(
                        {"ok": False, "error": f"Código '{args.code}' no encontrado"}
                    )
                )
        else:
            catalog = {
                code: {**data, "code": code} for code, data in ERROR_CATALOG.items()
            }
            print(
                json.dumps(
                    {"ok": True, "count": len(catalog), "catalog": catalog},
                    indent=2,
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    sys.exit(wrap_main(_main, "vault_errors"))

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


class VaultWriteError(Exception):
    """Error de escritura con código de catálogo conocido.

    Permite a vault_io.atomic_write_text() emitir un error específico
    (DISK_FULL, PERMISSION_DENIED) sin血行 un Exception genérico que
    wrap_main convertiría en UNEXPECTED_ERROR.
    """

    def __init__(self, error_code: str, message: str) -> None:
        self.error_code = error_code
        self.message = message
        super().__init__(message)


def _map_exception_to_code(e: BaseException) -> str:
    """Mapea excepciones Python comunes a códigos del catálogo.

    Evita que PermissionError, OSError y MemoryError caigan en
    UNEXPECTED_ERROR sin distinguir. Añadir aquí cuando se descubra
    una excepción que el consumidor necesita identificar.
    """
    if isinstance(e, PermissionError):
        return "PERMISSION_DENIED"
    if isinstance(e, OSError):
        import errno
        if e.errno == errno.ENOSPC:
            return "DISK_FULL"
        if e.errno == errno.EACCES:
            return "PERMISSION_DENIED"
        if e.errno == errno.ENOENT:
            return "FILE_NOT_FOUND"
    if isinstance(e, FileNotFoundError):
        return "FILE_NOT_FOUND"
    if isinstance(e, IsADirectoryError):
        return "INVALID_PATH"
    if isinstance(e, NotADirectoryError):
        return "INVALID_PATH"
    if isinstance(e, MemoryError):
        return "MEMORY_ERROR"
    if isinstance(e, RecursionError):
        return "FRONTMATTER_PARSE_ERROR"
    if isinstance(e, KeyboardInterrupt):
        return "INTERRUPTED"
    if isinstance(e, (GeneratorExit, SystemExit)):
        return "UNEXPECTED_ERROR"
    return "UNEXPECTED_ERROR"


MEMORY_ERROR: Dict[str, Any] = {
    "category": "infrastructure",
    "severity": "critical",
    "message": "Memoria agotada durante la ejecución de la tool.",
    "recovery": {
        "action": "manual",
        "hint": "Reducir el alcance de la operación: menos archivos, batches más pequeños. Verificar que no hay fuga de memoria en procesos hijos.",
        "docs": None,
    },
}


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


#: Causa del dominio -> código del catálogo. La otra mitad de la frase que
#: `vault/kernel/fallos.py` empieza: allí se nombra **qué pasó**, aquí **qué
#: puede hacer el consumidor**.
#:
#: Vive en un solo sitio a propósito. La misma tabla repartida entre
#: `vault_folder_registry`, `vault_backup` y `vault_restore` sería AP-57
#: cometido justo al saldar AP-52: tres adaptadores decidiendo por su cuenta
#: qué código le toca a una causa que no es suya. Un test comprueba que cubre
#: `fallos.CAUSAS` entera y que ningún destino falta del `ERROR_CATALOG`.
#:
#: Que tres causas del manifiesto compartan destino no pierde información: la
#: causa exacta viaja en el campo `causa` del envelope. El catálogo dice cómo se
#: recupera, y de las tres se recupera igual.
MAPA_DE_FALLOS: Dict[str, str] = {
    "CARPETA_YA_REGISTRADA": "INVALID_FOLDER",
    "CARPETA_NO_ENCONTRADA": "FOLDER_NOT_FOUND",
    "BACKUP_NO_ENCONTRADO": "BACKUP_NOT_FOUND",
    "MANIFIESTO_AUSENTE": "BACKUP_MANIFEST_INVALID",
    "MANIFIESTO_ILEGIBLE": "BACKUP_MANIFEST_INVALID",
    "MANIFIESTO_SIN_HUELLA": "BACKUP_MANIFEST_INVALID",
    "CONFIRMACION_REQUERIDA": "MISSING_REQUIRED_ARG",
}


def emit_fallo(tool: str, fallo: Any) -> Dict[str, Any]:
    """Traduce un `FalloDeDominio` al envelope de la herramienta.

    Es el único punto donde el vocabulario del dominio se convierte en contrato
    de salida, y por eso es el único sitio de `scripts/` que sabe que
    `fallos.CAUSAS` existe.

    Toma el fallo por pato y no por `isinstance`: importar `vault/kernel` desde
    aquí invertiría la dependencia —el kernel del vault no debe estar debajo del
    catálogo de errores de la tool— y no compra nada, porque una causa que no
    esté en `MAPA_DE_FALLOS` ya falla igual.

    **`error` se sigue emitiendo.** No es redundante con `message`: es un campo
    estable declarado en `field-compat-baseline.json` para `vault_restore`, y el
    contrato dice que un campo estable no desaparece porque hayamos mejorado el
    envelope por debajo. Lo mismo con `hint` y `searched`, que llegan por
    `fallo.datos`. Quitarlos habría sido cambiar el arreglo de AP-52 por una
    infracción del contrato de campos.
    """
    causa = getattr(fallo, "causa", None)
    if causa not in MAPA_DE_FALLOS:
        raise ValueError(
            f"causa sin traducción al catálogo: {causa!r}. Añadirla a "
            "MAPA_DE_FALLOS es parte de declararla en fallos.CAUSAS."
        )
    mensaje = getattr(fallo, "mensaje", None) or str(fallo)
    envelope = emit_error(tool, MAPA_DE_FALLOS[causa], mensaje)
    envelope["causa"] = causa
    envelope["error"] = mensaje
    envelope.update(getattr(fallo, "datos", None) or {})
    return envelope


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
        pass  # AP-37: fail-safe — voice injection must never break the tool


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
        # AP-37: fail-safe — error output must never crash the tool
        try:
            print(text)
        except Exception:
            pass  # AP-37: truly last resort — silent


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
            # v40.17: la hoja `vault_ledger`, no `vault_io`. Contar escrituras no
            # necesita saber de saneado ni de índices, y pedir el módulo entero
            # era lo que ataba el módulo de errores al ciclo del núcleo.
            from vault_ledger import write_report

            return write_report()
        except Exception as exc:
            emit_error("vault_errors", "WRITE_REPORT_ERROR", str(exc))
            return {}

    def _target():
        captured = io.StringIO()
        sys.stdout = captured
        # AP-37: el contador de escrituras es thread-local y la tool corre en
        # ESTE hilo, así que se pone a cero aquí — no en wrap_main, que se
        # ejecuta en el hilo principal y no vería el mismo ledger.
        try:
            from vault_ledger import write_ledger_reset

            write_ledger_reset()
        except Exception:
            pass  # AP-37: fail-safe — ledger reset must not crash the tool
        try:
            exit_code = _run()
            result_q.put(("ok", exit_code, captured.getvalue(), _writes()))
        except Exception as exc:
            result_q.put(("exc", exc, captured.getvalue(), _writes()))
        except BaseException as exc:
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
        if isinstance(value, VaultWriteError):
            err = emit_error(tool_name, value.error_code, value.message)
        else:
            code = _map_exception_to_code(value)
            if code == "MEMORY_ERROR":
                err = emit_error(tool_name, code, str(value), exception=value)
            elif code == "UNEXPECTED_ERROR":
                err = emit_error(
                    tool=tool_name,
                    code="UNEXPECTED_ERROR",
                    message=f"{type(value).__name__}: {value}",
                    exception=value,
                )
            else:
                err = emit_error(tool_name, code, f"{type(value).__name__}: {value}")
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
                        {"ok": False, "error": f"Código '{args.code}' no encontrado"},
                        ensure_ascii=False,
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

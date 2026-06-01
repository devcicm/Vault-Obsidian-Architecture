#!/usr/bin/env python3
"""
vault_errors.py — Observabilidad y trazabilidad centralizada para vault tools.

Uso en cualquier tool:
    from vault_errors import wrap_main, emit_error

    def main():
        # ... lógica ...
        if algo_falla:
            print(json.dumps(emit_error("vault_write", "VAULT_NOT_FOUND", "Vault root no existe")))
            sys.exit(1)

    if __name__ == "__main__":
        sys.exit(wrap_main(main, "vault_write"))
"""

import io
import json
import os
import queue
import sys
import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from vault_io import atomic_write_text, file_lock, VAULT_ROOT

# Timeout en segundos para cualquier tool. Override via env: VAULT_TOOL_TIMEOUT=120
TOOL_TIMEOUT_SECONDS: int = int(os.environ.get("VAULT_TOOL_TIMEOUT", "60"))

TRACE_FILE = VAULT_ROOT / "00_System" / ".tool-trace.json"
TOKENS_FILE = VAULT_ROOT / "00_System" / ".tool-tokens.json"
TRACE_MAX_ENTRIES = 500
TOKENS_MAX_ENTRIES = 2000

# ──────────────────────────────────────────────────────────────────────────────
# Catálogo de errores — error_code → metadata + recovery hints
# ──────────────────────────────────────────────────────────────────────────────
ERROR_CATALOG: Dict[str, Dict[str, Any]] = {

    # ── Infrastructure ────────────────────────────────────────────────────────
    "VAULT_NOT_FOUND": {
        "category": "infrastructure",
        "severity": "critical",
        "message": "El directorio raíz del vault no existe o no es accesible.",
        "recovery": {
            "action": "fix_input",
            "hint": "Verificar que el vault tenga carpeta 99_Index/ para que _detect_vault_root() lo detecte, o definir la env var VAULT_ROOT con la ruta absoluta al vault.",
            "docs": "vault-obsidian-architecture.md §Estructura de carpetas"
        }
    },
    "FOLDER_NOT_FOUND": {
        "category": "infrastructure",
        "severity": "error",
        "message": "La carpeta especificada no existe dentro del vault.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_standard_upgrade",
            "args": ["--check"],
            "hint": "Ejecutar vault_standard_upgrade --check para detectar carpetas faltantes y aplicar migraciones.",
            "docs": "vault-obsidian-architecture.md §Versionado del estándar"
        }
    },
    "FILE_NOT_FOUND": {
        "category": "infrastructure",
        "severity": "error",
        "message": "El archivo de nota especificado no existe.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_search",
            "args": ["--query", "<title>"],
            "hint": "Usar vault_search para localizar la nota por título o contenido.",
            "docs": "vault-obsidian-architecture.md §Grupo 1 — Búsqueda"
        }
    },
    "FILE_WRITE_ERROR": {
        "category": "infrastructure",
        "severity": "error",
        "message": "No se pudo escribir el archivo.",
        "recovery": {
            "action": "manual",
            "hint": "Verificar permisos del directorio destino y que no haya otro proceso bloqueando el archivo.",
            "docs": None
        }
    },
    "FILE_READ_ERROR": {
        "category": "infrastructure",
        "severity": "error",
        "message": "No se pudo leer el archivo (encoding o permisos).",
        "recovery": {
            "action": "fix_input",
            "hint": "El archivo puede tener encoding no UTF-8. Abrirlo en Obsidian y guardarlo de nuevo.",
            "docs": None
        }
    },
    "INDEX_NOT_FOUND": {
        "category": "infrastructure",
        "severity": "warning",
        "message": "El índice requerido no existe. Debe generarse antes.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_reindex",
            "args": [],
            "hint": "Ejecutar vault_reindex para regenerar todos los índices (graph.json, search-index.json).",
            "docs": "vault-obsidian-architecture.md §Grupo 10 — Indexación"
        }
    },
    "HISTORY_NOT_FOUND": {
        "category": "infrastructure",
        "severity": "warning",
        "message": "No se encontraron versiones anteriores en .history/ para esta nota.",
        "recovery": {
            "action": "manual",
            "hint": "El plugin Obsidian File Recovery / Vault History debe estar habilitado para generar .history/.",
            "docs": None
        }
    },
    "BACKUP_ERROR": {
        "category": "infrastructure",
        "severity": "error",
        "message": "Error al crear o restaurar el backup.",
        "recovery": {
            "action": "manual",
            "hint": "Verificar espacio en disco y permisos del directorio destino.",
            "docs": None
        }
    },

    # ── Validation ────────────────────────────────────────────────────────────
    "MISSING_REQUIRED_ARG": {
        "category": "validation",
        "severity": "error",
        "message": "Argumento requerido no proporcionado.",
        "recovery": {
            "action": "fix_input",
            "hint": "Ejecutar el script con --help para ver los argumentos requeridos.",
            "docs": None
        }
    },
    "INVALID_PATH": {
        "category": "validation",
        "severity": "error",
        "message": "La ruta proporcionada contiene caracteres inválidos o sale del vault.",
        "recovery": {
            "action": "fix_input",
            "hint": "Las rutas deben ser relativas al vault root. Ejemplo: 01_Projects/mi-api/overview.md",
            "docs": "vault-obsidian-architecture.md §Estructura de carpetas"
        }
    },
    "INVALID_FOLDER": {
        "category": "validation",
        "severity": "error",
        "message": "La carpeta destino no pertenece a la estructura estándar del vault.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_audit",
            "args": [],
            "hint": "Usar una carpeta de la estructura estándar (01_Projects, 03_Decisions, 05_Patterns, etc.).",
            "docs": "vault-obsidian-architecture.md §Estructura de carpetas"
        }
    },
    "INVALID_ACTION": {
        "category": "validation",
        "severity": "error",
        "message": "La acción o comando especificado no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Ejecutar el script con --help para ver las acciones disponibles.",
            "docs": None
        }
    },
    "FRONTMATTER_MISSING": {
        "category": "validation",
        "severity": "warning",
        "message": "La nota no tiene frontmatter YAML válido.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_write",
            "args": ["--path", "<path>", "--title", "<title>"],
            "hint": "Usar vault_write para reescribir la nota con frontmatter completo.",
            "docs": "vault-obsidian-architecture.md §Frontmatter obligatorio"
        }
    },
    "FRONTMATTER_PARSE_ERROR": {
        "category": "validation",
        "severity": "warning",
        "message": "El frontmatter YAML no se pudo parsear.",
        "recovery": {
            "action": "manual",
            "hint": "Abrir la nota en Obsidian y corregir el bloque --- manualmente.",
            "docs": "vault-obsidian-architecture.md §Frontmatter obligatorio"
        }
    },

    # ── Governance (antipatrones del estándar) ────────────────────────────────
    "AP20_EMPTY_LIST": {
        "category": "governance",
        "severity": "error",
        "message": "AP-20: Más del 50% de los bullets están vacíos (deceptive skeleton).",
        "recovery": {
            "action": "fix_input",
            "hint": "Completar o eliminar los bullets vacíos antes de guardar. Una nota con contenido mínimo es mejor que una con esqueleto vacío.",
            "docs": "vault-obsidian-architecture.md §AP-20"
        }
    },
    "AP21_PATH_WIKILINKS": {
        "category": "governance",
        "severity": "error",
        "message": "AP-21: Se detectaron wiki-links con ruta (path-anchored). Usar solo [[nombre-nota]].",
        "recovery": {
            "action": "fix_input",
            "hint": "Reemplazar [[carpeta/nota]] por [[nota]] en todos los links del contenido.",
            "docs": "vault-obsidian-architecture.md §AP-21"
        }
    },
    "WIKILINK_SYNTAX_ERROR": {
        "category": "governance",
        "severity": "error",
        "message": "Wiki-link mal formado: corchetes extra, cierre/apertura faltante, target vacio o brackets anidados.",
        "recovery": {
            "action": "fix_input",
            "hint": "Usar exactamente [[nombre-nota]] o [[nombre-nota|alias]]. No usar [[[...]]], [[...]]], [[]], [[carpeta/nota]], ni links sin cierre.",
            "docs": "vault-obsidian-architecture.md AP-21"
        }
    },
    "AP17_DUPLICATE_TITLE": {
        "category": "governance",
        "severity": "warning",
        "message": "AP-17: Posible canonical-shadow: existe otra nota con título muy similar.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_audit",
            "args": [],
            "hint": "Ejecutar vault_audit para identificar pares duplicados y decidir cuál es la nota canónica.",
            "docs": "vault-obsidian-architecture.md §AP-17, PAT-3"
        }
    },
    "AP18_HASH_DUPLICATE": {
        "category": "governance",
        "severity": "warning",
        "message": "AP-18: Contenido duplicado detectado en otra carpeta.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_audit",
            "args": [],
            "hint": "Ejecutar vault_audit --hash para identificar duplicados exactos cross-folder.",
            "docs": "vault-obsidian-architecture.md §AP-18, PAT-3"
        }
    },
    "AP19_SHADOW_INDEX": {
        "category": "governance",
        "severity": "error",
        "message": "AP-19: Se intentó crear un índice sombra. Ya existe index.md en esta sección.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_section_index",
            "args": ["--folder", "<folder>"],
            "hint": "Usar vault_section_index para actualizar el índice existente en lugar de crear uno nuevo.",
            "docs": "vault-obsidian-architecture.md §AP-19"
        }
    },
    "CONTENT_TOO_SHORT": {
        "category": "governance",
        "severity": "error",
        "message": "El contenido es demasiado corto (menos de 3 líneas). No se puede guardar una nota vacía.",
        "recovery": {
            "action": "fix_input",
            "hint": "Agregar al menos 3 líneas de contenido sustantivo. Un stub mínimo tiene: título, descripción de 1 línea, 1 referencia.",
            "docs": "vault-obsidian-architecture.md §PAT-2"
        }
    },

    # ── IO ────────────────────────────────────────────────────────────────────
    "ENCODING_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "Problema de encoding al leer o escribir. Se aplicó fallback latin-1.",
        "recovery": {
            "action": "manual",
            "hint": "El archivo tiene encoding no UTF-8. Abrirlo en un editor que soporte recodificación y guardarlo como UTF-8.",
            "docs": None
        }
    },
    "JSON_PARSE_ERROR": {
        "category": "io",
        "severity": "error",
        "message": "El archivo JSON del índice está corrupto o mal formado.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_reindex",
            "args": [],
            "hint": "Ejecutar vault_reindex para regenerar los índices desde cero.",
            "docs": None
        }
    },
    "JSON_WRITE_ERROR": {
        "category": "io",
        "severity": "error",
        "message": "No se pudo serializar la salida como JSON.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el contenido de la nota: puede contener caracteres de control no serializables.",
            "docs": None
        }
    },

    # ── Dependency ────────────────────────────────────────────────────────────
    "DEPENDENCY_MISSING": {
        "category": "dependency",
        "severity": "warning",
        "message": "Dependencia opcional no disponible. Se usó modo fallback.",
        "recovery": {
            "action": "manual",
            "hint": "Instalar la dependencia con pip. Ejemplo: pip install nltk",
            "docs": None
        }
    },
    "PYTHON_VERSION": {
        "category": "dependency",
        "severity": "warning",
        "message": "Versión de Python inferior a la recomendada (3.9+).",
        "recovery": {
            "action": "manual",
            "hint": "Usar Python 3.9 o superior.",
            "docs": None
        }
    },

    # ── Not found ─────────────────────────────────────────────────────────────
    "NOTE_NOT_FOUND": {
        "category": "not_found",
        "severity": "error",
        "message": "La nota especificada no existe en el vault.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_search",
            "args": ["--query", "<title>"],
            "hint": "Usar vault_search para localizar la nota por título, tags o contenido.",
            "docs": None
        }
    },
    "PROJECT_NOT_FOUND": {
        "category": "not_found",
        "severity": "error",
        "message": "El proyecto especificado no tiene carpeta en 01_Projects/.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_project_overview",
            "args": ["--project", "<project>"],
            "hint": "Usar vault_project_overview --project <slug> para crear la estructura inicial del proyecto.",
            "docs": "vault-obsidian-architecture.md §Grupo 2 — Proyectos"
        }
    },
    "VERSION_NOT_FOUND": {
        "category": "not_found",
        "severity": "error",
        "message": "No se encontró la versión del estándar especificada.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_standard_upgrade",
            "args": ["--check"],
            "hint": "Ejecutar vault_standard_upgrade --check para ver versiones disponibles.",
            "docs": "vault-obsidian-architecture.md §Versionado del estándar"
        }
    },

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    "TOOL_TIMEOUT": {
        "category": "infrastructure",
        "severity": "error",
        "message": "La tool excedió el timeout configurado y fue terminada.",
        "recovery": {
            "action": "retry",
            "hint": "Reducir el alcance de la operación (usar --folder, --limit, --project) o aumentar VAULT_TOOL_TIMEOUT env var.",
            "docs": None
        }
    },

    # ── Catch-all ─────────────────────────────────────────────────────────────
    "UNEXPECTED_ERROR": {
        "category": "infrastructure",
        "severity": "critical",
        "message": "Error inesperado no clasificado.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None
        }
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Core functions
# ──────────────────────────────────────────────────────────────────────────────

def emit_error(
    tool: str,
    code: str,
    message: str = None,
    args: Dict[str, Any] = None,
    exception: Exception = None,
) -> Dict[str, Any]:
    """
    Construye un dict de error estructurado y lo registra en el trace log.

    Retorno: dict listo para json.dumps() — siempre tiene ok=False, error_code,
    category, severity, message, recovery, timestamp, tool.
    """
    catalog_entry = ERROR_CATALOG.get(code, ERROR_CATALOG["UNEXPECTED_ERROR"])

    entry = {
        "ok": False,
        "tool": tool,
        "error_code": code,
        "category": catalog_entry["category"],
        "severity": catalog_entry["severity"],
        "message": message or catalog_entry["message"],
        "recovery": catalog_entry["recovery"],
        "timestamp": datetime.now().isoformat()[:19] + "Z",
    }

    if args:
        entry["args"] = args
    if exception:
        entry["traceback"] = traceback.format_exc()

    log_trace(entry)
    return entry


def emit_ok(tool: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce envelope de éxito uniforme y registra en trace log.

    Retorno: {ok: true, tool: str, timestamp: str, **data}
    """
    result = {
        "ok": True,
        "tool": tool,
        "timestamp": datetime.now().isoformat()[:19] + "Z",
        **data,
    }
    log_trace(result)
    return result


def _inject_tool_envelope(text: str, tool_name: str) -> str:
    """Inyecta tool+timestamp en el JSON de salida si aún no los tiene."""
    text = text.strip()
    if not text:
        return text
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("ok") is True and "tool" not in data:
            data["tool"] = tool_name
            data["timestamp"] = datetime.now().isoformat()[:19] + "Z"
            log_trace(data)
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return text


def _write_output(text: str, stdout_ref=None) -> None:
    """Escribe texto a stdout (con soporte de buffer para UTF-8)."""
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


def _append_trace_entry(entry: Dict[str, Any], use_atomic: bool) -> None:
    """Lee, rota y escribe el trace file. Compartido entre ruta con lock y fallback sin lock."""
    if TRACE_FILE.exists():
        try:
            entries: List[Dict] = json.loads(TRACE_FILE.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except Exception:
            entries = []
    else:
        entries = []

    entries.append(entry)
    if len(entries) > TRACE_MAX_ENTRIES:
        entries = entries[-TRACE_MAX_ENTRIES:]

    text = json.dumps(entries, indent=2, ensure_ascii=False)
    if use_atomic:
        atomic_write_text(TRACE_FILE, text)
    else:
        TRACE_FILE.write_text(text, encoding="utf-8")


def log_trace(entry: Dict[str, Any]) -> None:
    """Añade entrada al trace log con rotación a TRACE_MAX_ENTRIES."""
    try:
        TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with file_lock(TRACE_FILE, timeout=5):
                _append_trace_entry(entry, use_atomic=True)
            return
        except TimeoutError:
            pass  # lock timeout — fallback a escritura directa
        _append_trace_entry(entry, use_atomic=False)
    except Exception:
        pass  # Trace log failure must never crash the tool itself


def _count_tokens(text: str) -> Tuple[int, str]:
    """
    Count tokens using the best available tokenizer.
    Chain: anthropic (local) → tiktoken → chars//4 heuristic.
    Returns (token_count, provider_used).
    """
    if not text:
        return 0, "heuristic"

    # 1. Anthropic tokenizer (local, no API call)
    try:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key="dummy")  # key not needed for count_tokens
        count = client.count_tokens(text)
        return count, "anthropic"
    except Exception:
        pass

    # 2. tiktoken (OpenAI tokenizer — close approximation for Claude)
    try:
        import tiktoken  # type: ignore
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text)), "tiktoken"
    except Exception:
        pass

    # 3. Heuristic fallback: regex-based word/symbol split (~4 chars per word-piece)
    import re as _re
    pieces = _re.findall(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", text)
    total = sum(max(1, (len(p) + 3) // 4) if _re.match(r"^[A-Za-z0-9_]+$", p) else 1 for p in pieces)
    return max(1, total), "heuristic"


def log_token_usage(tool: str, input_text: str, output_text: str) -> None:
    """
    Record token usage for a tool invocation to .tool-tokens.json.
    Called by wrap_main when VAULT_COUNT_TOKENS=1.
    """
    try:
        in_tokens, provider = _count_tokens(input_text)
        out_tokens, _ = _count_tokens(output_text)

        entry = {
            "tool": tool,
            "timestamp": datetime.now().isoformat()[:19] + "Z",
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "total_tokens": in_tokens + out_tokens,
            "provider": provider,
        }

        TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if TOKENS_FILE.exists():
            try:
                entries: List[Dict] = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
                if not isinstance(entries, list):
                    entries = []
            except Exception:
                entries = []
        else:
            entries = []

        entries.append(entry)
        if len(entries) > TOKENS_MAX_ENTRIES:
            entries = entries[-TOKENS_MAX_ENTRIES:]

        TOKENS_FILE.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # Token logging must never crash a tool


def wrap_main(fn: Callable, tool_name: str, timeout: int = None) -> int:
    """
    Envuelve main() para:
    - Capturar excepciones no manejadas → emitir JSON estructurado en lugar de traceback
    - Aplicar timeout (default: TOOL_TIMEOUT_SECONDS) — la tool muere limpiamente si cuelga
    - Registrar todo en 00_System/.tool-trace.json

    Uso:
        if __name__ == "__main__":
            sys.exit(wrap_main(main, "vault_write"))

    Override de timeout para una tool específica:
        sys.exit(wrap_main(main, "vault_backup", timeout=120))
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

    # Guardar referencia real de stdout antes de redirigir en el thread.
    _real_stdout = sys.stdout

    # Daemon thread: si el proceso termina (timeout), el thread muere con él.
    result_q: queue.Queue = queue.Queue()

    def _target():
        captured = io.StringIO()
        sys.stdout = captured
        try:
            exit_code = _run()
            result_q.put(("ok", exit_code, captured.getvalue()))
        except Exception as exc:
            result_q.put(("exc", exc, captured.getvalue()))
        finally:
            sys.stdout = _real_stdout

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout=limit)

    if t.is_alive():
        # Thread sigue vivo → timeout; sys.stdout puede estar redirigido, usar ref guardada.
        err = emit_error(
            tool=tool_name,
            code="TOOL_TIMEOUT",
            message=f"La tool '{tool_name}' excedio el limite de {limit}s y fue terminada.",
        )
        _write_output(json.dumps(err, ensure_ascii=False), _real_stdout)
        # Daemon thread morirá cuando el proceso termine (sys.exit a continuación).
        return 1

    try:
        kind, value, captured_text = result_q.get_nowait()
    except queue.Empty:
        return 1

    if kind == "exc":
        err = emit_error(
            tool=tool_name,
            code="UNEXPECTED_ERROR",
            message=f"{type(value).__name__}: {value}",
            exception=value,
        )
        _write_output(json.dumps(err, ensure_ascii=False), _real_stdout)
        return 1

    # Inyectar envelope tool+timestamp en el JSON capturado.
    output = _inject_tool_envelope(captured_text, tool_name)
    if output:
        _write_output(output, _real_stdout)

    # Registrar tokens si el modo está activo.
    if os.environ.get("VAULT_COUNT_TOKENS") == "1":
        input_text = " ".join(sys.argv)
        log_token_usage(tool_name, input_text, captured_text)

    return value


def query_trace(
    tool: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    last: int = 20,
) -> List[Dict[str, Any]]:
    """
    Consulta el trace log. Útil para agentes que necesitan diagnóstico de fallos.

    Args:
        tool:     filtrar por nombre de tool
        severity: filtrar por severity (critical, error, warning)
        category: filtrar por categoría (infrastructure, governance, validation, io, dependency, not_found)
        last:     número máximo de entradas a retornar

    Returns: lista de entradas del trace log ordenadas de más reciente a más antigua.
    """
    if not TRACE_FILE.exists():
        return []

    try:
        entries: List[Dict] = json.loads(TRACE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    if tool:
        entries = [e for e in entries if e.get("tool") == tool]
    if severity:
        entries = [e for e in entries if e.get("severity") == severity]
    if category:
        entries = [e for e in entries if e.get("category") == category]

    return list(reversed(entries))[:last]


# ──────────────────────────────────────────────────────────────────────────────
# CLI standalone — para consultar el trace desde el terminal
# ──────────────────────────────────────────────────────────────────────────────

def _main():
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
    parser.add_argument("--severity", "-s", choices=["critical", "error", "warning"], help="Filtrar por severity")
    parser.add_argument("--category", "-c", help="Filtrar por categoría")
    parser.add_argument("--last", "-l", type=int, default=20, help="Últimas N entradas")
    parser.add_argument("--code", "-k", help="Código de error específico (para catalog)")

    args = parser.parse_args()

    if args.command == "query":
        results = query_trace(tool=args.tool, severity=args.severity, category=args.category, last=args.last)
        print(json.dumps({"ok": True, "count": len(results), "entries": results}, indent=2, ensure_ascii=False))

    elif args.command == "catalog":
        if args.code:
            entry = ERROR_CATALOG.get(args.code)
            if entry:
                print(json.dumps({"ok": True, "code": args.code, **entry}, indent=2, ensure_ascii=False))
            else:
                print(json.dumps({"ok": False, "error": f"Código '{args.code}' no encontrado"}))
        else:
            catalog = {code: {**data, "code": code} for code, data in ERROR_CATALOG.items()}
            print(json.dumps({"ok": True, "count": len(catalog), "catalog": catalog}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(wrap_main(_main, "vault_errors"))

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
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

# Adaptador legacy: las tools históricas se ejecutan como ficheros dentro de
# ``scripts/`` y pueden tener como CWD el runtime externo. El servicio de voz
# sí es un módulo de paquete; se hace visible aquí, en el borde legacy.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# La configuración se lee del registro único, no con un default por punto
# de uso. Ver `vault_entorno.py`.
from vault_entorno import leer as _env
from vault_raiz import RaizNoIdentificada, get_vault_root, raiz_es_el_programa, vault_root_origin
from typing import Any, Callable, Dict, List, Optional

from vault_errors_catalog import (
    ERROR_CATALOG, completar_envelope, construir_error, get_error, mensaje_de, problemas_de_forma,
)
from vault_errors_trace import log_trace, log_token_usage
from vault.autoria.voz import speak as _speak_estable
from vault.kernel import proyectos as _proyectos
from vault.kernel.errores import MAPA_DE_FALLOS as _MAPA_DE_FALLOS, traducir_fallo as _traducir_fallo

TOOL_TIMEOUT_SECONDS: int = _env("VAULT_TOOL_TIMEOUT")


class VaultWriteError(Exception):
    """Error de escritura con código de catálogo conocido.

    Permite a vault_io.atomic_write_text() emitir un error específico
    (DISK_FULL, PERMISSION_DENIED) sin lanzar un Exception genérico que
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
    # Antes que PermissionError, de la que hereda: no saber cuál es el vault
    # no es un problema de permisos (AP-51).
    if isinstance(e, RaizNoIdentificada):
        return "VAULT_NOT_FOUND"
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


def _rutas_locales() -> List[tuple]:
    """(prefijo, marcador) a reducir, del más largo al más corto.

    La raíz del vault va antes que el home porque suele colgar de él. Solo se
    usan rutas absolutas: con `VAULT_ROOT=vault` sustituir el texto crudo
    borraría la palabra «vault» de cualquier mensaje.
    """
    pares = []
    raiz = _env("VAULT_ROOT")
    if raiz and Path(raiz).is_absolute():
        for p in {Path(raiz), Path(raiz).resolve()}:
            pares.append((p, "<vault>"))
    try:
        home = Path.home()
    except RuntimeError:
        home = None
    if home is not None:
        for p in {home, home.resolve()}:
            pares.append((p, "~"))
    salida = []
    for ruta, marcador in pares:
        if len(ruta.parts) < 2:  # `/` o `C:\` como home: reducirlo lo borraría todo
            continue
        for forma in {str(ruta), ruta.as_posix()}:
            salida.append((forma, marcador))
    return sorted(salida, key=lambda par: len(par[0]), reverse=True)


def _sin_rutas_locales(texto: Optional[str]) -> Optional[str]:
    """AP-36 aplicado a la salida: el mensaje no publica el disco local.

    Un envelope sale por MCP hacia el agente y sus logs. La raíz del vault se
    reduce a `<vault>` —la parte relativa sigue siendo útil— y el directorio
    del usuario a `~`.
    """
    if not texto:
        return texto
    bandera = re.IGNORECASE if os.name == "nt" else 0
    for forma, marcador in _rutas_locales():
        texto = re.sub(re.escape(forma), lambda _m, m=marcador: m, texto, flags=bandera)
    return texto


def emit_error(
    tool: str,
    code: str,
    message: str = None,
    args: Dict[str, Any] = None,
    exception: Exception = None,
    pista: str = None,
) -> Dict[str, Any]:
    """Construye error estructurado y lo registra en el trace log.

    El traceback solo viaja con `VAULT_DEBUG=1`, y las rutas locales del
    mensaje se reducen antes de construirlo.
    """
    entry = construir_error(
        tool, code, _sin_rutas_locales(message), args, exception,
        incluir_traceback=bool(_env("VAULT_DEBUG")),
        pista=pista,
    )
    log_trace(entry)
    return entry


#: La tabla y su traducción viven en el núcleo desde v40.34 (`vault.kernel.
#: errores`); se reexporta para no derogar el nombre.
MAPA_DE_FALLOS = _MAPA_DE_FALLOS


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
    codigo, mensaje, campos = _traducir_fallo(fallo)
    envelope = emit_error(tool, codigo, mensaje)
    envelope.update(campos)
    return envelope


def proyecto_registrado(tool: str) -> Callable[[str], str]:
    """`type=` de argparse para el `--project` de toda tool (AP-63).

    El nombre de un proyecto es identidad, no texto libre: lo que llega a la
    tool ya es el slug canónico, así que lo que escribe en `project:` o en la
    ruta es la identidad y no la cadena que tecleó alguien. Resolver en
    `type=` y no dentro de cada tool es lo que deja medirlo: un
    `add_argument("--project")` sin él es una tool que vuelve a aceptar texto
    libre, y `test_project_registrado` lo nombra.

    Un nombre que no resuelve no llega a la tool: se imprime el envelope de
    `emit_fallo` con el nombre de **la tool que llama** —por eso es una
    fábrica— y se sale con 1, antes de que la tool cree nada. No se usa
    `ArgumentTypeError`: argparse lo convertiría en un texto por stderr con
    código 2, fuera del contrato de errores que leen la CLI y el MCP. La
    cadena vacía pasa tal cual: es el «sin proyecto» de las opcionales con
    `default=""`.

    **Por qué aquí (v40.34).** Vivió en `vault_project` (Autoría), y cada tool
    de otro contexto que la importaba abría un cruce. Después en un módulo
    propio del núcleo, `vault_proyecto_arg`, que le subía el fan-out a
    `vault_log_error` y volteaba el escalón de AP-59. Aquí no añade ninguna
    arista: todas las tools con `--project` ya importan este módulo, y este
    módulo ya dependía de `vault/kernel` por `vault_errors_catalog`. Es además
    el vecino natural: quien traduce el fallo es `emit_fallo`, dos líneas más
    arriba.
    """

    return _proyectos.proyecto_registrado(tool, get_vault_root, emitir=emit_fallo)


def fuera_de_sesion(tool: str, *rutas: Any) -> Optional[Dict[str, Any]]:
    """El envelope `PROJECT_LOCKED` si alguna ruta es de otro proyecto, o None.

    AP-63, P5: el candado de `proyecto_registrado` para las tools que reciben
    ruta y no `--project`. El criterio es del núcleo
    (`proyectos.comprobar_ruta_en_sesion`); aquí solo se elige el transporte.
    """
    raiz = get_vault_root()
    for ruta in rutas:
        try:
            _proyectos.comprobar_ruta_en_sesion(raiz, ruta)
        except _proyectos.FalloDeDominio as fallo:
            return emit_fallo(tool, fallo)
    return None


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
    # AP-43: el refuerzo va en el punto de uso, en la salida de toda tool.
    if not isinstance(data, dict) or "vault_says" in data:
        return
    try:
        # Compatibilidad para instrumentación histórica: si la fachada ya está
        # cargada y un consumidor parcheó explícitamente su `speak`, se respeta
        # ese seam. El camino normal llama al servicio de paquete directamente;
        # no hay import de `vault_voice` desde el runtime.
        legacy = sys.modules.get("vault_voice")
        speak_legacy = getattr(legacy, "speak", None) if legacy is not None else None
        if callable(speak_legacy):
            bloque = speak_legacy(tool_name, data, writes)
        else:
            bloque = _speak_estable(
                tool_name,
                data,
                writes,
                voice_mode=_env("VAULT_VOICE"),
            )
        if bloque:
            data["vault_says"] = bloque
    except Exception:
        pass  # AP-37: fail-safe — voice injection must never break the tool


def _inject_tool_envelope(
    text: str, tool_name: str, writes: Optional[Dict[str, int]] = None
) -> str:
    """Inyecta tool+timestamp en el JSON de salida si aún no los tiene.

    Un fallo con `error_code` construido a mano sale en la forma del contrato
    (AP-52, v40.34): había 82 `return {"ok": False, "error_code": …}` en 30
    tools, sin `category`, `severity`, `recovery` ni `timestamp`. Se canoniza
    aquí, la salida por la que pasan todas, y no en cada `return`: así el 83
    no nace igual. Sus textos pasan por el mismo reductor de rutas que
    `emit_error`, para que el error hecho a mano no publique más que el
    canónico.
    """
    text = text.strip()
    if not text:
        return text
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("ok") is True and "tool" not in data:
            data["tool"] = tool_name
            data["timestamp"] = datetime.now(timezone.utc).isoformat()[:19] + "Z"
            log_trace(data)
        elif (isinstance(data, dict) and data.get("ok") is False
              and data.get("error_code") and problemas_de_forma(data)):
            # Solo lo que no está en forma: lo que ya emitió `emit_error` está
            # canónico y en el trace, y rehacerlo lo registraría dos veces.
            data = completar_envelope(tool_name, data)
            for clave in ("message", "error"):
                if isinstance(data.get(clave), str):
                    data[clave] = _sin_rutas_locales(data[clave])
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


def _rechazo_por_raiz_inexistente(tool_name: str) -> Optional[Dict[str, Any]]:
    """AP-36: con `VAULT_ROOT` apuntando a nada, la tool no llega a ejecutarse.

    Bloquear solo la escritura de la nota no basta: medido en v40.34, los
    locks, la traza y el contador de voz se escriben por su cuenta y dejaban
    igualmente `00_System/` en la raíz inexistente. Aquí es el único punto por
    el que pasan las 127 tools antes de tocar nada. El envelope no pasa por
    `emit_error` a propósito: registrarlo en la traza sería escribir en el
    vault fantasma justo al rechazarlo.
    """
    if vault_root_origin() != "env_inexistente":
        return None
    return construir_error(
        tool_name, "VAULT_NOT_FOUND",
        _sin_rutas_locales(
            f"VAULT_ROOT apunta a '{get_vault_root()}', que no es un directorio. "
            "No se ejecuta nada para no crear un vault fantasma: revisa la "
            "variable (¿está sin expandir?) o crea el directorio y ejecuta vault_init."
        ),
        # La pista del catálogo habla de `99_Index/` y de la autodetección, que
        # aquí no aplican: la variable ya está definida y apunta a nada. El
        # código no cambia porque los consumidores deciden por él.
        pista=(
            "Corregir VAULT_ROOT: si contiene %VAR% o $VAR literal, la shell no la "
            "expandió. Para un vault nuevo, `vault init <ruta>` crea el directorio "
            "(el padre debe existir) y después VAULT_ROOT apunta a esa ruta."
        ),
    )


#: Con estos argumentos la tool no lee la raíz adivinada: `--help` no toca el
#: vault y `--root` lo fija la propia tool antes de leer nada.
_ARGUMENTOS_SIN_RAIZ = ("-h", "--help", "--root")


def _rechazo_por_raiz_del_programa(tool_name: str) -> Optional[Dict[str, Any]]:
    """AP-36: la raíz adivinada es el propio toolkit instalado; no se lee.

    Medido como consumidor el 2026-10-15 con la wheel 41.6: sin `VAULT_ROOT`,
    `vault_audit` auditó `site-packages/vault_toolkit`, devolvió `ok: true` y
    propuso reparar los ficheros del paquete, mientras `vault_write` ya se
    negaba. El criterio «esto es el programa» es de `vault_raiz`; aquí solo se
    decide no ejecutar. `VAULT_PERMISSIVE_ROOT=1` conserva lo anterior.
    """
    if not raiz_es_el_programa() or _env("VAULT_PERMISSIVE_ROOT"):
        return None
    if any(a.split("=", 1)[0] in _ARGUMENTOS_SIN_RAIZ for a in sys.argv[1:]):
        return None
    en_runtime = (Path.cwd() / "00_System" / "standard-version.json").is_file()
    pista = (
        "Indica el vault: `VAULT_ROOT=<runtime> vault run <tool> …`. Para crear "
        "uno, `vault init <ruta>`."
    )
    if en_runtime:
        pista = (
            "El directorio actual es un runtime: `VAULT_ROOT=. vault run <tool> …` "
            "lo usa. La raíz no se deduce del directorio actual a propósito: "
            "lanzar una tool desde otra carpeta cambiaría en silencio el vault."
        )
    return construir_error(
        tool_name, "VAULT_NOT_FOUND",
        "No hay vault identificado: sin VAULT_ROOT, la única raíz disponible es "
        "el propio paquete instalado, y leerla sería tratar el programa como si "
        "fuera tu vault. No se ejecuta nada.",
        extra={"cwd_is_runtime": en_runtime},
        pista=pista,
    )


class _ArgumentosRechazados(SystemExit):
    """argparse rechazó la línea de órdenes antes de que la tool hiciera nada.

    Hereda de `SystemExit`, como el `exit(2)` que sustituye: un `except
    Exception` dentro de la tool no debe tragárselo y seguir ejecutando.
    """

    def __init__(self, prog: str, usage: str, detalle: str):
        super().__init__(2)
        self.prog = prog
        self.usage = usage
        self.detalle = detalle


def _rechazar_argumentos(self, message):
    # Sustituye a `ArgumentParser.error` mientras corre la tool: el texto de
    # uso sigue yendo a stderr, como siempre, y además la tool responde con
    # su envelope en vez de dejar stdout vacío.
    raise _ArgumentosRechazados(self.prog, self.format_usage(), message)


def wrap_main(fn: Callable, tool_name: str, timeout: int = None) -> int:
    """Envuelve main() con timeout, captura de excepciones, y trace log.

    Args:
        fn: Función main() a ejecutar
        tool_name: Nombre de la tool (para logs)
        timeout: Segundos máximo (default: TOOL_TIMEOUT_SECONDS)

    Returns: exit code (0 = éxito, 1 = error)
    """
    limit = timeout if timeout is not None else TOOL_TIMEOUT_SECONDS

    rechazo = _rechazo_por_raiz_inexistente(tool_name) or _rechazo_por_raiz_del_programa(tool_name)
    if rechazo is not None:
        _write_output(json.dumps(rechazo, ensure_ascii=False), sys.stdout)
        return 1

    def _run():
        try:
            result = fn()
            if result is None:
                return 0
            return int(result)
        except _ArgumentosRechazados as rechazo:
            # Medido el 2026-10-04: un flag que la tool no programa salía solo
            # como texto de uso en stderr, con stdout vacío. Quien consume el
            # contrato JSON (`vault run`, el agente) no tenía envelope que leer
            # y lo veía como salida no estructurada. El rc sigue siendo 2, el
            # de argparse, y no se ha ejecutado nada.
            sys.stderr.write(f"{rechazo.usage}{rechazo.prog}: error: {rechazo.detalle}\n")
            # Solo los nombres de los flags: los valores pueden ser el
            # contenido de una nota, y el envelope va también al trace log.
            err = emit_error(
                tool_name,
                "INVALID_ARGS",
                f"argumentos rechazados: {rechazo.detalle}",
                args={"flags": [a.split("=", 1)[0] for a in sys.argv[1:] if a.startswith("-")]},
                pista=f"`{rechazo.prog} --help` lista los argumentos que acepta.",
            )
            _write_output(json.dumps(err, ensure_ascii=False), _real_stdout)
            return 2
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

    import argparse

    _error_original = argparse.ArgumentParser.error
    argparse.ArgumentParser.error = _rechazar_argumentos
    t = threading.Thread(target=_target, daemon=True)
    t.start()
    try:
        t.join(timeout=limit)
    finally:
        argparse.ArgumentParser.error = _error_original

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
        elif getattr(value, "causa", None) in MAPA_DE_FALLOS:
            # Un fallo con causa del dominio que ningún adaptador capturó —el
            # `IndiceIlegible` de `vault_io.indice_compartido`, que comparten
            # nueve tools— sale con su código y no como UNEXPECTED_ERROR.
            err = emit_fallo(tool_name, value)
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
        allow_abbrev=False,
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

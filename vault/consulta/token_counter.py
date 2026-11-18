#!/usr/bin/env python3
"""Client tool for the vault token counter service."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import vault_grafo_import
from vault_errors import emit_error, wrap_main
from vault_token_service import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    ENV_TOKEN,
    TokenHandler,
    _flow_path,
    _port_file,
    _usage_dir,
    estimate_tokens,
    get_flow,
    serve,
    token_del_cliente,
)


SCRIPTS_DIR = vault_grafo_import.DIRECTORIO  # deuda #12: el dueño vive en vault/, `scripts/` lo dice el puente
SERVICE_SCRIPT = SCRIPTS_DIR / "vault_token_service.py"
#: Seconds `start-service` waits for the new service to answer. Each failed
#: probe of a port nobody listens on costs about two seconds on Windows (the
#: SYN is retried after the reset), so the former 5 s left two probes: under
#: load the service started and the command still said SERVICE_UNAVAILABLE,
#: which breaks the recovery that SERVICE_UNAVAILABLE itself publishes
#: (QA-FL-10). A healthy start answers in well under a second.
PLAZO_ARRANQUE = 20.0


def _base_url(port: Optional[int] = None) -> str:
    selected = port
    if selected is None and _port_file().exists():
        try:
            selected = int(_port_file().read_text(encoding="utf-8").strip())
        except ValueError:
            selected = DEFAULT_PORT
    return f"http://{DEFAULT_HOST}:{selected or DEFAULT_PORT}"


def _request(method: str, path: str, payload: Optional[Dict[str, Any]] = None, port: Optional[int] = None) -> Dict[str, Any]:
    data = None
    headers = {"Authorization": f"Bearer {token_del_cliente()}"}  # SP-04
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(_base_url(port) + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # QA-FL-10: the service answers its own refusals (404 for a flow it
        # does not have, 400 for an event it does not admit) with a catalog
        # envelope. That envelope IS the answer, not a transport failure that
        # `main` would turn into UNEXPECTED_ERROR. A body without `error_code`
        # (the 401/403 of SP-04) stays an exception, as before.
        try:
            cuerpo = json.loads(exc.read().decode("utf-8"))
        except (OSError, ValueError):
            raise exc
        if isinstance(cuerpo, dict) and cuerpo.get("error_code"):
            return cuerpo
        raise


def _is_running(port: Optional[int] = None) -> bool:
    try:
        result = _request("GET", "/status", port=port)
        return bool(result.get("ok"))
    except (URLError, OSError) as exc:
        emit_error("vault_token_counter", "SERVICE_UNAVAILABLE", str(exc))
        return False
    except ValueError as exc:
        # AP-51: lo que responde en el puerto y no habla JSON no es el servicio.
        emit_error("vault_token_counter", "SERVICE_UNAVAILABLE", str(exc))
        return False


def start_service(port: int = DEFAULT_PORT) -> Dict[str, Any]:
    if _is_running(port):
        return {"ok": True, "alreadyRunning": True, "url": _base_url(port)}

    _usage_dir().mkdir(parents=True, exist_ok=True)
    log_path = _usage_dir() / "token-service.log"
    err_path = _usage_dir() / "token-service.err.log"
    if os.name == "nt":
        def ps_quote(value: str) -> str:
            return "'" + value.replace("'", "''") + "'"

        arg_string = f'"{str(SERVICE_SCRIPT)}" --port {port}'
        command = (
            "Start-Process "
            f"-FilePath {ps_quote(sys.executable)} "
            f"-ArgumentList {ps_quote(arg_string)} "
            f"-WorkingDirectory {ps_quote(str(SCRIPTS_DIR.parent))} "
            "-WindowStyle Hidden "
            f"-RedirectStandardOutput {ps_quote(str(log_path))} "
            f"-RedirectStandardError {ps_quote(str(err_path))}"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            cwd=str(SCRIPTS_DIR.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    else:
        flags = 0
        with open(log_path, "a", encoding="utf-8") as log, open(err_path, "a", encoding="utf-8") as err:
            subprocess.Popen(
                [sys.executable, str(SERVICE_SCRIPT), "--port", str(port)],
                cwd=str(SCRIPTS_DIR.parent),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=err,
                creationflags=flags,
                close_fds=True,
            )

    deadline = time.time() + PLAZO_ARRANQUE
    while time.time() < deadline:
        if _is_running(port):
            return {"ok": True, "started": True, "url": _base_url(port), "log": str(log_path), "errLog": str(err_path)}
        time.sleep(0.1)
    return {**emit_error("vault_token_counter", "SERVICE_UNAVAILABLE", "El servicio no respondio dentro del plazo de arranque."), "log": str(log_path), "errLog": str(err_path)}


def stop_service(port: Optional[int] = None) -> Dict[str, Any]:
    try:
        return _request("POST", "/stop", {}, port=port)
    except URLError as exc:
        if isinstance(getattr(exc, "reason", None), ConnectionRefusedError):
            # QA-FL-10: nothing listens, so the service is already stopped.
            # Idempotent like `start-service` on a running service
            # (`alreadyRunning`); a failure of another kind (timeout, a port
            # held by someone else) is still SERVICE_UNAVAILABLE.
            return {"ok": True, "alreadyStopped": True, "url": _base_url(port)}
        return {**emit_error("vault_token_counter", "SERVICE_UNAVAILABLE", f"El servicio no responde: {exc}", exception=exc), "detail": str(exc)}


def status(port: Optional[int] = None) -> Dict[str, Any]:
    try:
        return _request("GET", "/status", port=port)
    except Exception as exc:
        return {**emit_error("vault_token_counter", "SERVICE_UNAVAILABLE", str(exc), exception=exc), "running": False, "url": _base_url(port)}


def begin(flow_id: str, operation: str, budget: Optional[Dict[str, Any]], port: Optional[int] = None) -> Dict[str, Any]:
    if not _is_running(port):
        start = start_service(port or DEFAULT_PORT)
        if not start.get("ok"):
            return start
    return _request("POST", "/flows/start", {"flow_id": flow_id, "operation": operation, "budget": budget or {}}, port=port)


def event(
    flow_id: str,
    text: str,
    source: str,
    phase: str,
    tool: str,
    direction: str,
    note: str,
    tokens: Optional[int],
    store_text: bool,
    port: Optional[int] = None,
) -> Dict[str, Any]:
    if not _is_running(port):
        return emit_error("vault_token_counter", "SERVICE_UNAVAILABLE", "El servicio no esta corriendo; usa start-service o begin.")
    return _request(
        "POST",
        "/events",
        {
            "flow_id": flow_id,
            "text": text,
            "source": source,
            "phase": phase,
            "tool": tool,
            "direction": direction,
            "note": note,
            "tokens": tokens,
            "store_text": store_text,
        },
        port=port,
    )


def report(flow_id: str, port: Optional[int] = None) -> Dict[str, Any]:
    if _is_running(port):
        return _request("GET", f"/flows/{flow_id}", port=port)
    # QA-FL-10: with the service down, a persisted flow is still readable.
    # The flow file is the service's own record —`get_flow` reads that same
    # file to answer `GET /flows/<id>`—, so this is its answer, not a rebuild.
    if _flow_path(flow_id).is_file():
        return {**get_flow(flow_id), "source": "persisted", "running": False}
    return emit_error(
        "vault_token_counter", "SERVICE_UNAVAILABLE",
        f"El servicio no esta corriendo y el flujo {flow_id} no esta persistido; "
        "usa start-service.")


def end(flow_id: str, port: Optional[int] = None) -> Dict[str, Any]:
    if not _is_running(port):
        # QA-FL-10: closing a flow writes it, and only the service writes flows.
        return emit_error("vault_token_counter", "SERVICE_UNAVAILABLE",
                          "El servicio no esta corriendo; usa start-service y repite end.")
    return _request("POST", "/flows/end", {"flow_id": flow_id}, port=port)


def self_test() -> Dict[str, Any]:
    port = DEFAULT_PORT + 1
    server = ThreadingHTTPServer((DEFAULT_HOST, port), TokenHandler)
    # El servidor en proceso no escribe el fichero del token: se lo pasa al
    # cliente por la variable, y la deja como estaba al salir.
    server.token = secrets.token_urlsafe(32)
    previo = os.environ.get(ENV_TOKEN)
    os.environ[ENV_TOKEN] = server.token
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # QA-RO-01 (AP-37): the self-test writes its flow file. The in-process
    # server writes it from its own thread, whose write ledger is not this
    # one, so the work is measured on the file itself.
    destino = _flow_path("self-test")
    antes = destino.read_bytes() if destino.is_file() else None
    try:
        started = _request("POST", "/flows/start", {"flow_id": "self-test", "operation": "token counter self-test"}, port=port)
        ev = event(
            flow_id="self-test",
            text="Token counter self test payload.",
            source="self-test",
            phase="probe",
            tool="vault_token_counter",
            direction="input",
            note="",
            tokens=None,
            store_text=False,
            port=port,
        )
        rep = report("self-test", port=port)
        ended = end("self-test", port=port)
        despues = destino.read_bytes() if destino.is_file() else None
        return {"ok": True, "started": started, "event": ev, "report": rep, "ended": ended,
                "written": int(despues is not None and despues != antes),
                "path": started.get("path")}
    finally:
        if previo is None:
            os.environ.pop(ENV_TOKEN, None)
        else:
            os.environ[ENV_TOKEN] = previo
        server.shutdown()
        server.server_close()


def _load_text_arg(value: str) -> str:
    if value.startswith("@file:"):
        return Path(value[6:]).read_text(encoding="utf-8")
    return value


def _load_json_arg(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    raw = value
    if raw.startswith("@file:"):
        raw = Path(raw[6:]).read_text(encoding="utf-8")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        normalized = raw.strip()
        if (normalized.startswith("'") and normalized.endswith("'")) or (
            normalized.startswith('"') and normalized.endswith('"')
        ):
            normalized = normalized[1:-1]
        normalized = normalized.replace('\\"', '"')
        parsed = json.loads(normalized)
    if not isinstance(parsed, dict):
        raise ValueError("budget must be a JSON object")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Token Counter Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python vault_token_counter.py start-service
  python vault_token_counter.py begin --flow-id recovery-001 --operation "project recovery"
  python vault_token_counter.py event --flow-id recovery-001 --direction input --phase scan --tool vault_code_module --text @file:prompt.txt
  python vault_token_counter.py report --flow-id recovery-001
  python vault_token_counter.py end --flow-id recovery-001

Operational rule:
  Invoke begin before mass documentation. Other vault tools stay independent;
  this service receives explicit flow events and reports token usage separately.
  event and end need the running service; report reads the persisted flow file
  when the service is down. An ended flow admits no events until begin reopens it.
  stop-service on a stopped service is a no-op (alreadyStopped).
""",
        allow_abbrev=False,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start-service", allow_abbrev=False)
    p_start.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Puerto del servicio de tokens (default: {DEFAULT_PORT})")
    sub.add_parser("stop-service", allow_abbrev=False)
    sub.add_parser("status", allow_abbrev=False)
    p_serve = sub.add_parser("serve", allow_abbrev=False)
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Puerto del servicio de tokens (default: {DEFAULT_PORT})")
    sub.add_parser("self-test", allow_abbrev=False)

    p_begin = sub.add_parser("begin", allow_abbrev=False)
    p_begin.add_argument("--flow-id", required=True,
                        help="Identificador del flujo cuyos tokens se cuentan")
    p_begin.add_argument("--operation", default="",
                        help="Operación del flujo, p. ej. el nombre de la tarea")
    p_begin.add_argument("--budget", help="JSON budget metadata (CLI only: @file:path), e.g. '{\"max_tokens\":100000}'")

    p_event = sub.add_parser("event", allow_abbrev=False)
    p_event.add_argument("--flow-id", required=True,
                        help="Identificador del flujo cuyos tokens se cuentan")
    p_event.add_argument("--text", required=True, help="Text to count (CLI only: @file:path)")
    p_event.add_argument("--source", default="agent",
                        help="Origen del evento (default: agent)")
    p_event.add_argument("--phase", default="",
                        help="Fase del flujo en la que ocurre el evento")
    p_event.add_argument("--tool", default="",
                        help="Tool del evento; agrupa los totales en by_tool")
    p_event.add_argument("--direction", choices=["input", "output", "tool", "unknown"], default="unknown",
                        help="Sentido de los tokens: input, output y tool suman a su total (default: unknown)")
    p_event.add_argument("--note", default="",
                        help="Nota libre sobre el evento")
    p_event.add_argument("--tokens", type=int, help="Explicit token count if known from provider")
    p_event.add_argument("--store-text", action="store_true", help="Persist raw text; default stores only token metadata")

    p_count = sub.add_parser("count", allow_abbrev=False)
    p_count.add_argument("--text", required=True, help="Text to count (CLI only: @file:path)")

    p_report = sub.add_parser("report", allow_abbrev=False)
    p_report.add_argument("--flow-id", required=True,
                        help="Identificador del flujo cuyos tokens se cuentan")

    p_end = sub.add_parser("end", allow_abbrev=False)
    p_end.add_argument("--flow-id", required=True,
                        help="Identificador del flujo cuyos tokens se cuentan")

    args = parser.parse_args()

    try:
        if args.command == "start-service":
            result = start_service(args.port)
        elif args.command == "stop-service":
            result = stop_service()
        elif args.command == "status":
            result = status()
        elif args.command == "serve":
            return serve(DEFAULT_HOST, args.port)
        elif args.command == "self-test":
            result = self_test()
        elif args.command == "begin":
            result = begin(args.flow_id, args.operation, _load_json_arg(args.budget))
        elif args.command == "event":
            result = event(
                flow_id=args.flow_id,
                text=_load_text_arg(args.text),
                source=args.source,
                phase=args.phase,
                tool=args.tool,
                direction=args.direction,
                note=args.note,
                tokens=args.tokens,
                store_text=args.store_text,
            )
        elif args.command == "count":
            text = _load_text_arg(args.text)
            result = {"ok": True, "tokens": estimate_tokens(text), "chars": len(text), "mode": "approximate"}
        elif args.command == "report":
            result = report(args.flow_id)
        elif args.command == "end":
            result = end(args.flow_id)
        else:
            result = emit_error("vault_token_counter", "INVALID_ACTION", "Comando desconocido.")
    except Exception as exc:
        result = emit_error("vault_token_counter", "UNEXPECTED_ERROR", f"{type(exc).__name__}: {exc}", exception=exc)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_token_counter"))

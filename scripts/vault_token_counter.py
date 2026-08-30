#!/usr/bin/env python3
"""Client tool for the vault token counter service."""

import argparse
import json
import os
import subprocess
import sys
import time
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from vault_errors import emit_error, wrap_main
from vault_token_service import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    TokenHandler,
    _port_file,
    _usage_dir,
    estimate_tokens,
    serve,
)


SCRIPTS_DIR = Path(__file__).resolve().parent
SERVICE_SCRIPT = SCRIPTS_DIR / "vault_token_service.py"


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
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(_base_url(port) + path, data=data, headers=headers, method=method)
    with urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _is_running(port: Optional[int] = None) -> bool:
    try:
        result = _request("GET", "/status", port=port)
        return bool(result.get("ok"))
    except (URLError, OSError) as exc:
        emit_error("vault_token_counter", "SERVICE_UNAVAILABLE", str(exc))
        return False
    except Exception as exc:
        emit_error("vault_token_counter", "UNEXPECTED_ERROR", str(exc))
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

    deadline = time.time() + 5
    while time.time() < deadline:
        if _is_running(port):
            return {"ok": True, "started": True, "url": _base_url(port), "log": str(log_path), "errLog": str(err_path)}
        time.sleep(0.1)
    return {**emit_error("vault_token_counter", "SERVICE_UNAVAILABLE", "El servicio no respondio dentro del plazo de arranque."), "log": str(log_path), "errLog": str(err_path)}


def stop_service(port: Optional[int] = None) -> Dict[str, Any]:
    try:
        return _request("POST", "/stop", {}, port=port)
    except URLError as exc:
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
    return _request("GET", f"/flows/{flow_id}", port=port)


def end(flow_id: str, port: Optional[int] = None) -> Dict[str, Any]:
    return _request("POST", "/flows/end", {"flow_id": flow_id}, port=port)


def self_test() -> Dict[str, Any]:
    port = DEFAULT_PORT + 1
    server = ThreadingHTTPServer((DEFAULT_HOST, port), TokenHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
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
        return {"ok": True, "started": started, "event": ev, "report": rep, "ended": ended}
    finally:
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
""",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start-service")
    p_start.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub.add_parser("stop-service")
    sub.add_parser("status")
    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub.add_parser("self-test")

    p_begin = sub.add_parser("begin")
    p_begin.add_argument("--flow-id", required=True)
    p_begin.add_argument("--operation", default="")
    p_begin.add_argument("--budget", help="JSON budget metadata or @file:path, e.g. '{\"max_tokens\":100000}'")

    p_event = sub.add_parser("event")
    p_event.add_argument("--flow-id", required=True)
    p_event.add_argument("--text", required=True, help="Text to count, or @file:path")
    p_event.add_argument("--source", default="agent")
    p_event.add_argument("--phase", default="")
    p_event.add_argument("--tool", default="")
    p_event.add_argument("--direction", choices=["input", "output", "tool", "unknown"], default="unknown")
    p_event.add_argument("--note", default="")
    p_event.add_argument("--tokens", type=int, help="Explicit token count if known from provider")
    p_event.add_argument("--store-text", action="store_true", help="Persist raw text; default stores only token metadata")

    p_count = sub.add_parser("count")
    p_count.add_argument("--text", required=True, help="Text to count, or @file:path")

    p_report = sub.add_parser("report")
    p_report.add_argument("--flow-id", required=True)

    p_end = sub.add_parser("end")
    p_end.add_argument("--flow-id", required=True)

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

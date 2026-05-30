#!/usr/bin/env python3
"""Local token usage service for vault documentation flows."""

import argparse
import json
import os
import re
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from vault_errors import wrap_main
from vault_io import atomic_write_json, file_lock


SCRIPTS_DIR = Path(__file__).resolve().parent
VAULT_ROOT = SCRIPTS_DIR.parent
USAGE_DIR = VAULT_ROOT / "00_System" / "token-usage"
FLOW_DIR = USAGE_DIR / "flows"
PID_FILE = USAGE_DIR / "token-service.pid"
PORT_FILE = USAGE_DIR / "token-service.port"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def estimate_tokens(text: str) -> int:
    """Approximate tokenizer without external dependencies.

    Intentionally conservative for operational budgeting, not billing.
    Exact billing tokens require provider/model tokenizer APIs.
    """
    if not text:
        return 0
    pieces = re.findall(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", text)
    total = 0
    for piece in pieces:
        if re.match(r"^[A-Za-z0-9_]+$", piece):
            total += max(1, (len(piece) + 3) // 4)
        else:
            total += 1
    return total


def _flow_path(flow_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", flow_id).strip("-") or "default"
    return FLOW_DIR / f"{safe}.json"


def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else dict(default)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(default)


def _default_flow(flow_id: str, operation: str = "") -> Dict[str, Any]:
    now = _utcnow()
    return {
        "flow_id": flow_id,
        "operation": operation,
        "status": "active",
        "createdAt": now,
        "updatedAt": now,
        "endedAt": "",
        "budget": {},
        "totals": {
            "events": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "tool_tokens": 0,
            "total_tokens": 0,
        },
        "by_tool": {},
        "events": [],
    }


def _update_totals(flow: Dict[str, Any], event: Dict[str, Any]) -> None:
    direction = event.get("direction", "unknown")
    tokens = int(event.get("tokens", 0))
    totals = flow.setdefault("totals", {})
    totals["events"] = int(totals.get("events", 0)) + 1
    totals["total_tokens"] = int(totals.get("total_tokens", 0)) + tokens
    if direction == "input":
        totals["input_tokens"] = int(totals.get("input_tokens", 0)) + tokens
    elif direction == "output":
        totals["output_tokens"] = int(totals.get("output_tokens", 0)) + tokens
    elif direction == "tool":
        totals["tool_tokens"] = int(totals.get("tool_tokens", 0)) + tokens

    tool = event.get("tool") or "flow"
    by_tool = flow.setdefault("by_tool", {})
    bucket = by_tool.setdefault(tool, {"events": 0, "tokens": 0})
    bucket["events"] = int(bucket.get("events", 0)) + 1
    bucket["tokens"] = int(bucket.get("tokens", 0)) + tokens


def start_flow(payload: Dict[str, Any]) -> Dict[str, Any]:
    flow_id = payload.get("flow_id") or f"flow-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    operation = payload.get("operation", "")
    path = _flow_path(flow_id)
    FLOW_DIR.mkdir(parents=True, exist_ok=True)
    with file_lock(path):
        flow = _read_json(path, _default_flow(flow_id, operation))
        if not flow.get("createdAt"):
            flow = _default_flow(flow_id, operation)
        flow["flow_id"] = flow_id
        flow["operation"] = operation or flow.get("operation", "")
        flow["status"] = "active"
        flow["updatedAt"] = _utcnow()
        if isinstance(payload.get("budget"), dict):
            flow["budget"] = payload["budget"]
        atomic_write_json(path, flow)
    return {"ok": True, "flow_id": flow_id, "path": str(path.relative_to(VAULT_ROOT)).replace("\\", "/")}


def add_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    flow_id = payload.get("flow_id")
    if not flow_id:
        return {"ok": False, "error": "missing_flow_id"}
    path = _flow_path(flow_id)
    FLOW_DIR.mkdir(parents=True, exist_ok=True)
    text = payload.get("text", "")
    tokens = payload.get("tokens")
    token_count = int(tokens) if tokens is not None else estimate_tokens(str(text))
    event = {
        "ts": _utcnow(),
        "source": payload.get("source", "agent"),
        "phase": payload.get("phase", ""),
        "tool": payload.get("tool", ""),
        "direction": payload.get("direction", "unknown"),
        "tokens": token_count,
        "chars": len(str(text)),
        "note": payload.get("note", ""),
    }
    if payload.get("store_text") is True:
        event["text"] = str(text)

    with file_lock(path):
        flow = _read_json(path, _default_flow(flow_id))
        flow["status"] = "active"
        flow["updatedAt"] = _utcnow()
        flow.setdefault("events", []).append(event)
        _update_totals(flow, event)
        atomic_write_json(path, flow)
    return {"ok": True, "flow_id": flow_id, "tokens": token_count, "event": event}


def end_flow(payload: Dict[str, Any]) -> Dict[str, Any]:
    flow_id = payload.get("flow_id")
    if not flow_id:
        return {"ok": False, "error": "missing_flow_id"}
    path = _flow_path(flow_id)
    with file_lock(path):
        flow = _read_json(path, _default_flow(flow_id))
        flow["status"] = "ended"
        flow["updatedAt"] = _utcnow()
        flow["endedAt"] = flow["updatedAt"]
        atomic_write_json(path, flow)
    return {"ok": True, "flow_id": flow_id, "totals": flow.get("totals", {})}


def get_flow(flow_id: str) -> Dict[str, Any]:
    path = _flow_path(flow_id)
    if not path.exists():
        return {"ok": False, "error": "flow_not_found", "flow_id": flow_id}
    flow = _read_json(path, {})
    return {"ok": True, "flow": flow}


def service_status() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "vault_token_service",
        "pid": os.getpid(),
        "time": _utcnow(),
        "usageDir": str(USAGE_DIR.relative_to(VAULT_ROOT)).replace("\\", "/"),
    }


class TokenHandler(BaseHTTPRequestHandler):
    server_version = "VaultTokenService/1.0"

    def _send(self, status: int, data: Dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _payload(self) -> Tuple[bool, Dict[str, Any]]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            data = json.loads(raw)
            return isinstance(data, dict), data if isinstance(data, dict) else {}
        except Exception as exc:
            return False, {"error": str(exc)}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/status":
            self._send(200, service_status())
            return
        if parsed.path.startswith("/flows/"):
            flow_id = parsed.path.split("/", 2)[2]
            result = get_flow(flow_id)
            self._send(200 if result.get("ok") else 404, result)
            return
        self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        ok, payload = self._payload()
        if not ok:
            self._send(400, {"ok": False, "error": "invalid_json", **payload})
            return
        if parsed.path == "/flows/start":
            self._send(200, start_flow(payload))
            return
        if parsed.path == "/events":
            result = add_event(payload)
            self._send(200 if result.get("ok") else 400, result)
            return
        if parsed.path == "/flows/end":
            result = end_flow(payload)
            self._send(200 if result.get("ok") else 400, result)
            return
        if parsed.path == "/stop":
            self._send(200, {"ok": True, "stopping": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self._send(404, {"ok": False, "error": "not_found"})

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def serve(host: str, port: int) -> int:
    USAGE_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    PORT_FILE.write_text(str(port), encoding="utf-8")
    server = ThreadingHTTPServer((host, port), TokenHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        for file in (PID_FILE, PORT_FILE):
            try:
                file.unlink()
            except OSError:
                pass
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Vault token usage HTTP service")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    return serve(args.host, args.port)


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_token_service"))

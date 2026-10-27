#!/usr/bin/env python3
"""Local token usage service for vault documentation flows."""

import argparse
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from vault_errors import emit_error, wrap_main
from vault_lib import utcnow
from vault_io import atomic_write_json, file_lock


SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
# SP-04: sin esta variable el servicio genera el token al arrancar y lo deja
# en `_token_file()`, de donde lo lee el cliente.
ENV_TOKEN = "VAULT_TOKEN_SERVICE_TOKEN"



sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.consulta.repositorio import RepositorioConsulta  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioConsulta:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioConsulta(construir(root))


def _usage_dir() -> Path:
    return _repo().dir_uso_tokens


def _flow_dir() -> Path:
    return _repo().dir_flujos_tokens


def _pid_file() -> Path:
    return _repo().pid_servicio_tokens


def _port_file() -> Path:
    return _repo().puerto_servicio_tokens


def _token_file() -> Path:
    return _repo().token_servicio_tokens


def token_del_cliente() -> str:
    """El token con el que un cliente se presenta: el de la variable de
    entorno o, si no hay, el que el servicio dejó al arrancar."""
    token = os.environ.get(ENV_TOKEN, "").strip()
    if token:
        return token
    try:
        return _token_file().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


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
    return _flow_dir() / f"{safe}.json"


def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else dict(default)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(default)


def _default_flow(flow_id: str, operation: str = "") -> Dict[str, Any]:
    now = utcnow()
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
    flow_id = (
        payload.get("flow_id")
        or f"flow-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    )
    operation = payload.get("operation", "")
    path = _flow_path(flow_id)
    _flow_dir().mkdir(parents=True, exist_ok=True)
    with file_lock(path):
        flow = _read_json(path, _default_flow(flow_id, operation))
        if not flow.get("createdAt"):
            flow = _default_flow(flow_id, operation)
        flow["flow_id"] = flow_id
        flow["operation"] = operation or flow.get("operation", "")
        flow["status"] = "active"
        flow["updatedAt"] = utcnow()
        if isinstance(payload.get("budget"), dict):
            flow["budget"] = payload["budget"]
        atomic_write_json(path, flow)
    return {
        "ok": True,
        "flow_id": flow_id,
        "path": str(path.relative_to(_raiz())).replace("\\", "/"),
    }


def add_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    flow_id = payload.get("flow_id")
    if not flow_id:
        return emit_error("vault_token_service", "MISSING_REQUIRED_ARG", "falta flow_id")
    path = _flow_path(flow_id)
    _flow_dir().mkdir(parents=True, exist_ok=True)
    text = payload.get("text", "")
    tokens = payload.get("tokens")
    token_count = int(tokens) if tokens is not None else estimate_tokens(str(text))
    event = {
        "ts": utcnow(),
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
        flow["updatedAt"] = utcnow()
        flow.setdefault("events", []).append(event)
        _update_totals(flow, event)
        atomic_write_json(path, flow)
    return {"ok": True, "flow_id": flow_id, "tokens": token_count, "event": event}


def end_flow(payload: Dict[str, Any]) -> Dict[str, Any]:
    flow_id = payload.get("flow_id")
    if not flow_id:
        return emit_error("vault_token_service", "MISSING_REQUIRED_ARG", "falta flow_id")
    path = _flow_path(flow_id)
    with file_lock(path):
        flow = _read_json(path, _default_flow(flow_id))
        flow["status"] = "ended"
        flow["updatedAt"] = utcnow()
        flow["endedAt"] = flow["updatedAt"]
        atomic_write_json(path, flow)
    return {"ok": True, "flow_id": flow_id, "totals": flow.get("totals", {})}


def get_flow(flow_id: str) -> Dict[str, Any]:
    path = _flow_path(flow_id)
    if not path.exists():
        return {**emit_error("vault_token_service", "FILE_NOT_FOUND", f"flow no encontrado: {flow_id}"), "flow_id": flow_id}
    flow = _read_json(path, {})
    return {"ok": True, "flow": flow}


def service_status() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "vault_token_service",
        "pid": os.getpid(),
        "time": utcnow(),
        "usageDir": str(_usage_dir().relative_to(_raiz())).replace("\\", "/"),
    }


class TokenHandler(BaseHTTPRequestHandler):
    """SP-04: toda ruta exige `Authorization: Bearer` y rechaza a un
    navegador (`Origin`) y un `Host` ajeno (DNS rebinding). Un servidor sin
    `token` no atiende a nadie: el default es cerrado."""

    server_version = "VaultTokenService/1.0"

    def _autorizado(self) -> bool:
        # SP-04: Origin → 403, Host ajeno → 403, sin Bearer válido → 401.
        if self.headers.get("Origin") is not None:
            self._send(403, {"ok": False, "error": "origin_rejected"})
            return False
        host, port = self.server.server_address[:2]
        validos = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if host not in ("", "0.0.0.0", "::"):
            validos.add(f"{host}:{port}")
        if (self.headers.get("Host") or "").lower() not in validos:
            self._send(403, {"ok": False, "error": "host_rejected"})
            return False
        esperado = getattr(self.server, "token", "") or ""
        cabecera = self.headers.get("Authorization") or ""
        dado = cabecera[7:] if cabecera.startswith("Bearer ") else ""
        if not esperado or not hmac.compare_digest(dado.encode("utf-8"), esperado.encode("utf-8")):
            self._send(401, {"ok": False, "error": "unauthorized"})
            return False
        return True

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
        if not self._autorizado():
            return
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
        if not self._autorizado():
            return
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
    t0 = time.monotonic()
    _usage_dir().mkdir(parents=True, exist_ok=True)
    t_rutas = time.monotonic()
    # El socket se enlaza ANTES de escribir los ficheros: el `token-service.port`
    # es la señal de "el servicio ya escucha" (la usa el cliente para
    # encontrarlo), y si se escribiera antes, un cliente podría leer un puerto
    # que todavía no acepta conexiones. Medido el 2026-10-26 en la CI (macOS):
    # el servicio llegaba a enlazar, pero el test no lo encontraba a tiempo y
    # fallaba sin decir nada (12 arranques por job, 12 fallos).
    server = ThreadingHTTPServer((host, port), TokenHandler)
    t_bind = time.monotonic()
    server.token = os.environ.get(ENV_TOKEN, "").strip()
    generado = not server.token
    if generado:
        # Generado, no fijo: solo lo conoce quien puede leer el vault.
        server.token = secrets.token_urlsafe(32)
    _pid_file().write_text(str(os.getpid()), encoding="utf-8")
    # El puerto que se publica es el ENLAZADO, no el pedido: con `--port 0`
    # (que es lo que usa el test) son distintos, y publicar el pedido
    # escribiria un 0 donde el cliente debe ir a buscar.
    _port_file().write_text(str(server.server_address[1]), encoding="utf-8")
    if generado:
        _token_file().write_text(server.token, encoding="utf-8")
        try:
            os.chmod(_token_file(), 0o600)
        except OSError:
            pass
    t_ficheros = time.monotonic()
    # Los tiempos de arranque van al stderr: NUNCA al stdout (que es el
    # protocolo) y NUNCA con el token. Si el servicio tarda en abrir el
    # puerto, esto dice en qué fase se fue el tiempo.
    print(
        f"[vault_token_service] listo en {t_ficheros - t0:.3f} s "
        f"(import+rutas {t_rutas - t0:.3f} s, enlace {t_bind - t_rutas:.3f} s, "
        f"ficheros {t_ficheros - t_bind:.3f} s) en "
        f"{server.server_address[0]}:{server.server_address[1]}",
        file=sys.stderr, flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        for file in (_pid_file(), _port_file(), _token_file()):
            try:
                file.unlink()
            except OSError:
                pass
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Vault token usage HTTP service", allow_abbrev=False)
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"Interfaz de escucha (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Puerto de escucha (default: {DEFAULT_PORT})")
    args = parser.parse_args()
    return serve(args.host, args.port)


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_token_service"))

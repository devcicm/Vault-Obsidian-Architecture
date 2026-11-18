"""QA-FL-10 — the token counter flow, end to end, on a fresh vault.

Measured on 2026-11-17 against the real CLI:

- with the service down, `report` and `end` answered `UNEXPECTED_ERROR`
  (critical) instead of `SERVICE_UNAVAILABLE`, and a flow that was already
  persisted and ended could not be read without the service;
- with the service up, `begin`, `end` and then `event` on the same flow
  silently set `status: active` and kept `endedAt`;
- `stop-service` on a stopped service failed with a recovery that said
  `start-service`.

QA-RO-01: `self-test` writes the flow file under `00_System/token-usage/`, so
its envelope carries a work indicator (`written`), as AP-37 asks of every tool
that writes.

Every case goes through the CLI (`apoyo.correr_tool`) on a temporary vault.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from apoyo import correr_tool, entorno, esperar_condicion
from vault.consulta.repositorio import RepositorioConsulta
from vault.kernel import construir

TOOL = "vault_token_counter"
#: The port the published recovery starts the service on (`start-service`
#: without `--port`).
PUERTO_POR_DEFECTO = 8765


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    return raiz


def _repo(vault: Path) -> RepositorioConsulta:
    return RepositorioConsulta(construir(vault))


def _flujo(vault: Path, flow_id: str) -> Path:
    return _repo(vault).dir_flujos_tokens / f"{flow_id}.json"


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _puerto_ocupado(puerto: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", puerto))
        except OSError:
            return True
    return False


def _cli(vault: Path, *argv):
    return correr_tool(TOOL, *argv, env=entorno(vault, quitar=("VAULT_TOKEN_SERVICE_TOKEN",)))


def _parar(vault: Path) -> None:
    """Stop the service of this vault and wait until it released its files."""
    _cli(vault, "stop-service")
    puerto = _repo(vault).puerto_servicio_tokens
    assert esperar_condicion(lambda: not puerto.exists(), timeout=30), \
        "the service did not release its port file after stop-service"


def _sin_servicio(r, comando: str) -> None:
    env = r.envelope
    assert r.codigo == 1, (comando, env)
    assert env["ok"] is False
    assert env["error_code"] == "SERVICE_UNAVAILABLE", (comando, env)
    assert env["recovery"]["action"] == "run_tool"
    assert env["recovery"]["tool"] == TOOL
    assert env["recovery"]["args"] == ["start-service"]


def test_report_and_end_without_service_name_the_service(vault):
    """No service, no persisted flow: the answer is SERVICE_UNAVAILABLE."""
    for comando in ("report", "end"):
        r = _cli(vault, comando, "--flow-id", "f1")
        _sin_servicio(r, comando)
    assert not _flujo(vault, "f1").exists(), "end without service must not write a flow"


def test_stop_service_on_a_stopped_service_is_idempotent(vault):
    """Mirrors `start-service` on a running service (`alreadyRunning`)."""
    r = _cli(vault, "stop-service")
    assert r.codigo == 0, r.envelope
    assert r.envelope["ok"] is True
    assert r.envelope["alreadyStopped"] is True
    assert "url" in r.envelope


def test_status_without_service_keeps_its_answer(vault):
    """Previous behavior: `status` with the service down."""
    r = _cli(vault, "status")
    assert r.codigo == 1
    assert r.envelope["error_code"] == "SERVICE_UNAVAILABLE"
    assert r.envelope["running"] is False


def test_self_test_declares_the_flow_it_writes(vault):
    r = _cli(vault, "self-test")
    env = r.envelope
    assert r.codigo == 0, env
    assert env["ok"] is True
    # Previous envelope keys stay.
    for clave in ("started", "event", "report", "ended"):
        assert env[clave]["ok"] is True, (clave, env[clave])
    assert env["report"]["flow"]["status"] == "active"
    assert env["ended"]["totals"]["events"] >= 1
    # QA-RO-01: the write is real and the envelope says so.
    escrito = _flujo(vault, "self-test")
    assert escrito.is_file()
    assert env["written"] == 1
    assert env["path"] == "00_System/token-usage/flows/self-test.json"


def test_flow_lifecycle_with_and_without_service(vault):
    puerto = _puerto_libre()
    try:
        r = _cli(vault, "start-service", "--port", puerto)
        assert r.codigo == 0 and r.envelope["ok"] is True, r.envelope

        # Previous behavior: begin, event and report on a live flow.
        r = _cli(vault, "begin", "--flow-id", "f1", "--operation", "qa")
        assert r.codigo == 0 and r.envelope["ok"] is True, r.envelope
        r = _cli(vault, "event", "--flow-id", "f1", "--direction", "input",
                 "--text", "hola mundo")
        assert r.codigo == 0 and r.envelope["ok"] is True, r.envelope
        r = _cli(vault, "report", "--flow-id", "f1")
        assert r.codigo == 0, r.envelope
        assert r.envelope["flow"]["totals"]["events"] == 1
        assert r.envelope["flow"]["status"] == "active"

        # A flow nobody began is reported as not found, not as a crash.
        r = _cli(vault, "report", "--flow-id", "nadie")
        assert r.codigo == 1
        assert r.envelope["error_code"] == "FILE_NOT_FOUND", r.envelope

        r = _cli(vault, "end", "--flow-id", "f1")
        assert r.codigo == 0 and r.envelope["ok"] is True, r.envelope
        cerrado = _flujo(vault, "f1").read_bytes()

        # An event on an ended flow is rejected and nothing is written.
        r = _cli(vault, "event", "--flow-id", "f1", "--text", "tarde")
        env = r.envelope
        assert r.codigo == 1, env
        assert env["ok"] is False
        assert env["error_code"] == "INVALID_STATUS", env
        assert "begin --flow-id f1" in env["message"]
        assert _flujo(vault, "f1").read_bytes() == cerrado

        # The path the error names reopens the flow consistently.
        r = _cli(vault, "begin", "--flow-id", "f1")
        assert r.codigo == 0, r.envelope
        r = _cli(vault, "report", "--flow-id", "f1")
        assert r.envelope["flow"]["status"] == "active"
        assert r.envelope["flow"]["endedAt"] == ""
        r = _cli(vault, "event", "--flow-id", "f1", "--text", "otra vez")
        assert r.codigo == 0 and r.envelope["ok"] is True, r.envelope
        r = _cli(vault, "end", "--flow-id", "f1")
        assert r.codigo == 0, r.envelope
        assert r.envelope["totals"]["events"] == 2
        persistido = _flujo(vault, "f1").read_bytes()

        r = _cli(vault, "stop-service")
        assert r.codigo == 0 and r.envelope["ok"] is True, r.envelope
        assert esperar_condicion(
            lambda: not _repo(vault).puerto_servicio_tokens.exists(), timeout=30)
        r = _cli(vault, "stop-service")
        assert r.codigo == 0 and r.envelope["alreadyStopped"] is True, r.envelope

        # Service down: the persisted flow is still readable, from its file.
        r = _cli(vault, "report", "--flow-id", "f1")
        env = r.envelope
        assert r.codigo == 0, env
        assert env["ok"] is True
        assert env["source"] == "persisted"
        assert env["flow"]["status"] == "ended"
        assert env["flow"]["totals"]["events"] == 2

        # `end` needs the service: it says so, and writes nothing.
        fallo = _cli(vault, "end", "--flow-id", "f1")
        _sin_servicio(fallo, "end")
        assert _flujo(vault, "f1").read_bytes() == persistido

        # The recovery, followed literally, and the original command again.
        if _puerto_ocupado(PUERTO_POR_DEFECTO):
            pytest.skip(f"port {PUERTO_POR_DEFECTO} is taken: the literal recovery cannot start")
        r = _cli(vault, *fallo.envelope["recovery"]["args"])
        assert r.codigo == 0 and r.envelope["ok"] is True, r.envelope
        r = _cli(vault, "end", "--flow-id", "f1")
        assert r.codigo == 0 and r.envelope["ok"] is True, r.envelope
        assert r.envelope["totals"]["events"] == 2
    finally:
        _parar(vault)


def test_ending_a_flow_never_begun_writes_nothing(vault, monkeypatch):
    """`end` on an unknown flow used to create an empty, ended flow file
    (W5 advisory, 2026-11-17). Like `get_flow`, it reports FILE_NOT_FOUND."""
    import vault_io
    import vault_token_service as servicio

    monkeypatch.setenv("VAULT_ROOT", str(vault))
    vault_io.set_vault_root(vault)
    r = servicio.end_flow({"flow_id": "nunca"})
    assert r["ok"] is False and r["error_code"] == "FILE_NOT_FOUND", r
    assert r["flow_id"] == "nunca"
    assert not _flujo(vault, "nunca").exists()

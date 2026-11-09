"""SP-04 — el transporte HTTP/SSE del servidor MCP no lo abre cualquiera.

Medido antes del arreglo con `--port`: el servidor respondía
`Access-Control-Allow-Origin: *` y no pedía credencial alguna. Cualquier página
abierta en el navegador del usuario podía hacer `GET /sse`, leer el
`sessionId` del primer evento y llamar a `vault_delete` o `vault_write` con
`POST /message`. Escuchar solo en 127.0.0.1 no lo impedía: el navegador vive en
127.0.0.1. Además, `/health` publicaba las rutas absolutas de todos los vaults
registrados, y la respuesta de cada llamada se reenviaba a **todas** las
sesiones abiertas sobre el mismo vault.

Se comprueba con el criterio del consumidor (AP-44): el servidor real, por
HTTP, desde fuera.
"""

import http.client
import json
import os
import shutil
import socket
import ssl
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER = REPO_ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs"
TOKEN = "t0ken-de-prueba-" + "x" * 32

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="el servidor MCP necesita Node en el PATH"
)


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Servidor:
    def __init__(self, vault: Path, token=TOKEN, tokens=None, bind_host="127.0.0.1", tls=None):
        self.port = _puerto_libre()
        self.bind_host = bind_host
        env = {**os.environ, "VAULT_ROOT": str(vault), "VAULT_SCAN_ROOTS": str(vault)}
        env.pop("VAULT_MCP_TOKEN", None)
        env.pop("VAULT_MCP_TOKENS", None)
        if token is not None:
            env["VAULT_MCP_TOKEN"] = token
        if tokens is not None:
            env["VAULT_MCP_TOKENS"] = tokens
        self.proc = subprocess.Popen(
            ["node", str(SERVER), "--port", str(self.port), "--host", bind_host] +
            (["--tls-cert", str(tls[0]), "--tls-key", str(tls[1])] if tls else []),
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            env=env, cwd=str(REPO_ROOT),
        )
        self.tls = tls
        limite = time.time() + 20
        while time.time() < limite:
            try:
                with socket.create_connection((bind_host, self.port), timeout=0.5):
                    return
            except OSError:
                if self.proc.poll() is not None:
                    raise RuntimeError(self.proc.stderr.read().decode("utf-8", "replace"))
                time.sleep(0.1)
        raise RuntimeError("el servidor no abrió el puerto")

    def pedir(self, metodo, ruta, cabeceras=None, cuerpo=None, host=None):
        if self.tls:
            c = http.client.HTTPSConnection(self.bind_host, self.port, timeout=10,
                                            context=ssl.create_default_context(cafile=str(self.tls[0])))
        else:
            c = http.client.HTTPConnection(self.bind_host, self.port, timeout=10)
        c.putrequest(metodo, ruta, skip_host=True)
        c.putheader("Host", host or f"{self.bind_host}:{self.port}")
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else b""
        for k, v in (cabeceras or {}).items():
            c.putheader(k, v)
        if cuerpo is not None:
            c.putheader("Content-Type", "application/json")
        c.putheader("Content-Length", str(len(datos)))
        c.endheaders(datos)
        return c, c.getresponse()

    def abrir_sse(self, token=TOKEN):
        c, r = self.pedir("GET", "/sse", {"Authorization": f"Bearer {token}"})
        assert r.status == 200, r.status
        linea = r.fp.readline().decode()
        while not linea.startswith("data: "):
            linea = r.fp.readline().decode()
        return c, r, json.loads(linea[6:])["sessionId"]

    def cerrar(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc.stderr.close()


@pytest.fixture
def servidor(tmp_path):
    vault = tmp_path / "vault"
    for s in ("00_System", "07_Knowledge"):
        (vault / s).mkdir(parents=True)
    srv = Servidor(vault)
    yield srv
    srv.cerrar()


def test_sin_token_no_se_abre_sesion(servidor):
    _, r = servidor.pedir("GET", "/sse")
    assert r.status == 401


def test_wildcard_host_is_rejected():
    r = subprocess.run(["node", str(SERVER), "--port", "3000", "--host", "0.0.0.0"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=20)
    assert r.returncode == 2


def test_lan_binding_auth_and_host_checks(tmp_path):
    host = os.environ.get("VAULT_MCP_TEST_LAN_HOST")
    if not host:
        pytest.skip("set VAULT_MCP_TEST_LAN_HOST to an assigned local IPv4 address")
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    srv = Servidor(vault, bind_host=host)
    try:
        c, r = srv.pedir("GET", "/sse")
        assert r.status == 401
        c.close()
        c, r = srv.pedir("GET", "/health", host=f"evil.example:{srv.port}")
        assert r.status == 403
        c.close()
        c, r = srv.pedir("GET", "/sse", {"Authorization": f"Bearer {TOKEN}",
                                           "Origin": "https://evil.example"})
        assert r.status == 403
        c.close()
        c, _, sid = srv.abrir_sse()
        assert sid
        msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                          "clientInfo": {"name": "test", "version": "1"}}}
        conn, response = srv.pedir("POST", "/message",
                                   {"Authorization": f"Bearer {TOKEN}", "X-MCP-Session": sid}, msg)
        assert response.status == 200 and "result" in json.loads(response.read())
        conn.close()
        conn, response = srv.pedir("POST", "/message",
                                   {"Authorization": f"Bearer {TOKEN}", "X-MCP-Session": sid},
                                   {"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert response.status == 202
        response.read()
        conn.close()
        conn, response = srv.pedir("POST", "/message",
                                   {"Authorization": f"Bearer {TOKEN}", "X-MCP-Session": sid},
                                   {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert response.status == 200 and json.loads(response.read())["result"]["tools"]
        conn.close()
        c.close()
    finally:
        srv.cerrar()


def test_un_token_equivocado_no_abre_sesion(servidor):
    _, r = servidor.pedir("GET", "/sse", {"Authorization": "Bearer otro"})
    assert r.status == 401


def test_con_token_se_abre_sesion(servidor):
    c, _, sid = servidor.abrir_sse()
    assert sid
    c.close()


def test_message_limit_counts_bytes_and_server_remains_available(servidor):
    sse, _, sid = servidor.abrir_sse()
    try:
        conn, response = servidor.pedir(
            "POST", "/message", {"Authorization": f"Bearer {TOKEN}", "X-MCP-Session": sid},
            {"jsonrpc": "2.0", "id": 1, "method": "x", "params": {"body": "a" * (1024 * 1024)}})
        assert response.status == 413
        response.read()
        conn.close()
        conn, response = servidor.pedir("GET", "/health")
        assert response.status == 200
        conn.close()
    finally:
        sse.close()


def test_session_limit_releases_slot_after_disconnect(servidor):
    clients = []
    try:
        for _ in range(64):
            c, _, _ = servidor.abrir_sse()
            clients.append(c)
        c, response = servidor.pedir("GET", "/sse", {"Authorization": f"Bearer {TOKEN}"})
        assert response.status == 503
        response.read()
        c.close()
        clients.pop().close()
        deadline = time.time() + 5
        while True:
            c, response = servidor.pedir("GET", "/sse", {"Authorization": f"Bearer {TOKEN}"})
            if response.status == 200:
                c.close()
                break
            response.read()
            c.close()
            assert time.time() < deadline
    finally:
        for client in clients:
            client.close()


def test_chunked_message_cannot_bypass_size_limit(servidor):
    sse, _, sid = servidor.abrir_sse()
    try:
        conn = http.client.HTTPConnection(servidor.bind_host, servidor.port, timeout=10)
        conn.request("POST", "/message", body=iter([b"x" * 600000, b"x" * 600000]),
                     headers={"Authorization": f"Bearer {TOKEN}", "X-MCP-Session": sid},
                     encode_chunked=True)
        response = conn.getresponse()
        assert response.status == 413
        response.read()
        conn.close()
    finally:
        sse.close()


def test_tls_requires_both_files_and_no_silent_fallback(tmp_path):
    invalid = tmp_path / "invalid.pem"
    invalid.write_text("not a TLS certificate or key", encoding="utf-8")
    for args in (["--tls-cert", str(tmp_path / "absent")],
                 ["--tls-cert", str(tmp_path / "absent"), "--tls-key", str(tmp_path / "absent")],
                 ["--tls-cert", str(invalid), "--tls-key", str(invalid)]):
        result = subprocess.run(["node", str(SERVER), "--port", "12345", *args],
                                capture_output=True, timeout=20)
        assert result.returncode != 0


def test_https_auth_and_request_limits(tmp_path):
    openssl = shutil.which("openssl")
    if not openssl:
        git_openssl = Path("C:/Program Files/Git/usr/bin/openssl.exe")
        openssl = str(git_openssl) if git_openssl.exists() else None
    if not openssl:
        pytest.skip("OpenSSL required to create a disposable test certificate")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", str(key), "-out", str(cert), "-days", "1",
                    "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"],
                   check=True, capture_output=True, timeout=30)
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    srv = Servidor(vault, tls=(cert, key))
    try:
        c, response = srv.pedir("GET", "/sse")
        assert response.status == 401
        response.read()
        c.close()
        sse, _, sid = srv.abrir_sse()
        c, response = srv.pedir("POST", "/message",
                               {"Authorization": f"Bearer {TOKEN}", "X-MCP-Session": sid},
                               {"jsonrpc": "2.0", "method": "x", "data": "a" * (1024 * 1024)})
        assert response.status == 413
        response.read()
        c.close()
        sse.close()
    finally:
        srv.cerrar()


def test_una_peticion_de_navegador_se_rechaza_aun_con_token(servidor):
    _, r = servidor.pedir("GET", "/sse", {
        "Authorization": f"Bearer {TOKEN}", "Origin": "https://evil.example"})
    assert r.status == 403


def test_un_host_ajeno_se_rechaza_anti_dns_rebinding(servidor):
    _, r = servidor.pedir("GET", "/sse", {"Authorization": f"Bearer {TOKEN}"},
                          host=f"evil.example:{servidor.port}")
    assert r.status == 403


def test_no_hay_cors_abierto(servidor):
    _, r = servidor.pedir("OPTIONS", "/message")
    assert r.getheader("Access-Control-Allow-Origin") is None


def test_message_sin_token_se_rechaza_aunque_conozca_la_sesion(servidor):
    c, _, sid = servidor.abrir_sse()
    _, r = servidor.pedir("POST", "/message", {"X-MCP-Session": sid},
                          {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status == 401
    c.close()


def test_health_sin_token_no_publica_rutas(servidor, tmp_path):
    _, r = servidor.pedir("GET", "/health")
    cuerpo = r.read().decode()
    assert r.status == 200 and json.loads(cuerpo)["ok"]
    assert str(tmp_path) not in cuerpo and str(tmp_path).replace("\\", "/") not in cuerpo
    assert "vaults" not in json.loads(cuerpo)


def test_la_respuesta_no_se_reenvia_a_otra_sesion(servidor):
    ca, ra, sid_a = servidor.abrir_sse()
    cb, rb, _ = servidor.abrir_sse()
    _, r = servidor.pedir("POST", "/message",
                          {"Authorization": f"Bearer {TOKEN}", "X-MCP-Session": sid_a},
                          {"jsonrpc": "2.0", "id": 7, "method": "tools/list"})
    assert r.status == 200
    r.read()
    rb.fp.raw._sock.settimeout(1.5)
    with pytest.raises((socket.timeout, TimeoutError, OSError)):
        linea = rb.fp.readline()
        while linea in (b"\n", b"\r\n"):
            linea = rb.fp.readline()
        if not linea:
            raise OSError("cerrado")
        pytest.fail(f"la sesión B recibió: {linea[:120]!r}")
    ca.close()
    cb.close()


def test_sin_token_configurado_se_genera_uno_y_se_exige(tmp_path):
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    srv = Servidor(vault, token=None)
    try:
        _, r = srv.pedir("GET", "/sse")
        assert r.status == 401
    finally:
        srv.cerrar()


def test_sp04_esta_catalogada_con_enforcement_real():
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import vault_norms_catalog

    norma = next(n for n in vault_norms_catalog.NORM_CATALOG if n["code"] == "SP-04")
    assert norma["enforcement"] == "guard"
    assert "vault_produccion" in norma["tools_enforcing"]
    assert "SP-04" in vault_norms_catalog.NORM_CATALOG[
        [n["code"] for n in vault_norms_catalog.NORM_CATALOG].index("AP-36")
    ]["distinguido_de"]

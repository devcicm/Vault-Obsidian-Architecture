"""SP-11 — el transporte HTTP/SSE del servidor MCP no lo abre cualquiera.

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
    def __init__(self, vault: Path, token=TOKEN):
        self.port = _puerto_libre()
        env = {**os.environ, "VAULT_ROOT": str(vault), "VAULT_SCAN_ROOTS": str(vault)}
        env.pop("VAULT_MCP_TOKEN", None)
        if token is not None:
            env["VAULT_MCP_TOKEN"] = token
        self.proc = subprocess.Popen(
            ["node", str(SERVER), "--port", str(self.port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            env=env, cwd=str(REPO_ROOT),
        )
        limite = time.time() + 20
        while time.time() < limite:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return
            except OSError:
                if self.proc.poll() is not None:
                    raise RuntimeError(self.proc.stderr.read().decode("utf-8", "replace"))
                time.sleep(0.1)
        raise RuntimeError("el servidor no abrió el puerto")

    def pedir(self, metodo, ruta, cabeceras=None, cuerpo=None, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.putrequest(metodo, ruta, skip_host=True)
        c.putheader("Host", host or f"127.0.0.1:{self.port}")
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


def test_un_token_equivocado_no_abre_sesion(servidor):
    _, r = servidor.pedir("GET", "/sse", {"Authorization": "Bearer otro"})
    assert r.status == 401


def test_con_token_se_abre_sesion(servidor):
    c, _, sid = servidor.abrir_sse()
    assert sid
    c.close()


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

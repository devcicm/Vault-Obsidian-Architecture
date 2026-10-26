"""Los recursos del servidor MCP se leen de verdad: `resources/read` no miente.

El PRD de MCP (`docs/product/prd-mcp.md`) declaraba el punto de uso de
`vault://` en su Definition of Done como PENDIENTE, y el servidor exponía los
siete recursos sin que nadie los leyera. Medido el 2026-10-26 con una sesión
JSON-RPC real: `resources/read vault://graph` devolvía `contents[0].text` con
el texto del error («Error reading resource vault://graph: The "path" argument
must be…») — un recurso con apariencia de contenido válido que no lo era. El
defecto era una llamada sin la raíz del vault; el Agente que lo detecta es
este test, que lee los siete.

Criterio del consumidor (AP-44): sesión JSON-RPC real contra el servidor, no
lectura del fuente. Por eso no se comprueba que el código «parezca» bien: se
comprueba que lo que llega al cliente es lo que un agente leería.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER = REPO_ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="el servidor MCP necesita Node en el PATH"
)

#: Los siete recursos que el servidor declara en `resources/list`.
RECURSOS = (
    "vault://graph",
    "vault://graph/enriched",
    "vault://health",
    "vault://registry",
    "vault://traceability/mutations",
    "vault://catalog",
    "vault://state",
)


class SesionRecursos:
    """Cliente JSON-RPC mínimo: initialize → resources/list → resources/read."""

    def __init__(self, vault_root: Path):
        env = {**os.environ, "VAULT_ROOT": str(vault_root),
               "VAULT_SCAN_ROOTS": str(vault_root)}
        env.pop("PYTHONIOENCODING", None)
        env.pop("PYTHONUTF8", None)
        self.proc = subprocess.Popen(
            ["node", str(SERVER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", env=env, cwd=str(REPO_ROOT),
        )
        threading.Thread(target=self._drenar, daemon=True).start()
        self._id = 0
        self._pedir("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"},
        })
        self._enviar({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _drenar(self) -> None:
        for _ in self.proc.stderr:
            pass

    def _enviar(self, mensaje: dict) -> None:
        self.proc.stdin.write(json.dumps(mensaje) + "\n")
        self.proc.stdin.flush()

    def _pedir(self, metodo: str, params: dict | None = None) -> dict:
        self._id += 1
        self._enviar({"jsonrpc": "2.0", "id": self._id, "method": metodo,
                      "params": params or {}})
        while True:
            linea = self.proc.stdout.readline()
            if not linea:
                raise AssertionError(f"el servidor cerró stdout en {metodo}")
            try:
                d = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if d.get("id") == self._id:
                return d

    def cerrar(self) -> None:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                               capture_output=True, check=False)
            else:
                self.proc.terminate()
                self.proc.wait(timeout=5)
        except Exception:  # noqa: BLE001 — el cierre no es lo que se prueba
            pass


@pytest.fixture(scope="module")
def sesion(tmp_path_factory):
    vault = tmp_path_factory.mktemp("mcp-recursos") / "vault"
    vault.mkdir()
    s = SesionRecursos(vault)
    try:
        yield s
    finally:
        s.cerrar()


def _texto_de(respuesta: dict) -> str:
    return respuesta["result"]["contents"][0]["text"]


def test_los_siete_recursos_se_declaran(sesion):
    r = sesion._pedir("resources/list")
    uris = [x["uri"] for x in r["result"]["resources"]]
    assert set(RECURSOS) <= set(uris), uris


@pytest.mark.parametrize("uri", RECURSOS)
def test_cada_recurso_se_lee_y_no_trae_un_error_disfrazado(sesion, uri):
    """El defecto medido: el error venía dentro de `text` con cara de contenido."""
    r = sesion._pedir("resources/read", {"uri": uri})
    texto = _texto_de(r)
    assert not texto.startswith("Error reading resource"), texto
    datos = json.loads(texto)  # todo lo que se publica es JSON parseable
    if isinstance(datos, dict) and datos.get("ok") is False:
        # Un `ok: false` explícito es una respuesta legítima (p. ej. un
        # artefacto que aún no existe), pero tiene que decirlo con su código.
        assert datos.get("error_code"), datos
    assert r["result"]["contents"][0]["uri"] == uri


def test_el_grafo_trae_nodos_y_no_una_excepcion(sesion):
    """`vault://graph` sin la raíz del vault reventaba dentro de `readFile`."""
    r = sesion._pedir("resources/read", {"uri": "vault://graph"})
    datos = json.loads(_texto_de(r))
    assert datos.get("ok") is True, datos
    assert "nodes" in datos and "edges" in datos, list(datos)

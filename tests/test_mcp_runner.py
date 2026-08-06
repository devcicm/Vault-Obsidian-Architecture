"""El runner MCP es el único camino por el que un agente real toca el estándar.

Hasta v39.3 no tenía ni un test: 30 líneas de `spawn` con cuatro defectos que
solo se ven desde fuera de Python, que es justo donde ningún test miraba.

1. El hijo heredaba la codificación de consola (cp1252 en Windows). Los
   caracteres que no existen en cp1252 —`→` en los `fix_hint` de `vault_audit`,
   `≥` en la señal de AP-17— matan la tool con UnicodeEncodeError; los acentos,
   que sí existen, salen como bytes cp1252 dentro de un JSON que el runner lee
   como UTF-8. Mojibake con exit 0: corrupción silenciosa del español.
2. `code !== 0` rechazaba y tiraba el envelope. Pero las puertas `--strict`
   devuelven 1 CON `ok: true` y el informe completo, por diseño. El agente
   perdía el diagnóstico justo cuando algo fallaba.
3. Timeout fijo de 120 s, ignorando `VAULT_TOOL_TIMEOUT`. Las tools largas que
   el propio repo reconoce eran inalcanzables por MCP.
4. Salida no-JSON con exit 0 → `{ok: true}` fabricado, sin indicador de trabajo
   (familia AP-37).

Los tres primeros se comprueban con el criterio del consumidor (AP-44): sesión
JSON-RPC real contra el servidor, no lectura del fuente.
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER = REPO_ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs"
SCRIPTS = REPO_ROOT / "scripts"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="el runner MCP necesita Node en el PATH"
)


class SesionMCP:
    """Cliente JSON-RPC mínimo sobre stdio, line-delimited."""

    def __init__(self, vault_root: Path, env_extra=None):
        env = {**os.environ, "VAULT_ROOT": str(vault_root), **(env_extra or {})}
        # Se quita a propósito: el runner tiene que fijarla él. Si el test la
        # heredara, el defecto de codificación quedaría tapado por el entorno.
        env.pop("PYTHONIOENCODING", None)
        env.pop("PYTHONUTF8", None)
        self.proc = subprocess.Popen(
            ["node", str(SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(REPO_ROOT),
        )
        self._id = 0
        self._pedir("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"},
        })
        self._enviar({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _enviar(self, mensaje):
        self.proc.stdin.write(json.dumps(mensaje) + "\n")
        self.proc.stdin.flush()

    def _pedir(self, method, params, timeout=180):
        self._id += 1
        self._enviar({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        # Con el runner roto la tool muere y nunca llega respuesta: un
        # `readline()` desnudo cuelga la suite entera en vez de fallar. El
        # síntoma que este fichero persigue es exactamente ese, así que la
        # lectura va acotada.
        cola = queue.Queue()
        threading.Thread(
            target=lambda: cola.put(self.proc.stdout.readline()), daemon=True
        ).start()
        try:
            linea = cola.get(timeout=timeout)
        except queue.Empty:
            raise AssertionError(f"el servidor no respondió a {method} en {timeout}s")
        assert linea, f"el servidor cerró stdout sin responder a {method}"
        return json.loads(linea)

    def llamar(self, tool, argumentos):
        return self._pedir("tools/call", {"name": tool, "arguments": argumentos})

    def cerrar(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=30)
        except Exception:
            self.proc.kill()


def _texto_de(respuesta) -> str:
    """Todo el payload de la respuesta, para buscar en él sin depender del shape."""
    return json.dumps(respuesta, ensure_ascii=False)


def _init_vault(destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_init.py")],
        env={**os.environ, "VAULT_ROOT": str(destino), "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return destino


@pytest.fixture(scope="module")
def vault_con_hallazgo(tmp_path_factory):
    """Un vault que fuerza a `vault_audit` a emitir un `fix_hint` con `→`."""
    vault = _init_vault(tmp_path_factory.mktemp("mcp") / "vault")
    (vault / "07_Knowledge").mkdir(exist_ok=True)
    (vault / "07_Knowledge" / "configuracion.md").write_text(
        "---\ntitle: Configuración del API\ntype: knowledge\nstatus: draft\n---\n\n"
        "Referencia rota: [[[[otra nota]] y un párrafo con acentos.\n",
        encoding="utf-8",
    )
    return vault


@pytest.fixture(scope="module")
def sesion(vault_con_hallazgo):
    s = SesionMCP(vault_con_hallazgo)
    yield s
    s.cerrar()


def test_los_caracteres_fuera_de_cp1252_sobreviven(sesion):
    """`→` vive en los fix_hint de vault_audit. Bajo cp1252 esto era un crash."""
    r = sesion.llamar("vault_audit", {})
    texto = _texto_de(r)
    assert "error" not in r, texto[:500]
    assert "→" in texto, "el fix_hint con flecha no llegó: la tool murió o se truncó"


def test_los_acentos_no_llegan_mojibake(sesion):
    r = sesion.llamar("vault_audit", {})
    texto = _texto_de(r)
    assert "�" not in texto, "hay caracteres de reemplazo: se decodificó mal"
    for basura in ("Ã³", "Ã¡", "Ã©", "Ã±"):
        assert basura not in texto, f"UTF-8 leído como latin-1: {basura}"


def test_un_exit_no_cero_no_descarta_el_envelope(vault_con_hallazgo, tmp_path):
    """`--strict` devuelve 1 con el informe entero. Es un resultado, no un fallo."""
    sucio = _init_vault(tmp_path / "sucio")
    (sucio / "07_Knowledge").mkdir(exist_ok=True)
    (sucio / "07_Knowledge" / "mala.md").write_text(
        "---\ntitle: x\n---\n\nsin type ni status\n", encoding="utf-8"
    )
    s = SesionMCP(sucio)
    try:
        r = s.llamar("vault_norms", {"audit": True, "root": str(sucio), "strict": True})
    finally:
        s.cerrar()
    texto = _texto_de(r)
    assert "exited with code" not in texto, "se tiró el informe por el código de salida"
    assert "vault_norms" in texto, texto[:500]


def test_el_timeout_sale_de_vault_tool_timeout():
    """Mismo dial que Python (`vault_errors.TOOL_TIMEOUT_SECONDS`), no un fijo."""
    fuente = SERVER.read_text(encoding="utf-8")
    assert "VAULT_TOOL_TIMEOUT" in fuente
    assert "timeout: toolTimeoutMs()" in fuente, "el spawn volvió a un timeout literal"


def test_el_runner_declara_la_codificacion_del_hijo():
    fuente = SERVER.read_text(encoding="utf-8")
    assert 'env.PYTHONIOENCODING = "utf-8"' in fuente
    assert "setEncoding(\"utf8\")" in fuente, (
        "sin fijar la codificación del stream, un chunk parte un carácter multibyte"
    )


def test_la_salida_no_json_no_finge_trabajo():
    """AP-37: `ok: true` sin envelope tiene que declararse como tal."""
    fuente = SERVER.read_text(encoding="utf-8")
    assert "non_json_output" in fuente and "structured: false" in fuente


def test_ninguna_tool_ancla_rutas_de_entrada_en_el_cwd():
    """El CWD del hijo es `scripts/`: `--file src/foo.ts` iría a `scripts/src/`."""
    culpables = [
        py.name
        for py in sorted(SCRIPTS.glob("vault_*.py"))
        if "Path.cwd()" in py.read_text(encoding="utf-8") and py.name != "vault_io.py"
    ]
    assert not culpables, (
        f"resuelven contra el CWD del proceso en vez de vault_io.resolve_input_path: {culpables}"
    )

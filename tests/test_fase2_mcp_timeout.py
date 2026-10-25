"""El timeout del cliente MCP tiene que cumplirse (H-L3-03).

El cliente leia la respuesta del servidor con `readline()` sobre el pipe, que
BLOQUEA: el `timeout` del metodo se calculaba mientras se esperaba y, con la
llamada bloqueada, nunca llegaba a dispararse. Un servidor MCP que no contesta
dejaba el harness colgado para siempre.

La lectura va ahora en un hilo aparte, con una cola: el metodo espera con
`queue.get(timeout=...)` y el timeout se cumple.

Este test es la PRUEBA del defecto: con la version antigua (readline
bloqueante) se colgaba; con la actual vuelve con el error de timeout en el
tiempo previsto. Un proceso que lee stdin y nunca contesta hace de servidor
mudo.
"""
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "audits" / "fase2"))

import paridad_cli_mcp as verificador  # noqa: E402


def test_el_timeout_se_cumple_con_un_servidor_que_no_contesta():
    mudo = [sys.executable, "-c", "import sys; sys.stdin.read()"]
    cliente = verificador.Mcp(Path("nada"), dict(os.environ), cmd=mudo)
    inicio = time.monotonic()
    try:
        respuesta = cliente.llamar("initialize", {}, timeout=2)
    finally:
        cliente.cerrar()
    elapsed = time.monotonic() - inicio
    assert "error" in respuesta, respuesta
    assert "timeout" in str(respuesta["error"]).lower(), respuesta
    assert elapsed < 20, f"el timeout no se cumplio: tardo {elapsed:.1f}s"


def test_una_respuesta_normal_sigue_llegando():
    """El arreglo del timeout no puede romper el camino feliz."""
    mjs_env = os.environ.get("VAULT_MCP_MJS", "")
    if not mjs_env:
        pytest.skip("sin VAULT_MCP_MJS: la comprobacion en vivo requiere el "
                    "servidor MCP instalado")
    mjs = Path(mjs_env)
    if not mjs.exists():
        pytest.skip(f"el servidor MCP indicado no existe: {mjs}")
    cliente = verificador.Mcp(mjs, dict(os.environ))
    try:
        respuesta = cliente.llamar("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "test-timeout", "version": "1"}}, timeout=60)
    finally:
        cliente.cerrar()
    assert "result" in respuesta, respuesta
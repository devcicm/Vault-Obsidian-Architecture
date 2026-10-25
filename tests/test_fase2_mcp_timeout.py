"""El timeout del cliente MCP tiene que ser un PLAZO GLOBAL (H-L3-03, H-L3-06).

El cliente leia la respuesta del servidor con `readline()` sobre el pipe, que
BLOQUEA: el `timeout` del metodo se calculaba mientras se esperaba y, con la
llamada bloqueada, nunca llegaba a dispararse. Un servidor MCP que no contesta
dejaba el harness colgado para siempre.

Ahora la lectura va en un hilo aparte y la espera gobierna un UNICO deadline
monotonico: `queue.get(timeout=restante)`. Por eso un goteo de notificaciones
que no son la respuesta esperada NO puede alargar la espera: el plazo se
consume igual.

Estos tests cubren: servidor silencioso, respuesta valida, mensajes con otro id,
notificaciones continuas sin la respuesta esperada y terminacion del proceso.
NO son un fallo del servidor MCP: son fallos del harness.
"""
import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
def _cargar_paridad_cli_mcp():
    """Carga por ruta: `audits/fase2/` no es un paquete de la suite."""
    import importlib.util

    ruta = ROOT / "audits" / "fase2" / "paridad_cli_mcp.py"
    spec = importlib.util.spec_from_file_location("paridad_cli_mcp", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


verificador = _cargar_paridad_cli_mcp()


def _cliente(codigo: str, extra: str = ""):
    return verificador.Mcp(Path("nada"), dict(os.environ),
                            cmd=[sys.executable, "-c", codigo + extra])


def test_el_timeout_se_cumple_con_un_servidor_que_no_contesta():
    cliente = _cliente("import sys; sys.stdin.read()")
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


def test_ignora_las_lineas_con_otro_id():
    """Primero llega una respuesta con OTRO id (ruido de otro cliente o una
    notificacion mal formada): el cliente debe seguir esperando la suya."""
    codigo = (
        "import sys, json\n"
        "for linea in sys.stdin:\n"
        "    d = json.loads(linea)\n"
        "    print(json.dumps({'jsonrpc':'2.0','id':999,'result':{'ok':True}}), flush=True)\n"
        "    print(json.dumps({'jsonrpc':'2.0','id':d['id'],'result':{'ok':'mio'}}), flush=True)\n"
    )
    cliente = _cliente(codigo)
    try:
        respuesta = cliente.llamar("initialize", {}, timeout=15)
    finally:
        cliente.cerrar()
    assert "result" in respuesta, respuesta
    assert respuesta["result"].get("ok") == "mio", respuesta


def test_las_notificaciones_continuas_no_alargan_el_plazo():
    """El caso adversarial: el servidor NO contesta, pero no para de hablar.
    Un `queue.get(timeout=...)` por linea habria renovado el plazo en cada
    notificacion y la espera podia no acabar nunca."""
    codigo = (
        "import sys, json, time\n"
        "i = 0\n"
        "for linea in sys.stdin:\n"
        "    while True:\n"
        "        i += 1\n"
        "        print(json.dumps({'jsonrpc':'2.0','method':'notifications/x','params':{'n':i}}), flush=True)\n"
    )
    cliente = _cliente(codigo)
    inicio = time.monotonic()
    try:
        respuesta = cliente.llamar("initialize", {}, timeout=3)
    finally:
        cliente.cerrar()
    elapsed = time.monotonic() - inicio
    assert "error" in respuesta, respuesta
    assert "timeout" in str(respuesta["error"]).lower(), respuesta
    assert elapsed < 25, (
        f"el goteo de notificaciones alargo el plazo: tardo {elapsed:.1f}s "
        f"con un timeout de 3s")


def test_la_terminacion_del_proceso_no_cuelga_el_harness():
    """Si el proceso MCP muere, el cliente debe volver (con el motivo del
    proceso terminado), no quedarse esperando."""
    cliente = _cliente("import sys; sys.exit(0)")
    inicio = time.monotonic()
    try:
        respuesta = cliente.llamar("initialize", {}, timeout=30)
    finally:
        cliente.cerrar()
    elapsed = time.monotonic() - inicio
    assert "error" in respuesta, respuesta
    assert elapsed < 20, f"el harness se quedo esperando: tardo {elapsed:.1f}s"
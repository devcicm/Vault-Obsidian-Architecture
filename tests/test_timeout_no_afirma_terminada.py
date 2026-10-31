"""A-06 (vault dev codex): TOOL_TIMEOUT no puede afirmar que la tool «fue terminada».

`wrap_main` corre la tool en un hilo daemon y, al vencer el plazo, no lo
detiene: sigue ejecutando y puede escribir después de que el agente ya recibió
el error. Decir «terminada» induce a reintentar sobre una escritura en curso.
"""

import json
import sys
import threading
import time
from pathlib import Path


import vault_errors  # noqa: E402


def test_timeout_dice_que_el_hilo_puede_seguir(capsys):
    liberar = threading.Event()

    def lenta():
        liberar.wait(5)
        return 0

    try:
        rc = vault_errors.wrap_main(lenta, "probe_lenta", timeout=1)
    finally:
        liberar.set()
        time.sleep(0.05)
    assert rc == 1
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert env["error_code"] == "TOOL_TIMEOUT"
    assert "terminada" not in env["message"]
    assert "segundo plano" in env["message"]


def test_el_catalogo_no_promete_que_se_termina():
    from vault.kernel.errores import ERROR_CATALOG

    assert "terminada" not in ERROR_CATALOG["TOOL_TIMEOUT"]["message"]

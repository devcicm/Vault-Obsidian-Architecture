"""La CLI escribe su JSON en UTF-8 aunque la consola no lo sea.

Medido en v40.34 en Windows con la wheel instalada: `vault run` redirigido a un
fichero o a una tubería escribía su propio envelope —`PREFLIGHT_REJECTED`,
«encontró»— en cp1252, la codificación de la consola. Un consumidor que lee
UTF-8 recibía bytes inválidos (`encontr\\xf3`) dentro del JSON. La salida de las
tools ya llegaba en UTF-8: solo fallaba lo que escribe la propia CLI.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_el_envelope_propio_sale_en_utf8_con_una_consola_cp1252(tmp_path):
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8",)}
    env.update(PYTHONIOENCODING="cp1252", PYTHONPATH=str(RAIZ),
               VAULT_ROOT=str(vault), VAULT_STRICT_ROOT="1")

    proceso = subprocess.run(
        [sys.executable, "-c", "import sys; from vault.product_cli import main; sys.exit(main())",
         "run", "vault_read", "--path", "../fuera/nota.md"],
        env=env, cwd=str(cwd), capture_output=True, timeout=120,
    )

    salida = proceso.stdout + proceso.stderr
    texto = salida.decode("utf-8")  # UnicodeDecodeError es exactamente el fallo
    envelope = json.loads(texto[texto.index("{"):].splitlines()[0])
    assert envelope["error_code"] == "PREFLIGHT_REJECTED", texto
    assert any(ord(c) > 127 for c in texto), "el mensaje ya no lleva acentos: el test no mide nada"

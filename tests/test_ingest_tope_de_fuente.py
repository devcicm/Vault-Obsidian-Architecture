"""El tope de la ingesta es el mismo venga por donde venga.

`vault_ingest` es la **única** superficie de escritura del eje de consulta: es
la puerta por la que entra texto que el estándar no escribió. Tenía tres topes
distintos y uno inexistente:

  * `--text`  → 200.000 caracteres, impuestos por `safety.MAX_ARG_LENGTH`
                sobre argv, no por la tool.
  * `--url`   → 5.000.000 de bytes, escritos a mano en la llamada de red.
  * `--file`  → sin tope.
  * `--stdin` → sin tope.

Un tope que se puede rodear cambiando de puerta no es un tope. Y las dos
puertas sin control eran justamente las cómodas: redirigir un fichero es más
fácil que pasar el texto por argv.

Estos tests fijan las dos propiedades que importan: que el veredicto no dependa
del origen, y que el rechazo ocurra **sin haber leído entero** lo que se
rechaza — leer diez gigas para luego decir que son demasiados es agotar la
memoria antes de llegar al guard.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _corre(tmp_path, *argv, entrada=None):
    entorno = dict(os.environ, VAULT_ROOT=str(tmp_path), PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "vault_init.py")],
                   env=entorno, capture_output=True, cwd=str(REPO_ROOT))
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "vault_ingest.py"), *argv],
        env=entorno, input=entrada, capture_output=True, text=True,
        encoding="utf-8", cwd=str(REPO_ROOT))


def test_el_tope_por_defecto_esta_declarado_y_no_escrito_a_mano():
    """Estaba como `5_000_000` literal dentro de la llamada de red."""
    import vault_ingest

    assert isinstance(vault_ingest.DEFAULT_MAX_CHARS, int)
    fuente = (REPO_ROOT / "scripts" / "vault_ingest.py").read_text(encoding="utf-8")
    assert "response.read(5_000_000)" not in fuente, (
        "el tope de red sigue escrito a mano en vez de derivar del declarado")


@pytest.mark.parametrize("puerta", ["file", "stdin", "text"])
def test_el_mismo_texto_grande_se_rechaza_por_las_tres_puertas(tmp_path, puerta):
    """La propiedad: el veredicto no depende de por dónde entró el texto."""
    grande = "x" * 3000
    argv = ["--section", "07_Knowledge", "--max-chars", "1000"]
    entrada = None

    if puerta == "file":
        fichero = tmp_path / "grande.md"
        fichero.write_text(grande, encoding="utf-8")
        argv += ["--file", str(fichero)]
    elif puerta == "stdin":
        argv += ["--stdin"]
        entrada = grande
    else:
        argv += ["--text", grande]

    r = _corre(tmp_path / "vault", *argv, entrada=entrada)
    salida = json.loads(r.stdout)
    assert salida["ok"] is False, salida
    assert salida["error_code"] == "SOURCE_TOO_LARGE", salida
    # El envelope dice cómo salir de aquí (AP-52), no sólo que falló.
    assert "recovery" in salida and "--max-chars" in salida["recovery"]


def test_por_debajo_del_tope_no_se_rechaza(tmp_path):
    """El guard no puede rechazar lo normal: sería un tope inservible."""
    r = _corre(tmp_path / "vault", "--section", "07_Knowledge",
               "--max-chars", "1000", "--text", "y" * 300)
    salida = json.loads(r.stdout)
    assert salida.get("error_code") != "SOURCE_TOO_LARGE", salida


def test_el_rechazo_no_lee_el_fichero_entero(tmp_path):
    """Se lee `tope + 1` y se decide: lo que sobra nunca entra en memoria.

    Sin esto el guard existe pero llega tarde, que en un tope de recurso es lo
    mismo que no existir.
    """
    import argparse
    import vault_ingest

    fichero = tmp_path / "enorme.md"
    fichero.write_text("z" * 200_000, encoding="utf-8")
    args = argparse.Namespace(text=None, stdin=False, file=str(fichero),
                              url=None, allow_network=False, max_chars=500)
    leido = vault_ingest._read_source(args)
    assert leido["ok"] is True
    assert len(leido["text"]) == 501, (
        f"se leyeron {len(leido['text'])} caracteres para aplicar un tope de 500")

    veredicto = vault_ingest._check_size(leido, 500)
    assert veredicto["ok"] is False
    assert veredicto["error_code"] == "SOURCE_TOO_LARGE"

"""Un título que produce un dispositivo de Windows se rechaza antes de leer nada.

Medido instalando la wheel en un venv limpio (Fase 6): `vault run vault_write
--title CON` no fallaba, se colgaba 60 s hasta `TOOL_TIMEOUT`. `con.md` es la
consola: `exists()` es True en una carpeta vacía y la tool lee la nota
existente antes de escribir, así que `read_text` esperaba entrada. El guard de
dispositivos vivía solo en `atomic_write`, que llega después.

El dueño es `vault.kernel.indices_structural.es_nombre_reservado`; las tools
que derivan el nombre de un título ya le preguntan. Cada llamada lleva timeout:
si el bug vuelve, el test falla en vez de colgar la suite.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from vault.kernel.indices_structural import es_dispositivo_windows, motivo_de_reserva

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CONTENIDO = (
    "Primera linea sobre reintentos exponenciales.\n"
    "Segunda linea con el jitter aplicado al intervalo.\n"
    "Tercera linea con el limite de cinco intentos."
)


@pytest.mark.parametrize("nombre", ["con.md", "CON", "Aux.md", "nul", "com1.md", "lpt9.md",
                                    "con.tar.md", "con .md", "conin$.md", "CONOUT$"])
def test_el_predicado_reconoce_los_dispositivos(nombre):
    assert es_dispositivo_windows(nombre)
    assert motivo_de_reserva(nombre) == "dispositivo"


@pytest.mark.parametrize("nombre", ["console.md", "contrato.md", "com0.md", "com10.md",
                                    "auxiliar.md", "nulo.md", ""])
def test_el_predicado_no_captura_nombres_normales(nombre):
    assert not es_dispositivo_windows(nombre)
    assert motivo_de_reserva(nombre) is None


def _cli(vault: Path, script: str, *args: str) -> dict:
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        env=dict(os.environ, VAULT_ROOT=str(vault), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest", VAULT_TOOL_TIMEOUT="20"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=45, stdin=subprocess.DEVNULL,
    )
    salida = p.stdout or p.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    (v / "00_System").mkdir(parents=True)
    (v / "07_Knowledge").mkdir()
    return v


@pytest.mark.parametrize("titulo", ["CON", "aux", "Com1", "con.tar"])
def test_vault_write_rechaza_el_dispositivo_sin_colgarse(vault, titulo):
    r = _cli(vault, "vault_write.py", "--folder", "07_Knowledge", "--title", titulo,
             "--tags", "prueba", "--content", CONTENIDO)
    assert r["ok"] is False and r["error_code"] == "RESERVED_NAME", r
    assert "dispositivo" in r["message"]


def test_vault_preferences_rechaza_el_dispositivo(vault):
    r = _cli(vault, "vault_preferences.py", "--set", "--category", "style", "--title", "NUL",
             "--statement", "Una regla de estilo cualquiera con texto suficiente.")
    assert r["ok"] is False and r["error_code"] == "RESERVED_NAME", r


def test_atomic_write_mira_hasta_el_primer_punto(tmp_path):
    sys.path.insert(0, str(SCRIPTS))
    from vault_io import _rechazar_nombre_reservado
    for nombre in ("con.tar.md", "con .md", "CONIN$.md"):
        with pytest.raises(ValueError):
            _rechazar_nombre_reservado(tmp_path / nombre)
    _rechazar_nombre_reservado(tmp_path / "console.md")

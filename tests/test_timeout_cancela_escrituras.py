"""El timeout de una tool no deja que su hilo siga escribiendo después.

Hallazgo 3.6 del paper de la re-auditoría del vault: el aviso ya era
honesto —«se dejó de esperar, pero seguía ejecutándose en segundo plano y
pudo escribir después»— pero **nada lo impedía**. El hilo de la tool es
daemon: vive más allá del envelope, y una tool de escritura podía
escribir DESPUÉS de que el envelope dijera `TOOL_TIMEOUT`. Quien recibía
ese envelope y reintentaba se encontraba con dos escrituras y un estado
que no sabía.

Lo que se corrige, y lo que no:

- **Sí:** tras el timeout (o una interrupción), las escrituras **nuevas**
  del hilo fugado se niegan. La valla se instala en los dueños de
  escritura, así que cubre las 129 tools sin tocar una por una.
- **No:** una escritura que ya estaba en curso cuando llegó el timeout
  puede terminar. `atomic_write_text` escribe a un temporal y renombra:
  renombra o no renombra, pero nunca deja medio fichero.
- **No:** el hilo no se mata. En CPython un hilo no se puede matar sin
  reclamar el proceso; lo honesto es negarle el disco, no fingir que paró.
- **Límite declarado:** el veto alcanza a lo que pasa por los dueños de
  escritura. Una escritura en crudo (`Path.write_text`) lo esquivaría; en
  este repo las que quedan así escriben artefactos derivados fuera del
  vault, no notas del vault.

**Sin esperas fijas:** el test decide *cuándo* el hilo fugado intenta
escribir (un `Event` que él suelta) y espera a la **condición** —que el
hilo termine— con plazo. Un `sleep` sería a la vez lento en la máquina
rápida e insuficiente en la lenta.
"""

import json
import threading

import pytest

import vault_errors
from vault_io import atomic_write_text, set_vault_root
from vault.kernel.ledger import (
    EscrituraCancelada,
    cancelar_escrituras,
    descartar_cancelacion,
    reanudar_escrituras,
)

PLAZO = 10.0


@pytest.fixture
def raiz(tmp_path):
    previa = set_vault_root(tmp_path)
    yield tmp_path
    set_vault_root(previa)


def _envelope(capsys) -> dict:
    salida = capsys.readouterr().out.strip()
    lineas = [l for l in salida.splitlines() if l.strip().startswith("{")]
    return json.loads(lineas[-1]) if lineas else {}


def test_tras_el_timeout_no_hay_escritura_nueva(raiz, capsys):
    """El repro: el hilo de la tool escribe cuando el envelope ya salió.

    Antes: el fichero aparecía. El envelope ya había dicho que parara, y el
    fichero aparecía igual — con `ok: false` en la consola y el cambio en
    el vault.
    """
    marca = raiz / "escritura-tardia.txt"
    suelta = threading.Event()
    termino = threading.Event()
    frenado = []

    def tool():
        suelta.wait(timeout=PLAZO)
        try:
            atomic_write_text(marca, "escrito despues del timeout")
        except EscrituraCancelada as exc:
            frenado.append(exc)
        finally:
            termino.set()

    rc = vault_errors.wrap_main(tool, "test_timeout", timeout=0.2)

    assert rc == 1
    envelope = _envelope(capsys)
    assert envelope.get("error_code") == "TOOL_TIMEOUT", envelope

    # Ahora el hilo fugado intenta escribir.
    suelta.set()
    assert termino.wait(timeout=PLAZO), "el hilo no terminó"
    assert frenado, "el hilo fugado no fue frenado por la valla"
    assert not marca.exists(), (
        "la tool escribio DESPUES de que el envelope dijera timeout")


def test_el_envelope_declara_el_limite_y_el_desconocimiento(raiz, capsys):
    """Un timeout sin más datos obliga a adivinar; el envelope los da."""
    suelta = threading.Event()
    termino = threading.Event()

    def tool():
        suelta.wait(timeout=PLAZO)
        termino.set()
        return 0

    rc = vault_errors.wrap_main(tool, "test_timeout", timeout=0.2)
    assert rc == 1
    envelope = _envelope(capsys)
    assert envelope.get("error_code") == "TOOL_TIMEOUT"
    args = envelope.get("args") or {}
    assert args.get("timeout_seconds") == 0.2, envelope
    assert args.get("reintentar") is False, envelope
    suelta.set()
    assert termino.wait(timeout=PLAZO)


def test_el_timeout_deja_su_testigo(raiz, capsys):
    """La valla no puede negar la traza del propio timeout.

    Si el hilo principal perdiera el derecho a escribir al cerrar la
    valla, el evento quedaría sin auditar: el timeout se negaría a sí mismo
    su constancia. El hilo que cierra la valla conserva ese derecho.
    """
    suelta = threading.Event()
    termino = threading.Event()

    def tool():
        suelta.wait(timeout=PLAZO)
        termino.set()
        return 0

    rc = vault_errors.wrap_main(tool, "test_timeout", timeout=0.2)
    assert rc == 1
    envelope = _envelope(capsys)
    assert envelope.get("error_code") == "TOOL_TIMEOUT", envelope
    # La traza del evento existe: `emit_error` pudo escribir después de
    # cerrar la valla (si no pudo, el envelope no habría salido tampoco).
    assert envelope.get("timestamp")
    suelta.set()
    assert termino.wait(timeout=PLAZO)


def test_una_ejecucion_nueva_puede_volver_a_escribir(raiz, capsys):
    """La valla es de esta ejecución: la siguiente tool escribe normal."""
    suelta = threading.Event()
    termino = threading.Event()

    def tool_lenta():
        suelta.wait(timeout=PLAZO)
        termino.set()
        return 0

    assert vault_errors.wrap_main(tool_lenta, "test_timeout", timeout=0.2) == 1
    capsys.readouterr()
    suelta.set()
    assert termino.wait(timeout=PLAZO)

    destino = raiz / "despues.txt"

    def tool_rapida():
        atomic_write_text(destino, "escrito en la siguiente ejecucion")
        return 0

    assert vault_errors.wrap_main(tool_rapida, "test_timeout", timeout=5) == 0
    assert destino.read_text(encoding="utf-8").startswith("escrito")


def test_la_escritura_directa_tambien_se_niega(raiz):
    """La valla está en el dueño de la escritura, no en un wrapper."""
    cancelar_escrituras()
    try:
        with pytest.raises(EscrituraCancelada):
            atomic_write_text(raiz / "nope.txt", "no debe existir")
        assert not (raiz / "nope.txt").exists()
    finally:
        descartar_cancelacion()

    atomic_write_text(raiz / "si.txt", "ahora si")
    assert (raiz / "si.txt").is_file()


def test_la_valla_no_alcanza_a_otros_hilos(raiz):
    """La valla es del hilo fugado, no del proceso.

    Una valla de proceso cerraba el portón a todo lo que venía después en
    ese proceso —medido el 2026-11-09: el test de concurrencia del
    change-log fallaba porque el timeout de un test anterior había dejado
    la valla cerrada—. Aquí se fija ese límite.
    """
    cancelar_escrituras()
    errores = []

    def intento():
        try:
            atomic_write_text(raiz / "de-otro-hilo.txt", "permitido")
        except EscrituraCancelada as exc:
            errores.append(exc)

    try:
        hilo = threading.Thread(target=intento)
        hilo.start()
        hilo.join(timeout=PLAZO)
        assert not hilo.is_alive()
        assert not errores, "otro hilo quedó frenado por la valla ajena"
        assert (raiz / "de-otro-hilo.txt").is_file()
    finally:
        descartar_cancelacion()

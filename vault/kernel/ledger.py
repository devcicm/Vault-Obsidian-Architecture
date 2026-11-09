"""vault.kernel.ledger — cuánto trabajo hizo esta ejecución. Módulo hoja.

Vive aquí desde 2026-10-09 (deuda #12, segunda migración del puente);
`scripts/vault_ledger.py` es su fachada y reexporta los mismos objetos.

Contabilidad thread-local de escrituras: created / updated / unchanged. No abre
un fichero, no sabe dónde está el vault, no importa nada de `vault_*`.

**Por qué existe (v40.17).** Estaba dentro de `vault_io`, y por eso
`vault_errors` —el módulo con más fan-in del repo: 110 importadores— tenía que
importar el módulo de IO entero para hacer una sola cosa: poner el contador a
cero en el hilo donde va a correr la tool. Esa arista cerraba el ciclo
`errors → io → encoding → errors`, y estaba escrita como import diferido dentro
de la función, que es la forma de tener un ciclo sin que el intérprete se queje.

Contar no es escribir. Separarlo hace legible una cosa que el módulo-dios
escondía: el indicador de AP-37 se puede medir sin tocar el disco, y un test
puede comprobar la clasificación sin montar un vault.

El contrato no cambia: `vault_io` reexporta `write_report`, `write_ledger_reset`
y `record_raw_write`, así que ninguna de las tools que los usa se entera.
"""

import threading
from pathlib import Path
from typing import Dict, Optional


# ── La valla de cancelación (hallazgo 3.6) ────────────────────────────────
#
# `wrap_main` lanza la tool en un hilo daemon con un límite de tiempo. Al
# agotarse, el envelope dice `TOOL_TIMEOUT` y **el hilo sigue vivo**: en
# CPython un hilo no se puede matar sin reclamar el proceso. Lo que sí se
# puede es negarle el disco —que no vuelva a escribir— que es la garantía
# alcanzable y honesta. El aviso ya decía «pudo escribir después»; esto es
# lo que hace que no pueda.
#
# El flag es **de proceso**, no de hilo: el hilo de la tool y el hilo que
# espera comparten la misma verdade. `wrap_main` lo abre al arrancar cada
# ejecución (una tool anterior cancelada no puede dejar cerrado el
# portón de la siguiente).
#: La valla es **por hilo**, no de proceso. Un timeout tiene que negarle el
#: disco al hilo fugado —el de la tool que se pasó de tiempo— y a nadie más:
#: en el mismo proceso puede estar corriendo la traza del evento, otra
#: operación o una suite. Una valla de proceso cerraba el portón a todo el
#: que vino después (medido el 2026-11-09: el test de concurrencia del
#: change-log fallaba porque el timeout de un test anterior había dejado la
#: valla cerrada para los hilos siguientes).
_cancelados: "set[int]" = set()
_cancelados_lock = threading.Lock()


class EscrituraCancelada(RuntimeError):
    """La ejecución se canceló: esta escritura ya no puede ocurrir.

    Lo lanza el dueño de la escritura cuando el hilo que escribe está
    cancelado. No es un fallo del dominio —no hay código en `ERROR_CATALOG`
    para esto—: es una señal de control, y el hilo que la recibe muere con
    ella.
    """


def cancelar_escrituras(hilo_id: "int | None" = None) -> None:
    """Cierra la valla para un hilo: sus escrituras nuevas se niegan.

    La llama `wrap_main` al agotarse el límite de tiempo de una tool o al
    interrumpirla el usuario, con el identificador del hilo de la tool. A
    partir de ahí, cualquier dueño de escritura que intente escribir
    **desde ese hilo** lanza `EscrituraCancelada`.
    """
    objetivo = hilo_id if hilo_id is not None else threading.get_ident()
    with _cancelados_lock:
        _cancelados.add(objetivo)


def descartar_cancelacion(hilo_id: "int | None" = None) -> None:
    """Quita la valla de un hilo. Lo llama el propio hilo al terminar.

    Sin esto, un identificador de hilo reciclado heredaría la prohibición
    de una ejecución anterior.
    """
    objetivo = hilo_id if hilo_id is not None else threading.get_ident()
    with _cancelados_lock:
        _cancelados.discard(objetivo)


def reanudar_escrituras() -> None:
    """Abre la valla para este hilo. La llama `wrap_main` al arrancar.

    Con la valla por hilo, esto solo afecta al hilo principal (que nunca
    queda cancelado): está por simetría con el resto del contrato y para
    que una ejecución en el mismo proceso no herede nada.
    """
    descartar_cancelacion()


def cancelacion_activa() -> bool:
    """¿Hay algún hilo con la valla cerrada?"""
    with _cancelados_lock:
        return bool(_cancelados)


def exigir_escritura_permitida() -> None:
    """El punto único por donde pasa toda escritura: comprueba la valla.

    Lo llaman los dueños de escritura (`vault_io.atomic_write_text`,
    `atomic_write_json` y `vault.kernel.escritura.escritura_atomica`, que es
    la puerta de los escritores en crudo). Cubrir la valla **aquí** es lo
    que evita tocar las 129 tools una por una: el veto es del dueño, no del
    llamador.

    **Límite declarado:** el veto alcanza a lo que pasa por los dueños. Una
    escritura en crudo (`Path.write_text`) lo esquivaría — y en este repo
    las que quedan así escriben artefactos derivados **fuera** del vault
    (blueprint, catálogo, tablas), no notas del vault. La traza de errores,
    que sí escribe dentro del vault, va por `escritura_atomica` y no queda
    frenada: la cierra el hilo de la tool, no el principal que la audita.
    """
    with _cancelados_lock:
        cancelado = threading.get_ident() in _cancelados
    if cancelado:
        raise EscrituraCancelada(
            "la ejecución se canceló (timeout o interrupción): la escritura "
            "no se ha hecho. Comprueba el estado del vault antes de reintentar."
        )


# El indicador de trabajo se MIDE donde el trabajo ocurre, no lo afirma cada
# tool en su return. Una tool que se limita a declarar `ok: true` está haciendo
# una afirmación no falsable; una que reporta `unchanged: 1` está diciendo algo
# comprobable — y es justo el caso que AP-37 nació para destapar (una migración
# que devolvía éxito habiendo aplicado cero cambios).
#
# El ledger es thread-local a propósito: la CLI consolidada ejecuta varias
# operaciones a la vez y un contador de módulo mezclaría el trabajo de unas con
# el de otras.
_write_ledger = threading.local()


def _ledger() -> Dict[str, int]:
    contadores = getattr(_write_ledger, "counts", None)
    if contadores is None:
        contadores = {"created": 0, "updated": 0, "unchanged": 0}
        _write_ledger.counts = contadores
    return contadores


def write_ledger_reset() -> None:
    """Pone el contador a cero. Lo llama `wrap_main` al arrancar cada tool."""
    _write_ledger.counts = {"created": 0, "updated": 0, "unchanged": 0}


def write_report() -> Dict[str, int]:
    """Qué escribió esta ejecución. Pensado para expandirse en el return de la tool.

    `written` es el total de archivos que cambiaron en disco: `unchanged` NO
    cuenta, porque reescribir un archivo con el mismo contenido no es trabajo.
    """
    c = dict(_ledger())
    c["written"] = c["created"] + c["updated"]
    return c


def record_raw_write(path: Path, text: str, encoding: str = "utf-8") -> str:
    """Registra una escritura que NO pasa por `atomic_write_text`, a propósito.

    Hay dos motivos válidos para escribir en crudo, y ambos están declarados:

    1. `vault_section_index` genera índices con `Path.write_text` porque
       `atomic_write_text` dispara `_auto_section_index`, y el generador
       escribiéndose a sí mismo sería una recursión infinita.
    2. `vault_mermaid_check --fix` escribe el contenido EXACTO que el
       compilador de Mermaid aprobó (2026-10-19): `atomic_write_text` aplica
       `sanitize_content` DESPUÉS del criterio de aceptación, y una mutación
       no verificada (NFC, comillas tipográficas) invalidaría la cura. El
       La ruta conserva el escaneo de secretos vía `guarda_secretos` en las
       `guardas` de `escritura_atomica` — el saneado es lo único que se
       omite, con nombre y motivo.

    Llamar a esto NO escribe: solo clasifica. Se invoca junto al `write_text`.
    """
    return _record_write(path, text, encoding)


#: Ficheros de telemetría interna que NO son trabajo de la tool. Escribir una
#: traza no es haber hecho nada por el vault, y contarla haría que el indicador
#: de AP-37 subiera con el número de errores registrados — justo al revés de lo
#: que mide. Se declaran por nombre porque viven en `00_System/`, que ya está
#: fuera de la cascada de índices por el mismo motivo.
_NO_ES_TRABAJO = frozenset({".tool-trace.json"})


def _record_write(path: Path, text: str, encoding: str) -> str:
    """Clasifica la escritura antes de hacerla. Nunca propaga errores."""
    if path.name in _NO_ES_TRABAJO:
        return "unchanged"
    try:
        if not path.exists():
            resultado = "created"
        else:
            resultado = (
                "unchanged"
                if path.read_text(encoding=encoding, errors="replace") == text
                else "updated"
            )
    except OSError:
        resultado = "updated"
    _ledger()[resultado] += 1
    return resultado

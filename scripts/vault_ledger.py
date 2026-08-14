#!/usr/bin/env python3
"""vault_ledger — cuánto trabajo hizo esta ejecución. Módulo hoja.

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
from typing import Dict


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

    Hay exactamente un motivo válido para escribir en crudo: `vault_section_index`
    genera índices con `Path.write_text` porque `atomic_write_text` dispara
    `_auto_section_index`, y el generador escribiéndose a sí mismo sería una
    recursión infinita. Esas escrituras son trabajo real y tienen que contar.

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

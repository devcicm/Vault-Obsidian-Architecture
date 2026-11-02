"""El registro de productores: quién se ofrece al importarse.

## Qué resuelve

El kernel no puede importar a sus productores —eso es un ciclo (AP-58) o un
cruce de contexto—, pero sí puede **pedir** lo que necesita. El registro es el
sitio donde un productor se ofrece al importarse y el kernel lo encuentra.

La diferencia con el valor por defecto que hoy da el import no es de forma, es
de propiedad: hoy, si nadie importa al productor, el gancho **desaparece en
silencio**. Un tool que escribe y no regenera el índice no da ningún error:
solo un índice viejo. Con el registro, la ausencia de un productor es un
estado **observable** —`registro.hay("indices")` es `False`— y por tanto
declarable.

## Por qué no un `importlib` diferido

Porque `importlib.import_module` esconde el ciclo en vez de romperlo: el
import diferido dentro de una función es exactamente lo que AP-58 mide, y lo
que el repo congela hoy en `scripts/ciclos-baseline.json`. Con el registro, el
productor se importa **en su propio módulo**, en su propio contexto, y el
kernel solo ve la interfaz.

## El valor por defecto

`registro.buscar("indices")` devuelve `None` si nadie se ha ofrecido. La
diferencia con el valor por defecto del import es que **ese `None` se puede
comprobar**. El que hoy desaparece en silencio —la ausencia del productor— pasa
a ser un dato, y quien llama decide qué hacer con él.

## Por qué es un módulo del kernel y no del contexto de cada productor

Porque el kernel es el que lo consulta. Si el registro viviera en
`vault.autoria`, el kernel tendría que importarlo para usarlo y el problema
vuelve dressed de otra manera.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

#: Los productores registrados, por nombre. El tipo es `Any` a propósito: el
#: registro guarda el PRODUCTO (una implementación del puerto), no el módulo
#: que lo define —así el kernel no depende de la clase, solo del contrato.
_PRODUCTORES: Dict[str, Any] = {}

#: El candado: el registro se escribe al importarse un productor, y varios
#: importadores pueden estar a la vez en hilos distintos.
_CANDADO = threading.Lock()


def registrar(nombre: str, productor: Any) -> None:
    """Ofrece un productor bajo un nombre. Lo último que se registra gana.

    El nombre es el del puerto que implementa: ``"indices"``,
    ``"voz"``. Registrar dos veces el mismo nombre es un error de
    programación, no una condición de carrera —y por eso el segundo registro
    avisa en vez de cambiar en silencio.
    """
    with _CANDADO:
        anterior = _PRODUCTORES.get(nombre)
        _PRODUCTORES[nombre] = productor
    if anterior is not None and anterior is not productor:
        import warnings

        warnings.warn(
            f"el productor {nombre!r} ya estaba registrado y se ha sustituido "
            "por otro. Si es a propósito (un test que inyecta un doble), "
            "restaura el anterior al terminar.",
            RuntimeWarning,
            stacklevel=2,
        )


def buscar(nombre: str) -> Optional[Any]:
    """El productor registrado bajo `nombre`, o `None` si no hay ninguno.

    `None` es un estado legítimo —el producto no se ha cargado— y por eso la
    ausencia se puede comprobar. No es un error: quién llama decide.
    """
    with _CANDADO:
        return _PRODUCTORES.get(nombre)


def hay(nombre: str) -> bool:
    """¿Hay alguien que atienda a `nombre`?"""
    return buscar(nombre) is not None


def restaurar(nombre: str, productor: Any) -> None:
    """Devuelve al registro a su estado anterior (lo usan los tests)."""
    with _CANDADO:
        if productor is None:
            _PRODUCTORES.pop(nombre, None)
        else:
            _PRODUCTORES[nombre] = productor


def registrados() -> Dict[str, Any]:
    """Una foto de lo registrado. Para diagnóstico y tests."""
    with _CANDADO:
        return dict(_PRODUCTORES)


def limpiar() -> None:
    """Vacía el registro. Solo para tests: el registro vive por proceso."""
    with _CANDADO:
        _PRODUCTORES.clear()

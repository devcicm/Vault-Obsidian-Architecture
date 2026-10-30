"""Memoización para los tests que miden el repo entero.

`vault_arch.check()` recorre y parsea todo `scripts/`: unos 3 s por llamada, y
diecisiete tests le hacían la misma pregunta al mismo repo sin tocar nada. Aquí
se calcula una vez por combinación de argumentos. Solo vale para tests que leen
el estado real: el que parchea algo con `monkeypatch` llama a la función de
verdad, no a la memoizada.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Tuple


def memoizar(fn: Callable[..., Any]) -> Callable[..., Any]:
    """`fn` con caché por argumentos. Una excepción no se guarda: se vuelve a lanzar."""
    guardado: Dict[Tuple[Any, ...], Any] = {}

    def envuelta(*args: Any, **kwargs: Any) -> Any:
        clave = (args, tuple(sorted(kwargs.items())))
        if clave not in guardado:
            guardado[clave] = fn(*args, **kwargs)
        return guardado[clave]

    return envuelta

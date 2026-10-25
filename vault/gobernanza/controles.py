"""Contrato de ejecucion de los controles obligatorios del estandar (TD-0003).

El defecto que este modulo corrige: `_checks_estandar` capturaba
`ImportError/OSError/ValueError` con `pass`, asi que un control que no podia
ejecutarse **desaparecia** del resultado y la auditoria quedaba
indistinguible de una auditoria limpia. Cero hallazgos no es prueba de
ejecucion.

Aqui no se importa a nadie: el ejecutor lo entrega quien tiene el verificador
(inversion de la dependencia). Este modulo solo normaliza el resultado a uno de
los cuatro estados y calcula la cobertura.

Estados:
  - ejecutado    : el verificador corrio y devolvio sus hallazgos;
  - degradado    : corrio a medias (fallo de E/S o de datos), con detalle;
  - fallido      : el verificador existe pero fallo al ejecutarse;
  - no_ejecutado : la dependencia no esta disponible o no se invoco.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List

CONTROLES_OBLIGATORIOS = ("AP-40", "AP-42", "AP-43")
ESTADOS = ("ejecutado", "degradado", "fallido", "no_ejecutado")

__all__ = [
    "CONTROLES_OBLIGATORIOS",
    "ESTADOS",
    "ejecutar_control",
    "resumen",
]


def _check(control: str, estado: str, detalle: str | None,
           hallazgos: int = 0) -> Dict[str, Any]:
    assert estado in ESTADOS, estado
    return {"control": control, "estado": estado, "detalle": detalle,
            "hallazgos": int(hallazgos)}


def ejecutar_control(control: str, ejecutor: Callable[..., int | Dict[str, Any]],
                     *args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Ejecuta un control y devuelve su estado explicito, nunca lo silencia.

    `ejecutor` devuelve el numero de hallazgos que reporto (o un dict con
    `hallazgos`). Cualquier excepcion se traduce a un estado observable: un
    control que no pudo correr **no** es un control sin hallazgos.
    """
    try:
        resultado = ejecutor(*args, **kwargs)
    except ImportError as exc:
        return _check(control, "no_ejecutado",
                      f"dependencia_no_disponible ({exc})")
    except (OSError, ValueError) as exc:
        return _check(control, "degradado", f"{type(exc).__name__} ({exc})")
    except Exception as exc:  # el verificador existe y fallo: hay que verlo
        return _check(control, "fallido", f"{type(exc).__name__} ({exc})")
    if isinstance(resultado, dict):
        hallazgos = resultado.get("hallazgos", 0)
        estado = resultado.get("estado", "ejecutado")
        detalle = resultado.get("detalle")
        return _check(control, estado if estado in ESTADOS else "degradado",
                      detalle, hallazgos)
    if isinstance(resultado, int):
        return _check(control, "ejecutado", None, resultado)
    if resultado is None:
        return _check(control, "ejecutado", None, 0)
    return _check(control, "degradado",
                  f"resultado_no_interpretable ({type(resultado).__name__})")


def resumen(checks: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Cobertura de los controles obligatorios a partir de sus estados.

    `completo` es True solo si estan los TRES controles obligatorios y todos
    en `ejecutado`. Un envelope sin controles no es un envelope completo.
    """
    lista: List[Dict[str, Any]] = [dict(c) for c in checks]
    nombres = {c.get("control") for c in lista}
    faltan = [c for c in CONTROLES_OBLIGATORIOS if c not in nombres]
    pendientes = [c.get("control") for c in lista
                  if c.get("estado") != "ejecutado"]
    completo = not faltan and not pendientes
    return {
        "checks": lista,
        "completo": completo,
        "controles_obligatorios": list(CONTROLES_OBLIGATORIOS),
        "controles_faltantes": faltan,
        "controles_no_ejecutados": pendientes,
    }

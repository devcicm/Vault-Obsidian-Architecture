"""La ronda de trabajo de un agente: quién la abre, qué la identifica y dónde vive (D-07).

## Por qué existe

Hasta v41.26 una ronda de trabajo no dejaba rastro propio: las notas que un
agente escribía en una tanda no tenían nada en común que las uniera, y
`04_Sessions/` solo recibía lo que alguien escribiera a mano. `vault_session`,
que hacía de contenedor, se archivó en favor de `vault_delta`, y con ella se
fue la única forma de responder «¿qué se escribió en esta ronda?» sin
reconstruirlo por fechas.

La decisión (2026-10-30) es que la ronda la abre **el agente**, vía MCP, con
`vault_ronda --abrir`. Mientras está abierta, `vault_write` estampa su
`round_id` en cada nota que escribe; al cerrarla, `vault_ronda --cerrar`
escribe la nota de sesión con lo que lleva ese `round_id`. La ronda no es una
identidad nueva: es una vista sobre notas que ya tienen la suya.

## Qué hay aquí y qué no

Este módulo es la **hoja**: el formato del identificador y el fichero de la
ronda activa. No escribe notas. Lo importan `vault_write` (para estampar) y la
tool `vault_ronda` (para abrir y cerrar), y si escribiera notas los dos se
importarían entre sí —el ciclo que AP-58 prohíbe esquivar con un import
diferido—.

El fichero vive en `<vault>/00_System/ronda-activa.json` (AP-36: dentro del
vault) y lo declara `RepositorioAutoria`, que es como `vault_arch` sabe quién
es su dueño.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ..kernel.contexto import construir
from ..kernel.normativa.contrato_nota import CAMPOS
from .repositorio import RepositorioAutoria

#: `r<AAAAMMDD>-<6 hex>`. El dueño es el contrato de nota (`CAMPOS["round_id"]`):
#: aquí se lee, no se repite (AP-57). La fecha va dentro para que la nota de
#: sesión se ordene sola; el sufijo aleatorio, para que dos rondas del mismo día
#: no colisionen.
_PATRON = re.compile(CAMPOS["round_id"]["patron"])


def nuevo_round_id(ahora: Optional[datetime] = None) -> str:
    ahora = ahora or datetime.now(timezone.utc)
    return f"r{ahora:%Y%m%d}-{secrets.token_hex(3)}"


def es_round_id(valor: Any) -> bool:
    return isinstance(valor, str) and bool(_PATRON.match(valor))


def ruta_activa(raiz: Optional[Path] = None) -> Path:
    return RepositorioAutoria(construir(raiz)).ronda_activa


def leer_activa(raiz: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """La ronda abierta, o None si no hay ninguna.

    Un fichero que existe y no se puede leer como ronda **lanza** `ValueError`:
    devolver None diría «no hay ronda» y las notas se escribirían sin su
    `round_id` sin que nadie lo supiera (AP-51).
    """
    ruta = ruta_activa(raiz)
    if not ruta.is_file():
        return None
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(datos, dict) or not es_round_id(datos.get("round_id")):
        raise ValueError(f"{ruta.name} no describe una ronda: falta un round_id válido")
    return datos


def round_id_activo(raiz: Optional[Path] = None) -> Optional[str]:
    activa = leer_activa(raiz)
    return activa["round_id"] if activa else None

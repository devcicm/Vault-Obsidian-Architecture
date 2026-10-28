"""Reparto determinista de la suite en shards (`VAULT_SHARD=i/n`).

La CI corría la suite entera en cada columna y la de Windows tardaba ~40 min:
el reloj de cada corrida lo marcaba ese job. Partirla en `n` trozos que corren
en paralelo baja el reloj sin quitar un solo test.

Reglas:
- La unidad es el MÓDULO de test, no el test: los fixtures de módulo se
  construyen una vez por trozo y no una vez por test repartido.
- Cada módulo cae en exactamente un trozo (`tests/test_reparto.py` lo fija):
  la unión de los `n` trozos es la suite completa.
- El equilibrio usa `tests/duraciones-por-modulo.json` (segundos medidos). Un
  módulo que no está ahí pesa la mediana. Un dato viejo solo empeora el
  equilibrio; nunca saca un test de la corrida.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Dict, Iterable, Optional, Tuple

DURACIONES = Path(__file__).resolve().parent / "duraciones-por-modulo.json"


def leer_shard(valor: Optional[str]) -> Optional[Tuple[int, int]]:
    """`"2/3"` -> `(2, 3)`. Vacío -> `None`. Mal formado -> ValueError."""
    if not valor:
        return None
    i, _, n = valor.partition("/")
    indice, total = int(i), int(n)
    if not (total >= 1 and 1 <= indice <= total):
        raise ValueError(f"VAULT_SHARD fuera de rango: {valor!r}")
    return indice, total


def _pesos() -> Dict[str, float]:
    try:
        datos = json.loads(DURACIONES.read_text(encoding="utf-8"))
        return {k: float(v) for k, v in datos["segundos_por_modulo"].items()}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def repartir(modulos: Iterable[str], total: int) -> Dict[str, int]:
    """Módulo -> índice de trozo (0..total-1), por LPT: el más pesado primero
    al trozo más ligero. Empates por nombre, para que sea determinista."""
    pesos = _pesos()
    nombres = sorted(set(modulos))
    defecto = median(pesos.values()) if pesos else 1.0
    carga = [0.0] * total
    asignacion: Dict[str, int] = {}
    for nombre in sorted(nombres, key=lambda m: (-pesos.get(m, defecto), m)):
        destino = min(range(total), key=lambda k: (carga[k], k))
        asignacion[nombre] = destino
        carga[destino] += pesos.get(nombre, defecto)
    return asignacion


def modulo_de(nodeid: str) -> str:
    """`tests/test_x.py::test_y[1]` -> `test_x`."""
    return Path(nodeid.split("::", 1)[0]).stem

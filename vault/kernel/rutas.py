#!/usr/bin/env python3
"""vault.kernel.rutas — el layout de este repositorio, con dueño.

Hoja del núcleo: solo `pathlib`. Si algún día necesita más, ha dejado de ser
hoja y pierde el sitio (AP-62).

## Por qué existe (v41.21)

La disposición de este repo — `scripts/`, `docs/`, `schemas/`, `normas/`,
`vault-sandbox/`, `empaquetado/` — estaba escrita como **literal suelto en
~30 módulos**. Cada uno era razonable por separado, y el agregado era la forma
exacta en que un cambio de layout rompe treinta sitios en silencio: el día que
`normas/` pasara a `gobernanza/`, ningún guard lo habría visto venir porque
nadie posee el nombre.

## Qué es y qué no es

Es el dueño de **los nombres del layout del repo** y de cómo se resuelven
desde cualquier sitio. No es un dueño de rutas de vault — eso lo hace
`vault_io.get_vault_root()` / `vault_registry` — ni de la disposición de un
vault de consumidor, que el estándar fija por otra parte.

Los literales de estos nombres en módulos que no sean este **son deuda**: los
cuenta el test `tests/test_rutas_repo.py` contra una baseline que solo
encoge, con la misma mecánica que las de AP-58/AP-62.
"""

from __future__ import annotations

import re
from pathlib import Path

#: Los nombres de directorio del layout de este repo. Lista cerrada: un
#: nombre nuevo entra aquí en el diff que lo estrena, con su motivo si hace
#: falta — como los mutadores de `procesos_git`.
NOMBRES = frozenset({
    "scripts", "docs", "schemas", "normas", "empaquetado", "tests",
    "vault-sandbox", "mcp", "cli",
})

#: Patrón de las combinaciones `padre/hijo` que los módulos escriben a mano:
#: `docs/sdd`, `vault-sandbox/00_System`, `scripts/README.md`… El guard las
#: usa para reconocer un literal de layout aunque lleve dos segmentos.
PATRON_LAYOUT = re.compile(
    r"^(?:" + "|".join(sorted(NOMBRES)) + r")(?:/[^/]+)*$")


def raiz_repo() -> Path:
    """La raíz de este checkout, derivada del propio fichero.

    Igual que la calcula cada script con `Path(__file__).resolve().parents[2]`,
    con un solo dueño: si el paquete se reasienta, aquí se cambia una vez.
    """
    return Path(__file__).resolve().parents[2]


def ruta_repo(nombre: str) -> Path:
    """La ruta absoluta de un directorio del layout, pidiéndolo por nombre.

    `ruta_repo("scripts")` en cualquier módulo vale lo que valía
    `RAIZ / "scripts"` — con la diferencia de que el nombre ahora se valida
    contra la lista cerrada y se resuelve una vez.
    """
    if nombre not in NOMBRES:
        raise ValueError(
            f"{nombre!r} no es un directorio del layout del repo; los que hay "
            f"son {sorted(NOMBRES)}. Si el layout estrenó uno, se declara en "
            "NOMBRES en el mismo diff que lo usa (AP-68 lo llama 'el diff que "
            "lo revisa'; aquí vale el mismo criterio)."
        )
    return raiz_repo() / nombre


def es_layout_repo(texto: str) -> bool:
    """True si `texto` es un literal de layout del repo — `scripts`,
    `docs/sdd`, `vault-sandbox/00_System`…

    Es lo que usa el guard para reconocer un literal sin adivinar: si empieza
    por un nombre del layout y solo lleva segmentos de ruta detrás, lo es.
    """
    return bool(PATRON_LAYOUT.match((texto or "").strip()))

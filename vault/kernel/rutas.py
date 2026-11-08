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
from typing import Optional

#: Los nombres de directorio del layout de este repo, **uno a uno**. Lista
#: cerrada: un nombre nuevo entra aquí en el diff que lo estrena, con su
#: motivo si hace falta — como los mutadores de `procesos_git`.
#:
#: Son constantes y no literales sueltos porque hay dos formas de nombrar el
#: layout: la que pide el nombre (`ruta_repo`) y la que lo **cita** en prosa o
#: en un registro (`cita_repo`). Las dos salen de aquí. `NOMBRES` se arma con
#: ellas y no al revés: un solo sitio donde el layout se nombra, que es lo que
#: esta hoja promete ser.
SCRIPTS = "scripts"
CLI = "cli"
DOCS = "docs"
MCP = "mcp"
NORMAS = "normas"
SCHEMAS = "schemas"
TESTS = "tests"
EMPAQUETADO = "empaquetado"
SANDBOX = "vault-sandbox"
VAULT = "vault"
VAULT_TOOLKIT = "vault_toolkit"
AUDITS = "audits"
AGENT = "agent"

#: Los nombres que el guard de literales vigila: si uno aparece citado en
#: código que no es este módulo, es deuda. v41.26 sumó `vault`, `vault_toolkit`
#: y `audits` —existían desde antes y no estaban declaradas, así que su código
#: quedaba fuera del guard (medido en `audits/analisis-por-pendiente/`)—.
NOMBRES = frozenset({
    SCRIPTS, CLI, DOCS, MCP, NORMAS, SCHEMAS, TESTS, EMPAQUETADO, SANDBOX,
    VAULT, VAULT_TOOLKIT, AUDITS,
})

#: Las carpetas que el repositorio **genera**: las produce un generador, sus
#: ficheros son idénticos por construcción y un barrido que los mida como
#: código está midiendo ruido (medido el 2026-11-08: 97 adaptadores en
#: `vault_toolkit/operations/`, 0 clones entre ellos y 0 sombras).
#:
#: Lo declara aquí el dueño del layout, y lo usan **los dos**: el generador
#: (`vault_distribution_sync`) para escribir ahí y los barridos para
#: excluirlo. Un solo sitio dice dónde está lo generado.
GENERADOS = {"operations": VAULT_TOOLKIT}

#: **Todo** el layout del repo: lo vigilado más lo que existe sin dar señal
#: al guard. `agent/` está aquí y no en `NOMBRES` con una medida detrás: de
#: las 47 apariciones del literal `"agent"` en `scripts/`, `vault/` y `cli/`,
#: 46 nombran un actor del dominio y una sola es una ruta
#: (`agent/skills/ no encontrado, omitido`). Meterlo en el patrón habría
#: congelado 46 falsos positivos y ahogado la señal que el guard existe para
#: dar — el criterio es «el nombre citado apunta al directorio», no «la
#: carpeta existe». `ruta_repo("agent")` sí lo resuelve: declarado no es lo
#: mismo que vigilado.
CARPETAS_DEL_REPO = NOMBRES | {AGENT}

#: Las carpetas del repo donde vive **código**, para los barridos que
#: miden el código. Es un subconjunto de `CARPETAS_DEL_REPO`: deja fuera las
#: carpetas de gobernanza (`audits`, `docs`). Los dos conjuntos se usan
#: enteros: quien barre los dos, no uno y medio.
CARPETAS_DE_CODIGO = (SCRIPTS, CLI, VAULT, TESTS)

#: Las mismas, más el servidor MCP: el guard de git mira también el `.mjs`,
#: que no es Python pero sí es código de este repo.
CARPETAS_DE_CODIGO_Y_MCP = (SCRIPTS, CLI, VAULT, MCP)

#: Las carpetas que los barridos de **código Python** miden: `scripts/`,
#: `cli/`, `vault/` y la capa de despacho del producto (`vault_toolkit/`).
#:
#: `vault_toolkit/` entra desde el 2026-11-08 (C‑08): antes la medía solo el
#: guard de criterios, y el guard de clones —el que exige un cuerpo por
#: dueño— no la veía. La parte **generada** (`vault_toolkit/operations/`) se
#: excluye por nombre, con la razón escrita: 97 ficheros idénticos por
#: construcción son ruido, no deuda. La parte escrita a mano
#: (`loading.py`, `__init__.py`) sí se mide.
#:
#: Los dos barridos que la usan no la excluyen igual, y es deliberado: un
#: **cuerpo** repetido por el generador es ruido; un **criterio** copiado en
#: los 97 adaptadores sería un defecto real.
CARPETAS_DE_CODIGO_PYTHON = (SCRIPTS, CLI, VAULT, VAULT_TOOLKIT)


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

    Acepta todo `CARPETAS_DEL_REPO`, no solo `NOMBRES`: resolver una carpeta
    declarada y vigilar sus literales son dos cosas distintas (ver `AGENT`).
    """
    if nombre not in CARPETAS_DEL_REPO:
        raise ValueError(
            f"{nombre!r} no es un directorio del layout del repo; los que hay "
            f"son {sorted(CARPETAS_DEL_REPO)}. Si el layout estrenó uno, se "
            "declara en CARPETAS_DEL_REPO en el mismo diff que lo usa (AP-68 "
            "lo llama 'el diff que lo revisa'; aquí vale el mismo criterio)."
        )
    return raiz_repo() / nombre


def ruta_generada(nombre: str, raiz: Optional[Path] = None) -> Path:
    """La ruta de una carpeta **generada**, resuelta contra `raiz`.

    `raiz` existe para los barridos que miden un árbol de prueba: la ruta
    tiene que ser la de ese árbol, no la del checkout. Sin `raiz`, es la del
    repositorio.
    """
    if nombre not in GENERADOS:
        raise ValueError(
            f"{nombre!r} no es una carpeta generada; las que hay son "
            f"{sorted(GENERADOS)}. Si el generador arctic una, se declara en "
            "GENERADOS en el mismo diff que la usa."
        )
    base = Path(raiz) if raiz is not None else raiz_repo()
    return base / GENERADOS[nombre] / nombre


def cita_repo(directorio: str, relativo: str) -> str:
    """La ruta de un fichero del repo **citada como la citan los registros**:
    relativa a la raíz y con el directorio del layout delante.

    `cita_repo("tests", "test_x.py::test_y")` devuelve `"tests/test_x.py::test_y"`.
    El directorio se pide por su nombre —validado contra la lista cerrada— y
    el resto del camino es lo que el registro cita: la cita no se inventa aquí,
    solo se le pone delante el directorio que le corresponde.

    Es la forma de citar sin escribir el layout a mano: un registro que cita
    un test lo pide al dueño, y si el layout cambiara, la cita cambiaría con
    él en vez de quedarse apuntando a un sitio que ya no existe.
    """
    if directorio not in CARPETAS_DEL_REPO:
        raise ValueError(
            f"{directorio!r} no es un directorio del layout del repo; los que hay "
            f"son {sorted(CARPETAS_DEL_REPO)}. Si el layout estiró uno, se declara "
            "en CARPETAS_DEL_REPO en el mismo diff que lo usa.")
    return f"{directorio}/{relativo}"


def es_layout_repo(texto: str) -> bool:
    """True si `texto` es un literal de layout del repo — `scripts`,
    `docs/sdd`, `vault-sandbox/00_System`…

    Es lo que usa el guard para reconocer un literal sin adivinar: si empieza
    por un nombre del layout y solo lleva segmentos de ruta detrás, lo es.
    """
    return bool(PATRON_LAYOUT.match((texto or "").strip()))

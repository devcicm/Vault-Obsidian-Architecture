"""El nombre de una versión en `.history/`: un solo criterio para escribirlo y leerlo.

Hasta v41.2 lo decidían cuatro sitios a su manera. `vault_undo` filtraba por el
prefijo `carpeta__stem-` y ordenaba por mtime, `vault_read` por una subcadena
del stem, `vault_diff` por prefijo con orden alfabético, y `vault_history_compact`
era el único que lo parseaba. El prefijo no separa notas: las versiones de
`a-b.md` empiezan por `carpeta__a-` y salían como versiones de `a.md`, de modo
que `vault_undo a.md` podía restaurar el contenido de otra nota. Y `vault_write`
nombraba la versión con `slugify(title)` en vez de con el fichero, así que la de
una nota heredada quedaba bajo un nombre que nadie la iba a buscar.

Forma: `{carpeta con / → __}__{stem}-{AAAA-MM-DDTHH-MM-SS}[-{n}].md`. El sufijo
`-n` separa dos versiones del mismo segundo.

Hoja del núcleo: solo stdlib.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional

#: Formato del sello de tiempo, sin `:` para que el nombre valga en Windows.
FORMATO = "%Y-%m-%dT%H-%M-%S"

#: El sello y la secuencia opcional al final del nombre sin extensión.
_PATRON = re.compile(r"-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})(?:-(\d+))?$")


def clave(rel: str) -> str:
    """El stem con el que se guardan las versiones de la nota `rel` (POSIX)."""
    p = PurePosixPath(rel.replace("\\", "/"))
    return f"{p.parent.as_posix().replace('/', '__')}__{p.stem}"


def parsear(nombre: str) -> Dict[str, Any]:
    """`{stem, timestamp, timestamp_str, secuencia}` de un nombre de `.history/`.

    Un nombre sin sello sale con `timestamp: None` y el nombre entero como stem:
    no es una versión de ninguna nota con sello, y fingirle uno sería inventar.
    """
    sin_ext = nombre[:-3] if nombre.endswith(".md") else nombre
    m = _PATRON.search(sin_ext)
    if m:
        try:
            ts: Optional[datetime] = datetime.strptime(
                m.group(1), FORMATO).replace(tzinfo=timezone.utc)
        except ValueError:
            ts = None
        return {"stem": sin_ext[:m.start()], "timestamp": ts,
                "timestamp_str": m.group(1), "secuencia": int(m.group(2) or 0)}
    return {"stem": sin_ext, "timestamp": None, "timestamp_str": "", "secuencia": 0}


def nombre_libre(dir_historial: Path, rel: str,
                 ahora: Optional[datetime] = None) -> Path:
    """La ruta donde guardar ahora una versión de `rel` sin pisar otra."""
    sello = (ahora or datetime.now(timezone.utc)).strftime(FORMATO)
    base = f"{clave(rel)}-{sello}"
    destino = dir_historial / f"{base}.md"
    n = 1
    while destino.exists():
        destino = dir_historial / f"{base}-{n}.md"
        n += 1
    return destino


def versiones(dir_historial: Path, rel: str) -> List[Dict[str, Any]]:
    """Las versiones de `rel`, de la más reciente a la más vieja.

    Se compara el stem parseado entero, no un prefijo, y se ordena por el sello
    del nombre y no por mtime: copiar `.history/` a otra máquina conserva el
    nombre pero no siempre la fecha del fichero.
    """
    if not dir_historial.is_dir():
        return []
    buscada = clave(rel)
    salida: List[Dict[str, Any]] = []
    for f in dir_historial.iterdir():
        if not f.is_file() or not f.name.endswith(".md"):
            continue
        meta = parsear(f.name)
        if meta["stem"] != buscada or meta["timestamp"] is None:
            continue
        salida.append({"filename": f.name, "path": f, **meta})
    salida.sort(key=lambda v: (v["timestamp"], v["secuencia"]), reverse=True)
    return salida

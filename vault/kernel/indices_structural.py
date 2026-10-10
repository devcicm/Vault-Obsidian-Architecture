"""Hoja canónica de nombres reservados de índice.

AP-57: el dueño de este criterio es vault/kernel. Definido aquí para que
los módulos de vault/ puedan consultarlo sin cruzar la frontera scripts→vault
en la wheel instalada.

Nombres completos (con .md):
  "index.md", "readme.md"
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Optional

RESERVED_INDEX_NAMES: frozenset[str] = frozenset({"index.md", "readme.md"})
"""Nombres de fichero (con .md) reservados para índices generados automáticamente."""

RESERVED_INDEX_STEMS: frozenset[str] = frozenset({"index", "readme"})
"""Stems sin extensión — para comparar con slugify_strict output."""


#: Nombres de dispositivo de Windows. Un fichero llamado así no es un fichero:
#: `CON` es la consola, `NUL` el vacío, `COM1`/`LPT1` puertos. Medido en
#: Windows 10 con Python 3.14: `Path(n).exists()` es True en un directorio
#: vacío para `con.md`, `con.tar.md`, `con .md`, `conin$.md` y `aux.md`, y
#: leerlo **cuelga** el proceso esperando entrada de consola. La reserva mira
#: lo que va antes del primer punto, sin los espacios finales y sin distinguir
#: mayúsculas; `COM0` y `console.md` son ficheros normales.
DISPOSITIVOS_WINDOWS: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{i}" for i in "123456789\u00b9\u00b2\u00b3"}
    | {f"LPT{i}" for i in "123456789\u00b9\u00b2\u00b3"}
)


def es_dispositivo_windows(nombre: str) -> bool:
    """True si ``nombre`` (con extensión o sin ella) es un dispositivo de Windows.

    Se aplica en todas las plataformas: un vault escrito en Linux con una nota
    `con.md` cuelga a quien lo abra en Windows, y el vault viaja.
    """
    base = (nombre or "").strip().split(".", 1)[0].rstrip(" ").upper()
    return base in DISPOSITIVOS_WINDOWS


def motivo_de_reserva(nombre: str) -> Optional[str]:
    """Por qué ``nombre`` no puede ser una nota: ``"indice"``, ``"dispositivo"`` o None."""
    base = (nombre or "").strip().lower()
    if base.endswith(".md"):
        base = base[:-3]
    if base in RESERVED_INDEX_STEMS:
        return "indice"
    if es_dispositivo_windows(nombre):
        return "dispositivo"
    return None


def describir_reserva(nombre: str) -> str:
    """La frase que explica la reserva, para el mensaje de error de quien rechaza."""
    if motivo_de_reserva(nombre) == "dispositivo":
        return ("nombre de dispositivo de Windows (CON, NUL, AUX, COM1…): no sería "
                "un fichero, y leerlo cuelga el proceso en vez de fallar")
    return "nombre reservado para el índice generado de la carpeta"


def es_nombre_reservado(nombre: str) -> bool:
    """True si ``nombre`` (con o sin ``.md``) no puede ser el de una nota.

    Dos motivos, un solo dueño (`motivo_de_reserva`): el índice generado y el
    dispositivo de Windows. El segundo entró en v40.34 porque `vault_write
    --title CON` se colgaba 60 s hasta el timeout: el guard de dispositivos
    vivía solo en `atomic_write`, y la tool **lee** la nota existente antes de
    escribir — `exists()` es True para la consola y `read_text` espera entrada.

    Sin distinguir mayúsculas: en Windows y macOS ``Index.md`` e ``index.md``
    son el mismo fichero, así que una nota titulada «Index» acaba siendo el
    índice que ``vault_section_index`` regenera encima — el contenido del
    usuario solo sobrevive en un backup oculto. Toda entrada que deriva un
    nombre de un título pregunta aquí antes de escribir (AP-57: un solo dueño).
    """
    return motivo_de_reserva(nombre) is not None


#: Argumentos que nombran una ruta del vault. Se reconocen por subcadena del
#: nombre (`folder`, `to_path`, `output_dir`…), igual en `cli/safety` y en el
#: pre-flight de `vault run`: dos listas eran dos criterios (AP-57).
ARGUMENTOS_DE_RUTA: tuple = ("folder", "path", "file", "output", "dest", "target", "source", "dir")

#: Prefijo con el que `vault_write --content` lee el contenido de un fichero.
#: Lo que sigue es una ruta, y se mide como tal.
PREFIJO_FICHERO = "@file:"

_UNIDAD = re.compile(r"^[A-Za-z]:")


def es_argumento_de_ruta(nombre: str) -> bool:
    """True si el argumento ``nombre`` nombra una ruta (por subcadena, sin mayúsculas)."""
    clave = nombre.lower().lstrip("-").replace("-", "_")
    return any(pista in clave for pista in ARGUMENTOS_DE_RUTA)


def motivo_de_ruta_insegura(ruta: str) -> Optional[str]:
    """``"absolute"``, ``"traversal"`` o None para una ruta que el vault recibe.

    AP-36: una ruta relativa al vault no empieza por raíz, unidad ni `~`, y
    ninguna de sus partes es `..`. Se mide en las dos sintaxis a la vez, porque
    el vault viaja entre sistemas: `C:x` y una ruta UNC son absolutas en Windows
    aunque `PurePosixPath` no lo sepa.
    """
    crudo = str(ruta).strip()
    unificado = crudo.replace("\\", "/")
    if unificado.startswith(("/", "~")) or _UNIDAD.match(crudo):
        return "absolute"
    if ".." in PurePosixPath(unificado).parts:
        return "traversal"
    return None

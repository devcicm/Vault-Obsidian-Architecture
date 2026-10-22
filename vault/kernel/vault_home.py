r"""O11 — la casa de los vaults: dónde viven (hoja del núcleo, solo stdlib).

`~/.vault-master/` — Windows: `C:\Users\<usuario>\.vault-master\`, Linux y
macOS: `~/.vault-master/`. Cada vault que se crea ahí es un artefacto con su
propio repositorio git: la memoria del agente se versiona como lo que es (una
memoria), no como un fichero suelto dentro del repositorio del proyecto —que
es lo que pasaba en un vault real: las notas del proyecto absorbidas quedaban
borradas del repo del proyecto y sin versionar en ninguna parte—.

Se cambia con `VAULT_MASTER` (el registro del entorno lo publica).

El puntero `.vault-path` —la declaración que hace un repositorio de dónde
está su vault— **no vive aquí**: es del dueño de la raíz
(`vault.kernel.raiz`), que es quien decide cuál es el vault activo.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

#: Nombre de la carpeta que guarda los vaults del usuario.
MASTER_DIR_NAME = ".vault-master"

#: Variable que cambia la casa. La publica `vault_entorno --limites`.
ENV_MASTER = "VAULT_MASTER"


def master_home() -> Path:
    """La ruta donde el estándar deja los vaults del usuario.

    Windows: `C:\\Users\\<usuario>\\.vault-master\\`
    Linux y macOS: `~/.vault-master/`

    `Path.home()` es la forma multiplataforma de decirlo: el mismo nombre de
    carpeta vale en los dos sistemas, y quien la mueva lo hace con
    `VAULT_MASTER`.
    """
    crudo = (os.environ.get(ENV_MASTER) or "").strip()
    if crudo:
        return Path(crudo).expanduser()
    return Path.home() / MASTER_DIR_NAME


def vault_en_master(nombre: str) -> Path:
    """La ruta de un vault con ese nombre dentro de la casa.

    El nombre es un nombre, no una ruta: separadores y `..` se rechazan,
    porque un nombre de vault se usa para componer rutas.
    """
    limpio = (nombre or "").strip()
    if not limpio or limpio in {".", ".."}:
        raise ValueError(f"nombre de vault invalido: {nombre!r}")
    if any(sep in limpio for sep in ("/", "\\", ":")):
        raise ValueError(
            f"nombre de vault invalido: {nombre!r} (no puede traer separadores)")
    return master_home() / limpio


def es_ruta_de_master(ruta: "str | Path") -> bool:
    """¿La ruta vive dentro de la casa de los vaults?"""
    try:
        return Path(ruta).expanduser().resolve().is_relative_to(master_home().resolve())
    except (OSError, ValueError):
        return False


def listar_vaults_de_la_casa() -> list:
    """Los vaults de la casa, con lo que se sabe de cada uno sin abrirlo.

    El nombre, la ruta, la versión declarada en su `00_System/` y si tiene
    repositorio. Un vault de la casa que no se puede leer no se esconde: sale
    con lo que se sepa de él.
    """
    import json

    casa = master_home()
    vaults = []
    if not casa.is_dir():
        return vaults
    for hijo in sorted(p for p in casa.iterdir() if p.is_dir()):
        version = ""
        try:
            datos = json.loads(
                (hijo / "00_System" / "standard-version.json").read_text(encoding="utf-8"))
            version = str(datos.get("version") or datos.get("standard_version") or "")
        except (OSError, ValueError):
            version = ""
        vaults.append({
            "nombre": hijo.name,
            "ruta": str(hijo),
            "version": version,
            "git": (hijo / ".git").is_dir(),
        })
    return vaults

#!/usr/bin/env python3

"""

Vault List Tool — List notes in vault



Lists notes in the vault sorted by updatedAt descending.

Without folder: returns root structure with icons and descriptions.

With folder: returns notes in that folder with full metadata.



Usage:

    python vault_list.py

    python vault_list.py --folder "01_Projects"

    python vault_list.py --folder "07_Knowledge/apis" --limit 10

"""



import argparse

import json

import os

import re

import sys

from vault_registry import ORDERED_SECTIONS, section_description
from vault_errors import emit_error, wrap_main
from vault_lib import parse_frontmatter as _parse_frontmatter

from datetime import datetime

from pathlib import Path

from typing import Any, Dict, List, Optional



# Configuration

from vault_io import get_vault_root


# Folder descriptions

# Doce descripciones escritas a mano que ya no coincidían con ninguna del
# registro, y diez secciones sin entrada. Duplicar el texto no daba nada: aquí
# solo se muestra.
FOLDER_DESCRIPTIONS = {f: section_description(f) for f in ORDERED_SECTIONS}



# El icono sí es dato propio de esta tool —el registro no lo tiene— y por eso
# se escribe entero: una sección sin entrada se listaba sin icono, y las diez
# que faltaban eran justo las diez más nuevas.
FOLDER_ICONS = {
    "00_System": "⚙️",
    "01_Projects": "📁",
    "02_Observability": "🔍",
    "03_Decisions": "📋",
    "04_Sessions": "📅",
    "05_Patterns": "🔄",
    "06_Diagrams": "📊",
    "07_Knowledge": "📚",
    "08_Runbooks": "📖",
    "09_Infrastructure": "🏗️",
    "10_Migrated": "📦",
    "11_Code": "💻",
    "12_Bibliography": "🔖",
    "13_Flows": "🔀",
    "14_Requirements": "📐",
    "15_Tests": "🧪",
    "16_AI_Governance": "⚖️",
    "17_Preferences": "🎛️",
    "18_Bugs": "🐞",
    "19_Audits": "🗒️",
    "20_Quarantine": "🚧",
    "99_Index": "🗂️",
}





def parse_frontmatter(content: str) -> Dict[str, Any]:
    """Frontmatter de una nota. Delega en el dueño canónico (AP-44/AP-57).

    Hasta v40.23 esto era un regex línea a línea, copiado en seis módulos. Medido
    sobre el corpus de `vault-sandbox/` (126 notas), devolvía `{{}}` —"esta nota no
    tiene frontmatter"— en **110** de ellas: el patrón `^---
` no casa `---
`
    ni sobrevive al BOM que dejan los editores de Windows, y ambas cosas están en
    el material real. Además leía todo valor como texto: `evergreen: true` salía
    `'true'`, que es verdadero como cadena aun cuando el dato diga lo contrario.
    `vault_lib.parse_frontmatter` hace BOM-strip, YAML de verdad, normaliza fechas
    y contiene `RecursionError` (AP-61).
    """
    return _parse_frontmatter(content)
def get_note_metadata(note_path: Path) -> Dict[str, Any]:

    """Get metadata from a note."""

    try:

        with open(note_path, "r", encoding="utf-8") as f:

            content = f.read()

    except (UnicodeDecodeError, PermissionError):

        return {}



    meta = parse_frontmatter(content)



    # Get preview

    body = content.split("---", 2)[-1] if content.startswith("---") else content

    preview = body.strip()[:150].replace("\n", " ")



    # Get stats

    try:

        stat = note_path.stat()

        updated = datetime.fromtimestamp(stat.st_mtime).isoformat()

    except OSError:

        updated = meta.get("updatedAt", "")



    return {

        "title": meta.get("title", note_path.stem),

        "tags": meta.get("tags", []),

        "status": meta.get("status", ""),

        "type": meta.get("type", ""),

        "preview": preview,

        "updatedAt": meta.get("updatedAt", updated),

        "createdAt": meta.get("createdAt", ""),

    }





def vault_list(folder: Optional[str] = None, status: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:

    """

    List notes in the vault.



    Args:

        folder: List notes in specific folder (None = root structure)

        status: Filter by status tag

        limit: Maximum number of notes to return



    Returns:

        Root structure or list of notes with metadata

    """

    if folder is None:

        # Return root structure

        folders = []

        for item in sorted(get_vault_root().iterdir()):

            if item.is_dir() and not item.name.startswith("."):

                note_count = sum(1 for _ in item.rglob("*.md"))

                folder_id = (

                    item.name[:2] if item.name.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")) else ""

                )

                folders.append(

                    {

                        "name": item.name,

                        "icon": FOLDER_ICONS.get(item.name, "📂"),

                        "description": FOLDER_DESCRIPTIONS.get(item.name, ""),

                        "noteCount": note_count,

                        "path": str(item.relative_to(get_vault_root())),

                    }

                )



        return {"ok": True, "type": "root", "folders": folders}



    # List notes in folder

    folder_path = get_vault_root() / folder

    if not folder_path.exists():

        return {**emit_error("vault_list", "FOLDER_NOT_FOUND", f"Folder not found: {folder}"), "path": folder}



    notes = []

    for note_path in sorted(folder_path.rglob("*.md"), key=lambda p: os.path.getmtime(p), reverse=True):

        meta = get_note_metadata(note_path)



        if status and meta.get("status") != status:

            continue



        notes.append(

            {

                "path": str(note_path.relative_to(get_vault_root())),

                "title": meta.get("title", note_path.stem),

                "tags": meta.get("tags", []),

                "status": meta.get("status", ""),

                "type": meta.get("type", ""),

                "preview": meta.get("preview", ""),

                "updatedAt": meta.get("updatedAt", ""),

            }

        )



        if len(notes) >= limit:

            break



    return {"ok": True, "type": "notes", "folder": folder, "total": len(notes), "limit": limit, "notes": notes}





def main():

    parser = argparse.ArgumentParser(

        description="Vault List Tool",

        formatter_class=argparse.RawDescriptionHelpFormatter,

        epilog="""

Ejemplos:

  python vault_list.py

  python vault_list.py --folder "01_Projects"

  python vault_list.py --folder "07_Knowledge/apis" --limit 10

  python vault_list.py --folder "05_Patterns" --status "implementado"



Notas:

  - Sin --folder retorna la estructura raiz del vault con iconos y descripciones

  - Con --folder retorna las notas en esa carpeta con metadata completa

""",

    )

    parser.add_argument("--folder", help="Folder to list")

    parser.add_argument("--status", help="Filter by status")

    parser.add_argument("--limit", type=int, default=50, help="Max notes to return")



    args = parser.parse_args()

    result = vault_list(args.folder, args.status, args.limit)



    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1





if __name__ == "__main__":

    sys.exit(wrap_main(main, "vault_list"))


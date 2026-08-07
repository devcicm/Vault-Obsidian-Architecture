#!/usr/bin/env python3

"""

Vault Index - Generar indice markdown desde JSON

"""



import sys

from vault_errors import wrap_main

import json

import argparse

from pathlib import Path





from vault_io import get_vault_root, safe_wikilink




#: Destino por defecto. Era `INDEX.md` en la raíz del vault: un fichero suelto
#: fuera de toda sección canónica, que es exactamente lo que AP-15 prohíbe y lo
#: que la auditoría del vault de pruebas marcaba. `--output` sigue aceptando
#: cualquier ruta, así que ninguna invocación existente cambia de comportamiento
#: salvo la que no pasaba destino — y esa escribía donde no debía.
DEFAULT_OUTPUT = "99_Index/INDEX.md"


def generate_index(output=DEFAULT_OUTPUT):

    """Generar indice markdown"""

    index_file = get_vault_root() / "99_Index" / "search-index.json"



    if not index_file.exists():

        return {"error": "No search-index.json found"}



    data = json.loads(index_file.read_text(encoding="utf-8"))



    by_folder = {}

    for note in data.get("notes", []):

        note_path = Path(note["path"])

        folder = str(note_path.parent)

        if folder not in by_folder:

            by_folder[folder] = []

        by_folder[folder].append(note)



    md = "# Vault Index\n\n"

    md += f"Ultima actualizacion: {data.get('updatedAt', 'N/A')}\n\n"

    md += f"Total notas: {len(data.get('notes', 0))}\n\n"

    md += "---\n\n"



    for folder, notes in sorted(by_folder.items()):

        md += f"## {folder}\n\n"

        for note in sorted(notes, key=lambda x: x.get("title", "")):

            # El enlace va por el nombre de fichero, nunca por `title:`.
            # Obsidian resuelve un wikilink por stem y por `aliases:`, y no mira
            # `title:` en absoluto: enlazar por título deja el enlace roto para
            # el único consumidor que importa, y al abrirlo crea una nota en
            # blanco. Son las quince violaciones AP-44 que la auditoría del
            # vault de pruebas atribuía a este fichero — todas escritas aquí.
            # El título sigue visible, pero como texto, no como destino.

            stem = Path(note.get("path", "")).stem or note.get("title", "")

            md += (
                f"- [[{safe_wikilink(stem)}]] — {note.get('title', '')}"
                f" · `{note.get('path', '')}`\n"
            )

        md += "\n"



    dest = get_vault_root() / output

    dest.write_text(md, encoding="utf-8")



    return {"generated": len(data.get("notes", 0)), "file": str(dest)}





def main():

    parser = argparse.ArgumentParser(

        description="Vault Index",

        formatter_class=argparse.RawDescriptionHelpFormatter,

        epilog="""

Ejemplos:

  python vault_index.py --index

  python vault_index.py --index --output "99_Index/INDEX.md"

  python vault_index.py --readme



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Requiere que 99_Index/search-index.json exista (generado por vault_write o vault_reindex)

  - Genera un indice Markdown agrupado por carpeta con links tipo [[titulo]]

""",

    )

    parser.add_argument("--index", "-i", action="store_true", help="Generar indice")

    parser.add_argument("--readme", "-r", action="store_true", help="Generar README")

    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT)



    args = parser.parse_args()



    result = generate_index(args.output)

    print(f"Index: {result.get('generated', 0)} notes -> {result.get('file')}")





if __name__ == "__main__":

    sys.exit(wrap_main(main, "vault_index"))


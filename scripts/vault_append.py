#!/usr/bin/env python3

"""

Vault Append Tool — Append content to existing note



Appends content to an existing note without creating a historical version.

Append is non-destructive - ideal for changelogs, session logs, and decision logs.



Usage:

    python vault_append.py --path "01_Projects/ans/changelog.md" --content "## v1.2 - 2026-05-03\n\nAdded feature X"

    python vault_append.py --path "04_Sessions/2026-05-03.md" --content "Completed task" --section "## Tasks"

"""

import argparse

import json

import re

import sys

from vault_errors import emit_error, fuera_de_sesion, wrap_main

from vault_io import assert_within_vault, atomic_write_text, get_vault_root, tomar_lock
from vault_lib import separar_frontmatter, utcnow
from vault.kernel.frontmatter_escritura import Frontmatter
from datetime import datetime, timezone

from pathlib import Path

from typing import Optional


# Configuration


def vault_append(
    path: str, content: str, section: Optional[str] = None, timestamped: bool = True
) -> dict:
    """

    Append content to an existing note.



    Args:

        path: Relative path to the note

        content: Text to add

        section: Add within a specific ## Heading section

        timestamped: If True, adds **YYYY-MM-DD HH:MM** before content



    Returns:

        Dict with success status and details

    """

    note_path = get_vault_root() / path

    try:
        assert_within_vault(note_path, get_vault_root())

    except ValueError as exc:
        return {"ok": False, "error_code": "INVALID_PATH", "error": str(exc)}

    bloqueo = fuera_de_sesion("vault_append", note_path)
    if bloqueo:
        return bloqueo

    if not note_path.exists():
        return {**emit_error("vault_append", "NOTE_NOT_FOUND", f"Note not found: {path}"), "path": path}

    # Leer, modificar y escribir bajo el mismo lock que `vault_write`: sin él,
    # dos appends leían la misma versión y el segundo `os.replace` borraba el
    # primero con los dos envelopes en ok:true (medido: 7 de 12 en paralelo).
    # `tomar_lock` y no `except TimeoutError` alrededor del bloque: el de un
    # lock interno (índice de sección) saldría como NOTE_LOCKED con la nota
    # ya escrita.
    lock = tomar_lock(note_path, 10.0)
    if lock is None:
        return {**emit_error("vault_append", "NOTE_LOCKED", f"Note locked: {path}"), "path": path}
    with lock:
        return _append_bajo_lock(note_path, path, content, section, timestamped)


def _insertar(texto: str, pos: int, bloque: str) -> str:
    """Inserta `bloque` en `pos` separado por una línea en blanco a cada lado.

    Medido el 2026-10-05 sobre una copia de un vault real: concatenar
    `"\n\n" + bloque` dejaba tres saltos delante y ninguno al final, y el
    `end-of-file-fixer` del consumidor ensuciaba el commit siguiente con un
    cambio que la tool no había pedido. La nota acaba en un solo `\n`.
    """
    antes = texto[:pos].rstrip("\n")
    despues = texto[pos:].lstrip("\n")
    bloque = bloque.strip("\n")
    cabeza = f"{antes}\n\n{bloque}" if antes else bloque
    return f"{cabeza}\n\n{despues}" if despues else f"{cabeza}\n"


def _refrescar_updated_at(texto: str) -> "tuple[str, Optional[str]]":
    """AP-13: un append es una escritura, y `updatedAt` sale del reloj.

    Medido el 2026-10-05: la nota recién ampliada conservaba el `updatedAt` de
    su creación, así que F6 la auditaba como obsoleta y `vault_context_pack`
    la ordenaba como vieja. Solo se refresca si la nota ya lo declara: append
    es no destructivo y no le cambia el esquema a una nota ajena —que falte es
    cosa de F3—. El bloque lo reescribe su dueño (AP-46); un YAML ilegible lo
    sigue parando `atomic_write_text` con FRONTMATTER_PARSE_ERROR.
    """
    bloque, cuerpo = separar_frontmatter(texto)
    if bloque is None or not re.search(r"^updatedAt\s*:", bloque, re.MULTILINE):
        return texto, None
    ahora = utcnow()
    return Frontmatter.editar(bloque).set("updatedAt", ahora).render() + "\n" + cuerpo, ahora


def _append_bajo_lock(
    note_path: Path, path: str, content: str, section: Optional[str], timestamped: bool
) -> dict:
    with open(note_path, "r", encoding="utf-8") as f:
        existing_content = f.read()

    # Prepare appended content

    append_text = content

    if timestamped:
        timestamp = datetime.now(timezone.utc).strftime("**%Y-%m-%d %H:%M**")

        append_text = f"\n\n{timestamp} {content}"

    else:
        append_text = f"\n\n{content}"

    # If section specified, find and append within that section

    if section:
        # Look for the section heading

        section_pattern = rf"(## {re.escape(section.lstrip('# ').strip())})"

        section_match = re.search(section_pattern, existing_content)

        if section_match:
            # Find the position right after the section heading

            section_start = section_match.start()

            section_end = section_match.end()

            # Find the next section or end of file

            next_section = re.search(r"\n## [^#]", existing_content[section_end:])

            if next_section:
                insert_pos = section_end + next_section.start()

            else:
                insert_pos = len(existing_content)

            existing_content = _insertar(existing_content, insert_pos, append_text)

        else:
            # Section not found, append at end

            existing_content = _insertar(existing_content, len(existing_content), append_text)

    else:
        existing_content = _insertar(existing_content, len(existing_content), append_text)

    existing_content, updated_at = _refrescar_updated_at(existing_content)

    # Write back

    atomic_write_text(note_path, existing_content)

    return {
        "ok": True,
        "path": path,
        "appendedLength": len(append_text),
        "section": section,
        "timestamped": timestamped,
        "updatedAt": updated_at,
        "message": "Content appended successfully",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Append Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_append.py --path "01_Projects/ans/changelog.md" --content "## v1.2 - 2026-05-03\\n\\nAdded feature X"

  python vault_append.py --path "04_Sessions/2026-05-03.md" --content "Completed task" --section "## Tasks"

  python vault_append.py --path "08_Runbooks/deploy/ans-deploy.md" --content "Updated step 3" --no-timestamp

  python vault_append.py --path "02_Observability/errors/timeout.md" --content "Error resolved on 2026-05-03"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Sin --no-timestamp se agrega marca de tiempo automaticamente

""",
        allow_abbrev=False,
    )

    parser.add_argument("--path", required=True, help="Relative path to note")

    parser.add_argument("--content", required=True, help="Content to append")

    parser.add_argument("--section", help="Section heading to append within")

    parser.add_argument(
        "--no-timestamp", action="store_true", help="Don't add timestamp"
    )

    args = parser.parse_args()

    result = vault_append(args.path, args.content, args.section, not args.no_timestamp)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_append"))

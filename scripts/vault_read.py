#!/usr/bin/env python3

"""

Vault Read Tool — Read note with metadata



Reads a note by relative path and returns structured content.

Extracts frontmatter, body, wiki-links, and history versions.



Usage:

    python vault_read.py --path "01_Projects/ans/overview.md"

    python vault_read.py --path "07_Knowledge/apis/mcp-tools-index.md"

"""

import argparse

import json

import os

import re

import sys

from vault_errors import emit_error, wrap_main
from vault_lib import parse_frontmatter_with_body as _parse_frontmatter_with_body

from vault_io import assert_within_vault
from vault_encoding import decode_safely, normalize_to_nfc
from vault_regex import extract_wiki_links_strict
from datetime import datetime
from pathlib import Path

from typing import Any, Dict, List, Optional


# Configuration


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _history_dir() -> Path:
    return _repo().dir_historial


def parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
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
    meta, body = _parse_frontmatter_with_body(content)
    return meta, body.strip()  # el `.strip()` es el contrato de esta tool, no del dueño
def extract_wiki_links(content: str) -> List[str]:
    """Extract wiki-links [[note]] from content.

    Uses strict extraction that filters:
    - Empty links
    - Links exceeding max length
    - Links with invalid characters
    """

    return extract_wiki_links_strict(content)


def get_history_versions(note_path: Path) -> List[str]:
    """Get list of historical versions in .history/"""

    if not _history_dir().exists():
        return []

    note_name = note_path.stem  # filename without extension

    folder_prefix = str(note_path.parent.relative_to(_raiz())).replace("/", "__")

    versions = []

    for history_file in _history_dir().iterdir():
        if history_file.is_file() and note_name in history_file.stem:
            # Check if this version matches our note

            prefix = f"{folder_prefix}__{note_name}-"

            if history_file.stem.startswith(
                prefix.replace("-", "_").replace("__", "__")
            ):
                versions.append(history_file.name)

    # Sort by date (most recent first)

    versions.sort(reverse=True)

    return versions[:10]  # Return last 10 versions


def vault_read(path: str) -> Dict[str, Any]:
    """

    Read a note from the vault.



    Args:

        path: Relative path to the note (e.g., "01_Projects/ans/overview.md")



    Returns:

        Dict with meta, body, wikiLinks, and historyVersions

    """

    note_path = _raiz() / path

    try:
        assert_within_vault(note_path, _raiz())
    except ValueError as exc:
        return {"ok": False, "error_code": "INVALID_PATH", "error": str(exc)}

    if not note_path.exists():
        return {**emit_error("vault_read", "NOTE_NOT_FOUND", f"Note not found: {path}"), "path": path}

    # Use decode_safely for proper encoding detection with fallback
    bytes_content = note_path.read_bytes()
    content, encoding_used = decode_safely(bytes_content)

    # Normalize to NFC for consistency
    content = normalize_to_nfc(content)

    # Parse frontmatter

    meta, body = parse_frontmatter(content)

    # Extract wiki-links

    wiki_links = extract_wiki_links(content)

    # Get history versions

    history_versions = get_history_versions(note_path)

    return {
        "ok": True,
        "path": path,
        "meta": meta,
        "body": body,
        "wikiLinks": wiki_links,
        "historyVersions": history_versions,
        "stats": {
            "size": len(content),
            "lines": len(content.split("\n")),
            "words": len(body.split()),
            "links": len(wiki_links),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Read Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_read.py --path "01_Projects/ans/overview.md"

  python vault_read.py --path "07_Knowledge/apis/mcp-tools-index.md"

  python vault_read.py --path "03_Decisions/adr-001-arquitectura.md"

  python vault_read.py --path "08_Runbooks/deploy/ans-deploy.md"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - La ruta debe ser relativa a la raiz del vault

""",
    )

    parser.add_argument("--path", required=True, help="Relative path to note")

    args = parser.parse_args()

    result = vault_read(args.path)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_read"))

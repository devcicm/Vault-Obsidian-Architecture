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

from vault_io import assert_within_vault, is_snapshot_path
from vault_encoding import decode_safely, normalize_to_nfc
from vault_regex import extract_wiki_links_strict
from datetime import datetime
from pathlib import Path

from typing import Any, Dict, List, Optional


# Configuration


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel import historia  # noqa: E402
from vault.kernel.frontmatter_parsing import parse_frontmatter_robust  # noqa: E402


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
    """Get list of historical versions in .history/ (las 10 más recientes).

    Delega en `vault.kernel.historia` (v41.3). Aquí se buscaba el stem como
    subcadena del nombre y se ordenaba alfabéticamente: `a.md` recibía las
    versiones de `casa.md`.
    """
    # Resueltas las dos: con la grafía cruda (`./`, `..`, otra caja en Windows,
    # la raíz en forma 8.3) la clave no casaba y salía `[]` con ok:true (AP-51).
    rel = note_path.resolve().relative_to(_raiz().resolve()).as_posix()
    return [v["filename"] for v in historia.versiones(_history_dir(), rel)][:10]


def _resolver_por_nombre(nombre: str):
    """`(ruta, candidatos)` resolviendo `nombre` como destino de Obsidian.

    La promesa del catálogo es «por ruta relativa o por título», y el criterio
    con el que Obsidian resuelve un nombre es **stem y `aliases:`** —nunca
    `title:`— (AP-44). El dueño del criterio es `vault_lib`, el mismo que usan
    el write path y los índices: aquí no se reimplementa (AP-57).
    """
    from vault_lib import indice_de_nombres, inventario_de_nombres, resolver_wikilink

    relativas, aliases = inventario_de_nombres(_raiz(), is_snapshot_path)
    indice = indice_de_nombres(relativas, aliases)
    ruta, candidatos = resolver_wikilink(nombre, None, indice)
    return (_raiz() / ruta if ruta else None), candidatos


def vault_read(path: str) -> Dict[str, Any]:
    """

    Read a note from the vault.



    Args:

        path: Relative path to the note (e.g., "01_Projects/ans/overview.md")



    Returns:

        Dict with meta, body, wikiLinks, and historyVersions

    """

    try:
        note_path = assert_within_vault(_raiz() / path, _raiz())
    except ValueError as exc:
        return {"ok": False, "error_code": "INVALID_PATH", "error": str(exc)}

    if not note_path.exists():
        # «Por ruta relativa o por título»: si la ruta no existe, el nombre se
        # resuelve como un destino de Obsidian antes de darlo por ausente.
        resuelta, candidatos = _resolver_por_nombre(path)
        if resuelta is not None:
            note_path = resuelta
            resuelta_desde = path
        elif candidatos:
            return {**emit_error(
                "vault_read", "NOTE_NOT_FOUND",
                f"Name '{path}' matches {len(candidatos)} notes: "
                f"{', '.join(candidatos)}; give the path to pick one"),
                "path": path, "candidates": candidatos}
        else:
            return {**emit_error("vault_read", "NOTE_NOT_FOUND", f"Note not found: {path}"), "path": path}
    else:
        resuelta_desde = None

    # AP-51: un directorio no es una nota. Hasta 2026-10-10 su lectura salía
    # como PERMISSION_DENIED (el PermissionError de Windows), y el agente
    # buscaba un problema de permisos donde había una ruta equivocada.
    if note_path.is_dir():
        return {**emit_error("vault_read", "INVALID_PATH",
                             f"Not a note: {path} (is a directory; use vault_list)"), "path": path}

    # AP-51: el `path` del sobre es la identidad de la nota, no el eco de la
    # petición. Hasta 2026-10-10 `./07_Knowledge//Nota.md` o `07_knowledge/nota.MD`
    # volvían tal cual: dos identidades para una nota (medido como consumidor).
    # La ruta resuelta trae la caja real del disco en Windows.
    canonica = note_path.relative_to(_raiz().resolve()).as_posix()

    # Use decode_safely for proper encoding detection with fallback
    bytes_content = note_path.read_bytes()
    content, encoding_used = decode_safely(bytes_content)

    # Normalize to NFC for consistency
    content = normalize_to_nfc(content)

    # Parse frontmatter

    # AP-51: `parse_frontmatter` devuelve `{}` tanto si la nota no tiene bloque
    # como si lo tiene y no parsea, y el agente no podía distinguirlos. La forma
    # robusta del dueño dice cuál de los dos es; el cuerpo es el mismo.
    meta, body, legible, causa = parse_frontmatter_robust(content)
    body = body.strip()

    # Extract wiki-links

    wiki_links = extract_wiki_links(content)

    # Get history versions

    history_versions = get_history_versions(note_path)

    result = {
        "ok": True,
        "path": canonica,
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
    if resuelta_desde is not None:
        # El nombre pedido no era una ruta: se dice por qué se resolvió, para
        # que el agente no crea que `path` es el eco de su petición (AP-51).
        result["resolved_from"] = resuelta_desde
    if not legible:
        result["frontmatter_error"] = causa
    return result


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
        allow_abbrev=False,
    )

    parser.add_argument("--path", required=True, help="Relative path to note")

    args = parser.parse_args()

    result = vault_read(args.path)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_read"))

#!/usr/bin/env python3

"""

Vault Search Tool — Full-text weighted search



Searches the vault using weighted scoring: title×4 + word matches + preview matches.

Returns up to 20 results ordered by score.



Usage:

    python vault_search.py --query "mcp tools ansible"

    python vault_search.py --query "deployment" --folder "08_Runbooks"

    python vault_search.py --query "api" --tag "mcp"

"""


import argparse

import json

import os
import re

import sys

from vault_errors import emit_error, wrap_main

from pathlib import Path

from typing import Any, Dict, List, Optional


# Configuration


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.normalizacion import fold_accents  # noqa: E402
from vault_io import assert_within_vault, is_snapshot_path  # noqa: E402
from vault_lib import parse_frontmatter, separar_frontmatter  # noqa: E402
from vault_entorno import leer as leer_entorno  # dueño del registro (AP-49/05)


def _notas_visibles_en_vivo(root: Path):
    """Read current visible Markdown for MCP; do not follow symlinks or history."""
    notes, skipped = [], []
    def onerror(exc):
        skipped.append(str(exc))
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
        parent = Path(directory)
        dirs[:] = [d for d in dirs if not d.startswith('.') and not is_snapshot_path(d) and not (parent / d).is_symlink()]
        for name in files:
            if name.startswith('.') or not name.lower().endswith('.md'):
                continue
            path = parent / name
            if path.is_symlink():
                continue
            try:
                text = path.read_text(encoding='utf-8')
                meta = parse_frontmatter(text) or {}
                tags = meta.get('tags') or []
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(',') if t.strip()]
                notes.append({'path': path.relative_to(root).as_posix(),
                              'title': meta.get('title') or path.stem,
                              'preview': separar_frontmatter(text)[1].strip()[:200].replace('\n', ' '),
                              'tags': tags, 'updatedAt': meta.get('updatedAt') or meta.get('createdAt') or ''})
            except (OSError, UnicodeError, ValueError) as exc:
                skipped.append(f'{path.relative_to(root).as_posix()}: {type(exc).__name__}')
    return notes, skipped


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _index_file() -> Path:
    return _repo().indice_busqueda


def _forma(texto: str) -> str:
    """AP-44: la forma con que se compara texto — sin acentos ni mayúsculas.

    Hasta 2026-10-10 era `.lower()`: «cancion» no encontraba «Canción» ni
    «CONFIGURACION» a «configuración» (medido como consumidor).
    """
    return fold_accents(texto or "").casefold()


def _en_carpeta(ruta: str, folder: str) -> bool:
    """La carpeta es un componente de la ruta, no un prefijo de texto."""
    folder = folder.strip("/")
    return ruta == folder or ruta.startswith(folder + "/")


def score_note(note: Dict[str, Any], query: str, folder: Optional[str], tag: Optional[str]) -> float:

    """Calculate weighted search score for a note."""

    if folder and not _en_carpeta(note.get("path", ""), folder):

        return 0


    # AP-44: la tag se compara con la normalización con que `vault_write` la
    # guardó; `--tag Música` no encontraba la `musica` que él mismo escribió.
    forma = _repo().forma_de_etiqueta if tag else None
    if tag and forma(tag) not in {forma(str(t)) for t in note.get("tags", [])}:

        return 0


    query_lower = _forma(query)

    query_words = query_lower.split()


    score = 0

    title_lower = _forma(note.get("title", ""))


    # Title matches (weight ×4)

    if query_lower in title_lower:

        score += 40

    for word in query_words:

        if word in title_lower:

            score += 4


    # Tag matches

    for tag_item in note.get("tags", []):

        tag_lower = _forma(str(tag_item))

        if query_lower in tag_lower:

            score += 3

        for word in query_words:

            if word in tag_lower:

                score += 1


    # Preview/body matches (weight ×1)

    preview_lower = _forma(note.get("preview", ""))

    if query_lower in preview_lower:

        score += 10

    for word in query_words:

        if word in preview_lower:

            score += 1


    return score


def vault_search(query: str, folder: Optional[str] = None, tag: Optional[str] = None) -> Dict[str, Any]:

    """

    Search the vault with weighted scoring.



    Args:

        query: Search terms (multiple words separated by space)

        folder: Restrict search to a folder (e.g., "02_Observability")

        tag: Filter by frontmatter tag



    Returns:

        Dict with results ordered by score

    """

    # AP-37: una consulta vacía no es una búsqueda; devolvía el vault entero.
    if not (query or "").strip():
        return {**emit_error("vault_search", "INVALID_INPUT", "--query vacío."),
                "query": query, "results": []}

    # Una carpeta que no existe o sale del vault respondía 0 resultados con
    # ok:true, indistinguible de «no hay coincidencias» (AP-51).
    if folder:
        carpeta = _raiz() / folder.strip("/")
        try:
            assert_within_vault(carpeta, _raiz())
        except ValueError as exc:
            return {**emit_error("vault_search", "INVALID_PATH", str(exc)),
                    "query": query, "results": []}
        if not carpeta.is_dir():
            return {**emit_error("vault_search", "FOLDER_NOT_FOUND",
                                 f"No existe la carpeta: {folder}"),
                    "query": query, "results": []}

    live = leer_entorno("VAULT_MCP_LIVE_SEARCH")
    skipped = []
    try:

        if live:
            notes, skipped = _notas_visibles_en_vivo(_raiz())
        else:

            with open(_index_file(), "r", encoding="utf-8") as f:

                index = json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):

        # `query` y `results: []` se conservan: los consumidores que iteran el
        # resultado sin mirar `ok` no empiezan a romperse por esto.
        return {

            **emit_error("vault_search", "INDEX_NOT_FOUND",
                         "Search index not found. Run vault_reindex first."),

            "query": query,

            "results": [],

        }


    if not live:
        notes = index.get("notes", [])


    # Score all notes

    scored_notes = []

    for note in notes:

        score = score_note(note, query, folder, tag)

        if score > 0:

            preview = note.get("preview", "")[:200]

            scored_notes.append(

                {

                    "path": note.get("path", ""),

                    "title": note.get("title", ""),

                    "preview": preview,

                    "tags": note.get("tags", []),

                    "score": score,

                    "updatedAt": note.get("updatedAt", ""),

                }

            )


    # Sort by score descending

    scored_notes.sort(key=lambda x: x["score"], reverse=True)


    # Return top 20

    results = scored_notes[:20]


    return {

        "ok": True,

        "query": query,

        **({"source": "live_visible_markdown", "incomplete": bool(skipped), "skipped": skipped} if live else {}),

        "folder": folder,

        "tag": tag,

        "total": len(results),

        # AP-37: el recorte a 20 se declara; antes `total` era lo devuelto y
        # nada decía cuántas coincidencias quedaban fuera.
        "matched": len(scored_notes),

        "truncated": len(scored_notes) > len(results),

        "results": results,

        "hint": "Use vault_read(path) to get full note content",

    }


def main():

    parser = argparse.ArgumentParser(

        description="Vault Search Tool",

        formatter_class=argparse.RawDescriptionHelpFormatter,

        epilog="""

Ejemplos:

  python vault_search.py --query "mcp tools ansible"

  python vault_search.py --query "deployment" --folder "08_Runbooks"

  python vault_search.py --query "api" --tag "mcp"

  python vault_search.py --query "circuit breaker" --folder "05_Patterns"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Requiere search-index.json generado por vault_reindex.py

  - Score: title×4 + word matches + preview matches

""",

        allow_abbrev=False,
    )

    parser.add_argument("--query", required=True, help="Search terms")

    parser.add_argument("--folder", help="Restrict to folder")

    parser.add_argument("--tag", help="Filter by tag")


    args = parser.parse_args()

    result = vault_search(args.query, args.folder, args.tag)


    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":

    sys.exit(wrap_main(main, "vault_search"))


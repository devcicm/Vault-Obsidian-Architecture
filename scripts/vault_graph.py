#!/usr/bin/env python3

"""

Vault Graph Tool — Generate wiki-links graph



Scans all wiki-links [[note]] in the vault and generates graph.json.

Returns nodes, edges, orphan notes, and broken links.



Usage:

    python vault_graph.py

"""

import json

import re

import sys

from vault_errors import wrap_main

from collections import defaultdict

from pathlib import Path

from typing import Any, Dict, List, Set

from vault_regex import RE_WIKILINK  # dueño único del patrón (AP-50)


# Configuration

from vault_io import atomic_write_json, write_report
from vault_lib import (  # dueño único de la identidad por nombre (AP-57, AP-17)
    colisiones_de_nombre,
    indice_de_nombres,
    parse_frontmatter,
    resolver_wikilink,
)
from vault_registry import ORDERED_SECTIONS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.grafo.aristas import consolidar_aristas  # noqa: E402
from vault.grafo.repositorio import RepositorioGrafo  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGrafo:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGrafo(construir(root))


def _graph_file() -> Path:
    return _repo().grafo


def _system_dir() -> Path:
    return _repo().dir_sistema

# `_system_dir()` se usaba en la lectura de `move-log.json` sin estar definido en
# ningún sitio: la rama de nodos movidos lanzaba NameError desde que se escribió.


# Only scan notes inside these standard sections — never root files or scripts/
#
# Derivado de `vault_registry`, no copiado. La copia literal se quedó en 18
# secciones mientras el estándar iba por 22: las notas de `17_Preferences`,
# `18_Bugs`, `19_Audits` y `20_Quarantine` no pasaban `_is_vault_note()` y por
# tanto no existían en `graph.json` — ni como nodo, ni como origen de enlace,
# ni como huérfana. Una sección entraba al estándar y salía invisible del grafo
# sin que nada fallara.
VAULT_SECTIONS = frozenset(ORDERED_SECTIONS)


def _is_vault_note(note_path: Path) -> bool:
    """Return True only for .md files inside a standard vault section."""

    try:
        parts = note_path.relative_to(_raiz()).parts

    except ValueError:
        return False

    if len(parts) < 2:
        return False  # Root-level file (spec doc, README, index.md at root)

    return parts[0] in VAULT_SECTIONS


def extract_wiki_links(content: str) -> List[str]:
    """Extract wiki-links [[note]] from content."""

    return RE_WIKILINK.findall(content)


def _build_slug_map(all_files: List[Path]) -> Dict[str, str]:
    """

    Build a map from possible wiki-link names to relative paths.

    superseded_by: vault_lib.indice_de_nombres. Con `if stem not in slug_map`
    un nombre compartido por dos notas resolvía a la que el recorrido del disco
    diera primero (AP-17); se conserva por la política de no-derogación, pero
    `vault_graph` ya no la usa.

    Handles: bare stem ('identity'), path with subdirs ('01_Projects/overview'),

    and Windows-style paths ('grooming-scheduler/overview\\').

    """

    slug_map: Dict[str, str] = {}

    for p in all_files:
        rel = str(p.relative_to(_raiz())).replace("\\", "/")

        rel_no_ext = rel.lower().removesuffix(".md")

        stem = p.stem.lower()

        # Register by stem (last component without extension)

        if stem not in slug_map:
            slug_map[stem] = rel

        # Register by full relative path without extension

        slug_map[rel_no_ext] = rel

        # Register by last two path components (e.g. 'grooming-scheduler/overview')

        parts = rel_no_ext.split("/")

        if len(parts) >= 2:
            short = "/".join(parts[-2:])

            if short not in slug_map:
                slug_map[short] = rel

    return slug_map


def _resolve_link(slug: str, slug_map: Dict[str, str]) -> str:
    """Try to resolve a wiki-link slug to a vault-relative path.

    superseded_by: vault_lib.resolver_wikilink, que devuelve los candidatos en
    vez de uno solo y quita alias y ancla antes de buscar.
    """

    # Normalize: backslashes, strip trailing separators

    normalized = slug.replace("\\", "/").strip("/").lower()

    # Try exact match

    if normalized in slug_map:
        return slug_map[normalized]

    # Try stem only (last segment)

    stem = normalized.split("/")[-1]

    if stem in slug_map:
        return slug_map[stem]

    return ""


def vault_graph() -> Dict[str, Any]:
    """

    Regenerate graph.json scanning all wiki-links in the vault.



    Returns:

        Nodes, edges, orphan notes, and broken links

    """

    nodes = {}  # path -> {title, type, tags, links}

    edges = []  # [{from, to, type}]

    broken_links = []  # [{from, link}]

    orphans = []  # [{path, title}]

    # Scan only notes inside the 13 standard vault sections

    all_files = [
        p
        for p in _raiz().rglob("*.md")
        if _is_vault_note(p) and not any(part.startswith(".") for part in p.parts)
    ]

    ambiguous_links = []  # [{from, link, candidates}]

    # Primera pasada: el índice de nombres necesita los `aliases:` de todas
    # las notas antes de resolver el primer enlace.

    repo = _repo()

    contenidos: Dict[Path, str] = {}

    aliases_por_ruta: Dict[str, List[str]] = {}

    for note_path in all_files:
        try:
            with open(note_path, "r", encoding="utf-8") as f:
                contenidos[note_path] = f.read()

        except (UnicodeDecodeError, PermissionError):
            continue

        aliases = parse_frontmatter(contenidos[note_path]).get("aliases") or []

        if isinstance(aliases, str):
            aliases = [aliases]

        if isinstance(aliases, list):
            aliases_por_ruta[repo.relativa(note_path)] = aliases

    relativas = [repo.relativa(p) for p in all_files]

    indice = indice_de_nombres(relativas, aliases_por_ruta)

    for note_path, content in contenidos.items():
        rel_path = str(note_path.relative_to(_raiz())).replace("\\", "/")

        # Parse frontmatter

        frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)

        if frontmatter_match:
            title = re.search(
                r"^title:\s*(.+)$", frontmatter_match.group(1), re.MULTILINE
            )

            tags_match = re.search(
                r"^tags:\s*(.+)$", frontmatter_match.group(1), re.MULTILINE
            )

            title = title.group(1).strip("\"'") if title else note_path.stem

            if tags_match:
                try:
                    tags = json.loads(tags_match.group(1))

                except json.JSONDecodeError:
                    tags = []

            else:
                tags = []

        else:
            title = note_path.stem

            tags = []

        # Extract wiki-links

        wiki_links = extract_wiki_links(content)

        nodes[rel_path] = {
            "title": title,
            "type": rel_path.split("/")[0] if "/" in rel_path else "other",
            "tags": tags,
            "links": wiki_links,
            "linkCount": len(wiki_links),
        }

        # Create edges — use recursive slug map instead of root-only lookup

        for link in wiki_links:
            resolved, candidatos = resolver_wikilink(link, Path(rel_path), indice)

            if resolved:
                edges.append({"from": rel_path, "to": resolved, "type": "wiki-link"})

            elif candidatos:
                # AP-17: el destino existe, pero responden dos notas. Elegir
                # una sería inventar la identidad; la carpeta en el enlace es
                # lo que la fija.
                ambiguous_links.append(
                    {"from": rel_path, "link": link, "candidates": candidatos}
                )

            else:
                # AP-14: el wikilink que no resuelve contra el mapa de slugs.
                # Es también la única evidencia de que **SP-02** no se siguió:
                # el protocolo pide buscar la nota antes de escribir `[[…]]`, y
                # un enlace roto es exactamente lo que queda cuando no se buscó.
                # Se publica el `targetPath` sin normalizar a propósito, para
                # que el consumidor vea el enlace tal como está escrito en la
                # nota y no la versión que esta tool preferiría (AP-44).
                broken_links.append(
                    {
                        "from": rel_path,
                        "link": link,
                        "targetPath": link.replace("\\", "/"),
                    }
                )

    # Una arista por relación (from, type, to), con sus apariciones.

    edges = consolidar_aristas(edges)

    # Find orphan notes (no incoming links, except 00_System)

    incoming_links = defaultdict(list)

    for edge in edges:
        incoming_links[edge["to"]].append(edge["from"])

    for path, node in nodes.items():
        if path not in incoming_links and not path.startswith("00_System/"):
            orphans.append({"path": path, "title": node["title"], "type": node["type"]})

    # Add status to each node (active, deleted, moved)
    for path, node in nodes.items():
        node["status"] = "active"

    # Check for deleted nodes from previous graph
    if _graph_file().exists():
        try:
            old_graph = json.loads(_graph_file().read_text(encoding="utf-8"))
            old_nodes = old_graph.get("nodes", {})

            for old_path in old_nodes:
                if old_path not in nodes:
                    old_node = old_nodes[old_path]
                    edges.append(
                        {
                            "from": old_path,
                            "to": "__deleted__",
                            "type": "deleted-node",
                            "original_status": old_node.get("status", "active"),
                        }
                    )
        except (json.JSONDecodeError, PermissionError):
            pass

    # Check for moved nodes from move-log
    move_log = _system_dir() / "move-log.json"
    if move_log.exists():
        try:
            move_data = json.loads(move_log.read_text(encoding="utf-8"))
            for move in move_data:
                old_path = move.get("from")
                new_path = move.get("to")
                if old_path in nodes:
                    nodes[old_path]["status"] = "moved"
                    nodes[old_path]["moved_to"] = new_path
                    nodes[old_path]["moved_at"] = move.get("timestamp")
        except (json.JSONDecodeError, PermissionError):
            pass

    name_collisions = colisiones_de_nombre(relativas)

    # Count deleted/moved nodes
    deleted_count = sum(1 for n in nodes.values() if n.get("status") == "deleted")
    moved_count = sum(1 for n in nodes.values() if n.get("status") == "moved")

    # Save graph

    graph_data = {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "totalNodes": len(nodes),
            "totalEdges": len(edges),
            "orphanNotes": len(orphans),
            "brokenLinks": len(broken_links),
            "ambiguousLinks": len(ambiguous_links),
            "nameCollisions": len(name_collisions),
            "deletedNodes": deleted_count,
            "movedNodes": moved_count,
        },
        "orphans": orphans,
        "brokenLinks": broken_links,
        "ambiguousLinks": ambiguous_links,
        "nameCollisions": name_collisions,
    }

    _graph_file().parent.mkdir(parents=True, exist_ok=True)

    # Escritura atómica: además de temp+replace, es lo que hace que la
    # regeneración quede contada en el ledger de AP-37. Con `json.dump` directo
    # la tool devolvía `written: 0` habiendo reescrito el grafo entero.
    atomic_write_json(_graph_file(), graph_data)

    return {
        "ok": True,
        **write_report(),
        "savedTo": _repo().relativa(_graph_file()),
        "stats": graph_data["stats"],
        "orphans": orphans[:10],  # Top 10
        "brokenLinks": broken_links[:10],  # Top 10
        "ambiguousLinks": ambiguous_links[:10],  # Top 10
        "nameCollisions": name_collisions[:10],  # Top 10
    }


def vault_graph_typed() -> Dict[str, Any]:
    """Generate graph-enriched.json with typed predicates (delegates to vault_graph_merge)."""
    from vault_graph_merge import vault_graph_merge
    return vault_graph_merge()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Vault Graph Tool -- Generate wiki-links graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_graph.py
  python vault_graph.py --typed



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Escanea todos los [[wiki-links]] y genera 99_Index/graph.json

  - Detecta notas huerfanas (sin links entrantes) y links rotos

  - --typed genera graph-enriched.json con predicates semanticos de entity + code relations

""",
    )

    parser.add_argument(
        "--typed",
        action="store_true",
        help="Generate graph-enriched.json with typed predicates (merges wiki-links + entity + code relations)",
    )

    args = parser.parse_args()

    if args.typed:
        result = vault_graph_typed()
    else:
        result = vault_graph()

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_graph"))

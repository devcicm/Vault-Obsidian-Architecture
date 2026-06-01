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

# Configuration
from vault_io import VAULT_ROOT
GRAPH_FILE = VAULT_ROOT / "99_Index" / "graph.json"

# Only scan notes inside these standard sections — never root files or scripts/
VAULT_SECTIONS = {
    "00_System", "01_Projects", "02_Observability", "03_Decisions",
    "04_Sessions", "05_Patterns", "06_Diagrams", "07_Knowledge",
    "08_Runbooks", "09_Infrastructure", "10_Migrated", "11_Code", "99_Index",
}


def _is_vault_note(note_path: Path) -> bool:
    """Return True only for .md files inside a standard vault section."""
    try:
        parts = note_path.relative_to(VAULT_ROOT).parts
    except ValueError:
        return False
    if len(parts) < 2:
        return False  # Root-level file (spec doc, README, index.md at root)
    return parts[0] in VAULT_SECTIONS


def extract_wiki_links(content: str) -> List[str]:
    """Extract wiki-links [[note]] from content."""
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)


def _build_slug_map(all_files: List[Path]) -> Dict[str, str]:
    """
    Build a map from possible wiki-link names to relative paths.
    Handles: bare stem ('identity'), path with subdirs ('01_Projects/overview'),
    and Windows-style paths ('grooming-scheduler/overview\\').
    """
    slug_map: Dict[str, str] = {}
    for p in all_files:
        rel = str(p.relative_to(VAULT_ROOT)).replace("\\", "/")
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
    """Try to resolve a wiki-link slug to a vault-relative path."""
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
        p for p in VAULT_ROOT.rglob("*.md")
        if _is_vault_note(p)
        and not any(part.startswith(".") for part in p.parts)
    ]

    # Build slug→path map for link resolution across the whole vault
    slug_map = _build_slug_map(all_files)

    for note_path in all_files:

        try:
            with open(note_path, "r", encoding="utf-8") as f:
                content = f.read()
        except (UnicodeDecodeError, PermissionError):
            continue

        rel_path = str(note_path.relative_to(VAULT_ROOT)).replace("\\", "/")

        # Parse frontmatter
        frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if frontmatter_match:
            title = re.search(r"^title:\s*(.+)$", frontmatter_match.group(1), re.MULTILINE)
            tags_match = re.search(r"^tags:\s*(.+)$", frontmatter_match.group(1), re.MULTILINE)

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
            resolved = _resolve_link(link, slug_map)
            if resolved:
                edges.append({"from": rel_path, "to": resolved, "type": "wiki-link"})
            else:
                broken_links.append({"from": rel_path, "link": link, "targetPath": link.replace("\\", "/")})

    # Find orphan notes (no incoming links, except 00_System)
    incoming_links = defaultdict(list)
    for edge in edges:
        incoming_links[edge["to"]].append(edge["from"])

    for path, node in nodes.items():
        if path not in incoming_links and not path.startswith("00_System/"):
            orphans.append({"path": path, "title": node["title"], "type": node["type"]})

    # Save graph
    graph_data = {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "totalNodes": len(nodes),
            "totalEdges": len(edges),
            "orphanNotes": len(orphans),
            "brokenLinks": len(broken_links),
        },
        "orphans": orphans,
        "brokenLinks": broken_links,
    }

    GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GRAPH_FILE, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)

    return {
        "ok": True,
        "savedTo": str(GRAPH_FILE.relative_to(VAULT_ROOT)),
        "stats": graph_data["stats"],
        "orphans": orphans[:10],  # Top 10
        "brokenLinks": broken_links[:10],  # Top 10
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Vault Graph Tool -- Generate wiki-links graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_graph.py

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Escanea todos los [[wiki-links]] y genera 99_Index/graph.json
  - Detecta notas huerfanas (sin links entrantes) y links rotos
""",
    )
    parser.parse_args()
    result = vault_graph()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_graph"))

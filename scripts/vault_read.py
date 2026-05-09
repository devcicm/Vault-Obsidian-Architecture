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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configuration
VAULT_ROOT = Path(__file__).parent.parent
HISTORY_DIR = VAULT_ROOT / ".history"


def parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter and return meta dict and body."""
    frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)

    if not frontmatter_match:
        return {}, content

    frontmatter_text = frontmatter_match.group(1)
    body = content[frontmatter_match.end() :].strip()

    meta = {}
    for line in frontmatter_text.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip("\"'")

            # Handle JSON arrays/objects
            if value.startswith("[") or value.startswith("{"):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass

            meta[key] = value

    return meta, body


def extract_wiki_links(content: str) -> List[str]:
    """Extract wiki-links [[note]] from content."""
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)


def get_history_versions(note_path: Path) -> List[str]:
    """Get list of historical versions in .history/"""
    if not HISTORY_DIR.exists():
        return []

    note_name = note_path.stem  # filename without extension
    folder_prefix = str(note_path.parent.relative_to(VAULT_ROOT)).replace("/", "__")

    versions = []
    for history_file in HISTORY_DIR.iterdir():
        if history_file.is_file() and note_name in history_file.stem:
            # Check if this version matches our note
            prefix = f"{folder_prefix}__{note_name}-"
            if history_file.stem.startswith(prefix.replace("-", "_").replace("__", "__")):
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
    note_path = VAULT_ROOT / path

    if not note_path.exists():
        return {"ok": False, "error": f"Note not found: {path}", "path": path}

    with open(note_path, "r", encoding="utf-8") as f:
        content = f.read()

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
    sys.exit(main())

#!/usr/bin/env python3
"""
Vault Diff Tool — Compare note versions

Compares current version vs previous version in .history/.
Returns + (added) and - (removed) lines.

Usage:
    python vault_diff.py --path "01_Projects/ans/overview.md"
    python vault_diff.py --path "01_Projects/ans/overview.md" --version "2"
"""

import argparse
import difflib
import json
import re
import sys
from vault_errors import wrap_main
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configuration
VAULT_ROOT = Path(__file__).parent.parent
HISTORY_DIR = VAULT_ROOT / ".history"


def get_history(note_path: Path) -> List[str]:
    """Get all historical versions sorted newest first."""
    if not HISTORY_DIR.exists():
        return []

    note_name = note_path.stem
    rel_parent = str(note_path.parent.relative_to(VAULT_ROOT))
    folder_prefix = rel_parent.replace("\\", "__").replace("/", "__")
    prefix = f"{folder_prefix}__{note_name}-"

    versions = [
        f.name for f in HISTORY_DIR.iterdir()
        if f.is_file() and f.name.startswith(prefix)
    ]
    versions.sort(reverse=True)
    return versions


def vault_diff(path: str, version: Optional[str] = None) -> Dict[str, Any]:
    """
    Compare current version vs historical version.

    Args:
        path:    Relative path to note
        version: Filename in .history/ to compare against (default: most recent)

    Returns:
        { path, compared_against, added, removed, history }
    """
    note_path = VAULT_ROOT / path

    if not note_path.exists():
        return {"ok": False, "error": f"Note not found: {path}"}

    current_lines = note_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    history = get_history(note_path)

    if not history:
        return {
            "ok": True,
            "path": path,
            "compared_against": None,
            "added": [],
            "removed": [],
            "history": [],
            "message": "No historical versions found",
        }

    # Resolve version: use provided filename or default to most recent
    if version is None:
        target_name = history[0]
    elif version in history:
        target_name = version
    else:
        return {"ok": False, "error": f"Version '{version}' not found in .history/. Available: {history}"}

    history_file = HISTORY_DIR / target_name
    old_lines = history_file.read_text(encoding="utf-8", errors="ignore").splitlines()

    added = []
    removed = []
    for line in difflib.unified_diff(old_lines, current_lines, lineterm=""):
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line)
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line)

    return {
        "ok": True,
        "path": path,
        "compared_against": target_name,
        "added": added,
        "removed": removed,
        "history": history,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Diff Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_diff.py --path "01_Projects/ans/overview.md"
  python vault_diff.py --path "01_Projects/ans/overview.md" --version "2"
  python vault_diff.py --path "07_Knowledge/apis/mcp-tools-index.md"
  python vault_diff.py --path "03_Decisions/adr-001.md"

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Sin --version compara contra la version mas reciente en .history/
  - --version acepta el nombre de archivo en .history/ (e.g., 01_Projects__ans__overview-2026-05-01.md)
""",
    )
    parser.add_argument("--path", required=True, help="Relative path to note")
    parser.add_argument("--version", help="Filename in .history/ to compare against (default: most recent)")

    args = parser.parse_args()
    result = vault_diff(args.path, args.version)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_diff"))

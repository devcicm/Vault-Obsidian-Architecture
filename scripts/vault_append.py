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
from datetime import datetime
from pathlib import Path
from typing import Optional

# Configuration
VAULT_ROOT = Path(__file__).parent.parent


def vault_append(path: str, content: str, section: Optional[str] = None, timestamped: bool = True) -> dict:
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
    note_path = VAULT_ROOT / path

    if not note_path.exists():
        return {"ok": False, "error": f"Note not found: {path}", "path": path}

    with open(note_path, "r", encoding="utf-8") as f:
        existing_content = f.read()

    # Prepare appended content
    append_text = content
    if timestamped:
        timestamp = datetime.now().strftime("**%Y-%m-%d %H:%M**")
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

            existing_content = existing_content[:insert_pos] + append_text + existing_content[insert_pos:]
        else:
            # Section not found, append at end
            existing_content += append_text
    else:
        existing_content += append_text

    # Write back
    with open(note_path, "w", encoding="utf-8") as f:
        f.write(existing_content)

    return {
        "ok": True,
        "path": path,
        "appendedLength": len(append_text),
        "section": section,
        "timestamped": timestamped,
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
    )
    parser.add_argument("--path", required=True, help="Relative path to note")
    parser.add_argument("--content", required=True, help="Content to append")
    parser.add_argument("--section", help="Section heading to append within")
    parser.add_argument("--no-timestamp", action="store_true", help="Don't add timestamp")

    args = parser.parse_args()
    result = vault_append(args.path, args.content, args.section, not args.no_timestamp)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

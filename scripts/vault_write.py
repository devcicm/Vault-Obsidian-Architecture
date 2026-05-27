#!/usr/bin/env python3
"""
Vault Write Tool — Core writing tool for Obsidian vault

Creates or updates any note with correct YAML frontmatter.
Implements versioning: copies previous version to .history/ before overwriting.
Updates search-index.json automatically.

Usage:
    python vault_write.py --folder "01_Projects/ans" --title "Status" --content "# Status\n\n..."
    python vault_write.py --folder "03_Decisions" --title "ADR-001" --tags "architecture,backend" --meta '{"status": "accepted"}'
"""

import argparse
import json
import os
import re
import shutil
import sys
from vault_errors import wrap_main
from vault_io import atomic_write_text, atomic_write_json, assert_within_vault
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    """Return current UTC time as ISO 8601 with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _check_content_gate(content: str, folder: str) -> bool:
    """Return True if content passes the 3-real-lines gate. 00_System is exempt."""
    if folder.startswith("00_System"):
        return True
    real_lines = [
        l for l in content.split("\n")
        if l.strip()
        and not l.strip().startswith("TODO")
        and l.strip() not in ("-", "- ", "---")
        and not re.match(r"^#+\s*$", l.strip())
    ]
    return len(real_lines) >= 3

# Configuration
VAULT_ROOT = Path(__file__).parent.parent
HISTORY_DIR = VAULT_ROOT / ".history"
INDEX_FILE = VAULT_ROOT / "99_Index" / "search-index.json"
TAG_REGISTRY = VAULT_ROOT / "00_System" / "tag-registry.json"


def _tag_suggestions(new_tags: List[str]) -> List[Dict[str, Any]]:
    """Return canonical similar tags for any new_tags not yet in registry. Non-blocking."""
    if not TAG_REGISTRY.exists():
        return []
    try:
        registry = json.loads(TAG_REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return []
    canonical: set = set(registry.get("tags", {}).keys())
    suggestions = []
    for tag in new_tags:
        if tag in canonical:
            continue
        for candidate in canonical:
            # simple similarity: exact prefix/substring
            a, b = tag.lower(), candidate.lower()
            if a == b:
                continue
            if a in b or b in a:
                score = 0.85
            else:
                common_prefix = sum(1 for x, y in zip(a, b) if x == y)
                if common_prefix >= 3:
                    score = 0.6 + (common_prefix / max(len(a), len(b))) * 0.2
                else:
                    score = sum(1 for x, y in zip(a, b) if x == y) / max(len(a), len(b))
            if score >= 0.6:
                suggestions.append({
                    "new_tag": tag,
                    "similar_canonical": candidate,
                    "score": round(score, 2),
                    "count": registry["tags"].get(candidate, {}).get("count", 0),
                })
    return sorted(suggestions, key=lambda x: -x["score"])[:10]


def slugify(title: str) -> str:
    """Convert title to kebab-case filename."""
    slug = title.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


def generate_frontmatter(
    title: str,
    tags: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
    existing_id: Optional[str] = None,
    existing_created: Optional[str] = None,
) -> str:
    """Generate YAML frontmatter with v27-compliant metadata (CIA + agent fields)."""
    meta = meta or {}
    frontmatter = ["---"]
    frontmatter.append(f"title: {title}")
    frontmatter.append(f"id: {existing_id or str(uuid.uuid4())}")
    frontmatter.append(f"createdAt: {existing_created or _utcnow()}")
    frontmatter.append(f"updatedAt: {_utcnow()}")

    if tags:
        frontmatter.append(f"tags: {json.dumps(tags)}")

    # v27 CIA schema — defaults overridable via meta
    frontmatter.append(f"cia_integrity: {meta.pop('cia_integrity', 'medium')}")
    frontmatter.append(f"cia_availability: {meta.pop('cia_availability', 'medium')}")
    frontmatter.append(f"cia_sensitivity: {meta.pop('cia_sensitivity', 'internal')}")
    frontmatter.append(f"agent: {meta.pop('agent', 'system')}")

    for key, value in meta.items():
        if isinstance(value, str):
            frontmatter.append(f"{key}: {value}")
        else:
            frontmatter.append(f"{key}: {json.dumps(value)}")

    frontmatter.append("---")
    return "\n".join(frontmatter)


def extract_wiki_links(content: str) -> List[str]:
    """Extract wiki-links [[note]] from content."""
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)


def update_search_index(vault_path: str, title: str, content: str, tags: List[str], is_new: bool = True) -> None:
    """Update search index with new or updated note."""
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        if not isinstance(index, dict):
            index = {"notes": []}
    except (FileNotFoundError, json.JSONDecodeError):
        index = {"notes": []}

    # Generate preview (first 200 chars of content without frontmatter)
    body = content.split("---", 2)[-1] if content.startswith("---") else content
    preview = body.strip()[:200].replace("\n", " ")

    note_entry = {
        "path": vault_path,
        "title": title,
        "preview": preview,
        "tags": tags,
        "updatedAt": _utcnow(),
    }

    if is_new:
        index["notes"].append(note_entry)
    else:
        for i, note in enumerate(index["notes"]):
            if note["path"] == vault_path:
                index["notes"][i] = note_entry
                break
        else:
            index["notes"].append(note_entry)

    atomic_write_json(INDEX_FILE, index)


def vault_write(
    folder: str, title: str, content: str, tags: Optional[List[str]] = None, meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create or update a note in the vault.

    Args:
        folder: Relative path to vault root (e.g., "01_Projects/ans")
        title: Note title - also determines filename via slugify
        content: Complete Markdown content
        tags: Tags for search and indexing
        meta: Additional frontmatter fields

    Returns:
        Dict with path, id, and operation details
    """
    tags = tags or []
    meta = meta or {}

    # Content gate: new notes must have ≥3 real lines (00_System exempt)
    if not _check_content_gate(content, folder):
        return {
            "ok": False,
            "error_code": "content_too_short",
            "error": "content_too_short",
            "message": "Minimum 3 real lines of content required. If content is not ready, do not create the note.",
        }

    # AP-20 guard: deceptive skeleton — reject if >50% of bullets are empty
    bullets = re.findall(r"^\s*[-*]\s*(.*)", content, re.MULTILINE)
    if bullets:
        empty_bullets = [b for b in bullets if not b.strip() or b.strip() in ("[]", "[[]]", "-", "[ ]")]
        if len(empty_bullets) / len(bullets) > 0.5:
            return {
                "ok": False,
                "error_code": "content_empty_list",
                "error": "content_empty_list",
                "message": f"AP-20: >{int(len(empty_bullets)/len(bullets)*100)}% of bullets are empty. Fill content before saving.",
            }

    # AP-21 guard: path-anchored wiki-links — reject [[folder/note]] patterns
    path_links = re.findall(r"\[\[[^\]]*\/[^\]]*\]\]", content)
    if path_links:
        return {
            "ok": False,
            "error_code": "path_anchored_wikilinks",
            "error": "path_anchored_wikilinks",
            "message": f"AP-21: path-anchored wiki-links detected: {path_links}. Use [[note-name]] without folder path.",
        }

    # Determine filename and validate path stays inside vault
    filename = f"{slugify(title)}.md"
    vault_path = VAULT_ROOT / folder / filename
    try:
        assert_within_vault(vault_path, VAULT_ROOT)
    except ValueError as exc:
        return {
            "ok": False,
            "error_code": "INVALID_PATH",
            "error": "INVALID_PATH",
            "message": str(exc),
        }
    existing_id = None
    existing_created = None

    # If note exists, backup to history
    if vault_path.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        history_filename = f"{folder.replace('/', '__')}__{slugify(title)}-{timestamp}.md"
        history_path = HISTORY_DIR / history_filename
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)

        existing_content = vault_path.read_text(encoding="utf-8")
        atomic_write_text(history_path, existing_content)

        # Extract existing frontmatter data
        frontmatter_match = re.match(r"^---\n(.*?)\n---", existing_content, re.DOTALL)
        if frontmatter_match:
            for line in frontmatter_match.group(1).split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    value = value.strip().strip("\"'")
                    if key == "id":
                        existing_id = value
                    elif key == "createdAt":
                        existing_created = value

    # Create folder if not exists
    vault_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate frontmatter and write file
    frontmatter = generate_frontmatter(title, tags, meta, existing_id, existing_created)

    final_content = f"{frontmatter}\n\n{content}"

    atomic_write_text(vault_path, final_content)

    # Update search index
    update_search_index(str(vault_path.relative_to(VAULT_ROOT)), title, content, tags, is_new=(existing_id is None))

    # Extract wiki-links for graph
    wiki_links = extract_wiki_links(content)

    # Auto-regenerate section index (derived artifact — never blocks write)
    try:
        import subprocess
        _section_index_script = Path(__file__).parent / "vault_section_index.py"
        if _section_index_script.exists():
            subprocess.run(
                [sys.executable, str(_section_index_script), "--folder", folder.split("/")[0]],
                capture_output=True, timeout=10
            )
    except Exception:
        pass  # section index failure never blocks the write

    tag_suggestions = _tag_suggestions(tags)

    result: Dict[str, Any] = {
        "ok": True,
        "path": str(vault_path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "id": existing_id or str(uuid.uuid4()),
        "filename": filename,
        "tags": tags,
        "wikiLinks": wiki_links,
        "created": existing_id is None,
        "message": f"Note {'created' if existing_id is None else 'updated'} successfully",
    }
    if tag_suggestions:
        result["tag_suggestions"] = tag_suggestions
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Vault Write Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_write.py --folder "01_Projects/mi-api" --title "Status" --content "# Status\\n\\nActivo"
  python vault_write.py --folder "03_Decisions" --title "ADR-001" --tags arch backend --meta '{"status":"accepted"}'
  python vault_write.py --folder "03_Decisions" --title "ADR-001" --content "..." --meta-file meta.json
  python vault_write.py --folder "07_Knowledge/concepts" --scan-path "docs/concepts/"

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Con --scan-path, --title y --content son opcionales
  - Solo se procesan archivos .md en --scan-path
""",
    )
    parser.add_argument("--folder", required=True, help="Folder path relative to vault root")
    parser.add_argument("--title", help="Note title (optional when --scan-path is used)")
    parser.add_argument("--content", help="Markdown content (use @file:path to read from file; optional when --scan-path is used)")
    parser.add_argument("--tags", nargs="*", help="Tags for search")
    parser.add_argument("--meta", type=json.loads, help="Additional frontmatter as JSON")
    parser.add_argument("--meta-file", help="Path to JSON file with additional frontmatter (avoids shell quoting issues)")
    parser.add_argument("--scan-path", help="Directory to scan for .md files and write each one to --folder")

    args = parser.parse_args()

    # --scan-path mode: scan directory for .md files
    if args.scan_path:
        scan_dir = Path(args.scan_path)
        if not scan_dir.exists():
            print(json.dumps({"ok": False, "error": f"scan-path not found: {args.scan_path}"}))
            return 1

        md_files = list(scan_dir.rglob("*.md"))
        written = []
        skipped = []

        meta = args.meta
        if args.meta_file:
            with open(args.meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

        for md_file in md_files:
            try:
                file_content = md_file.read_text(encoding="utf-8")
            except Exception as e:
                skipped.append({"file": str(md_file), "reason": str(e)})
                continue

            # Extract title from first # Heading or use filename
            heading_match = re.search(r"^#\s+(.+)$", file_content, re.MULTILINE)
            title = heading_match.group(1).strip() if heading_match else md_file.stem.replace("-", " ").replace("_", " ").title()

            # Check if note already exists
            filename = f"{slugify(title)}.md"
            vault_path = VAULT_ROOT / args.folder / filename
            if vault_path.exists():
                skipped.append({"file": str(md_file), "reason": "already exists in vault"})
                continue

            result = vault_write(args.folder, title, file_content, args.tags, meta)
            if result["ok"]:
                written.append(result["path"])
            else:
                skipped.append({"file": str(md_file), "reason": result.get("error", "unknown")})

        scan_result = {
            "ok": True,
            "scanned": len(md_files),
            "written": written,
            "skipped": skipped,
        }
        print(json.dumps(scan_result, indent=2, ensure_ascii=False))
        return 0

    # Standard single-note mode
    if not args.title:
        parser.error("--title is required when --scan-path is not used")
    if not args.content:
        parser.error("--content is required when --scan-path is not used")

    # Read content from file if @file:path
    if args.content.startswith("@file:"):
        file_path = Path(args.content[6:])
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = args.content

    meta = args.meta
    if args.meta_file:
        with open(args.meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

    result = vault_write(args.folder, args.title, content, args.tags, meta)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_write"))

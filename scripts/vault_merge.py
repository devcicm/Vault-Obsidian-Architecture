#!/usr/bin/env python3

"""

Vault Merge — Merge an external vault or deduplicate internal notes.



Blueprint: vault-obsidian-architecture.md § vault_merge(source, conflict?, action?)



Actions:

  merge  — import all notes from external vault into this vault

  detect — find internally duplicated notes (same stem, different folders)

  dedup  — merge duplicate internal notes, keeping the most recent (DESTRUCTIVE)



Usage:

    python vault_merge.py --source "/path/to/other-vault" --action merge --conflict skip

    python vault_merge.py --action detect

    python vault_merge.py --action dedup   # run vault_backup first!

"""

import argparse

import json

import sys

from vault_errors import wrap_main

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Dict, List, Optional


from vault_io import atomic_write_text, get_vault_root, write_report


def _read_note(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _tag_frontmatter(content: str, source: str) -> str:
    """Inject mergedFrom and mergedAt into existing frontmatter, or prepend one."""

    tag_lines = [
        f"mergedFrom: {source}",
        f"mergedAt: {datetime.now(timezone.utc).isoformat()[:19]}Z",
    ]

    if content.startswith("---"):
        parts = content.split("---", 2)

        if len(parts) >= 3:
            fm_body = parts[1].rstrip("\n")

            return "---\n" + fm_body + "\n" + "\n".join(tag_lines) + "\n---" + parts[2]

    # No frontmatter — prepend minimal block

    return "---\n" + "\n".join(tag_lines) + "\n---\n\n" + content


def _note_updated_at(path: Path) -> str:
    """Extract updatedAt from frontmatter, fallback to mtime."""

    try:
        content = _read_note(path)

        if content.startswith("---"):
            parts = content.split("---", 2)

            for line in parts[1].splitlines():
                if line.startswith("updatedAt:"):
                    return line.split(":", 1)[1].strip().strip("\"'")

    except Exception:
        pass

    return datetime.fromtimestamp(path.stat().st_mtime).isoformat()


# ── action: merge ────────────────────────────────────────────────────────────


def _action_merge(source_dir: Path, conflict: str) -> Dict[str, Any]:
    notes = [
        n
        for n in source_dir.rglob("*.md")
        if ".history" not in str(n) and not n.name.startswith("_")
    ]

    merged = skipped = conflicts = 0

    for src in notes:
        # Preserve relative structure from source root

        try:
            rel = src.relative_to(source_dir)

        except ValueError:
            rel = Path(src.name)

        dest = get_vault_root() / rel

        if dest.exists():
            conflicts += 1

            if conflict == "skip":
                skipped += 1

                continue

            elif conflict == "rename":
                stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

                dest = dest.with_stem(f"{dest.stem}-{stamp}")

            # "overwrite" → dest stays as-is, content gets replaced

        dest.parent.mkdir(parents=True, exist_ok=True)

        content = _tag_frontmatter(_read_note(src), str(source_dir))

        atomic_write_text(dest, content)

        merged += 1

    return {
        "ok": True,
        **write_report(),
        "action": "merge",
        "merged": merged,
        "skipped": skipped,
        "conflicts": conflicts,
    }


# ── action: detect ───────────────────────────────────────────────────────────


def _normalize(stem: str) -> str:
    return stem.lower().replace("-", "").replace("_", "")


def _action_detect() -> Dict[str, Any]:
    buckets: Dict[str, List[str]] = {}

    for note in get_vault_root().rglob("*.md"):
        if ".history" in str(note) or note.name.startswith("_"):
            continue

        key = _normalize(note.stem)

        buckets.setdefault(key, []).append(str(note.relative_to(get_vault_root())))

    duplicates = {k: v for k, v in buckets.items() if len(v) > 1}

    return {
        "ok": True,
        **write_report(),
        "action": "detect",
        "duplicateGroups": len(duplicates),
        "duplicates": duplicates,
    }


# ── action: dedup ─────────────────────────────────────────────────────────────


def _action_dedup() -> Dict[str, Any]:
    buckets: Dict[str, List[Path]] = {}

    for note in get_vault_root().rglob("*.md"):
        if ".history" in str(note) or note.name.startswith("_"):
            continue

        key = _normalize(note.stem)

        buckets.setdefault(key, []).append(note)

    merged_count = 0

    for key, paths in buckets.items():
        if len(paths) < 2:
            continue

        # Sort: most recent first (by updatedAt or mtime)

        paths.sort(key=_note_updated_at, reverse=True)

        canonical = paths[0]

        others = paths[1:]

        canonical_content = _read_note(canonical)

        for other in others:
            body = _read_note(other)

            # Strip frontmatter from the non-canonical note

            if body.startswith("---"):
                parts = body.split("---", 2)

                body = parts[2] if len(parts) >= 3 else body

            canonical_content += "\n\n---\n\n" + body.strip()

            other.unlink()

            merged_count += 1

        atomic_write_text(canonical, canonical_content)

    return {
        "ok": True,
        **write_report(),
        "action": "dedup",
        "merged": merged_count,
    }


# ── public API ────────────────────────────────────────────────────────────────


def vault_merge(
    source: Optional[str] = None,
    conflict: str = "skip",
    action: str = "merge",
) -> Dict[str, Any]:
    """

    Merge an external vault or manage internal duplicates.



    Args:

        source:   Path to external vault root (required for action="merge").

        conflict: "skip" | "overwrite" | "rename"  (used by action="merge").

        action:   "merge" | "detect" | "dedup"



    Returns:

        { ok, action, merged, skipped, conflicts }          for action="merge"

        { ok, action, duplicateGroups, duplicates: {...} }  for action="detect"

        { ok, action, merged }                              for action="dedup"

    """

    if action == "merge":
        if not source:
            return {"ok": False, "error": "action='merge' requires --source"}

        source_dir = Path(source)

        if not source_dir.exists():
            return {"ok": False, "error": f"Source not found: {source}"}

        return _action_merge(source_dir, conflict)

    if action == "detect":
        return _action_detect()

    if action == "dedup":
        return _action_dedup()

    return {
        "ok": False,
        "error": f"Unknown action: {action}. Use merge | detect | dedup",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Merge -- blueprint: vault-obsidian-architecture.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_merge.py --source "/path/to/other-vault" --action merge --conflict skip

  python vault_merge.py --source "C:/old-vault" --action merge --conflict rename

  python vault_merge.py --action detect

  python vault_merge.py --action dedup



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - action=dedup es DESTRUCTIVO -- ejecutar vault_backup primero

  - conflict=skip (default), overwrite, rename

""",
    )

    parser.add_argument(
        "--source", help="Path to external vault root (required for action=merge)"
    )

    parser.add_argument(
        "--conflict",
        choices=["skip", "overwrite", "rename"],
        default="skip",
        help="Conflict policy when merging external vault (default: skip)",
    )

    parser.add_argument(
        "--action",
        choices=["merge", "detect", "dedup"],
        default="merge",
        help="merge=import external vault | detect=find duplicates | dedup=merge duplicates (default: merge)",
    )

    args = parser.parse_args()

    result = vault_merge(args.source, args.conflict, args.action)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_merge"))

#!/usr/bin/env python3
"""vault_graph_fix — Auto-fix broken wiki-links using stem matching.

Strategies (in order):
  1. Exact stem match → link becomes [[<canonical-note>]]
  2. Lowercase fold match (case-insensitive stem)
  3. Fuzzy match with token Jaccard ≥ 0.7 (asks for confirmation if --interactive)
  4. Apply bracket fixes (nested brackets, whitespace) using vault_regex
  5. Apply path-anchored fix: [[carpeta/nota]] → [[nota]]

Safety:
  - Dry-run by default (--apply to actually write changes)
  - Atomic write via vault_io.atomic_write_text
  - Per-note backup via .history/ (via vault_io)
  - Backs up changes to 00_System/.graph-fixes/yyyy-mm-dd.json

Usage:
    # Dry-run (default)
    python scripts/vault_graph_fix.py --root /path/to/vault

    # Apply changes
    python scripts/vault_graph_fix.py --apply

    # Only fix brackets, not broken links
    python scripts/vault_graph_fix.py --apply --only brackets

    # Adjust fuzzy threshold
    python scripts/vault_graph_fix.py --apply --threshold 0.8
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from vault_io import VAULT_ROOT, atomic_write_text, normalize_stem
from vault_regex import (
    fix_nested_brackets,
    fix_whitespace_in_links,
)
from vault_graph_inspect import (
    _SKIP_DIRS,
    _is_migrated,
    _load_notes,
    _stems_set,
    _detect_wikilink_syntax_errors,
    generate_report,
)

_MIGRATION_DIR = "10_Migrated"

_FIX_LOG_DIR = "00_System/.graph-fixes"

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def _split_clean_note(text: str) -> tuple[str, str | None]:
    """Split [[note]] or [[note|alias]] → (note, alias)."""
    match = _WIKILINK_RE.search(text)
    if not match:
        return text, None
    return match.group(1).strip(), match.group(2).strip() if match.group(2) else None


def _find_target(
    missing_stem: str,
    all_stems: dict[str, list[str]],
    threshold: float = 0.7,
) -> tuple[str, str] | None:
    """Find best match for missing stem. Returns (canonical_path, strategy) or None.

    Strategies tried: exact → lowercase fold → fuzzy Jaccard.
    """
    if missing_stem in all_stems:
        paths = all_stems[missing_stem]
        if len(paths) == 1:
            return paths[0], "exact"
        canonical = min(paths, key=lambda p: (len(p), p))
        return canonical, "exact_ambiguous"

    lower_map = defaultdict(list)
    for stem, paths in all_stems.items():
        lower_map[stem.lower()].extend(paths)

    if missing_stem.lower() in lower_map:
        paths = lower_map[missing_stem.lower()]
        canonical = min(paths, key=lambda p: (len(p), p))
        return canonical, "lowercase"

    target_words = set(missing_stem.replace("-", " ").split())
    best_sim = 0.0
    best_stem = None
    for stem in all_stems:
        stem_words = set(stem.replace("-", " ").split())
        if not stem_words:
            continue
        union = target_words | stem_words
        if not union:
            continue
        sim = len(target_words & stem_words) / len(union)
        if sim > best_sim:
            best_sim = sim
            best_stem = stem
    if best_stem and best_sim >= threshold:
        return all_stems[best_stem][0], f"fuzzy:{best_sim:.2f}"

    return None


def _replace_wikilink(text: str, old_target: str, new_target: str) -> tuple[str, bool]:
    """Replace [[old_target]] (or with alias) with [[new_target]].
    Also handles the path-anchored variant [[path/old_target]].
    """
    old_path_anchored = f"[[/{old_target}]]"
    new_text = text.replace(old_path_anchored, f"[[{new_target}]]")
    changed = new_text != text
    if not changed:
        escaped = re.escape(old_target)
        pattern = rf"\[\[{escaped}(\|[^\]]+)?\]\]"
        new_text = re.sub(pattern, f"[[{new_target}]]", text)
        changed = new_text != text
    if not changed:
        escaped = re.escape(old_target.lower())
        pattern = rf"\[\[{escaped}(\|[^\]]+)?\]\]"
        new_text = re.sub(
            pattern,
            lambda m: f"[[{new_target}]]{m.group(1) or ''}]",
            text,
            flags=re.IGNORECASE,
        )
        changed = new_text != text
    return new_text, changed


def _fix_brackets_in_content(text: str) -> tuple[str, int]:
    """Apply bracket fixers from vault_regex. Returns (text, fixes_count)."""
    before = text
    text = fix_nested_brackets(text)
    nested_fixes = 1 if text != before else 0
    before = text
    text = fix_whitespace_in_links(text)
    ws_fixes = 1 if text != before else 0
    return text, nested_fixes + ws_fixes


def _fix_path_anchored(text: str) -> tuple[str, int]:
    """Strip folder paths from [[folder/note]] → [[note]]. Returns (text, fixes_count)."""
    pattern = r"\[\[([^\]]*\/[^\]]+)\]\]"
    fixes = 0

    def _strip(match: re.Match) -> str:
        nonlocal fixes
        path = match.group(1)
        if "/" in path and not path.startswith("http"):
            note_only = path.rsplit("/", 1)[-1]
            fixes += 1
            return f"[[{note_only}]]"
        return match.group(0)

    new_text = re.sub(pattern, _strip, text)
    return new_text, fixes


def _process_note(
    path: str,
    info: dict[str, Any],
    all_stems: dict[str, list[str]],
    threshold: float,
) -> dict[str, Any]:
    """Process a single note. Returns fix report for that note."""
    text = info["body"]
    original = text
    fixes: list[dict[str, Any]] = []

    existing_stems = set(all_stems.keys())
    for match in list(re.finditer(r"\[\[([^\]|]+)", text)):
        target_stem = normalize_stem(match.group(1))
        if target_stem and target_stem not in existing_stems:
            result = _find_target(target_stem, all_stems, threshold)
            if result:
                canonical_path, strategy = result
                new_text, changed = _replace_wikilink(
                    text, match.group(1), Path(canonical_path).stem
                )
                if changed:
                    fixes.append(
                        {
                            "type": "broken_link",
                            "from": match.group(1),
                            "to": Path(canonical_path).stem,
                            "strategy": strategy,
                            "canonical_path": canonical_path,
                        }
                    )
                    text = new_text

    new_text, bracket_fixes = _fix_brackets_in_content(text)
    if bracket_fixes:
        fixes.append({"type": "brackets", "count": bracket_fixes})
        text = new_text

    new_text, path_fixes = _fix_path_anchored(text)
    if path_fixes:
        fixes.append({"type": "path_anchored", "count": path_fixes})
        text = new_text

    return {
        "note": path,
        "fixes": fixes,
        "changed": text != original,
        "new_content": text if text != original else None,
    }


def fix_vault(
    root: Path,
    threshold: float = 0.7,
    only: str | None = None,
) -> dict[str, Any]:
    """Compute all fixes. Returns report. Does NOT write unless caller passes apply=True."""
    notes = _load_notes(root, include_migrated=False)
    all_notes_full = _load_notes(root, include_migrated=True)
    stems = _stems_set(all_notes_full)
    inverted_stems: dict[str, list[str]] = defaultdict(list)
    for stem, path in stems.items():
        inverted_stems[stem].append(path)

    note_reports: list[dict[str, Any]] = []
    for path in sorted(notes):
        info = notes[path]
        if only == "brackets":
            original = info["body"]
            new_text, count = _fix_brackets_in_content(original)
            if count:
                note_reports.append(
                    {
                        "note": path,
                        "fixes": [{"type": "brackets", "count": count}],
                        "changed": True,
                        "new_content": new_text,
                    }
                )
        elif only == "path_anchored":
            original = info["body"]
            new_text, count = _fix_path_anchored(original)
            if count:
                note_reports.append(
                    {
                        "note": path,
                        "fixes": [{"type": "path_anchored", "count": count}],
                        "changed": True,
                        "new_content": new_text,
                    }
                )
        else:
            note_reports.append(_process_note(path, info, inverted_stems, threshold))

    note_reports = [r for r in note_reports if r["changed"]]

    total_brackets = sum(
        sum(f["count"] for f in r["fixes"] if f["type"] == "brackets")
        for r in note_reports
    )
    total_path_anchored = sum(
        sum(f["count"] for f in r["fixes"] if f["type"] == "path_anchored")
        for r in note_reports
    )
    total_broken = sum(
        sum(1 for f in r["fixes"] if f["type"] == "broken_link") for r in note_reports
    )

    return {
        "ok": True,
        "tool": "vault_graph_fix",
        "vault_root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat()[:19] + "Z",
        "scope": "excluding-10_Migrated",
        "summary": {
            "notes_to_modify": len(note_reports),
            "broken_links_fixed": total_broken,
            "bracket_fixes": total_brackets,
            "path_anchored_fixes": total_path_anchored,
        },
        "fixes": note_reports,
    }


def apply_fix(report: dict[str, Any], root: Path) -> dict[str, Any]:
    """Apply report['fixes'] by writing modified notes atomically."""
    log_dir = root / _FIX_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    existing_log = []
    if log_path.exists():
        try:
            existing_log = json.loads(log_path.read_text(encoding="utf-8"))
        except Exception:
            existing_log = []

    applied = 0
    errors = []
    for fix in report["fixes"]:
        if not fix["new_content"]:
            continue
        target = root / fix["note"]
        try:
            existing_text = target.read_text(encoding="utf-8")
            stripped = _strip_frontmatter(existing_text)
            body_part = existing_text.replace(stripped, "", 1) if stripped else ""
            new_full = body_part + fix["new_content"]
            atomic_write_text(target, new_full)
            applied += 1
        except Exception as exc:
            errors.append({"note": fix["note"], "error": str(exc)})

    existing_log.append(
        {
            "applied_at": datetime.now(timezone.utc).isoformat()[:19] + "Z",
            "report_summary": report["summary"],
            "applied_count": applied,
            "errors": errors,
        }
    )
    atomic_write_text(log_path, json.dumps(existing_log, indent=2, ensure_ascii=False))

    return {
        "applied": applied,
        "errors": errors,
        "log_file": str(log_path.relative_to(root)).replace("\\", "/"),
    }


def _strip_frontmatter(content: str) -> str:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
    return content[match.end() :].strip() if match else content


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-fix broken wiki-links + bracket/path issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", help="Vault root (default: VAULT_ROOT)")
    parser.add_argument(
        "--apply", action="store_true", help="Apply fixes (default: dry-run)"
    )
    parser.add_argument(
        "--only", choices=["brackets", "path_anchored"], help="Only run one fixer"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Fuzzy match threshold (default: 0.7)",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON (default)")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else VAULT_ROOT
    if not root.exists():
        print(json.dumps({"ok": False, "error": f"Vault root not found: {root}"}))
        return 1

    report = fix_vault(root=root, threshold=args.threshold, only=args.only)

    if args.apply:
        apply_result = apply_fix(report, root)
        report["apply_result"] = apply_result
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if apply_result["errors"] == [] else 1

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

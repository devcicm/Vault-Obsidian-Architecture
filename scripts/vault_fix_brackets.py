#!/usr/bin/env python3
"""
vault_fix_brackets.py — AP-22 / AP-24 auto-fix for malformed wiki-link brackets.

Detects and SAFELY fixes brackets problems found by vault_audit:
  AP-22 (auto-fixable):
    - [[]]            → empty wiki-link (no info)
    - [[ ]]           → empty with whitespace

  AP-24 (auto-fixable subset):
    - [[[[            → nested double-open (collapse to [[)
    - ]]]]            → nested double-close (collapse to ]])

  AP-24 (NOT auto-fixed, reported only):
    - opens != closes (stray single brackets)
    - ]] … [[         → inverted order
    - Other unclassified bracket pathologies

Usage:
    # Dry-run: detect and report what would be fixed (default)
    python vault_fix_brackets.py

    # Apply fixes to ALL notes with bracket problems
    python vault_fix_brackets.py --apply

    # Only audit a specific note
    python vault_fix_brackets.py --path "02_Observability/errors/foo.md"

    # Filter by kind (empty, nested_open, nested_close)
    python vault_fix_brackets.py --only empty
    python vault_fix_brackets.py --only nested --apply

Output:
    JSON with ok, vault_root, scanned, problems (list of findings),
    fixes_applied (when --apply), files_modified (when --apply), backup_dir.

Behavior:
    - All writes are atomic via vault_io.atomic_write_text
    - Backups go to VAULT_ROOT/.vault-fix-backup-YYYYMMDD-HHMMSS/
      (gitignored via data/vault/scripts.bak-*/ pattern + .bak suffix)
    - NEVER modifies files outside VAULT_ROOT
    - NEVER modifies the spec markdown (vault-obsidian-architecture.md)
    - NEVER modifies anything under scripts/ (tools contain regex examples)
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import wrap_main
from vault_io import VAULT_ROOT, atomic_write_text, assert_within_vault
from vault_lib import utcnow, strip_code_blocks
from vault_regex import (
    RE_EMPTY_LINK,
    RE_NESTED_OPEN_3,
    RE_NESTED_CLOSE_3,
    fix_nested_brackets,
    fix_whitespace_in_links,
    detect_bracket_anomalies,
)


# ---- Detection patterns (using vault_regex for consistency) ----
RE_EMPTY = RE_EMPTY_LINK
RE_NESTED_OPEN = RE_NESTED_OPEN_3  # 3+ opens - more sensitive
RE_NESTED_CLOSE = RE_NESTED_CLOSE_3  # 3+ closes - more sensitive
RE_NESTED_OPEN_4 = re.compile(r"\[\[\[\[")  # keep legacy for compatibility
RE_NESTED_CLOSE_4 = re.compile(r"\]\]\]\]")  # keep legacy for compatibility

# Excluded paths — same as vault_audit
EXCLUDE_NAMES = {"vault-obsidian-architecture.md"}
EXCLUDE_PATH_SUBSTRINGS = ("/scripts/", "scripts/", ".bak", ".vault-fix-backup-")


def _is_excluded(rel: str, name: str) -> bool:
    if name in EXCLUDE_NAMES:
        return True
    return any(sub in rel for sub in EXCLUDE_PATH_SUBSTRINGS)


def _in_sandbox(rel: str) -> bool:
    """Check if a relative path lives under vault-sandbox/ (test fixture area)."""
    return rel.startswith("vault-sandbox/") or "/vault-sandbox/" in rel


def _is_in_test_sandbox() -> bool:
    """If VAULT_ROOT is itself the sandbox, allow scanning it."""
    return VAULT_ROOT.name == "vault-sandbox"


def _analyze_note(content: str) -> Dict[str, Any]:
    """Return bracket analysis for one note. Mirrors vault_audit._detect_malformed_wikilinks.

    Uses stack-based local tracking so we catch [[b missing where the GLOBAL
    balance is 0 (because some OTHER [[b]] closed earlier) but a LOCAL
    bracket was opened without ever closing.
    """
    clean = strip_code_blocks(content)
    empty_matches = list(RE_EMPTY.finditer(clean))
    nested_open_matches = list(RE_NESTED_OPEN_4.finditer(clean))
    nested_close_matches = list(RE_NESTED_CLOSE_4.finditer(clean))
    opens = len(re.findall(r"\[\[", clean))
    closes = len(re.findall(r"\]\]", clean))

    # Stack-based detection: walk the cleaned text, track bracket depth.
    # A stray `]]` with depth==0 → imbalance_close.
    # A `[[` that never closes (we hit EOF with depth>0) → imbalance_open.
    #
    # To avoid confusing nested_close with stray closes, we first apply the
    # nested fixes to a virtual copy of the text, then walk the stack on the
    # patched version. This way `]]]]` collapses to `]]` BEFORE stack-walk,
    # so the second pair doesn't get miscounted as a stray close.
    # (Same for `[[[[` → `[[`.)
    virtual = clean
    if nested_open_matches:
        virtual = re.sub(r"\[\[\[\[+", "[[", virtual)
    if nested_close_matches:
        virtual = re.sub(r"\]\]\]\]+", "]]", virtual)
    # Also collapse `]]] ` (triple close followed by non-bracket) — this is
    # a less-common but still pathological pattern (3 closes where 2 expected).
    virtual = re.sub(r"\]\]\](?!\])", "]]", virtual)

    stack_depth = 0
    max_depth = 0
    stray_closes = 0
    inverted_examples: List[str] = []

    i = 0
    while i < len(virtual):
        if virtual[i : i + 2] == "[[":
            stack_depth += 1
            max_depth = max(max_depth, stack_depth)
            i += 2
        elif virtual[i : i + 2] == "]]":
            if stack_depth == 0:
                stray_closes += 1
                start = max(0, i - 10)
                end = min(len(virtual), i + 12)
                inverted_examples.append(virtual[start:end].replace("\n", " "))
                i += 2
            else:
                stack_depth -= 1
                i += 2
        else:
            i += 1

    leftover_opens = stack_depth  # opens that never closed by EOF

    problems: List[Dict[str, Any]] = []

    if empty_matches:
        problems.append(
            {
                "kind": "empty",
                "norm_code": "AP-22",
                "count": len(empty_matches),
                "examples": [m.group(0) for m in empty_matches[:3]],
                "auto_fixable": True,
            }
        )

    if nested_open_matches:
        problems.append(
            {
                "kind": "nested_open",
                "norm_code": "AP-24",
                "count": len(nested_open_matches),
                "examples": [m.group(0) for m in nested_open_matches[:3]],
                "auto_fixable": True,
            }
        )

    if nested_close_matches:
        problems.append(
            {
                "kind": "nested_close",
                "norm_code": "AP-24",
                "count": len(nested_close_matches),
                "examples": [m.group(0) for m in nested_close_matches[:3]],
                "auto_fixable": True,
            }
        )

    # Local imbalance detection — fires when stack-based scan finds stranded
    # brackets even if global balance is 0.
    #
    # BUT: if the only imbalance sources are `[[[[` and `]]]]` that get
    # collapsed by the nested fixes, the post-fix balance becomes 0 and
    # the note becomes clean. In that case, mark the imbalance as
    # "resolvable" so apply mode can proceed safely.
    # Resolvable = (leftover_opens + stray_closes) is fully accounted for
    # by the nested counts that auto-fix will collapse.
    resolvable = (
        leftover_opens
        <= len(nested_open_matches) * 2  # each [[[[ has 2 stray opens after collapse
        and stray_closes
        <= len(nested_close_matches) * 2  # each ]]]] has 2 stray closes after collapse
    )
    # IMPORTANT: stray_closes and leftover_opens are computed on the VIRTUAL
    # post-fix text. So a value of 0 means the nested collapse fully resolved
    # the imbalance. If there are still stray/leftover after virtual fix,
    # they're real problems (not resolvable by nested collapse).

    if leftover_opens > 0 and not resolvable:
        # Imbalance can't be fixed by nested collapse — manual review needed
        problems.append(
            {
                "kind": "imbalance_open",
                "norm_code": "AP-24",
                "count": leftover_opens,
                "opens": opens,
                "closes": closes,
                "auto_fixable": False,
                "fix_hint": f"{leftover_opens} `[[` sin `]]` correspondiente (no cerrado al final del texto)",
            }
        )
    elif leftover_opens > 0 and resolvable:
        # Track as a "shadow" imbalance that nested fixes will resolve
        problems.append(
            {
                "kind": "imbalance_open_resolvable",
                "norm_code": "AP-24",
                "count": leftover_opens,
                "opens": opens,
                "closes": closes,
                "auto_fixable": True,
                "fix_hint": "Imbalance se resolverá al colapsar `[[[[` con nested_open",
            }
        )

    if stray_closes > 0 and not resolvable:
        problems.append(
            {
                "kind": "imbalance_close",
                "norm_code": "AP-24",
                "count": stray_closes,
                "opens": opens,
                "closes": closes,
                "examples": inverted_examples[:3],
                "auto_fixable": False,
                "fix_hint": f"{stray_closes} `]]` sin `[[` anterior (orden invertido)",
            }
        )
    elif stray_closes > 0 and resolvable:
        problems.append(
            {
                "kind": "imbalance_close_resolvable",
                "norm_code": "AP-24",
                "count": stray_closes,
                "opens": opens,
                "closes": closes,
                "examples": inverted_examples[:3],
                "auto_fixable": True,
                "fix_hint": "Imbalance se resolverá al colapsar `]]]]` con nested_close",
            }
        )

    return {
        "opens": opens,
        "closes": closes,
        "max_stack_depth": max_depth,
        "leftover_opens": leftover_opens,
        "stray_closes": stray_closes,
        "empty_count": len(empty_matches),
        "nested_open_count": len(nested_open_matches),
        "nested_close_count": len(nested_close_matches),
        "problems": problems,
        "auto_fixable": bool(problems) and all(p["auto_fixable"] for p in problems),
    }


def _apply_fixes(content: str, kinds: Optional[List[str]] = None) -> str:
    """Apply safe bracket fixes to content.

    kinds: filter — if provided, only fix those kinds. Default: all auto-fixable.

    Fixes applied:
      - empty [[]] / [[ ]] → removed entirely (the surrounding whitespace is collapsed)
      - nested_open [[[[ → [[ (collapse doubles)
      - nested_close ]]]] → ]] (collapse doubles)
    """
    allowed = set(kinds) if kinds else {"empty", "nested_open", "nested_close"}

    new = content

    if "empty" in allowed:
        # Remove `[[]]` and `[[ ]]` along with one adjacent space if present.
        # Run twice to handle cases where multiple empties are adjacent.
        for _ in range(3):
            new2 = re.sub(r"\s*\[\[\s*\]\]\s*", " ", new)
            new2 = re.sub(r" +", " ", new2)  # collapse double spaces
            if new2 == new:
                break
            new = new2

    if "nested_open" in allowed:
        # [[[[ → [[ (collapse 4+ opens to 2)
        new = re.sub(r"\[\[\[\[+", "[[", new)

    if "nested_close" in allowed:
        # ]]]] → ]] (collapse 4+ closes to 2)
        new = re.sub(r"\]\]\]\]+", "]]", new)

    return new


def _collect_notes(path_arg: Optional[str]) -> List[Path]:
    """Return list of .md files to scan."""
    if path_arg:
        target = Path(path_arg)
        if not target.is_absolute():
            target = VAULT_ROOT / path_arg
        try:
            target = assert_within_vault(target, VAULT_ROOT)
        except ValueError:
            return []
        target = target.resolve()
        if not target.exists():
            return []
        if target.is_file():
            return [target] if target.suffix == ".md" else []
        return sorted(target.rglob("*.md"))
    return sorted(VAULT_ROOT.rglob("*.md"))


def _make_backup(files: List[Path]) -> Optional[Path]:
    """Copy all files to a timestamped backup dir. Returns path or None if empty."""
    if not files:
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_dir = VAULT_ROOT / f".vault-fix-backup-{ts}"
    backup_dir.mkdir(exist_ok=True)
    for f in files:
        try:
            rel = f.relative_to(VAULT_ROOT)
        except ValueError:
            continue
        dest = backup_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
    return backup_dir


def vault_fix_brackets(
    path: Optional[str] = None,
    apply: bool = False,
    only: Optional[List[str]] = None,
    include_sandbox: bool = False,
) -> Dict[str, Any]:
    """Scan and optionally fix bracket problems. Returns a JSON-serializable report."""
    notes = _collect_notes(path)
    scanned = 0
    skipped = 0
    findings: List[Dict[str, Any]] = []
    files_to_backup: List[Path] = []
    files_modified: List[str] = []
    fixes_applied: List[Dict[str, Any]] = []

    for n in notes:
        scanned += 1
        try:
            rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")
        except ValueError:
            skipped += 1
            continue

        if _is_excluded(rel, n.name):
            skipped += 1
            continue

        # Skip vault-sandbox/ except when VAULT_ROOT is itself the sandbox
        # (test fixture scanning) or when --include-sandbox is set.
        if _in_sandbox(rel) and not _is_in_test_sandbox() and not include_sandbox:
            skipped += 1
            continue

        try:
            content = n.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            skipped += 1
            continue

        analysis = _analyze_note(content)
        if not analysis["problems"]:
            continue

        # Filter by --only if specified
        problems = analysis["problems"]
        if only:
            problems = [p for p in problems if p["kind"] in only]
            if not problems:
                continue
            analysis_filtered = dict(analysis)
            analysis_filtered["problems"] = problems
            analysis = analysis_filtered

        finding = {
            "path": rel,
            "from": rel,
            "opens": analysis["opens"],
            "closes": analysis["closes"],
            "problems": analysis["problems"],
            "auto_fixable": analysis["auto_fixable"],
            "kinds": sorted({p["kind"] for p in analysis["problems"]}),
            "norm_codes": sorted({p["norm_code"] for p in analysis["problems"]}),
        }
        findings.append(finding)

        if apply and analysis["auto_fixable"]:
            kinds = [p["kind"] for p in analysis["problems"] if p["auto_fixable"]]
            new_content = _apply_fixes(content, kinds)
            if new_content != content:
                files_to_backup.append(n)
                fixes_applied.append(
                    {
                        "path": rel,
                        "kinds_applied": kinds,
                        "before_chars": len(content),
                        "after_chars": len(new_content),
                        "delta": len(new_content) - len(content),
                    }
                )

    backup_dir: Optional[str] = None
    if apply and files_to_backup:
        bd = _make_backup(files_to_backup)
        backup_dir = str(bd.relative_to(VAULT_ROOT)).replace("\\", "/") if bd else None
        for fix in fixes_applied:
            target = VAULT_ROOT / fix["path"]
            try:
                # Recompute content from disk (in case multiple fixes share a file? no — unique paths)
                content = target.read_text(encoding="utf-8", errors="ignore")
                kinds = fix["kinds_applied"]
                new_content = _apply_fixes(content, kinds)
                atomic_write_text(target, new_content)
                files_modified.append(fix["path"])
            except Exception as e:
                fixes_applied.append({"path": fix["path"], "error": str(e)})

    # Group findings
    auto_fixable_count = sum(1 for f in findings if f["auto_fixable"])
    manual_count = sum(1 for f in findings if not f["auto_fixable"])

    return {
        "ok": True,
        "tool": "vault_fix_brackets",
        "vault_root": str(VAULT_ROOT),
        "timestamp": utcnow(),
        "mode": "apply" if apply else "dry-run",
        "scanned": scanned,
        "skipped": skipped,
        "findings_total": len(findings),
        "findings_auto_fixable": auto_fixable_count,
        "findings_manual_review": manual_count,
        "findings": findings,
        "fixes_applied_count": len(files_modified),
        "files_modified": files_modified,
        "backup_dir": backup_dir,
        "fixes_applied": fixes_applied,
        "hint": (
            "Run with --apply to apply the safe fixes. Manual-review findings "
            "(imbalance, inverted) require human decision."
        )
        if not apply
        else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect and optionally auto-fix malformed wiki-link brackets (AP-22 / AP-24).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run scan of all notes
  python vault_fix_brackets.py

  # Apply all auto-fixable fixes
  python vault_fix_brackets.py --apply

  # Only fix empty [[]] wiki-links
  python vault_fix_brackets.py --only empty --apply

  # Only audit a single note
  python vault_fix_brackets.py --path "02_Observability/errors/foo.md"

Kinds (for --only):
  empty         AP-22 — [[]] / [[ ]] (vacío sin info)
  nested_open   AP-24 — [[[[ (dobles corchetes abiertos)
  nested_close  AP-24 — ]]]] (dobles corchetes cerrados)
  imbalance_*   AP-24 — manual review only (not auto-fixed)
""",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apply safe fixes (default: dry-run)"
    )
    parser.add_argument(
        "--path", help="Limit to a specific note or folder (relative to VAULT_ROOT)"
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=[
            "empty",
            "nested_open",
            "nested_close",
            "imbalance_open",
            "imbalance_close",
        ],
        help="Only fix specific kinds (can repeat)",
    )
    parser.add_argument(
        "--include-sandbox",
        action="store_true",
        help="Include vault-sandbox/ in scan (test fixtures)",
    )
    args = parser.parse_args()

    result = vault_fix_brackets(
        path=args.path,
        apply=args.apply,
        only=args.only,
        include_sandbox=args.include_sandbox,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_fix_brackets"))

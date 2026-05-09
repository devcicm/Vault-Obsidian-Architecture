#!/usr/bin/env python3
"""
Vault Audit — Health check for the active vault.

Blueprint: vault-obsidian-architecture.md § vault_audit(project?)

Usage:
    python vault_audit.py
    python vault_audit.py --project "mi-proyecto"
"""

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

VAULT_ROOT = Path(__file__).parent.parent
SKIP_FOLDERS = {"10_Migrated", "vault-backups", ".history"}
STALE_DAYS = 30
STUCK_PATTERN_DAYS = 7
STALE_PROJECT_DAYS = 14

PLACEHOLDER_PATTERNS = [
    "yyyy", "nombre", "link-a", "{slug}", "archivo",
    "patron", "imagen", "img", "prisma", "postgres",
    "express", "hexagonal", "jsonwebtoken",
]


def _is_skipped(path: Path) -> bool:
    path_str = str(path.relative_to(VAULT_ROOT))
    return any(skip in path_str for skip in SKIP_FOLDERS)


def _get_active_notes(project: Optional[str] = None) -> List[Path]:
    notes = []
    for n in VAULT_ROOT.rglob("*.md"):
        if _is_skipped(n) or n.name.startswith("_"):
            continue
        if project:
            rel = str(n.relative_to(VAULT_ROOT))
            if project not in rel:
                continue
        notes.append(n)
    return notes


def _read_frontmatter(path: Path) -> Dict[str, str]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        if not content.startswith("---"):
            return {}
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}
        fm: Dict[str, str] = {}
        for line in parts[1].splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip("\"'")
        return fm
    except Exception:
        return {}


def _note_updated_at(path: Path) -> datetime:
    fm = _read_frontmatter(path)
    for field in ("updatedAt", "updated_at", "createdAt"):
        val = fm.get(field, "")
        if val:
            for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(val[:len(fmt) - 2], fmt[: len(val[:19])])
                except ValueError:
                    continue
            try:
                return datetime.fromisoformat(val[:19])
            except ValueError:
                pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def _extract_wiki_links(content: str) -> List[str]:
    content_clean = re.sub(r"```[\s\S]*?```", "", content)
    content_clean = re.sub(r"`[^`]+`", "", content_clean)
    links = []
    for m in re.finditer(r"\[\[([^\]]+)\]\]", content_clean):
        link = m.group(1).strip()
        if "|" in link:
            link = link.split("|")[0].strip()
        if link.startswith("http") or link.startswith("#"):
            continue
        if any(link.lower().startswith(ph) for ph in PLACEHOLDER_PATTERNS):
            continue
        links.append(link)
    return links


def _normalize(s: str) -> str:
    return s.lower().replace("-", "").replace("_", "")


def _build_indexes(notes: List[Path]) -> Tuple[Dict[str, Set[str]], Set[str]]:
    """Build backlink index and full-vault stem set for broken-link detection."""
    stem_map: Dict[str, str] = {}
    for n in notes:
        stem_map[_normalize(n.stem)] = n.stem

    all_stems: Set[str] = set()
    for n in VAULT_ROOT.rglob("*.md"):
        if ".history" not in str(n):
            all_stems.add(_normalize(n.stem))

    backlinks: Dict[str, Set[str]] = defaultdict(set)
    for n in notes:
        try:
            content = n.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for link in _extract_wiki_links(content):
            target_key = _normalize(link)
            if target_key in stem_map:
                backlinks[stem_map[target_key]].add(n.stem)

    return backlinks, all_stems


def _detect_orphans(notes: List[Path], backlinks: Dict[str, Set[str]]) -> List[Dict[str, Any]]:
    now = datetime.now()
    orphans = []
    for n in notes:
        rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")
        if rel.startswith("00_System"):
            continue
        if backlinks.get(n.stem):
            continue
        fm = _read_frontmatter(n)
        days_old = (now - _note_updated_at(n)).days
        orphans.append({
            "path": rel,
            "title": fm.get("title", n.stem),
            "daysOld": days_old,
        })
    return orphans


def _detect_stale(notes: List[Path]) -> List[Dict[str, Any]]:
    now = datetime.now()
    stale = []
    for n in notes:
        rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")
        if rel.startswith("00_System"):
            continue
        days = (now - _note_updated_at(n)).days
        if days > STALE_DAYS:
            fm = _read_frontmatter(n)
            stale.append({
                "path": rel,
                "title": fm.get("title", n.stem),
                "daysSinceUpdate": days,
            })
    return stale


def _detect_stuck_patterns(notes: List[Path]) -> List[Dict[str, Any]]:
    now = datetime.now()
    stuck = []
    for n in notes:
        rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")
        if "05_Patterns" not in rel:
            continue
        fm = _read_frontmatter(n)
        status = fm.get("status", "").lower().replace("-", "_")
        if status not in ("en_progreso", "in_progress"):
            continue
        days = (now - _note_updated_at(n)).days
        if days > STUCK_PATTERN_DAYS:
            stuck.append({
                "path": rel,
                "title": fm.get("title", n.stem),
                "status": fm.get("status", "en_progreso"),
                "daysSinceUpdate": days,
            })
    return stuck


def _detect_stale_projects(notes: List[Path]) -> List[Dict[str, Any]]:
    now = datetime.now()
    stale_projects = []
    for n in notes:
        rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")
        if "01_Projects" not in rel or n.name != "status.md":
            continue
        days = (now - _note_updated_at(n)).days
        if days > STALE_PROJECT_DAYS:
            fm = _read_frontmatter(n)
            stale_projects.append({
                "path": rel,
                "title": fm.get("title", n.stem),
                "daysSinceUpdate": days,
            })
    return stale_projects


def _detect_broken_links(notes: List[Path], all_stems: Set[str]) -> List[Dict[str, Any]]:
    broken = []
    for n in notes:
        rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")
        try:
            content = n.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for link in _extract_wiki_links(content):
            if _normalize(link) not in all_stems:
                broken.append({"from": rel, "link": link})
    return broken


def _detect_canonical_shadow(notes: List[Path]) -> List[Dict[str, Any]]:
    """AP-17: detect pairs of notes with fuzzy title similarity >85% (SequenceMatcher ratio)."""
    pairs = []
    items = []
    for n in notes:
        fm = _read_frontmatter(n)
        title = fm.get("title", n.stem).lower()
        rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")
        items.append((rel, title))

    seen: set = set()
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            rel_a, title_a = items[i]
            rel_b, title_b = items[j]
            ratio = SequenceMatcher(None, title_a, title_b).ratio()
            if ratio >= 0.85:
                key = tuple(sorted([rel_a, rel_b]))
                if key not in seen:
                    seen.add(key)
                    pairs.append({
                        "noteA": rel_a,
                        "noteB": rel_b,
                        "titleA": title_a,
                        "titleB": title_b,
                        "similarity": round(ratio, 3),
                    })
    return pairs


def _detect_cross_folder_duplicates(notes: List[Path]) -> List[Dict[str, Any]]:
    """AP-18: detect byte-identical content across different folders via MD5 hash."""
    hash_map: Dict[str, List[str]] = defaultdict(list)
    for n in notes:
        try:
            content = n.read_bytes()
        except Exception:
            continue
        digest = hashlib.md5(content).hexdigest()
        rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")
        hash_map[digest].append(rel)

    duplicates = []
    for digest, paths in hash_map.items():
        if len(paths) > 1:
            # Only report cross-folder duplicates (different top-level dirs)
            folders = {p.split("/")[0] for p in paths}
            if len(folders) > 1:
                duplicates.append({"hash": digest, "files": paths})
    return duplicates


def vault_audit(project: Optional[str] = None) -> Dict[str, Any]:
    """
    Run health audit on the active vault.

    Args:
        project: Optional project slug to filter audit scope.

    Returns:
        { healthScore, stats: {total, byFolder}, issues: {orphans, stale, stuckPatterns, staleProjects, brokenLinks}, summary }
    """
    notes = _get_active_notes(project)
    backlinks, all_stems = _build_indexes(notes)

    orphans = _detect_orphans(notes, backlinks)
    stale = _detect_stale(notes)
    stuck_patterns = _detect_stuck_patterns(notes)
    stale_projects = _detect_stale_projects(notes)
    broken_links = _detect_broken_links(notes, all_stems)
    canonical_shadow = _detect_canonical_shadow(notes)
    cross_folder_dupes = _detect_cross_folder_duplicates(notes)

    score = 100
    score -= min(30, len(orphans) * 2)
    score -= min(10, len(stale) * 1)
    score -= min(15, len(stuck_patterns) * 3)
    score -= min(25, len(stale_projects) * 5)
    score -= min(20, len(broken_links) * 2)
    score -= min(10, len(canonical_shadow) * 2)
    score -= min(10, len(cross_folder_dupes) * 3)
    score = max(0, score)

    by_folder: Dict[str, int] = defaultdict(int)
    for n in notes:
        parts = n.relative_to(VAULT_ROOT).parts
        by_folder[parts[0] if parts else "root"] += 1

    summary_parts = [f"Score: {score}/100", f"{len(notes)} notas"]
    if orphans:
        summary_parts.append(f"{len(orphans)} huerfanas")
    if broken_links:
        cnt = len(broken_links)
        summary_parts.append(f"{cnt} link{'s' if cnt != 1 else ''} roto{'s' if cnt != 1 else ''}")
    if stuck_patterns:
        summary_parts.append(f"{len(stuck_patterns)} patrones bloqueados")
    if stale_projects:
        summary_parts.append(f"{len(stale_projects)} proyectos sin actualizar")
    if canonical_shadow:
        summary_parts.append(f"{len(canonical_shadow)} pares AP-17")
    if cross_folder_dupes:
        summary_parts.append(f"{len(cross_folder_dupes)} duplicados AP-18")

    return {
        "ok": True,
        "healthScore": score,
        "stats": {
            "total": len(notes),
            "byFolder": dict(sorted(by_folder.items())),
        },
        "issues": {
            "orphans": orphans,
            "stale": stale,
            "stuckPatterns": stuck_patterns,
            "staleProjects": stale_projects,
            "brokenLinks": broken_links,
            "canonicalShadow": canonical_shadow,
            "crossFolderDuplicates": cross_folder_dupes,
        },
        "summary": " · ".join(summary_parts),
    }


def _audit_external_path(path: Path) -> Dict[str, Any]:
    """Audit .md files in an external directory path (not the vault)."""
    md_files = list(path.rglob("*.md"))
    total = len(md_files)
    no_frontmatter = []
    empty_files = []
    no_title = []

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if len(content) < 100:
            empty_files.append(str(md_file))

        if not content.startswith("---"):
            no_frontmatter.append(str(md_file))
            no_title.append(str(md_file))
            continue

        parts = content.split("---", 2)
        if len(parts) < 3:
            no_frontmatter.append(str(md_file))
            no_title.append(str(md_file))
            continue

        has_title = False
        for line in parts[1].splitlines():
            if line.lower().startswith("title:") and line.split(":", 1)[1].strip():
                has_title = True
                break
        # also check for a # heading
        if not has_title:
            import re as _re
            if _re.search(r"^#\s+.+", parts[2], _re.MULTILINE):
                has_title = True

        if not has_title:
            no_title.append(str(md_file))

    return {
        "ok": True,
        "mode": "external_path",
        "path": str(path),
        "total": total,
        "noFrontmatter": no_frontmatter,
        "emptyFiles": empty_files,
        "noTitle": no_title,
        "summary": f"{total} files · {len(no_frontmatter)} without frontmatter · {len(empty_files)} empty · {len(no_title)} without title",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Audit -- blueprint: vault-obsidian-architecture.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_audit.py
  python vault_audit.py --project "mi-proyecto"
  python vault_audit.py --path "C:/repos/mi-api/docs"
  python vault_audit.py --project "ans" --path "src/docs"

Notas:
  - Sin --path audita el vault interno
  - Con --path audita una ruta externa al vault (reporta frontmatter, vacios, sin titulo)
""",
    )
    parser.add_argument("--project", help="Optional project slug to filter audit scope")
    parser.add_argument("--path", help="External directory path to audit instead of vault")
    args = parser.parse_args()

    if args.path:
        ext_path = Path(args.path)
        if not ext_path.exists():
            print(json.dumps({"ok": False, "error": f"Path not found: {args.path}"}))
            return 1
        result = _audit_external_path(ext_path)
    else:
        result = vault_audit(args.project)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())

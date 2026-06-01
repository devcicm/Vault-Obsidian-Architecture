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
import os
import re
import subprocess
import sys
from vault_errors import wrap_main
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from vault_io import VAULT_ROOT
SCRIPTS_DIR = Path(__file__).parent
SYSTEM_DIR = VAULT_ROOT / "00_System"
QUALITY_INDEX = SYSTEM_DIR / "quality-index.json"
PROPAGATION_QUEUE = SYSTEM_DIR / "propagation-queue.json"

SKIP_FOLDERS = {"10_Migrated", "vault-backups", ".history"}
STALE_DAYS = 30
STUCK_PATTERN_DAYS = 7
STALE_PROJECT_DAYS = 14

VAULT_DQ_CACHE_MINUTES = int(os.environ.get("VAULT_DQ_CACHE_MINUTES", "30"))

# Archivos estructurales: auto-generados o de convención, no son "notas de contenido"
# Se excluyen de: orphans, stale, AP-17, duplicados
# Se INCLUYEN en: fuentes de backlinks, broken links detection
_STRUCTURAL_NAMES = frozenset({"index.md", "readme.md"})

PLACEHOLDER_PATTERNS = [
    "yyyy", "nombre", "link-a", "{slug}", "archivo",
    "patron", "imagen", "img", "prisma", "postgres",
    "express", "hexagonal", "jsonwebtoken",
]


def _is_skipped(path: Path) -> bool:
    path_str = str(path.relative_to(VAULT_ROOT))
    return any(skip in path_str for skip in SKIP_FOLDERS)


def _is_structural(path: Path) -> bool:
    return path.name.lower() in _STRUCTURAL_NAMES


def _get_active_notes(project: Optional[str] = None, include_structural: bool = False) -> List[Path]:
    notes = []
    for n in VAULT_ROOT.rglob("*.md"):
        if _is_skipped(n) or n.name.startswith("_"):
            continue
        if not include_structural and _is_structural(n):
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
    # Exclude structural files — identical names across sections are by design, not duplicates
    _EXCLUDED_STEMS = {"index", "readme", "change-log", "changelog", "gitkeep"}

    pairs = []
    items = []
    for n in notes:
        if n.stem.lower() in _EXCLUDED_STEMS:
            continue
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


def _detect_malformed_wikilinks(notes: List[Path]) -> List[Dict[str, Any]]:
    """AP-22: detect notes with unbalanced [[ ]] or empty [[]] wiki-links."""
    malformed = []
    for n in notes:
        try:
            content = n.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        clean = re.sub(r"```[\s\S]*?```", "", content)
        clean = re.sub(r"`[^`]+`", "", clean)
        opens = len(re.findall(r"\[\[", clean))
        closes = len(re.findall(r"\]\]", clean))
        empty = re.findall(r"\[\[\s*\]\]", clean)
        if opens != closes or empty:
            rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")
            malformed.append({
                "path": rel,
                "opens": opens,
                "closes": closes,
                "empty_links": len(empty),
            })
    return malformed


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


def _detect_empty_indexes() -> List[Dict[str, Any]]:
    """AP-11/AP-03: detect section folders whose index.md has no real notes.

    Scans every top-level vault folder for real notes (excludes index.md / README.md).
    Reports folders that exist but have zero content notes — their index is a stub.
    """
    empty = []
    try:
        for section_dir in sorted(VAULT_ROOT.iterdir()):
            if not section_dir.is_dir():
                continue
            name = section_dir.name
            if name.startswith(".") or name in ("scripts", ".history", "vault-backups"):
                continue
            real_notes = [
                p for p in section_dir.rglob("*.md")
                if p.name.lower() not in ("index.md", "readme.md")
                and not any(part.startswith(".") for part in p.parts)
            ]
            index_md = section_dir / "index.md"
            if len(real_notes) == 0:
                empty.append({
                    "norm_code": "AP-03",
                    "folder": name,
                    "index_exists": index_md.exists(),
                    "note": "Seccion sin notas — index es stub sin contenido real",
                })
    except Exception:
        pass
    return empty


def _read_quality_index() -> Optional[Dict[str, Any]]:
    if not QUALITY_INDEX.exists():
        return None
    try:
        return json.loads(QUALITY_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return None


def _dq_is_stale(qi: Dict[str, Any]) -> bool:
    generated_at = qi.get("generated_at", "")
    if not generated_at:
        return True
    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        age_minutes = (datetime.now(timezone.utc) - dt).total_seconds() / 60
        return age_minutes > VAULT_DQ_CACHE_MINUTES
    except Exception:
        return True


def _dq_is_locked() -> bool:
    lock_dir = QUALITY_INDEX.parent / f".{QUALITY_INDEX.name}.lock"
    return lock_dir.exists()


def _refresh_dq_if_needed() -> Dict[str, Any]:
    """Return dqHealth from current quality-index.json and trigger background refresh if stale."""
    qi = _read_quality_index()

    needs_refresh = (qi is None) or _dq_is_stale(qi)

    if needs_refresh and _dq_is_locked():
        dq_status = "update_in_progress"
    elif needs_refresh:
        # Fire quality_check in background — do NOT wait; read stale data immediately
        try:
            subprocess.Popen(
                [sys.executable, str(SCRIPTS_DIR / "vault_quality_check.py")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            dq_status = "refreshing_in_background" if qi else "unavailable"
        except Exception:
            dq_status = "stale" if qi else "unavailable"
    else:
        dq_status = "fresh"

    overall = qi.get("overall_dq_score") if qi else None
    below = qi.get("notes_below_07") if qi else None
    generated_at = qi.get("generated_at") if qi else None
    generated_by = qi.get("generated_by") if qi else None

    dq_health: Dict[str, Any] = {
        "dq_status": dq_status,
        "threshold": 0.7,
    }
    if overall is not None:
        dq_health["overall_dq_score"] = overall
    if below is not None:
        dq_health["notes_below_threshold"] = below
    if generated_at:
        dq_health["generated_at"] = generated_at
    if generated_by:
        dq_health["generated_by"] = generated_by

    return dq_health


def _read_propagation_pending() -> List[Dict[str, Any]]:
    """Read propagation-queue.json and return pending items sorted by priority."""
    if not PROPAGATION_QUEUE.exists():
        return []
    try:
        data = json.loads(PROPAGATION_QUEUE.read_text(encoding="utf-8"))
        pending = data.get("pending", [])
        risk_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        pending.sort(key=lambda e: (-risk_order.get(e.get("priority", "low"), 1), e.get("queued_at", "")))
        return [{"path": e["path"], "since": e.get("queued_at", ""), "priority": e.get("priority", "low")} for e in pending]
    except Exception:
        return []


def _cia_score_penalty(notes: List[Path], stale: List[Dict[str, Any]], propagation_pending: List[Dict[str, Any]]) -> int:
    """Extra health score penalty from CIA-weighted stale notes and propagation_pending."""
    penalty = 0
    stale_paths = {s["path"] for s in stale}
    pending_paths = {p["path"] for p in propagation_pending}

    for n in notes:
        rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")
        fm = _read_frontmatter(n)
        integrity = fm.get("cia_integrity", "medium").lower()
        if rel in stale_paths and integrity in ("critical",):
            penalty += 5
        if rel in pending_paths:
            penalty += 2

    return penalty


TAG_REGISTRY = VAULT_ROOT / "00_System" / "tag-registry.json"


def _read_tag_health() -> Optional[Dict[str, Any]]:
    """Load tag-registry.json and return tag health summary. Returns None if registry absent."""
    if not TAG_REGISTRY.exists():
        return None
    try:
        registry = json.loads(TAG_REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return None

    tags = registry.get("tags", {})
    untagged = registry.get("untagged_notes", [])

    orphaned = [t for t, info in tags.items() if info.get("count", 0) == 0]

    tag_names = list(tags.keys())
    near_dupes = 0
    seen_pairs: set = set()
    for i, tag_a in enumerate(tag_names):
        for tag_b in tag_names[i + 1:]:
            pair = tuple(sorted([tag_a, tag_b]))
            if pair in seen_pairs:
                continue
            a, b = tag_a.lower(), tag_b.lower()
            if a in b or b in a:
                score = 0.85
            else:
                common = sum(1 for x, y in zip(a, b) if x == y)
                score = common / max(len(a), len(b))
            if score >= 0.6:
                seen_pairs.add(pair)
                near_dupes += 1

    tag_health_score = 100
    tag_health_score -= len(orphaned) * 5
    tag_health_score -= near_dupes * 3
    tag_health_score -= min(len(untagged) * 2, 30)
    tag_health_score = max(0, tag_health_score)

    return {
        "total_tags": len(tags),
        "orphaned_tags": orphaned,
        "near_duplicate_pairs": near_dupes,
        "untagged_notes_count": len(untagged),
        "tag_health_score": tag_health_score,
        "registry_at": registry.get("updatedAt", "?"),
    }


def vault_audit(project: Optional[str] = None, refresh_dq: bool = False) -> Dict[str, Any]:
    """
    Run health audit on the active vault.

    Args:
        project:    Optional project slug to filter audit scope.
        refresh_dq: If True, refresh quality-index.json if stale (VAULT_DQ_CACHE_MINUTES threshold).

    Returns:
        { healthScore, stats, issues, dqHealth?, propagationPending?, summary }
    """
    # content_notes: notas reales (excluye index.md/README.md)
    # all_notes: incluye estructurales — para que sus links cuenten como backlinks
    content_notes = _get_active_notes(project, include_structural=False)
    all_notes = _get_active_notes(project, include_structural=True)

    # Indexes construidos desde all_notes para que index.md contribuya backlinks
    backlinks, all_stems = _build_indexes(all_notes)

    orphans = _detect_orphans(content_notes, backlinks)
    stale = _detect_stale(content_notes)
    stuck_patterns = _detect_stuck_patterns(content_notes)
    stale_projects = _detect_stale_projects(content_notes)
    # broken_links en all_notes: index.md roto también importa
    broken_links = _detect_broken_links(all_notes, all_stems)
    canonical_shadow = _detect_canonical_shadow(content_notes)
    cross_folder_dupes = _detect_cross_folder_duplicates(content_notes)
    malformed_wikilinks = _detect_malformed_wikilinks(all_notes)
    empty_indexes = _detect_empty_indexes()

    # DQ + propagation data (loaded regardless of refresh_dq; only refresh triggers subprocess)
    dq_health = _refresh_dq_if_needed() if refresh_dq else None
    propagation_pending = _read_propagation_pending()

    score = 100
    score -= min(30, len(orphans) * 2)
    score -= min(10, len(stale) * 1)
    score -= min(15, len(stuck_patterns) * 3)
    score -= min(25, len(stale_projects) * 5)
    score -= min(20, len(broken_links) * 2)
    score -= min(10, len(canonical_shadow) * 2)
    score -= min(10, len(cross_folder_dupes) * 3)
    score -= min(20, len(malformed_wikilinks) * 5)
    score -= min(10, len(empty_indexes) * 2)
    # CIA integrity + propagation_pending adjustments
    score -= min(15, _cia_score_penalty(content_notes, stale, propagation_pending))
    score = max(0, score)

    by_folder: Dict[str, int] = defaultdict(int)
    for n in content_notes:
        parts = n.relative_to(VAULT_ROOT).parts
        by_folder[parts[0] if parts else "root"] += 1

    summary_parts = [f"Score: {score}/100", f"{len(content_notes)} notas"]
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
    if malformed_wikilinks:
        summary_parts.append(f"{len(malformed_wikilinks)} corchetes AP-22")
    if empty_indexes:
        summary_parts.append(f"{len(empty_indexes)} secciones vacias AP-03")

    result: Dict[str, Any] = {
        "ok": True,
        "healthScore": score,
        "stats": {
            "total": len(content_notes),
            "byFolder": dict(sorted(by_folder.items())),
        },
        "issues": {
            "orphans": orphans,
            "stale": stale,
            "stuckPatterns": stuck_patterns,
            "staleProjects": stale_projects,
            "brokenLinks": [{"norm_code": "AP-14", **e} for e in broken_links],
            "canonicalShadow": [{"norm_code": "AP-17", **e} for e in canonical_shadow],
            "crossFolderDuplicates": [{"norm_code": "AP-18", **e} for e in cross_folder_dupes],
            "malformedWikilinks": [{"norm_code": "AP-22", **e} for e in malformed_wikilinks],
            "emptyIndexes": empty_indexes,
        },
        "norm_refs": {
            "AP-14": "Wiki-links rotos o vacíos",
            "AP-17": "Canonical-shadow duplication",
            "AP-18": "Cross-folder content duplication",
            "AP-22": "Bracket sanity — corchetes desbalanceados o vacíos",
        },
        "summary": " · ".join(summary_parts),
    }

    if dq_health is not None:
        result["dqHealth"] = dq_health

    if propagation_pending:
        result["propagationPending"] = propagation_pending

    tag_health = _read_tag_health()
    if tag_health is not None:
        result["tagHealth"] = tag_health

    return result


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
    parser.add_argument("--refresh-dq", action="store_true",
                        help="Refresh quality-index.json if stale and include dqHealth in output")
    args = parser.parse_args()

    if args.path:
        ext_path = Path(args.path)
        if not ext_path.exists():
            print(json.dumps({"ok": False, "error": f"Path not found: {args.path}"}))
            return 1
        result = _audit_external_path(ext_path)
    else:
        result = vault_audit(args.project, refresh_dq=args.refresh_dq)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_audit"))

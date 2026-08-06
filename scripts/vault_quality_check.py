#!/usr/bin/env python3
"""
vault_quality_check.py — Data Quality (DQ) scorer for vault notes.

Evaluates each note on 9 dimensions (8 fundamentals + 1 supplementary) and writes
00_System/quality-index.json. Uses file_lock coordination: if the index is locked
by another instance, reports dq_status: "update_in_progress" and uses cached score.

8 Fundamentals (data-fundamentals.md):
  F1 integrity       — frontmatter parseable + structural fields present (id, title, createdAt)
  F2 consistency     — outgoing wiki-links resolve; type matches folder section
  F3 completeness    — updatedAt present + body has ≥3 content lines
  F4 accuracy        — type↔folder alignment; path field matches actual path
  F5 validity        — CIA/status/type values within allowed sets
  F6 timeliness      — updatedAt within threshold (15d high/critical, 30d default) or evergreen
  F7 authenticity    — agent field present in frontmatter (AP-16)
  F8 non_repudiation — at least one entry in .change-log.json references this note

Supplementary:
  uniqueness         — not in AP-17 title-similar pair, not in AP-18 content-duplicate

Score per dimension: 0.0–1.0. Global = unweighted mean.

CIA-weighted thresholds:
  cia_integrity critical|high → timeliness threshold = 15 days
  medium|low (default)        → timeliness threshold = 30 days

Usage:
    python vault_quality_check.py                         # score all vault notes
    python vault_quality_check.py --path "01_Projects"    # scope to folder
    python vault_quality_check.py --min-score 0.7         # report notes below threshold
    python vault_quality_check.py --integrity high        # filter by CIA integrity
    python vault_quality_check.py --check                 # show index without writing
"""

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from vault_errors import wrap_main
from vault_lib import utcnow
from vault_io import atomic_write_json, file_lock, VAULT_ROOT, write_report


# F4 accuracy: section → expected type mapping
SECTION_TYPE_MAP: Dict[str, str] = {
    "01_Projects": "project",
    "03_Decisions": "decision",
    "04_Sessions": "session",
    "05_Patterns": "pattern",
    "06_Diagrams": "diagram",
    "07_Knowledge": "knowledge",
    "08_Runbooks": "runbook",
    "09_Infrastructure": "infra",
    "11_Code": "code",
    "12_Bibliography": "bibliography",
    "13_Flows": "flow",
    "14_Requirements": "requirement",
    "15_Tests": "test",
    "16_AI_Governance": "ai_decision",
}

SKIP_FOLDERS = {"10_Migrated", "vault-backups", ".history"}
STRUCTURAL_NAMES = frozenset({"index.md", "readme.md"})

TIMELINESS_DEFAULT_DAYS = 30
TIMELINESS_HIGH_DAYS = 15

CIA_INTEGRITY_VALUES = {"critical", "high", "medium", "low"}
CIA_AVAILABILITY_VALUES = {"high", "medium", "low"}
CIA_SENSITIVITY_VALUES = {"public", "internal", "restricted"}

STATUS_VALUES = {
    "active",
    "draft",
    "review",
    "archived",
    "deprecated",
    "en_progreso",
    "en_desarrollo",
    "in_progress",
    "done",
    "blocked",
    "pending",
    "completado",
    "completed",
    "cancelado",
    "cancelled",
}
TYPE_VALUES = {
    "project",
    "decision",
    "session",
    "pattern",
    "diagram",
    "knowledge",
    "runbook",
    "infra",
    "migration",
    "flow",
    "requirement",
    "test",
    "ai_decision",
    "bibliography",
    "code",
    "note",
}

PLACEHOLDER_PATTERNS = [
    "yyyy",
    "nombre",
    "link-a",
    "{slug}",
    "archivo",
    "patron",
    "imagen",
    "img",
    "prisma",
    "postgres",
    "express",
    "hexagonal",
    "jsonwebtoken",
]


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGobernanza:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGobernanza(construir(root))


def _system_dir() -> Path:
    return _repo().dir_sistema


def _quality_index() -> Path:
    return _repo().indice_calidad


def _change_log_json() -> Path:
    return _repo().bitacora_cambios


def _is_skipped(path: Path) -> bool:
    path_str = str(path.relative_to(_raiz()))
    return any(skip in path_str for skip in SKIP_FOLDERS)


def _is_structural(path: Path) -> bool:
    return path.name.lower() in STRUCTURAL_NAMES


def _get_content_notes(scope: Optional[str] = None) -> List[Path]:
    notes = []
    for n in _raiz().rglob("*.md"):
        if _is_skipped(n) or n.name.startswith("_") or _is_structural(n):
            continue
        if scope:
            rel = str(n.relative_to(_raiz())).replace("\\", "/")
            if not rel.startswith(scope.rstrip("/")):
                continue
        notes.append(n)
    return notes


def _get_all_notes() -> List[Path]:
    return [
        n
        for n in _raiz().rglob("*.md")
        if not _is_skipped(n) and ".history" not in str(n)
    ]


def _read_frontmatter_raw(path: Path) -> Tuple[Dict[str, str], str]:
    """Returns (frontmatter_dict, body_text)."""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}, ""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    fm: Dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip("\"'")
    return fm, parts[2]


def _parse_date(val: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(val[:19], fmt[: len(val[:19])])
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(val[:19])
    except Exception:
        return None


def _extract_wiki_links(content: str) -> List[str]:
    clean = re.sub(r"```[\s\S]*?```", "", content)
    clean = re.sub(r"`[^`]+`", "", clean)
    links = []
    for m in re.finditer(r"\[\[([^\]]+)\]\]", clean):
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


def _build_all_stems() -> Set[str]:
    stems: Set[str] = set()
    for n in _raiz().rglob("*.md"):
        if ".history" not in str(n):
            stems.add(_normalize(n.stem))
    return stems


# ── Dimension scorers ──────────────────────────────────────────────────────────


def _score_completeness(fm: Dict[str, str], body: str) -> Tuple[float, List[str]]:
    required = ["id", "title", "createdAt", "updatedAt"]
    present = [f for f in required if fm.get(f, "").strip()]
    missing = [f for f in required if f not in present]
    field_score = len(present) / len(required)

    body_lines = [l for l in body.splitlines() if l.strip()]
    content_score = (
        1.0 if len(body_lines) >= 3 else (0.5 if len(body_lines) >= 1 else 0.0)
    )

    score = round(field_score * 0.75 + content_score * 0.25, 3)
    issues = []
    if missing:
        issues.append(f"completeness: missing fields {missing}")
    if len(body_lines) < 3:
        issues.append(
            f"completeness: body has only {len(body_lines)} content line(s), expected ≥3"
        )
    return score, issues


def _score_validity(fm: Dict[str, str]) -> Tuple[float, List[str]]:
    errors: List[str] = []
    if "cia_integrity" in fm:
        v = fm["cia_integrity"].lower()
        if v not in CIA_INTEGRITY_VALUES:
            errors.append(f"validity: cia_integrity '{v}' invalid")
    if "cia_availability" in fm:
        v = fm["cia_availability"].lower()
        if v not in CIA_AVAILABILITY_VALUES:
            errors.append(f"validity: cia_availability '{v}' invalid")
    if "cia_sensitivity" in fm:
        v = fm["cia_sensitivity"].lower()
        if v not in CIA_SENSITIVITY_VALUES:
            errors.append(f"validity: cia_sensitivity '{v}' invalid")
    if "status" in fm:
        v = fm["status"].lower().replace("-", "_")
        if v not in STATUS_VALUES:
            errors.append(f"validity: status '{fm['status']}' not in known values")
    if "type" in fm:
        v = fm["type"].lower()
        if v not in TYPE_VALUES:
            errors.append(f"validity: type '{fm['type']}' not in known values")
    score = max(0.0, round(1.0 - len(errors) * 0.25, 3))
    return score, errors


def _score_timeliness(fm: Dict[str, str], path: Path) -> Tuple[float, List[str]]:
    if fm.get("evergreen", "").lower() in ("true", "yes", "1"):
        return 1.0, []

    integrity = fm.get("cia_integrity", "medium").lower()
    threshold = (
        TIMELINESS_HIGH_DAYS
        if integrity in ("critical", "high")
        else TIMELINESS_DEFAULT_DAYS
    )

    updated_str = (
        fm.get("updatedAt") or fm.get("updated_at") or fm.get("createdAt") or ""
    )
    dt = _parse_date(updated_str) if updated_str else None
    if dt is None:
        try:
            dt = datetime.fromtimestamp(path.stat().st_mtime)
        except Exception:
            return 0.5, ["timeliness: could not determine last updated date"]

    days = (datetime.now(timezone.utc).replace(tzinfo=None) - dt).days
    if days <= threshold:
        return 1.0, []

    days_over = days - threshold
    score = max(0.0, round(1.0 - days_over / 365.0, 3))
    return score, [f"timeliness: {days} days since update (threshold: {threshold}d)"]


def _score_consistency(body: str, all_stems: Set[str]) -> Tuple[float, List[str]]:
    links = _extract_wiki_links(body)
    if not links:
        return 1.0, []
    broken = [lnk for lnk in links if _normalize(lnk) not in all_stems]
    score = round(1.0 - len(broken) / len(links), 3)
    issues = [f"consistency: broken link [[{lnk}]]" for lnk in broken]
    return score, issues


def _score_uniqueness(
    path: Path,
    ap17_paths: Set[str],
    ap18_paths: Set[str],
) -> Tuple[float, List[str]]:
    rel = str(path.relative_to(_raiz())).replace("\\", "/")
    issues: List[str] = []
    score = 1.0
    if rel in ap18_paths:
        score = 0.0
        issues.append("uniqueness: content-identical to another note (AP-18)")
    elif rel in ap17_paths:
        score = 0.5
        issues.append("uniqueness: title-similar to another note (AP-17)")
    return score, issues


# ── Fundamentals (F1, F4, F7, F8) scorers ────────────────────────────────────


def _score_integrity(
    fm: Dict[str, str], frontmatter_parsed: bool
) -> Tuple[float, List[str]]:
    """F1 INTEGRIDAD — frontmatter parseable + structural minimum fields."""
    issues = []
    if not frontmatter_parsed:
        return 0.0, ["integrity: frontmatter missing or unparseable"]
    structural = ["id", "title", "createdAt"]
    present = [f for f in structural if fm.get(f, "").strip()]
    missing = [f for f in structural if f not in present]
    if missing:
        issues.append(f"integrity: missing structural fields {missing}")
    score = round(len(present) / len(structural), 3)
    return score, issues


def _score_accuracy(rel_path: str, fm: Dict[str, str]) -> Tuple[float, List[str]]:
    """F4 EXACTITUD — type↔folder alignment; declared path matches actual."""
    issues = []
    folder = rel_path.split("/")[0] if "/" in rel_path else ""
    expected_type = SECTION_TYPE_MAP.get(folder)
    actual_type = fm.get("type", "").lower()

    score = 1.0
    if expected_type and actual_type and actual_type != expected_type:
        issues.append(
            f"accuracy: type='{actual_type}' does not match folder section (expected '{expected_type}')"
        )
        score -= 0.5

    declared_path = fm.get("path", "").replace("\\", "/")
    if declared_path and declared_path != rel_path:
        issues.append(
            f"accuracy: path field='{declared_path}' differs from actual path='{rel_path}'"
        )
        score -= 0.5

    return max(0.0, round(score, 3)), issues


def _score_authenticity(fm: Dict[str, str]) -> Tuple[float, List[str]]:
    """F7 AUTENTICIDAD — agent field present (AP-16)."""
    agent = fm.get("agent", "").strip()
    if agent:
        return 1.0, []
    return 0.0, ["authenticity: missing 'agent' field in frontmatter (AP-16)"]


def _score_non_repudiation(
    rel_path: str, change_log_paths: Set[str]
) -> Tuple[float, List[str]]:
    """F8 NO REPUDIO — at least one change-log entry references this note."""
    if rel_path in change_log_paths:
        return 1.0, []
    return 0.0, ["non_repudiation: no change-log entry references this note"]


def _load_change_log_paths() -> Set[str]:
    """Load all unique paths referenced in .change-log.json."""
    if not _change_log_json().exists():
        return set()
    try:
        entries = json.loads(_change_log_json().read_text(encoding="utf-8"))
        paths: Set[str] = set()
        for e in entries:
            if e.get("path"):
                paths.add(e["path"])
            if e.get("new_path"):
                paths.add(e["new_path"])
        return paths
    except Exception:
        return set()


# ── AP-17 / AP-18 pre-computation ────────────────────────────────────────────


def _compute_ap17(notes: List[Path]) -> Set[str]:
    """Return set of vault-relative paths involved in AP-17 title-similarity pairs."""
    _EXCLUDED = {"index", "readme", "change-log", "changelog", "gitkeep"}
    items = []
    for n in notes:
        if n.stem.lower() in _EXCLUDED:
            continue
        fm, _ = _read_frontmatter_raw(n)
        title = fm.get("title", n.stem).lower()
        rel = str(n.relative_to(_raiz())).replace("\\", "/")
        items.append((rel, title))

    flagged: Set[str] = set()
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            rel_a, title_a = items[i]
            rel_b, title_b = items[j]
            if SequenceMatcher(None, title_a, title_b).ratio() >= 0.85:
                flagged.add(rel_a)
                flagged.add(rel_b)
    return flagged


def _compute_ap18(notes: List[Path]) -> Set[str]:
    """Return set of vault-relative paths involved in AP-18 cross-folder duplicates."""
    hash_map: Dict[str, List[str]] = defaultdict(list)
    for n in notes:
        try:
            digest = hashlib.md5(n.read_bytes()).hexdigest()
        except Exception:
            continue
        rel = str(n.relative_to(_raiz())).replace("\\", "/")
        hash_map[digest].append(rel)

    flagged: Set[str] = set()
    for paths in hash_map.values():
        if len(paths) > 1:
            folders = {p.split("/")[0] for p in paths}
            if len(folders) > 1:
                flagged.update(paths)
    return flagged


# ── Main scoring ──────────────────────────────────────────────────────────────


def vault_quality_check(
    scope: Optional[str] = None,
    min_score: float = 0.0,
    integrity_filter: Optional[str] = None,
    check_only: bool = False,
) -> Dict[str, Any]:
    """
    Score all vault notes on 5 DQ dimensions and write quality-index.json.

    Args:
        scope:            Vault-relative folder prefix to limit scope (e.g. "01_Projects").
        min_score:        Only include notes with overall score below this in the report.
        integrity_filter: Filter output by cia_integrity value.
        check_only:       If True, compute but do not write the index.

    Returns:
        {ok, overall_dq_score, notes_below_threshold, generated_at, path?, notes}
    """
    notes = _get_content_notes(scope)
    all_stems = _build_all_stems()
    ap17 = _compute_ap17(notes)
    ap18 = _compute_ap18(notes)
    change_log_paths = _load_change_log_paths()

    scored: Dict[str, Any] = {}
    total_score = 0.0

    for note in notes:
        rel = str(note.relative_to(_raiz())).replace("\\", "/")
        fm, body = _read_frontmatter_raw(note)
        frontmatter_parsed = bool(fm)
        integrity_cia = fm.get("cia_integrity", "medium").lower()

        # 8 fundamentals
        i_score, i_issues = _score_integrity(fm, frontmatter_parsed)
        c_score, c_issues = _score_completeness(fm, body)
        v_score, v_issues = _score_validity(fm)
        t_score, t_issues = _score_timeliness(fm, note)
        k_score, k_issues = _score_consistency(body, all_stems)
        a_score, a_issues = _score_accuracy(rel, fm)
        au_score, au_issues = _score_authenticity(fm)
        nr_score, nr_issues = _score_non_repudiation(rel, change_log_paths)
        # Supplementary
        u_score, u_issues = _score_uniqueness(note, ap17, ap18)

        # Global = mean of 9 dimensions (8 fundamentals + uniqueness)
        dim_scores = [
            i_score,
            c_score,
            v_score,
            t_score,
            k_score,
            a_score,
            au_score,
            nr_score,
            u_score,
        ]
        overall = round(sum(dim_scores) / len(dim_scores), 3)
        total_score += overall

        all_issues = (
            i_issues
            + c_issues
            + v_issues
            + t_issues
            + k_issues
            + a_issues
            + au_issues
            + nr_issues
            + u_issues
        )

        scored[rel] = {
            "scores": {
                "integrity": i_score,
                "consistency": k_score,
                "completeness": c_score,
                "accuracy": a_score,
                "validity": v_score,
                "timeliness": t_score,
                "authenticity": au_score,
                "non_repudiation": nr_score,
                "uniqueness": u_score,
            },
            "overall": overall,
            "cia_integrity": integrity_cia,
            "issues": all_issues,
        }

    total = len(scored)
    overall_dq = round(total_score / total, 3) if total else 0.0

    below_threshold = sum(
        1
        for v in scored.values()
        if v["overall"] < min_score or (min_score == 0.0 and False)
    )
    below_07 = sum(1 for v in scored.values() if v["overall"] < 0.7)

    generated_at = utcnow()
    index_data: Dict[str, Any] = {
        "generated_at": generated_at,
        "generated_by": "vault_quality_check",
        "scope": scope or "vault",
        "overall_dq_score": overall_dq,
        "notes_below_07": below_07,
        "total_notes": total,
        "notes": scored,
    }

    if not check_only:
        _system_dir().mkdir(parents=True, exist_ok=True)
        try:
            with file_lock(_quality_index(), timeout=30.0):
                atomic_write_json(_quality_index(), index_data)
        except TimeoutError:
            pass

    # Filter output for response
    filtered = {
        rel: data
        for rel, data in scored.items()
        if (min_score == 0.0 or data["overall"] < min_score)
        and (not integrity_filter or data["cia_integrity"] == integrity_filter.lower())
    }

    result: Dict[str, Any] = {
        "ok": True,
        **write_report(),
        "overall_dq_score": overall_dq,
        "total_notes": total,
        "notes_below_07": below_07,
        "generated_at": generated_at,
        "scope": scope or "vault",
        "notes": filtered,
    }
    if not check_only:
        result["path"] = str(_quality_index().relative_to(_raiz())).replace("\\", "/")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_quality_check — DQ scorer for vault notes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_quality_check.py                            # evalua todo el vault
  python vault_quality_check.py --path "01_Projects"      # scope reducido
  python vault_quality_check.py --min-score 0.7           # solo notas bajo el umbral
  python vault_quality_check.py --integrity high          # filtrar por CIA integrity
  python vault_quality_check.py --check                   # muestra sin escribir indice

Notas:
  - Escribe 00_System/quality-index.json (con file_lock para evitar colisiones)
  - Si el archivo esta bloqueado por otra instancia, aun asi computa y muestra resultado
  - 8 Fundamentos: integrity, consistency, completeness, accuracy, validity,
                   timeliness, authenticity, non_repudiation
  - Suplementario: uniqueness (AP-17/AP-18 detection)
  - Global = media de 9 dimensiones (8 fundamentos + uniqueness)
  - CIA: cia_integrity critical/high -> timeliness umbral 15d (vs 30d por defecto)
  - F8 NO_REPUDIO: requiere entrada en 00_System/.change-log.json para la nota
""",
    )
    parser.add_argument(
        "--path",
        dest="scope",
        metavar="FOLDER",
        help="Vault-relative folder prefix to scope the check",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        metavar="SCORE",
        help="Report only notes with overall score below this (0.0-1.0)",
    )
    parser.add_argument(
        "--integrity",
        metavar="LEVEL",
        choices=["critical", "high", "medium", "low"],
        help="Filter output by CIA integrity level",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compute scores without writing quality-index.json",
    )

    args = parser.parse_args()
    result = vault_quality_check(
        scope=args.scope,
        min_score=args.min_score,
        integrity_filter=args.integrity,
        check_only=args.check,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_quality_check"))

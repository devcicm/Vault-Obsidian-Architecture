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



from vault_io import VAULT_ROOT, normalize_stem as _normalize

SCRIPTS_DIR = Path(__file__).parent

SYSTEM_DIR = VAULT_ROOT / "00_System"

QUALITY_INDEX = SYSTEM_DIR / "quality-index.json"

PROPAGATION_QUEUE = SYSTEM_DIR / "propagation-queue.json"



SKIP_FOLDERS = {"vault-backups", ".history"}

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

    if ".vault-fix-backup-" in path_str:
        return True

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

    """Normalize a stem for fuzzy comparison.

    Strips: case, dashes, underscores, spaces, dots, and the .md suffix.
    Matches vault_write._collect_ghost_links normalization so a wiki-link
    like `[[Mi Proyecto Demo]]` correctly resolves to `mi-proyecto-demo.md`.
    """
    return s.lower().replace("-", "").replace("_", "").replace(" ", "").replace(".", "").removesuffix("md")





def _build_indexes(notes: List[Path]) -> Tuple[Dict[str, Set[str]], Set[str]]:

    """Build backlink index and full-vault stem set for broken-link detection."""

    stem_map: Dict[str, str] = {}

    for n in notes:

        stem_map[_normalize(n.stem)] = n.stem



    all_stems: Set[str] = set()

    for n in VAULT_ROOT.rglob("*.md"):

        if ".history" not in str(n):

            all_stems.add(_normalize(n.stem))
            # Register folder/stem paths: [[section/note]] resolves even if stem alone not unique
            try:
                rel = n.relative_to(VAULT_ROOT)
                if len(rel.parts) >= 2:
                    folder_stem = "".join(list(rel.parts[:-1])) + rel.stem
                    all_stems.add(_normalize(folder_stem))
            except ValueError:
                pass



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

        # Session notes are inherently orphan — each session is the start
        # of a new conversation. They are referenced by date, not by other
        # notes. Excluding them from orphan detection avoids false positives.
        if rel.startswith("04_Sessions/"):

            continue

        if backlinks.get(n.stem):

            continue

        # Scaffolds (vault_init primers) are placeholders by design —
        # they don't need inbound links. The user is expected to replace
        # them with real content; the nextActions block in the audit output
        # reminds them to do so. Excluding scaffolds avoids false-positive
        # orphan warnings on a freshly initialized vault.
        try:

            text = n.read_text(encoding="utf-8", errors="replace")
            if "scaffold: true" in text or "type: primer" in text:
                continue
        except Exception:
            pass

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

    # Pre-compute a set of relative paths for path-anchored link resolution.
    # Wiki-links like [[02_Observability/antipatterns/ap-foo]] should resolve
    # to a file at that relative path. The audit was treating them as broken
    # because stem-only normalization doesn't match the full path.
    all_paths: Set[str] = set()
    for n in VAULT_ROOT.rglob("*.md"):
        if ".history" not in str(n):
            rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")
            # Add both with and without .md extension
            all_paths.add(rel.lower())
            if rel.lower().endswith(".md"):
                all_paths.add(rel[:-3].lower())

    for n in notes:

        rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")

        # Spec/reference files contain wiki-link SYNTAX examples that are
        # documentation, not real links. Exclude them from broken-link detection.
        if n.name == "vault-obsidian-architecture.md" or "/scripts/" in rel or rel.startswith("scripts/"):
            continue

        try:

            content = n.read_text(encoding="utf-8", errors="ignore")

        except Exception:

            continue

        for link in _extract_wiki_links(content):

            if _normalize(link) in all_stems:
                continue

            # Try path-anchored resolution: the link might be a relative
            # file path that Obsidian can resolve. Check if a file exists
            # at this path (case-insensitive).
            link_normalized = link.lower().replace("\\", "/")
            if link_normalized in all_paths:
                continue

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

        rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")

        # Spec/reference files have the same title by design (it's the spec).
        # Exclude them from canonical-shadow detection.
        if n.name == "vault-obsidian-architecture.md" or "/scripts/" in rel or rel.startswith("scripts/"):
            continue

        # Session notes have similar titles by design (e.g. "2026-06-13",
        # "2026-06-14"). They're daily logs, not duplicates.
        if rel.startswith("04_Sessions/"):

            continue

        # Scaffolds (vault_init primers) are templates by design — all have
        # similar titles and structure. Excluding them avoids false positives.
        try:

            text = n.read_text(encoding="utf-8", errors="replace")
            if "scaffold: true" in text or "type: primer" in text:
                continue
        except Exception:
            pass

        fm = _read_frontmatter(n)

        title = fm.get("title", n.stem).lower()

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

    """AP-22 / AP-24: detect notes with malformed wiki-link brackets.

    Returns a list of findings with:
      - path: relative path of the offending note
      - norm_code: AP-22 (empty [[]]) or AP-24 (imbalance: opens != closes,
        nested brackets, inverted, or stray brackets)
      - kind: empty | imbalance_open | imbalance_close | nested | inverted
      - opens / closes: bracket counts (after stripping code blocks)
      - snippets: list of {line, text} with the offending context (first 3)
      - examples: short strings demonstrating each problem (first 3)

    Excluded:
      - vault-obsidian-architecture.md (the spec itself documents [[...]] syntax)
      - /scripts/* (tools contain regex examples that legitimately use brackets)
      - .bak backups (side-effects of upgrades)
      - sandbox directories (test fixtures)
    """

    findings: List[Dict[str, Any]] = []

    # Patterns
    RE_OPEN = re.compile(r"\[\[")
    RE_CLOSE = re.compile(r"\]\]")
    RE_EMPTY = re.compile(r"\[\[\s*\]\]")
    RE_NESTED_OPEN = re.compile(r"\[\[\[\[")  # [[[[ (4+ opens in a row)
    RE_NESTED_CLOSE = re.compile(r"\]\]\]\]")  # ]]]] (4+ closes in a row)
    # NOTE: "inverted" detection (]] … [[) is done via stack-based scanning
    # below — a naive regex here would false-positive on legitimate wiki-links
    # where `]]` from one link precedes `[[` of another link on a later line.

    for n in notes:

        rel = str(n.relative_to(VAULT_ROOT)).replace("\\", "/")

        # Spec/reference files contain unbalanced bracket examples as part
        # of documenting the syntax. Exclude them.
        if (
            n.name == "vault-obsidian-architecture.md"
            or "/scripts/" in rel
            or rel.startswith("scripts/")
            or ".bak" in rel
            or ".vault-fix-backup-" in rel
            or "vault-sandbox" in rel
        ):
            continue

        try:
            content = n.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Strip code blocks and inline code so we don't count regex examples
        clean = re.sub(r"```[\s\S]*?```", "", content)
        clean = re.sub(r"`[^`\n]+`", "", clean)

        opens = len(RE_OPEN.findall(clean))
        closes = len(RE_CLOSE.findall(clean))
        empty_matches = list(RE_EMPTY.finditer(clean))
        nested_open = list(RE_NESTED_OPEN.finditer(clean))
        nested_close = list(RE_NESTED_CLOSE.finditer(clean))

        # Stack-based detection of stray closes (inverted order) and unclosed
        # opens. More reliable than a regex pattern across the full text,
        # which would false-positive on legitimate links where `]]` from one
        # link precedes `[[` of another link on a later line.
        stack_depth = 0
        stray_closes = 0
        stray_close_examples: List[str] = []
        i = 0
        while i < len(clean):
            if clean[i:i+2] == "[[":
                stack_depth += 1
                i += 2
            elif clean[i:i+2] == "]]":
                if stack_depth == 0:
                    stray_closes += 1
                    start = max(0, i - 12)
                    end = min(len(clean), i + 14)
                    stray_close_examples.append(clean[start:end].replace("\n", " "))
                else:
                    stack_depth -= 1
                i += 2
            else:
                i += 1
        leftover_opens = stack_depth

        # Detect when an imbalance is fully resolvable by nested-collapse fixes
        # (so we don't false-block apply mode for fixable pathologies).
        resolvable = (
            leftover_opens <= len(nested_open) * 2
            and stray_closes <= len(nested_close) * 2
        )

        # Collect all bracket problems found in this note (filled below).
        problems: List[Dict[str, Any]] = []

        # AP-22: empty [[]] (no info — safe to auto-fix)
        if empty_matches:
            examples = [m.group(0) for m in empty_matches[:3]]
            problems.append({
                "kind": "empty",
                "norm_code": "AP-22",
                "count": len(empty_matches),
                "examples": examples,
                "auto_fixable": True,
                "fix_hint": "Eliminar `[[]]` (vacío sin info)",
            })

        # AP-24: nested [[ [[ — auto-fixable (collapse)
        if nested_open:
            examples = [m.group(0) for m in nested_open[:3]]
            problems.append({
                "kind": "nested_open",
                "norm_code": "AP-24",
                "count": len(nested_open),
                "examples": examples,
                "auto_fixable": True,
                "fix_hint": "Colapsar `[[[[` → `[[` (dobles corchetes anidados)",
            })

        # AP-24: nested ]] ]] — auto-fixable (collapse)
        if nested_close:
            examples = [m.group(0) for m in nested_close[:3]]
            problems.append({
                "kind": "nested_close",
                "norm_code": "AP-24",
                "count": len(nested_close),
                "examples": examples,
                "auto_fixable": True,
                "fix_hint": "Colapsar `]]]]` → `]]` (dobles corchetes anidados)",
            })

        # AP-24: inverted ]] [[ detected via stack (manual review when unresolvable)
        if stray_closes > 0 and not resolvable:
            problems.append({
                "kind": "inverted",
                "norm_code": "AP-24",
                "count": stray_closes,
                "examples": stray_close_examples[:3],
                "auto_fixable": False,
                "fix_hint": "Orden invertido `]]…[[` (stray close sin open previo). Probable copy-paste mal pegado.",
            })
        elif stray_closes > 0 and resolvable:
            problems.append({
                "kind": "inverted_resolvable",
                "norm_code": "AP-24",
                "count": stray_closes,
                "examples": stray_close_examples[:3],
                "auto_fixable": True,
                "fix_hint": "Stray closes se resolverán al colapsar `]]]]` con nested_close",
            })

        # AP-24: leftover opens at EOF (manual review when unresolvable)
        if leftover_opens > 0 and not resolvable:
            problems.append({
                "kind": "unclosed_open",
                "norm_code": "AP-24",
                "count": leftover_opens,
                "auto_fixable": False,
                "fix_hint": f"{leftover_opens} `[[` sin cerrar al final del texto",
            })
        elif leftover_opens > 0 and resolvable:
            problems.append({
                "kind": "unclosed_open_resolvable",
                "norm_code": "AP-24",
                "count": leftover_opens,
                "auto_fixable": True,
                "fix_hint": "Opens sin cerrar se resolverán al colapsar `[[[[` con nested_open",
            })

        if not problems:
            continue

        # Collect snippets with line + context for the first 3 problems
        snippets: List[Dict[str, Any]] = []
        for prob in problems[:3]:
            pattern_str = prob.get("examples", [""])
            if not pattern_str or pattern_str == [""]:
                # For imbalance, find the first stray bracket
                if prob["kind"] in ("imbalance_open", "imbalance_close"):
                    target = "[[" if prob["kind"] == "imbalance_open" else "]]"
                    for i, line in enumerate(content.split("\n"), start=1):
                        if target in line:
                            snippets.append({"line": i, "text": line.strip()[:160]})
                            break
            else:
                first_ex = prob["examples"][0]
                for i, line in enumerate(content.split("\n"), start=1):
                    if first_ex in line:
                        snippets.append({"line": i, "text": line.strip()[:160]})
                        break

        # Pick primary norm_code (AP-24 wins over AP-22 if both present)
        primary_norm = "AP-24" if any(p["norm_code"] == "AP-24" for p in problems) else "AP-22"
        kinds = sorted({p["kind"] for p in problems})
        counts = {p["kind"]: p["count"] for p in problems}

        findings.append({
            "path": rel,
            "from": rel,  # alias for consistency with brokenLinks output
            "norm_code": primary_norm,
            "kinds": kinds,
            "counts": counts,
            "opens": opens,
            "closes": closes,
            "auto_fixable": all(p["auto_fixable"] for p in problems),
            "snippets": snippets,
            "problems": problems,
        })

    return findings





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

            # Skip backup directories created by vault_init --clean or
            # manual copies. These shouldn't be treated as vault sections.
            if name.endswith(".bak") or ".bak-" in name or name == "vault-sandbox":

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


# ─────────────────────────────────────────────────────────────────────────────
# nextActions helpers — used by vault_audit to prescribe remediation
# ─────────────────────────────────────────────────────────────────────────────

# Per-section tool hint — mirrors the registry so the suggested command is
# correct even if the registry changes.
_SECTION_TOOL_HINT: Dict[str, str] = {
    "01_Projects":       "vault_project_overview --project <slug> --description '...' --runtime 'Node.js 20'",
    "02_Observability":  "vault_log_error --project <slug> --error '<msg>'",
    "03_Decisions":      "vault_write --folder 03_Decisions --title 'ADR-001 <titulo>' --content '...'",
    "04_Sessions":       "vault_write --folder 04_Sessions --title '$(date +%Y-%m-%d)' --content '...'",
    "05_Patterns":       "vault_pattern_save --project <slug> --name <patron> --status planificado",
    "06_Diagrams":       "vault_diagram_save --project <slug> --type erd --content '...'",
    "07_Knowledge":      "vault_knowledge_save --project <slug> --title <concepto> --category concept",
    "08_Runbooks":       "vault_runbook_save --project <slug> --title <runbook> --steps '...'",
    "09_Infrastructure": "vault_infra_save --project <slug> --name <servicio> --type server",
    "10_Migrated":       "vault_migrate_docs --source <path>",
    "11_Code":           "vault_code_module --project <slug> --file_path <path> --description '...'",
    "12_Bibliography":   "vault_bibliography_save --title <ref> --type web --url '...'",
    "13_Flows":          "vault_flow_save --project <slug> --title <flow> --type workflow",
    "14_Requirements":   "vault_requirement_save --project <slug> --title 'REQ-001 ...'",
    "15_Tests":          "vault_test_save --project <slug> --title <test> --type unit",
    "16_AI_Governance":  "vault_ai_decision --project <slug> --title <decision> --decision_type architecture",
}


def _suggest_command_for_folder(folder: str) -> str:
    """Return a copy-paste ready command for populating an empty section."""
    hint = _SECTION_TOOL_HINT.get(folder)
    if hint:
        return f"python scripts/{hint}"
    return f"python scripts/vault_write --folder {folder} --title '<titulo>' --content '...'"


def _detect_scaffold_only_sections(content_notes: List[Path]) -> List[str]:
    """Return sections that contain ONLY a vault_init primer (scaffold:true).

    These sections are at 100/100 thanks to the primer but the user should
    replace it with real content. Used by nextActions when score == 100.
    """
    sections_with_scaffold: Dict[str, bool] = {}
    sections_with_real: Dict[str, bool] = {}
    for n in content_notes:
        rel = n.relative_to(VAULT_ROOT)
        if not rel.parts:
            continue
        section = rel.parts[0]
        try:
            text = n.read_text(encoding="utf-8", errors="replace")
            is_scaffold = "scaffold: true" in text or "type: primer" in text
        except Exception:
            is_scaffold = False
        if is_scaffold:
            sections_with_scaffold[section] = True
        else:
            sections_with_real[section] = True
    result = []
    for sec, has_scaffold in sections_with_scaffold.items():
        if has_scaffold and not sections_with_real.get(sec, False):
            result.append(sec)
    return sorted(result)


def _get_roadmap_for_populated_vault(content_notes: List[Path]) -> List[Dict[str, Any]]:
    """When score == 100 AND no scaffolds, suggest what to document NEXT.

    This is the "what to do once everything is green" guidance: documented
    ADRs, runbooks, requirements, tests, SLOs, etc. Each item is ordered
    by the value it adds to the vault's coverage of the standard.
    """
    by_folder: Dict[str, int] = {}
    for n in content_notes:
        rel = n.relative_to(VAULT_ROOT)
        if rel.parts:
            by_folder[rel.parts[0]] = by_folder.get(rel.parts[0], 0) + 1

    actions: List[Dict[str, Any]] = []
    # Progression: once green, the next valuable things to add.
    if by_folder.get("01_Projects", 0) < 3:
        actions.append({
            "priority": "high",
            "category": "guidance",
            "description": "Documenta cada proyecto activo con `vault_project_overview` (mínimo 3 proyectos para cobertura significativa).",
            "command": "python scripts/vault_project_overview.py --project <slug> --description '...' --runtime '...'",
        })
    if by_folder.get("03_Decisions", 0) < 2:
        actions.append({
            "priority": "high",
            "category": "guidance",
            "description": "Registra tus decisiones arquitectónicas (ADRs). Mínimo 2 para mostrar el proceso.",
            "command": "python scripts/vault_write.py --folder 03_Decisions --title 'ADR-001 ...' --content '## Contexto\\n\\n## Opciones\\n\\n## Decision\\n\\n## Consecuencias'",
        })
    if by_folder.get("08_Runbooks", 0) < 1:
        actions.append({
            "priority": "medium",
            "category": "guidance",
            "description": "Crea al menos un runbook para el procedimiento más crítico (deploy, rollback, incident response).",
            "command": "python scripts/vault_runbook_save.py --project <slug> --title 'Deploy' --steps '...'",
        })
    if by_folder.get("02_Observability", 0) < 1:
        actions.append({
            "priority": "medium",
            "category": "guidance",
            "description": "Registra SLOs y métricas operacionales con `vault_slo_save` y `vault_log_error`.",
            "command": "python scripts/vault_slo_save.py --project <slug> --title 'API Availability' --sli 'requests < 500ms' --objective 99.9",
        })
    if by_folder.get("14_Requirements", 0) < 1:
        actions.append({
            "priority": "medium",
            "category": "guidance",
            "description": "Documenta los requerimientos formales (ISO 29148) con trazabilidad a tests y código.",
            "command": "python scripts/vault_requirement_save.py --project <slug> --title 'REQ-001 ...'",
        })
    if by_folder.get("15_Tests", 0) < 1:
        actions.append({
            "priority": "medium",
            "category": "guidance",
            "description": "Registra los casos de test formales (ISO 29119) con trazabilidad a requirements.",
            "command": "python scripts/vault_test_save.py --project <slug> --title 'Test: ...' --type unit",
        })
    if by_folder.get("11_Code", 0) < 1:
        actions.append({
            "priority": "medium",
            "category": "guidance",
            "description": "Documenta tus módulos de código siguiendo IEEE 1016 con `vault_code_module --tag-source` para inyectar trazabilidad bidireccional.",
            "command": "python scripts/vault_code_module.py --project <slug> --file_path <path> --description '...' --tag-source",
        })
    if by_folder.get("16_AI_Governance", 0) < 1 and len(content_notes) > 20:
        actions.append({
            "priority": "low",
            "category": "guidance",
            "description": "Una vez que el vault tenga >20 notas, registra decisiones de agentes IA (ISO 42001) en `16_AI_Governance/`.",
            "command": "python scripts/vault_ai_decision.py --project <slug> --title '<decision>' --decision_type architecture",
        })
    if not actions:
        actions.append({
            "priority": "low",
            "category": "guidance",
            "description": "Vault maduro. Siguiente: ejecuta `python scripts/vault_backup.py` para crear un snapshot con Merkle tree, y `python scripts/vault_drift_detect.py --path . --project <slug> --mode report` para detectar drift desde el último backup.",
        })
    return actions





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

    # broken_links en all_notes: index.md roto también importa (fix 2026-06-21: scope bug — antes pasaba content_notes)

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

    # AP-22 (empty [[]]) penaliza menos que AP-24 (imbalance real).
    # Auto-fixables tienen penalización baja; imbalance real penaliza más.
    ap22_count = sum(1 for m in malformed_wikilinks if m.get("norm_code") == "AP-22")
    ap24_count = sum(1 for m in malformed_wikilinks if m.get("norm_code") == "AP-24")
    score -= min(5, ap22_count * 2)  # AP-22 leve (vacíos sin info)
    score -= min(15, ap24_count * 5)  # AP-24 grave (brackets rotos)

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

        ap22_count = sum(1 for m in malformed_wikilinks if m.get("norm_code") == "AP-22")
        ap24_count = sum(1 for m in malformed_wikilinks if m.get("norm_code") == "AP-24")
        parts = []
        if ap22_count:
            parts.append(f"{ap22_count} AP-22")
        if ap24_count:
            parts.append(f"{ap24_count} AP-24")
        summary_parts.append(f"{len(malformed_wikilinks)} brackets rotos ({', '.join(parts)})")

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

            "AP-22": "Bracket sanity — wiki-links vacíos [[]]",

            "AP-23": "Note complexity ceiling — nota demasiado larga",

            "AP-24": "Bracket imbalance — corchetes sin pareja, anidados o invertidos",

        },

        "summary": " · ".join(summary_parts),

    }

    # nextActions: lista prescriptiva y ejecutable de lo que el agente (o el
    # humano) debe hacer para mantener o recuperar 100/100. Cada acción tiene:
    #   - priority: high | medium | low
    #   - category: empty_section | broken_link | malformed_wikilink | orphan |
    #               stale | scaffold_present | guidance
    #   - description: qué pasa y por qué importa
    #   - command: comando CLI sugerido (si aplica) — copy-paste ready
    #   - norm: AP-XX al que aplica
    #
    # Esto convierte el audit de "diagnóstico" a "agente prescriptivo" — el
    # usuario (o un agente LLM leyendo el output) sabe exactamente qué ejecutar.
    next_actions: List[Dict[str, Any]] = []

    # Empty sections: sugerir el comando del tool owner
    for e in empty_indexes:
        folder = e["folder"]
        next_actions.append({
            "priority": "high" if folder in ("01_Projects", "00_System") else "medium",
            "category": "empty_section",
            "folder": folder,
            "description": f"{folder} no tiene notas — la sección existe pero su contenido está vacío.",
            "command": _suggest_command_for_folder(folder),
            "norm": "AP-03",
        })

    # Broken links: 3 opciones
    for bl in broken_links:
        target = bl.get("link", "")
        src = bl.get("from", "")
        # build a clean slug from the target for the suggested filename
        slug = target.lower().replace(" ", "-")
        next_actions.append({
            "priority": "high",
            "category": "broken_link",
            "from": src,
            "link": target,
            "description": f"Wiki-link [[{target}]] en `{src}` no resuelve a ninguna nota del vault.",
            "remediation_options": [
                f"Crear la nota destino: `python scripts/vault_write.py --folder \"<carpeta>\" --title \"{target}\" --content \"...\"`",
                f"Editar `{src}` y corregir el link a una nota que sí exista.",
                f"Eliminar el link de `{src}` si ya no aplica.",
            ],
            "norm": "AP-14",
        })

    # Malformed wikilinks (AP-22 + AP-24)
    for ml in malformed_wikilinks:
        kinds = ml.get("kinds", [])
        auto_fixable = ml.get("auto_fixable", False)
        norm = ml.get("norm_code", "AP-22")
        path = ml.get("from", ml.get("path", ""))
        if auto_fixable:
            cmd = f"python scripts/vault_fix_brackets.py --apply {path}"
            desc_kind = ", ".join(kinds)
            next_actions.append({
                "priority": "medium",
                "category": "malformed_wikilink",
                "from": path,
                "kinds": kinds,
                "description": (
                    f"Brackets auto-arreglables ({desc_kind}) en `{path}`. "
                    "Ejecutar fix sin riesgo."
                ),
                "command": cmd,
                "norm": norm,
            })
        else:
            snippet = ""
            if ml.get("snippets"):
                s = ml["snippets"][0]
                snippet = f" Línea {s['line']}: `{s['text']}`."
            next_actions.append({
                "priority": "high",
                "category": "malformed_wikilink",
                "from": path,
                "kinds": kinds,
                "description": (
                    f"Brackets imbalanceados ({', '.join(kinds)}) en `{path}`."
                    f"{snippet} Revisar manualmente — fix automático NO seguro."
                ),
                "command": f"Revisar `{path}` y corregir `[[` / `]]` huérfanos.",
                "norm": norm,
            })

    # Orphans: notas sin backlinks
    for orph in orphans:
        next_actions.append({
            "priority": "low",
            "category": "orphan",
            "path": orph.get("path", ""),
            "description": f"Nota `{orph.get('path', '')}` no tiene wiki-links entrantes — está huérfana.",
            "command": "Añadir un wiki-link desde otra nota del vault, o marcar la nota como reference (no necesita backlinks).",
            "norm": "AP-13",
        })

    # Guidance cuando score == 100: qué documentar primero (siguiente paso)
    if score >= 100:
        # Detectar secciones que aún tienen solo el primer scaffold
        # para sugerir reemplazo por contenido real
        scaffold_reminders = _detect_scaffold_only_sections(content_notes)
        for sec in scaffold_reminders:
            next_actions.append({
                "priority": "high",
                "category": "scaffold_present",
                "folder": sec,
                "description": f"{sec} solo tiene el primer scaffold — listo para reemplazar con contenido real.",
                "command": _suggest_command_for_folder(sec),
                "norm": "CN-01",
            })
        if not next_actions:
            # Vault is at 100/100 and fully populated — provide a roadmap
            next_actions.extend(_get_roadmap_for_populated_vault(content_notes))

    if next_actions:
        result["nextActions"] = next_actions
        result["nextActionsCount"] = len(next_actions)



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


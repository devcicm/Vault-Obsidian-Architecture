#!/usr/bin/env python3
"""vault_graph_inspect — Vault graph analyzer + duplicate detector + syntax checker.

Scans a vault directory and reports:
- Total notes, total wikilink edges
- Broken links (target doesn't exist) — only outside 10_Migrated by default
- Orphans (notes with no incoming or outgoing links) — outside 10_Migrated
- Top hubs (most-connected notes)
- Exact duplicates (SHA256 body hash) — outside 10_Migrated
- Near-duplicates (Jaccard similarity ≥ threshold) — outside 10_Migrated
- Canonical shadows (same normalized stem) — outside 10_Migrated
- Wikilink syntax errors (malformed brackets, AP-21/22/24 violations) — outside 10_Migrated

Reads only — never modifies vault files.

Usage:
    # Default scan (auto-detects VAULT_ROOT)
    python scripts/vault_graph_inspect.py

    # Include 10_Migrated in scan
    python scripts/vault_graph_inspect.py --include-migrated

    # Custom root + JSON output
    python scripts/vault_graph_inspect.py --root /path/to/vault --json

    # Markdown report to file
    python scripts/vault_graph_inspect.py --md --threshold 0.85 > report.md

    # Exclude templates from near-dup detection
    python scripts/vault_graph_inspect.py --no-templates
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from vault_io import get_vault_root, normalize_stem
from vault_regex import (
    extract_wiki_links_strict,
    detect_bracket_anomalies,
    detect_path_anchored,
)
from vault_errors import emit_error, wrap_main


_SKIP_DIRS = frozenset(
    {
        "00_System",
        "99_Index",
        ".history",
        "vault-backups",
        "vault-sandbox",
        ".obsidian",
        ".trash",
    }
)

_MIGRATION_DIR = "10_Migrated"

_TITLE_RE = re.compile(r"^title:\s*(.+)$", re.MULTILINE)
_TAG_RE = re.compile(r"^tags:\s*(.+)$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

_WIKILINK_RAW_RE = re.compile(r"\[\[([^\]]*)\]\]")


def _is_migrated(rel_path: str) -> bool:
    """True if path belongs to 10_Migrated/ (any subfolder like direct/, indirect/, excluded/)."""
    return rel_path.split("/", 1)[0] == _MIGRATION_DIR


def _load_notes(
    root: Path,
    include_migrated: bool = False,
) -> dict[str, dict[str, Any]]:
    """Return {relative_path: {body, title, tags, body_hash}} for all .md notes.

    By default, skips 10_Migrated/* — pass include_migrated=True to include them.
    """
    notes: dict[str, dict[str, Any]] = {}
    for md in sorted(root.rglob("*.md")):
        try:
            rel = md.relative_to(root)
        except ValueError:
            continue
        rel_str = str(rel).replace("\\", "/")
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        if rel.name.startswith("."):
            continue
        if not include_migrated and _is_migrated(rel_str):
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        body = _strip_frontmatter(text)
        body_hash = hashlib.sha256(
            _normalize_for_hash(body).encode("utf-8")
        ).hexdigest()
        notes[rel_str] = {
            "body": body,
            "title": _extract_title(text) or rel.stem,
            "tags": _extract_tags(text),
            "body_hash": body_hash,
        }
    return notes


def _strip_frontmatter(content: str) -> str:
    match = _FRONTMATTER_RE.match(content)
    if match:
        return content[match.end() :].strip()
    return content


def _extract_title(content: str) -> str | None:
    match = _TITLE_RE.search(content[:2000])
    return match.group(1).strip().strip("'\"") if match else None


def _extract_tags(content: str) -> set[str]:
    match = _TAG_RE.search(content[:2000])
    if not match:
        return set()
    raw = match.group(1)
    return {t.strip().strip("[],") for t in re.findall(r"\w+", raw)}


def _normalize_for_hash(text: str) -> str:
    """Normalize text for exact-duplicate hash detection."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s-]", "", text)
    return text.strip()


def _build_graph(notes: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    """Build {source_note: set(target_stem)} from validated wikilinks."""
    graph: dict[str, set[str]] = defaultdict(set)
    for path, info in notes.items():
        for link in extract_wiki_links_strict(info["body"]):
            target_stem = normalize_stem(link)
            if target_stem:
                graph[path].add(target_stem)
    return dict(graph)


def _stems_set(notes: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Build {normalized_stem: relative_path} for quick existence lookup.

    Includes BOTH title-derived and filename-derived stems so links like
    [[00-14_requirements-primer]] resolve to the file (whose title is
    '14_Requirements — Guía rápida' which would otherwise normalize to a
    different stem).
    """
    stems: dict[str, str] = {}
    for p, info in notes.items():
        fname_stem = Path(p).stem
        title = info.get("title", "") or fname_stem
        candidates = [normalize_stem(title), normalize_stem(fname_stem)]
        for s in candidates:
            if s and s not in stems:
                stems[s] = p
    return stems


def _compute_metrics(
    notes: dict[str, dict[str, Any]],
    graph: dict[str, set[str]],
    stems: dict[str, str],
) -> dict[str, Any]:
    incoming: dict[str, int] = defaultdict(int)
    for source, targets in graph.items():
        for t in targets:
            if t in stems:
                incoming[stems[t]] += 1

    orphans = [p for p in notes if not graph.get(p) and incoming.get(p, 0) == 0]
    broken = []
    for source, targets in graph.items():
        for t in sorted(targets):
            if t not in stems:
                broken.append({"source": source, "target": t})

    in_degree = {p: incoming.get(p, 0) for p in notes}
    out_degree = {p: len(graph.get(p, set())) for p in notes}
    total_edges = sum(out_degree.values())
    hubs = sorted(notes, key=lambda p: (in_degree[p] + out_degree[p]), reverse=True)[
        :15
    ]
    top_hubs = [
        {
            "note": n,
            "in_degree": in_degree[n],
            "out_degree": out_degree[n],
        }
        for n in hubs
        if in_degree[n] + out_degree[n] > 0
    ]

    by_folder: dict[str, int] = defaultdict(int)
    for p in notes:
        by_folder[p.split("/", 1)[0]] += 1

    return {
        "total_notes": len(notes),
        "total_edges": total_edges,
        "broken_links_count": len(broken),
        "broken_links": broken[:50],
        "orphans_count": len(orphans),
        "orphans": sorted(orphans)[:50],
        "top_hubs": top_hubs,
        "by_folder": dict(sorted(by_folder.items())),
    }


def _detect_exact_duplicates(notes: dict[str, dict[str, Any]]) -> list[list[str]]:
    buckets: dict[str, list[str]] = defaultdict(list)
    for path, info in notes.items():
        buckets[info["body_hash"]].append(path)
    return [sorted(v) for v in buckets.values() if len(v) > 1]


def _shingles(text: str, k: int = 5) -> set[str]:
    words = _normalize_for_hash(text).split()
    if len(words) < k:
        return {" ".join(words)}
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _detect_near_duplicates(
    notes: dict[str, dict[str, Any]],
    threshold: float,
    exclude_templates: bool,
) -> list[dict[str, Any]]:
    path_list = sorted(notes)
    shingle_map: dict[str, set[str]] = {}
    for p in path_list:
        info = notes[p]
        is_template = any("template" in t for t in info["tags"])
        if exclude_templates and is_template:
            continue
        body = info["body"]
        if len(body) < 100:
            continue
        shingle_map[p] = _shingles(body)

    pairs: list[dict[str, Any]] = []
    paths_with_shingles = list(shingle_map)
    for i, a in enumerate(paths_with_shingles):
        for b in paths_with_shingles[i + 1 :]:
            sim = _jaccard(shingle_map[a], shingle_map[b])
            if sim >= threshold:
                pairs.append({"files": [a, b], "similarity": round(sim, 3)})
    return sorted(pairs, key=lambda x: -x["similarity"])


def _detect_canonical_shadows(notes: dict[str, dict[str, Any]]) -> list[list[str]]:
    """Canonical shadows = same normalized stem, but excluding 'index' which is everywhere."""
    buckets: dict[str, list[str]] = defaultdict(list)
    for path, info in notes.items():
        stem = normalize_stem(info["title"] or Path(path).stem)
        if stem == "index":
            continue
        buckets[stem].append(path)
    return [sorted(v) for v in buckets.values() if len(v) > 1]


def _detect_wikilink_syntax_errors(
    notes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect malformed brackets, path-anchored links, and other syntax issues per note."""
    errors: list[dict[str, Any]] = []
    for path, info in sorted(notes.items()):
        body = info["body"]
        bracket_errors = detect_bracket_anomalies(body)
        path_anchored = detect_path_anchored(body)
        for err in bracket_errors:
            errors.append(
                {
                    "note": path,
                    "type": err.get("type", "bracket_anomaly"),
                    "detail": err.get("detail", str(err)),
                    "line_hint": err.get("line_hint"),
                }
            )
        for err in path_anchored:
            errors.append(
                {
                    "note": path,
                    "type": "path_anchored",
                    "detail": str(err),
                    "line_hint": None,
                }
            )
    return errors


def _detect_graph_knowledge(root: Path) -> dict[str, Any]:
    """AP-31/34/35: analyze graph-enriched.json for knowledge graph health."""
    ENRICHED_FILE = root / "99_Index" / "graph-enriched.json"
    ENTITY_DIR = root / "06_Diagrams" / "entity"
    CODE_INDEX = root / "11_Code" / ".code-index.json"

    result: dict[str, Any] = {
        "enriched_exists": False,
        "typed_edges": 0,
        "total_edges": 0,
        "typed_ratio": 0.0,
        "predicate_counts": {},
        "unresolved_entity_relations": 0,
        "unresolved_code_relations": 0,
        "has_entity_relations": False,
        "has_code_relations": False,
        "graph_stale_hours": None,
    }

    has_entity = ENTITY_DIR.exists() and list(ENTITY_DIR.glob("*relations.json"))
    has_code = CODE_INDEX.exists()
    result["has_entity_relations"] = bool(has_entity)
    result["has_code_relations"] = has_code

    if not ENRICHED_FILE.exists():
        return result

    result["enriched_exists"] = True

    try:
        enriched = json.loads(ENRICHED_FILE.read_text(encoding="utf-8"))
        meta = enriched.get("metadata", {})
        result["typed_edges"] = meta.get("typed_edges", 0)
        result["total_edges"] = meta.get("total_edges", 0)
        if result["total_edges"] > 0:
            result["typed_ratio"] = round(result["typed_edges"] / result["total_edges"], 3)
        result["predicate_counts"] = meta.get("predicate_counts", {})

        diagnostics = enriched.get("diagnostics", {})
        result["unresolved_entity_relations"] = diagnostics.get("entity_relations", {}).get("unresolved", 0)
        result["unresolved_code_relations"] = diagnostics.get("code_relations", {}).get("unresolved", 0)

        merged_at = meta.get("merged_at", "")
        if merged_at:
            dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
            result["graph_stale_hours"] = round(
                (datetime.now(timezone.utc) - dt).total_seconds() / 3600, 1
            )
    except Exception:
        pass

    return result


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()[:19] + "Z"


def generate_report(
    root: Path,
    threshold: float = 0.85,
    exclude_templates: bool = False,
    include_migrated: bool = False,
) -> dict[str, Any]:
    notes = _load_notes(root, include_migrated=include_migrated)
    graph = _build_graph(notes)
    notes_for_stems = _load_notes(root, include_migrated=True)
    for md in sorted(root.rglob("*.md")):
        try:
            rel = md.relative_to(root)
        except ValueError:
            continue
        rel_str = str(rel).replace("\\", "/")
        if rel_str in notes_for_stems:
            continue
        if not rel_str.startswith("00_System/"):
            continue
        if rel.name.startswith("."):
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        from hashlib import sha256

        body = _strip_frontmatter(text)
        body_hash = sha256(_normalize_for_hash(body).encode("utf-8")).hexdigest()
        notes_for_stems[rel_str] = {
            "body": body,
            "title": _extract_title(text) or rel.stem,
            "tags": _extract_tags(text),
            "body_hash": body_hash,
        }
    stems = _stems_set(notes_for_stems)
    metrics = _compute_metrics(notes, graph, stems)
    exact_dups = _detect_exact_duplicates(notes)
    near_dups = _detect_near_duplicates(notes, threshold, exclude_templates)
    shadows = _detect_canonical_shadows(notes)
    syntax_errors = _detect_wikilink_syntax_errors(notes)
    graph_knowledge = _detect_graph_knowledge(root)

    severity = "none"
    if metrics["broken_links_count"] > 50:
        severity = "high"
    elif metrics["broken_links_count"] > 10:
        severity = "medium"
    elif metrics["broken_links_count"] > 0 or syntax_errors:
        severity = "low"

    return {
        "ok": True,
        "tool": "vault_graph_inspect",
        "vault_root": str(root),
        "generated_at": _now_iso(),
        "scope": "full" if include_migrated else "excluding-10_Migrated",
        "severity": severity,
        "summary": {
            "total_notes": metrics["total_notes"],
            "total_edges": metrics["total_edges"],
            "broken_links": metrics["broken_links_count"],
            "orphans": metrics["orphans_count"],
            "exact_duplicates_groups": len(exact_dups),
            "near_duplicates_pairs": len(near_dups),
            "canonical_shadow_groups": len(shadows),
            "syntax_errors": len(syntax_errors),
        },
        "metrics": metrics,
        "exact_duplicates": exact_dups[:50],
        "near_duplicates": near_dups[:50],
        "canonical_shadows": shadows[:50],
        "syntax_errors": syntax_errors[:50],
        "graph_knowledge": graph_knowledge,
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Vault Graph Inspection Report",
        "",
        f"**Vault root:** `{report['vault_root']}`  ",
        f"**Generated:** {report['generated_at']}  ",
        f"**Scope:** {report['scope']}  ",
        f"**Severity:** {report['severity']}  ",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total notes | {s['total_notes']} |",
        f"| Total edges | {s['total_edges']} |",
        f"| Broken links | {s['broken_links']} |",
        f"| Orphans | {s['orphans']} |",
        f"| Exact duplicate groups | {s['exact_duplicates_groups']} |",
        f"| Near-duplicate pairs | {s['near_duplicates_pairs']} |",
        f"| Canonical shadow groups | {s['canonical_shadow_groups']} |",
        f"| Syntax errors | {s['syntax_errors']} |",
        "",
        "## Notes by folder",
        "",
        "| Folder | Notes |",
        "|---|---|",
    ]
    for folder, count in report["metrics"]["by_folder"].items():
        lines.append(f"| {folder} | {count} |")

    lines += [
        "",
        "## Top 15 hubs",
        "",
        "| Note | In-degree | Out-degree |",
        "|---|---|---|",
    ]
    for h in report["metrics"]["top_hubs"]:
        lines.append(f"| `{h['note']}` | {h['in_degree']} | {h['out_degree']} |")

    if report["syntax_errors"]:
        lines += [
            "",
            "## Wikilink syntax errors (first 50)",
            "",
            "| Note | Type | Detail |",
            "|---|---|---|",
        ]
        for e in report["syntax_errors"]:
            detail = str(e["detail"])[:80]
            lines.append(f"| `{e['note']}` | {e['type']} | {detail} |")

    if report["metrics"]["broken_links"]:
        lines += [
            "",
            "## Broken links (first 50)",
            "",
            "| Source | Missing target |",
            "|---|---|",
        ]
        for b in report["metrics"]["broken_links"]:
            lines.append(f"| `{b['source']}` | `{b['target']}` |")

    if report["metrics"]["orphans"]:
        lines += ["", "## Orphans (first 50)", ""]
        for o in report["metrics"]["orphans"][:50]:
            lines.append(f"- `{o}`")

    if report["exact_duplicates"]:
        lines += ["", "## Exact duplicates", ""]
        for group in report["exact_duplicates"]:
            lines.append(f"- " + " • ".join(f"`{p}`" for p in group))

    if report["near_duplicates"]:
        lines += ["", "## Near duplicates (Jaccard ≥ threshold)", ""]
        for pair in report["near_duplicates"]:
            lines.append(
                f"- {pair['similarity']:.3f} — "
                + " • ".join(f"`{p}`" for p in pair["files"])
            )

    if report["canonical_shadows"]:
        lines += ["", "## Canonical shadows (same stem, excluding 'index')", ""]
        for group in report["canonical_shadows"]:
            lines.append(f"- " + " • ".join(f"`{p}`" for p in group))

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault graph inspector + duplicate detector + syntax checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", help="Vault root (default: VAULT_ROOT auto-detect)")
    parser.add_argument("--json", action="store_true", help="Output JSON (default)")
    parser.add_argument(
        "--md", action="store_true", help="Output Markdown instead of JSON"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Jaccard threshold for near-dups (default: 0.85)",
    )
    parser.add_argument(
        "--no-templates",
        action="store_true",
        help="Exclude template notes from near-dup detection",
    )
    parser.add_argument(
        "--include-migrated",
        action="store_true",
        help="Include 10_Migrated/ in scan (default: excluded)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else get_vault_root()
    if args.root:
        # AP-36: la observabilidad (traces/locks) debe escribir en el vault objetivo
        from vault_io import set_vault_root
        set_vault_root(root)
    if not root.exists():
        print(json.dumps(emit_error("vault_graph_inspect", "VAULT_NOT_FOUND", f"Vault root not found: {root}")))
        return 1

    report = generate_report(
        root=root,
        threshold=args.threshold,
        exclude_templates=args.no_templates,
        include_migrated=args.include_migrated,
    )

    # stdout may be a StringIO under wrap_main capture (no reconfigure) — guard it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.md:
        print(render_markdown(report))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if report["severity"] in ("none", "low") else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_graph_inspect"))

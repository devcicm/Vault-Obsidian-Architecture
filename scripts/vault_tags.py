#!/usr/bin/env python3
"""
Vault Tags — Registro canonico de tags, auditoria y control de consistencia.

Construye y mantiene 00_System/tag-registry.json escaneando todos los frontmatter.
Detecta tags huerfanos, notas sin tags, y tags near-duplicados para evitar
proliferacion incontrolada. Genera 99_Index/tag-index.md con backlinks por tag.

El tag-registry es la lista controlada: antes de crear un tag nuevo, el agente
consulta vault_tags --suggest para ver si ya existe uno canonico equivalente.

Usage:
    python vault_tags.py                        # rebuildar registry + tag-index.md
    python vault_tags.py --audit                # reporte de salud de tags
    python vault_tags.py --suggest PATH         # sugerir tags existentes para una nota
    python vault_tags.py --rename OLD NEW       # renombrar tag en todas las notas
    python vault_tags.py --dry-run              # rebuildar sin escribir archivos
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from vault_errors import wrap_main
from vault_io import atomic_write_json, atomic_write_text, assert_within_vault

VAULT_ROOT = Path(__file__).parent.parent
TAG_REGISTRY  = VAULT_ROOT / "00_System" / "tag-registry.json"
TAG_INDEX_MD  = VAULT_ROOT / "99_Index" / "tag-index.md"

VAULT_SECTIONS = {
    "00_System", "01_Projects", "02_Observability", "03_Decisions",
    "04_Sessions", "05_Patterns", "06_Diagrams", "07_Knowledge",
    "08_Runbooks", "09_Infrastructure", "10_Migrated", "11_Code",
    "12_Bibliography", "13_Flows", "14_Requirements", "15_Tests",
    "16_AI_Governance", "99_Index",
}

SKIP_NAMES = frozenset({"index.md", "readme.md"})


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _is_vault_note(path: Path) -> bool:
    try:
        parts = path.relative_to(VAULT_ROOT).parts
    except ValueError:
        return False
    if len(parts) < 2:
        return False
    if parts[0] not in VAULT_SECTIONS:
        return False
    if any(p.startswith(".") for p in parts):
        return False
    if path.name.lower() in SKIP_NAMES:
        return False
    return True


def _parse_frontmatter_tags(content: str) -> List[str]:
    if not content.startswith("---"):
        return []
    parts = content.split("---", 2)
    if len(parts) < 3:
        return []
    for line in parts[1].splitlines():
        if line.startswith("tags:"):
            raw = line.split(":", 1)[1].strip()
            if raw.startswith("["):
                try:
                    val = json.loads(raw)
                    if isinstance(val, list):
                        return [str(t).strip() for t in val if str(t).strip()]
                except json.JSONDecodeError:
                    pass
            return [t.strip() for t in raw.split(",") if t.strip()]
    return []


def _parse_frontmatter_title(content: str) -> str:
    if not content.startswith("---"):
        return ""
    parts = content.split("---", 2)
    if len(parts) < 3:
        return ""
    for line in parts[1].splitlines():
        if line.startswith("title:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    return ""


def _similarity_score(a: str, b: str) -> float:
    """Simple similarity: exact prefix/suffix overlap + shared chars ratio."""
    a, b = a.lower(), b.lower()
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.85
    # common prefix length
    common = sum(1 for x, y in zip(a, b) if x == y)
    prefix = 0
    for x, y in zip(a, b):
        if x == y:
            prefix += 1
        else:
            break
    if prefix >= 3:
        return 0.6 + (prefix / max(len(a), len(b))) * 0.2
    return common / max(len(a), len(b))


def _find_similar_tags(new_tag: str, existing_tags: Set[str], threshold: float = 0.6) -> List[Dict[str, Any]]:
    """Return existing tags similar to new_tag, sorted by similarity desc."""
    results = []
    for tag in existing_tags:
        score = _similarity_score(new_tag, tag)
        if score >= threshold and tag != new_tag:
            results.append({"tag": tag, "score": round(score, 2)})
    return sorted(results, key=lambda x: -x["score"])[:5]


def _scan_all_notes() -> Tuple[Dict[str, List[str]], List[str]]:
    """Scan vault notes → {tag: [paths]}, [untagged_paths]."""
    tag_map: Dict[str, List[str]] = defaultdict(list)
    untagged: List[str] = []

    for note_path in sorted(VAULT_ROOT.rglob("*.md")):
        if not _is_vault_note(note_path):
            continue
        try:
            content = note_path.read_text(encoding="utf-8", errors="ignore")
        except (PermissionError, OSError):
            continue
        rel = str(note_path.relative_to(VAULT_ROOT)).replace("\\", "/")
        tags = _parse_frontmatter_tags(content)
        if tags:
            for tag in tags:
                tag_map[tag].append(rel)
        else:
            untagged.append(rel)

    return dict(tag_map), untagged


def _generate_tag_index_md(tag_map: Dict[str, List[str]], untagged: List[str]) -> str:
    now = _utcnow()
    lines = [
        "---",
        "title: Tag Index",
        f"updatedAt: {now}",
        "type: index",
        "cia_integrity: low",
        "cia_availability: low",
        "cia_sensitivity: internal",
        "agent: system",
        "---",
        "",
        "# Tag Index",
        "",
        f"_{len(tag_map)} tags · {sum(len(v) for v in tag_map.values())} referencias · {len(untagged)} notas sin tag_",
        "",
    ]

    for tag in sorted(tag_map.keys(), key=str.lower):
        notes = sorted(tag_map[tag])
        lines.append(f"## `{tag}` ({len(notes)})")
        lines.append("")
        for note_path in notes:
            stem = Path(note_path).stem
            lines.append(f"- [[{stem}]]")
        lines.append("")

    if untagged:
        lines.append("## Sin tags")
        lines.append("")
        for note_path in sorted(untagged):
            stem = Path(note_path).stem
            lines.append(f"- [[{stem}]] — `{note_path}`")
        lines.append("")

    return "\n".join(lines)


def vault_tags_rebuild(dry_run: bool = False) -> Dict[str, Any]:
    tag_map, untagged = _scan_all_notes()

    registry = {
        "updatedAt": _utcnow(),
        "total_tags": len(tag_map),
        "total_tagged_notes": sum(len(v) for v in tag_map.values()),
        "total_untagged_notes": len(untagged),
        "tags": {
            tag: {"notes": sorted(paths), "count": len(paths)}
            for tag, paths in sorted(tag_map.items())
        },
        "untagged_notes": sorted(untagged),
    }

    tag_index_content = _generate_tag_index_md(tag_map, untagged)

    if not dry_run:
        VAULT_ROOT.joinpath("00_System").mkdir(parents=True, exist_ok=True)
        VAULT_ROOT.joinpath("99_Index").mkdir(parents=True, exist_ok=True)
        atomic_write_json(TAG_REGISTRY, registry)
        atomic_write_text(TAG_INDEX_MD, tag_index_content)

    return {
        "ok": True,
        "total_tags": len(tag_map),
        "total_tagged_notes": sum(len(v) for v in tag_map.values()),
        "total_untagged_notes": len(untagged),
        "tag_registry": str(TAG_REGISTRY.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "tag_index": str(TAG_INDEX_MD.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "dry_run": dry_run,
    }


def vault_tags_audit() -> Dict[str, Any]:
    if not TAG_REGISTRY.exists():
        return {"ok": False, "error": "tag-registry.json no encontrado. Ejecutar vault_tags.py primero."}

    try:
        registry = json.loads(TAG_REGISTRY.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"ok": False, "error": str(e)}

    tags = registry.get("tags", {})
    untagged = registry.get("untagged_notes", [])

    # Orphaned: tags that exist in registry but no current notes use them
    orphaned = [t for t, info in tags.items() if info.get("count", 0) == 0]

    # Near-duplicates: pairs of tags with high similarity
    tag_names = list(tags.keys())
    near_dupes: List[Dict[str, Any]] = []
    seen_pairs: Set[Tuple[str, str]] = set()
    for i, tag_a in enumerate(tag_names):
        for tag_b in tag_names[i+1:]:
            pair = tuple(sorted([tag_a, tag_b]))
            if pair in seen_pairs:
                continue
            score = _similarity_score(tag_a, tag_b)
            if score >= 0.6:
                seen_pairs.add(pair)
                near_dupes.append({
                    "tag_a": tag_a,
                    "tag_b": tag_b,
                    "score": round(score, 2),
                    "counts": {"a": tags[tag_a]["count"], "b": tags[tag_b]["count"]},
                })
    near_dupes.sort(key=lambda x: -x["score"])

    # Singleton tags (count == 1, not linked elsewhere)
    singletons = [t for t, info in tags.items() if info.get("count", 1) == 1]

    health_score = 100
    health_score -= len(orphaned) * 5
    health_score -= len(near_dupes) * 3
    health_score -= min(len(untagged) * 2, 30)
    health_score = max(0, health_score)

    return {
        "ok": True,
        "health_score": health_score,
        "total_tags": registry.get("total_tags", 0),
        "total_tagged_notes": registry.get("total_tagged_notes", 0),
        "total_untagged_notes": len(untagged),
        "orphaned_tags": orphaned,
        "near_duplicate_pairs": near_dupes[:10],
        "singleton_tags": singletons[:20],
        "untagged_notes": untagged[:20],
        "summary": (
            f"Score {health_score}/100 · {len(tags)} tags · "
            f"{len(orphaned)} huerfanos · {len(near_dupes)} near-dupes · "
            f"{len(untagged)} notas sin tag"
        ),
        "registry_at": registry.get("updatedAt", "?"),
    }


def vault_tags_suggest(note_path_str: str) -> Dict[str, Any]:
    note_path = VAULT_ROOT / Path(note_path_str)
    try:
        content = note_path.read_text(encoding="utf-8", errors="ignore")
    except (FileNotFoundError, PermissionError) as e:
        return {"ok": False, "error": str(e)}

    existing_tags = set(_parse_frontmatter_tags(content))
    title = _parse_frontmatter_title(content)

    if not TAG_REGISTRY.exists():
        return {
            "ok": False,
            "error": "tag-registry.json no encontrado. Ejecutar vault_tags.py primero.",
        }

    try:
        registry = json.loads(TAG_REGISTRY.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"ok": False, "error": str(e)}

    canonical_tags: Set[str] = set(registry.get("tags", {}).keys())

    words = re.findall(r"[a-zA-ZÀ-ɏ]{3,}", title + " " + " ".join(existing_tags))
    words = [w.lower() for w in words]

    candidates: Dict[str, float] = {}
    for word in words:
        for similar in _find_similar_tags(word, canonical_tags, threshold=0.5):
            tag = similar["tag"]
            score = similar["score"]
            if tag not in existing_tags:
                candidates[tag] = max(candidates.get(tag, 0), score)

    suggestions = [
        {"tag": tag, "score": round(score, 2), "count": registry["tags"].get(tag, {}).get("count", 0)}
        for tag, score in sorted(candidates.items(), key=lambda x: -x[1])
        if tag not in existing_tags
    ][:10]

    return {
        "ok": True,
        "path": note_path_str,
        "current_tags": sorted(existing_tags),
        "suggestions": suggestions,
        "canonical_tag_count": len(canonical_tags),
    }


def vault_tags_rename(old_tag: str, new_tag: str, dry_run: bool = False) -> Dict[str, Any]:
    if not old_tag or not new_tag:
        return {"ok": False, "error": "old_tag y new_tag son requeridos"}

    updated_notes: List[str] = []
    skipped: List[str] = []

    for note_path in VAULT_ROOT.rglob("*.md"):
        if not _is_vault_note(note_path):
            continue
        try:
            content = note_path.read_text(encoding="utf-8", errors="ignore")
        except (PermissionError, OSError):
            skipped.append(str(note_path))
            continue

        tags = _parse_frontmatter_tags(content)
        if old_tag not in tags:
            continue

        new_tags = [new_tag if t == old_tag else t for t in tags]
        new_tags_json = json.dumps(new_tags)
        # Replace tags line in frontmatter
        new_content = re.sub(
            r"^(tags:\s*).*$",
            f"tags: {new_tags_json}",
            content,
            count=1,
            flags=re.MULTILINE,
        )
        if new_content != content:
            rel = str(note_path.relative_to(VAULT_ROOT)).replace("\\", "/")
            if not dry_run:
                atomic_write_text(note_path, new_content)
            updated_notes.append(rel)

    if not dry_run and updated_notes:
        vault_tags_rebuild(dry_run=False)

    return {
        "ok": True,
        "old_tag": old_tag,
        "new_tag": new_tag,
        "updated_count": len(updated_notes),
        "updated_notes": updated_notes,
        "skipped": skipped,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Tags — registro canonico de tags y auditoria",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_tags.py                     # rebuildar registry + tag-index.md
  python vault_tags.py --audit             # reporte de salud de tags
  python vault_tags.py --suggest "01_Projects/mi-api/overview.md"
  python vault_tags.py --rename "api-rest" "rest-api"
  python vault_tags.py --dry-run           # simular sin escribir

Notas:
  - Tag registry: 00_System/tag-registry.json
  - Tag index: 99_Index/tag-index.md (con [[wiki-links]] por tag)
  - vault_write consulta el registry para sugerir tags existentes
  - vault_audit incluye tag_health en su output cuando el registry existe
""",
    )
    parser.add_argument("--audit", action="store_true", help="Reporte de salud de tags")
    parser.add_argument("--suggest", metavar="PATH", help="Sugerir tags canonicos para una nota")
    parser.add_argument("--rename", nargs=2, metavar=("OLD", "NEW"), help="Renombrar tag en todas las notas")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin escribir archivos")

    args = parser.parse_args()

    if args.audit:
        result = vault_tags_audit()
    elif args.suggest:
        result = vault_tags_suggest(args.suggest)
    elif args.rename:
        result = vault_tags_rename(args.rename[0], args.rename[1], dry_run=args.dry_run)
    else:
        result = vault_tags_rebuild(dry_run=args.dry_run)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_tags"))

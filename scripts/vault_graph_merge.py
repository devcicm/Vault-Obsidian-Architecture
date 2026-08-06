#!/usr/bin/env python3
"""
Vault Graph Merge Tool — Unifica wiki-links + entity relations + code relations

Lee los tres sistemas de relaciones del vault y genera graph-enriched.json
con predicados semanticos unificados basados en vault-ontology.json.

Sistemas mergeados:
  1. Wiki-links:        [[target]] en notas .md  →  predicate: "wiki_link"
  2. Entity relations:  06_Diagrams/entity/{project}-relations.json  →  predicates canon
  3. Code relations:    11_Code/.code-index.json  →  predicates canon

Tambien detecta: unknown_predicates, unresolved_entities, silo_flags.

Usage:
    python vault_graph_merge.py
    python vault_graph_merge.py --project "ans"
    python vault_graph_merge.py --predicate-filter depends_on,implements
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

from vault_errors import wrap_main
from vault_io import atomic_write_json, write_report
from vault_registry import ORDERED_SECTIONS

ONTOLOGY_FILE = Path(__file__).parent / "vault_ontology.json"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.grafo.repositorio import RepositorioGrafo  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGrafo:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGrafo(construir(root))


def _graph_file() -> Path:
    return _repo().grafo


def _enriched_file() -> Path:
    return _repo().grafo_enriquecido


def _entity_dir() -> Path:
    return _repo().dir_entidades


def _code_index() -> Path:
    return _repo().indice_codigo


def _move_log() -> Path:
    return _repo().bitacora_movimientos


# Derivado de `vault_registry`, no copiado: la copia literal se quedo en 18
# secciones y dejaba fuera `17_Preferences`, `18_Bugs`, `19_Audits` y
# `20_Quarantine` sin que nada fallara.
VAULT_SECTIONS = frozenset(ORDERED_SECTIONS)


def _load_ontology() -> Dict[str, Any]:
    if not ONTOLOGY_FILE.exists():
        return {}
    return json.loads(ONTOLOGY_FILE.read_text(encoding="utf-8"))


def _is_vault_note(note_path: Path) -> bool:
    try:
        parts = note_path.relative_to(_raiz()).parts
    except ValueError:
        return False
    if len(parts) < 2:
        return False
    return parts[0] in VAULT_SECTIONS


def _normalize_stem(s: str) -> str:
    return s.lower().replace("-", "").replace("_", "").replace(" ", "").replace(".", "").removesuffix("md")


def _extract_wiki_links(content: str) -> List[str]:
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)


def _extract_title(content: str) -> Optional[str]:
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if m:
        t = re.search(r"^title:\s*(.+)$", m.group(1), re.MULTILINE)
        if t:
            return t.group(1).strip("\"'")
    return None


def _extract_tags(content: str) -> List[str]:
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return []
    t = re.search(r"^tags:\s*(.+)$", m.group(1), re.MULTILINE)
    if not t:
        return []
    try:
        return json.loads(t.group(1))
    except json.JSONDecodeError:
        return []


def _folder_to_class(folder: str) -> str:
    mapping = {
        "00_System": "system", "01_Projects": "project", "02_Observability": "observability",
        "03_Decisions": "decision", "04_Sessions": "session", "05_Patterns": "pattern",
        "06_Diagrams": "diagram", "07_Knowledge": "knowledge", "08_Runbooks": "runbook",
        "09_Infrastructure": "infrastructure", "10_Migrated": "migrated", "11_Code": "code",
        "12_Bibliography": "bibliography", "13_Flows": "flow", "14_Requirements": "requirement",
        "15_Tests": "test", "16_AI_Governance": "ai_governance", "99_Index": "index",
    }
    return mapping.get(folder, "unknown")


def _build_node_class_index(ontology: Dict[str, Any]) -> Dict[str, str]:
    """Build folder → class_name mapping from ontology."""
    index = {}
    for class_name, cls in ontology.get("node_classes", {}).items():
        folder = cls.get("folder", "")
        if folder:
            index[folder] = class_name
    return index


def _build_wiki_link_graph() -> Tuple[Dict[str, Dict], List[Dict], List[Dict], Dict[str, str]]:
    """Scan all .md notes and build wiki-link graph."""
    nodes: Dict[str, Dict] = {}
    edges: List[Dict] = []
    broken: List[Dict] = []
    stem_map: Dict[str, str] = {}

    all_files = [
        p for p in _raiz().rglob("*.md")
        if _is_vault_note(p) and not any(part.startswith(".") for part in p.parts)
    ]

    for p in all_files:
        rel = str(p.relative_to(_raiz())).replace("\\", "/")
        stem_map[_normalize_stem(p.stem)] = rel
        fname_stem = _normalize_stem(p.stem)

        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue

        title = _extract_title(content) or p.stem
        tags = _extract_tags(content)

        title_stem = _normalize_stem(title)
        if title_stem != fname_stem:
            stem_map[title_stem] = rel

        folder = rel.split("/")[0] if "/" in rel else ""
        node_class = _folder_to_class(folder)

        wiki_links = _extract_wiki_links(content)

        nodes[rel] = {
            "path": rel,
            "title": title,
            "type": folder,
            "class": node_class,
            "tags": tags,
            "linkCount": len(wiki_links),
        }

    for rel, node in nodes.items():
        p = _raiz() / rel
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue

        for link in _extract_wiki_links(content):
            link_norm = _normalize_stem(link)
            raw_target = link.split("|")[0].strip() if "|" in link else link
            target_norm = _normalize_stem(raw_target)

            resolved = stem_map.get(target_norm)
            if resolved:
                edges.append({
                    "from": rel,
                    "to": resolved,
                    "predicate": "wiki_link",
                    "source": "wikilinks",
                })
            else:
                broken.append({
                    "from": rel,
                    "link": link,
                    "targetPath": link.replace("\\", "/"),
                })

    return nodes, edges, broken, stem_map


def _merge_entity_relations(ontology: Dict[str, Any], stem_map: Dict[str, str]) -> List[Dict]:
    """Read entity relations and convert to enriched edges."""
    edges: List[Dict] = []
    unresolved: List[Dict] = []
    unknown_predicates: List[Dict] = []

    valid_predicates = set(ontology.get("predicates", {}).keys())
    synonym_map = ontology.get("predicate_synonyms", {})

    if not _entity_dir().exists():
        return edges

    for rel_file in _entity_dir().glob("*relations.json"):
        try:
            raw = rel_file.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                raw = raw[3:]
            text = raw.decode("utf-8")
            data = json.loads(text)
        except Exception:
            continue

        project = data.get("project", "unknown")
        for rel in data.get("relations", []):
            raw_predicate = rel.get("relationType", "wiki_link")
            predicate = synonym_map.get(raw_predicate, raw_predicate)

            from_entity = rel.get("fromEntity", "")
            to_entity = rel.get("toEntity", "")
            from_norm = _normalize_stem(from_entity)
            to_norm = _normalize_stem(to_entity)

            from_path = stem_map.get(from_norm, "")
            to_path = stem_map.get(to_norm, "")

            if not from_path or not to_path:
                candidates = list(stem_map.values())
                for entity_name, is_from in [(from_entity, True), (to_entity, False)]:
                    entity_norm = _normalize_stem(entity_name)
                    if is_from and from_path:
                        continue
                    if not is_from and to_path:
                        continue
                    best_score = 0.0
                    best_path = ""
                    for cand_path in candidates:
                        stem = Path(cand_path).stem
                        score = SequenceMatcher(None, entity_norm, _normalize_stem(stem)).ratio()
                        if score > best_score and score >= 0.75:
                            best_score = score
                            best_path = cand_path
                    if best_path:
                        if is_from:
                            from_path = best_path
                        else:
                            to_path = best_path

            unresolved_parts = []
            if not from_path:
                unresolved_parts.append(from_entity)
            if not to_path:
                unresolved_parts.append(to_entity)
            if unresolved_parts:
                unresolved.append({
                    "fromEntity": from_entity,
                    "toEntity": to_entity,
                    "predicate": predicate,
                    "missing_endpoints": unresolved_parts,
                    "source_file": str(rel_file.relative_to(_raiz())).replace("\\", "/"),
                })

            if predicate not in valid_predicates:
                closest = _closest_predicate(predicate, valid_predicates)
                unknown_predicates.append({
                    "predicate": predicate,
                    "raw_predicate": raw_predicate,
                    "source": "entity",
                    "suggestion": closest,
                })
                if closest:
                    predicate = closest

            edge = {
                "from": from_path or from_entity,
                "to": to_path or to_entity,
                "predicate": predicate,
                "source": "entity_relations",
                "project": project,
                "cardinality": rel.get("cardinality"),
                "label": rel.get("label"),
                "entity_type": rel.get("entityType"),
                "endpoint_resolved": bool(from_path and to_path),
            }
            edges.append(edge)

    return edges


def _merge_code_relations(ontology: Dict[str, Any], stem_map: Dict[str, str]) -> List[Dict]:
    """Read code relations and convert to enriched edges."""
    edges: List[Dict] = []
    unresolved: List[Dict] = []
    unknown_predicates: List[Dict] = []

    valid_predicates = set(ontology.get("predicates", {}).keys())
    synonym_map = ontology.get("predicate_synonyms", {})

    if not _code_index().exists():
        return edges

    try:
        raw = _code_index().read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        text = raw.decode("utf-8")
        data = json.loads(text)
    except Exception:
        return edges

    for rel in data.get("relations", []):
        raw_predicate = rel.get("type", "wiki_link")
        predicate = synonym_map.get(raw_predicate, raw_predicate)

        from_file = rel.get("from", "")
        to_file = rel.get("to", "")

        from_norm = _normalize_stem(Path(from_file).stem)
        to_norm = _normalize_stem(Path(to_file).stem)

        from_path = stem_map.get(from_norm, "")
        to_path = stem_map.get(to_norm, "")

        if not from_path or not to_path:
            candidates = list(stem_map.values())
            for fname, is_from in [(from_file, True), (to_file, False)]:
                fnorm = _normalize_stem(Path(fname).stem)
                if is_from and from_path:
                    continue
                if not is_from and to_path:
                    continue
                best_score = 0.0
                best_path = ""
                for cand_path in candidates:
                    stem = Path(cand_path).stem
                    score = SequenceMatcher(None, fnorm, _normalize_stem(stem)).ratio()
                    if score > best_score and score >= 0.75:
                        best_score = score
                        best_path = cand_path
                if best_path:
                    if is_from:
                        from_path = best_path
                    else:
                        to_path = best_path

        unresolved_parts = []
        if not from_path:
            unresolved_parts.append(from_file)
        if not to_path:
            unresolved_parts.append(to_file)
        if unresolved_parts:
            unresolved.append({
                "fromFile": from_file,
                "toFile": to_file,
                "predicate": predicate,
                "missing_endpoints": unresolved_parts,
            })

        if predicate not in valid_predicates:
            closest = _closest_predicate(predicate, valid_predicates)
            unknown_predicates.append({
                "predicate": predicate,
                "raw_predicate": raw_predicate,
                "source": "code",
                "suggestion": closest,
            })
            if closest:
                predicate = closest

        edge = {
            "from": from_path or from_file,
            "to": to_path or to_file,
            "predicate": predicate,
            "source": "code_relations",
            "project": rel.get("project", ""),
            "cardinality": rel.get("cardinality"),
            "label": rel.get("label"),
            "endpoint_resolved": bool(from_path and to_path),
        }
        edges.append(edge)

    return edges


def _closest_predicate(predicate: str, valid: Set[str]) -> Optional[str]:
    """Find the closest valid predicate by string similarity."""
    best = None
    best_score = 0.0
    for v in valid:
        score = SequenceMatcher(None, predicate, v).ratio()
        if score > best_score:
            best_score = score
            best = v
    return best if best_score >= 0.5 else None


def _detect_orphans(nodes: Dict[str, Dict], edges: List[Dict]) -> List[Dict]:
    in_degree = defaultdict(int)
    for e in edges:
        if e.get("endpoint_resolved", True):
            in_degree[e["to"]] += 1

    orphans = []
    for path, node in nodes.items():
        if path.startswith("00_System/") or path.startswith("04_Sessions/"):
            continue
        if in_degree.get(path, 0) == 0:
            orphans.append({"path": path, "title": node.get("title", ""), "type": node.get("type", "")})
    return orphans


def _detect_silos() -> Dict[str, bool]:
    """AP-35: detect if entity/code relations exist but haven't been merged."""
    flags = {}
    entity_files = list(_entity_dir().glob("*relations.json")) if _entity_dir().exists() else []
    flags["entity_relations_exist"] = len(entity_files) > 0
    flags["code_relations_exist"] = _code_index().exists()

    if _enriched_file().exists():
        try:
            enriched = json.loads(_enriched_file().read_text(encoding="utf-8"))
            last_merge = enriched.get("metadata", {}).get("merged_at", "")
            if last_merge:
                dt = datetime.fromisoformat(last_merge.replace("Z", "+00:00"))
                hours_old = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                flags["graph_enriched_hours_old"] = round(hours_old, 1)
                flags["graph_enriched_stale"] = hours_old > 24
        except Exception:
            pass
    else:
        flags["graph_enriched_exists"] = False

    return flags


def _build_predicate_topology(edges: List[Dict]) -> Dict[str, int]:
    """Count edges by predicate type for health scoring."""
    counts = defaultdict(int)
    for e in edges:
        counts[e.get("predicate", "wiki_link")] += 1
    return dict(counts)


def vault_graph_merge(
    project: Optional[str] = None,
    predicate_filter: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Unifica los tres sistemas de relaciones en graph-enriched.json.

    Args:
        project: Optional project slug to filter scope.
        predicate_filter: Optional list of predicates to include (e.g. ['depends_on', 'implements']).

    Returns:
        Dict with nodes, edges, stats, diagnostics, and metadata.
    """
    ontology = _load_ontology()

    nodes, wiki_edges, broken_links, stem_map = _build_wiki_link_graph()

    entity_edges = _merge_entity_relations(ontology, stem_map)
    code_edges = _merge_code_relations(ontology, stem_map)

    all_edges = wiki_edges + entity_edges + code_edges

    if project:
        all_edges = [
            e for e in all_edges
            if e.get("project", "").lower() == project.lower() or e.get("source") == "wikilinks"
        ]

    if predicate_filter:
        predicates_set = set(predicate_filter)
        all_edges = [e for e in all_edges if e.get("predicate") in predicates_set]

    orphans = _detect_orphans(nodes, all_edges)
    predicate_counts = _build_predicate_topology(all_edges)
    silo_flags = _detect_silos()

    deleted_nodes = 0
    if _graph_file().exists():
        try:
            old = json.loads(_graph_file().read_text(encoding="utf-8"))
            for old_path in old.get("nodes", {}):
                if old_path not in nodes:
                    all_edges.append({
                        "from": old_path,
                        "to": "__deleted__",
                        "predicate": "deleted_node",
                        "source": "graph_history",
                    })
                    deleted_nodes += 1
        except Exception:
            pass

    resolved_entity = len([e for e in entity_edges if e.get("endpoint_resolved")])
    unresolved_entity = len(entity_edges) - resolved_entity
    resolved_code = len([e for e in code_edges if e.get("endpoint_resolved")])
    unresolved_code = len(code_edges) - resolved_code

    class_index = _build_node_class_index(ontology)
    for path, node in nodes.items():
        folder_derived = _folder_to_class(node.get("type", ""))
        node["class"] = class_index.get(node["type"], folder_derived)
        node["status"] = node.get("status", "active")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    total_edges = len(all_edges)
    typed_edges = len([e for e in all_edges if e.get("predicate") != "wiki_link"])

    enriched = {
        "metadata": {
            "version": "v37",
            "merged_at": now_iso,
            "ontology_version": ontology.get("version", "unknown"),
            "total_edges": total_edges,
            "wiki_edges": len(wiki_edges),
            "entity_edges": len(entity_edges),
            "code_edges": len(code_edges),
            "typed_edges": typed_edges,
            "predicate_counts": predicate_counts,
        },
        "nodes": nodes,
        "edges": all_edges,
        "stats": {
            "totalNodes": len(nodes),
            "totalEdges": total_edges,
            "typedEdges": typed_edges,
            "orphanNotes": len(orphans),
            "brokenWikiLinks": len(broken_links),
            "deletedNodes": deleted_nodes,
            "predicateCounts": predicate_counts,
        },
        "orphans": orphans,
        "brokenLinks": broken_links,
        "diagnostics": {
            "entity_relations": {
                "total": len(entity_edges),
                "resolved": resolved_entity,
                "unresolved": unresolved_entity,
            },
            "code_relations": {
                "total": len(code_edges),
                "resolved": resolved_code,
                "unresolved": unresolved_code,
            },
            "silo_flags": silo_flags,
        },
    }

    _enriched_file().parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(_enriched_file(), enriched)

    next_actions = []
    if unresolved_entity > 0:
        next_actions.append(
            f"{unresolved_entity} entity relations con endpoints no resueltos (AP-34). "
            "Ejecutar vault_search para verificar que las entidades existen como notas del vault."
        )
    if unresolved_code > 0:
        next_actions.append(
            f"{unresolved_code} code relations con endpoints no resueltos (AP-34). "
            "Verificar que los modulos de codigo esten documentados en 11_Code/."
        )
    if typed_edges == 0 and (entity_edges or code_edges):
        next_actions.append(
            "El grafo tiene entity/code relations pero 0 edges tipados (AP-31). "
            "Verificar que stem_map resuelva correctamente los endpoints."
        )
    if silo_flags.get("graph_enriched_stale"):
        next_actions.append(
            f"graph-enriched.json tiene {silo_flags.get('graph_enriched_hours_old', '?')}h de antiguedad (AP-35). "
            "Recomendado: ejecutar vault_graph_merge al final de cada sesion."
        )

    return {
        "ok": True,
        **write_report(),
        "savedTo": str(_enriched_file().relative_to(_raiz())).replace("\\", "/"),
        "metadata": enriched["metadata"],
        "stats": enriched["stats"],
        "diagnostics": enriched["diagnostics"],
        "nextActions": next_actions,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Graph Merge — unify wiki-links + entity + code relations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_graph_merge.py
  python vault_graph_merge.py --project "ans"
  python vault_graph_merge.py --predicate-filter depends_on,implements,calls

Notas:
  - Genera 99_Index/graph-enriched.json con predicados semanticos unificados
  - Detecta unknown_predicates, unresolved_entities (AP-34), y silos (AP-35)
  - La ontologia se define en vault_ontology.json
""",
    )
    parser.add_argument("--project", help="Optional project slug to filter scope")
    parser.add_argument(
        "--predicate-filter",
        help="Comma-separated list of predicates to include (e.g. depends_on,implements)",
    )
    args = parser.parse_args()

    predicate_filter = None
    if args.predicate_filter:
        predicate_filter = [p.strip() for p in args.predicate_filter.split(",")]

    result = vault_graph_merge(
        project=args.project,
        predicate_filter=predicate_filter,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_graph_merge"))

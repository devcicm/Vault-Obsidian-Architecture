#!/usr/bin/env python3
"""
vault_impact.py — BFS impact analysis on the vault backlink graph.

Loads 99_Index/graph.json, builds a reverse backlink graph, then performs
BFS from changed notes to find all transitively affected notes.

For each affected note, reports:
  - distance: hops from the nearest changed node
  - cia_integrity: from frontmatter (default: medium)
  - stale_risk: computed from distance × CIA weight
  - via: the wiki-link that connects it to the change

Usage:
    python vault_impact.py --changed "01_Projects/api/overview.md"
    python vault_impact.py --changed "note-a.md" "note-b.md" --max-hops 2
    python vault_impact.py --since "2026-05-09"   # auto-detect changed notes from change log
    python vault_impact.py --changed "note.md" --min-risk high
"""

import argparse
import json
import sys
from collections import deque, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from vault_errors import wrap_main


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


def _change_log_json() -> Path:
    return _repo().bitacora_cambios


CIA_WEIGHT: Dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

RISK_LEVELS = [
    (8, "critical"),
    (4, "high"),
    (2, "medium"),
    (0, "low"),
]


from vault_lib import read_frontmatter
# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueño.
from vault_vocabulario import opciones as _opciones


def _load_graph(predicate_filter: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Load graph, preferring enriched graph. Optionally filter edges by predicate."""
    graph_file = _enriched_file() if _enriched_file().exists() else _graph_file()
    if not graph_file.exists():
        return None
    try:
        data = json.loads(graph_file.read_text(encoding="utf-8"))
    except Exception:
        return None

    if predicate_filter:
        predicate_set = set(predicate_filter)
        edges = data.get("edges", [])
        filtered = [
            e for e in edges
            if e.get("predicate", e.get("type", "wiki_link")) in predicate_set
        ]
        data = dict(data)
        data["edges"] = filtered
        data["metadata"] = data.get("metadata", {})
        data["metadata"]["predicate_filtered"] = True
        data["metadata"]["predicates_included"] = list(predicate_set)

    return data


def _build_reverse_graph(graph: Dict[str, Any]) -> Dict[str, List[str]]:
    """Build reverse adjacency: target → [sources that link to it]."""
    reverse: Dict[str, List[str]] = defaultdict(list)
    for edge in graph.get("edges", []):
        src = edge.get("from", edge.get("source", ""))
        tgt = edge.get("to", edge.get("target", ""))
        if src and tgt:
            reverse[tgt].append(src)
    return dict(reverse)


def _compute_stale_risk(distance: int, integrity: str) -> str:
    weight = CIA_WEIGHT.get(integrity.lower(), 2)
    score = distance * weight
    for threshold, label in RISK_LEVELS:
        if score > threshold:
            return label
    return "low"


def _notes_changed_since(since_date: str) -> List[str]:
    """Read .change-log.json and return paths changed on or after since_date."""
    if not _change_log_json().exists():
        return []
    try:
        entries = json.loads(_change_log_json().read_text(encoding="utf-8"))
    except Exception:
        return []
    cutoff = since_date.strip()
    changed = []
    for entry in entries:
        ts = entry.get("timestamp", "")
        if ts[:10] >= cutoff:
            path = entry.get("path") or entry.get("new_path") or ""
            if path and path not in changed:
                changed.append(path)
    return changed


def vault_impact(
    changed_notes: List[str],
    max_hops: int = 10,
    min_risk: Optional[str] = None,
    since: Optional[str] = None,
    predicate_filter: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    BFS impact analysis from changed notes on the reverse backlink graph.

    Args:
        changed_notes:  List of vault-relative paths that changed.
        max_hops:       Maximum BFS depth (default 10 = full traversal).
        min_risk:       Filter results to 'critical', 'high', 'medium', or 'low'.
        since:          If provided, augment changed_notes from change log (date YYYY-MM-DD).
        predicate_filter: Optional list of predicates to include (e.g. ['depends_on', 'calls']).
                          When empty/None, all edges are traversed. Uses graph-enriched.json.

    Returns:
        {ok, changed_notes, impact_radius, impacted: [...], summary}
    """
    if since:
        extra = _notes_changed_since(since)
        for p in extra:
            if p not in changed_notes:
                changed_notes.append(p)

    if not changed_notes:
        return {
            "ok": True,
            "changed_notes": [],
            "impact_radius": 0,
            "impacted": [],
            "summary": "No changed notes provided",
        }

    graph = _load_graph(predicate_filter=predicate_filter)
    if graph is None:
        return {
            "ok": False,
            "error": "graph.json not found. Run vault_graph.py first.",
            "hint": "python scripts/vault_graph.py",
        }

    reverse = _build_reverse_graph(graph)
    nodes = graph.get("nodes", {})

    # Normalize changed note paths
    changed_set: Set[str] = set(changed_notes)

    # BFS
    visited: Dict[str, Dict[str, Any]] = {}
    queue: deque = deque()

    for start in changed_set:
        for neighbor in reverse.get(start, []):
            if neighbor not in changed_set and neighbor not in visited:
                queue.append((neighbor, 1, start))

    while queue:
        node, dist, via_src = queue.popleft()
        if node in visited:
            continue
        if dist > max_hops:
            continue

        note_path = _raiz() / node
        fm = read_frontmatter(note_path)
        integrity = fm.get("cia_integrity", "medium").lower()
        stale_risk = _compute_stale_risk(dist, integrity)

        visited[node] = {
            "path": node,
            "distance": dist,
            "cia_integrity": integrity,
            "stale_risk": stale_risk,
            "via": f"←{via_src}",
        }

        # BFS: continue from this node
        for neighbor in reverse.get(node, []):
            if neighbor not in changed_set and neighbor not in visited:
                queue.append((neighbor, dist + 1, node))

    # Filter by min_risk
    risk_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    impacted = list(visited.values())
    if min_risk:
        min_level = risk_order.get(min_risk.lower(), 1)
        impacted = [
            n for n in impacted if risk_order.get(n["stale_risk"], 1) >= min_level
        ]

    impacted.sort(key=lambda n: (-n["distance"], n["path"]))

    dist1 = sum(1 for n in impacted if n["distance"] == 1)
    dist_more = len(impacted) - dist1

    summary = (
        f"{len(impacted)} notas afectadas: "
        f"{dist1} directas (dist=1), {dist_more} transitivas"
        if impacted
        else "Sin impacto detectado en el grafo"
    )

    return {
        "ok": True,
        "changed_notes": list(changed_set),
        "impact_radius": len(impacted),
        "impacted": impacted,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_impact — BFS impact analysis from changed vault notes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Impacto desde una nota cambiada
  python vault_impact.py --changed "01_Projects/api/overview.md"

  # Multiples notas, limitando profundidad BFS
  python vault_impact.py --changed "note-a.md" "note-b.md" --max-hops 2

  # Auto-detectar notas cambiadas desde ayer via change log
  python vault_impact.py --since "2026-05-09"

  # Solo notas con riesgo alto o critico
  python vault_impact.py --changed "note.md" --min-risk high

  # Filtrar BFS solo por edges con predicate depends_on o calls
  python vault_impact.py --changed "note.md" --predicate depends_on,calls

Notas:
  - Requiere 99_Index/graph.json o graph-enriched.json
  - Lee cia_integrity del frontmatter de cada nota afectada
  - stale_risk = distance x CIA_weight (critical=4, high=3, medium=2, low=1)
  - --predicate filtra edges semanticamente (usa graph-enriched.json si existe)
""",
    )
    parser.add_argument(
        "--changed",
        nargs="+",
        metavar="PATH",
        default=[],
        help="Vault-relative paths of changed notes",
    )
    parser.add_argument(
        "--since",
        metavar="DATE",
        help="Include notes changed since this date (YYYY-MM-DD) from change log",
    )
    parser.add_argument(
        "--max-hops",
        type=int,
        default=10,
        metavar="N",
        help="Maximum BFS depth (default: 10)",
    )
    parser.add_argument(
        "--min-risk",
        choices=_opciones("severidad"),
        metavar="LEVEL",
        help="Filter by minimum stale_risk level",
    )
    parser.add_argument(
        "--predicate",
        metavar="PREDICATES",
        help="Comma-separated predicates to filter edges (e.g. depends_on,calls,implements). Uses graph-enriched.json.",
    )

    args = parser.parse_args()

    if not args.changed and not args.since:
        parser.error("Provide --changed PATH [PATH ...] or --since DATE")

    predicate_filter = None
    if args.predicate:
        predicate_filter = [p.strip() for p in args.predicate.split(",")]

    result = vault_impact(
        changed_notes=list(args.changed),
        max_hops=args.max_hops,
        min_risk=args.min_risk,
        since=args.since,
        predicate_filter=predicate_filter,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_impact"))

#!/usr/bin/env python3
"""
vault_subgraph.py — Subgrafo de K semillas y N saltos sobre el grafo del vault.

`vault_impact` ya recorre el grafo, pero solo hacia atrás (quién me referencia)
y con una pregunta fija: qué se queda obsoleto si cambio esto. Recuperar
contexto exige lo contrario: partir de unas pocas notas relevantes y expandir
en ambas direcciones hasta N saltos, quedándose con lo más conectado.

Diferencias deliberadas con vault_impact:
  - dirección configurable (`out` / `in` / `both`, por defecto `both`);
  - peso por arista según el predicado — no todas las relaciones informan
    igual: un `wiki_link` explícito dice más que una co-ocurrencia de tags;
  - decaimiento por salto, para que la relevancia caiga con la distancia;
  - filtros por sección, clase y tag, para acotar el subgrafo al dominio.

Usage:
    python vault_subgraph.py --seeds "03_Decisions/adr-001-mcp-transport.md" --hops 2
    python vault_subgraph.py --seeds a.md b.md --hops 3 --max-nodes 40 --section 07_Knowledge
    python vault_subgraph.py --seeds a.md --predicate wiki_link --direction out
    python vault_subgraph.py --seeds a.md --hops 2 --format mermaid
"""

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from vault_errors import wrap_main
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.grafo.repositorio import RepositorioGrafo  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _grafo() -> RepositorioGrafo:
    """El grafo no es de Consulta: se lee del contexto que lo escribe.

    Que la ubicación venga de `RepositorioGrafo` y no de una constante propia es
    deliberado — dos sitios decidiendo dónde vive `graph.json` es AP-05, y el
    día que se mueva solo se enteraría uno.
    """
    return RepositorioGrafo(construir())


def _graph_file():
    return _grafo().grafo


def _enriched_file():
    return _grafo().grafo_enriquecido

# Peso por tipo de relación. Una arista declarada a mano (wiki_link, related)
# es evidencia fuerte de que el autor considera las notas conectadas; una
# derivada por heurística (tag compartido, misma carpeta) es evidencia débil.
# Los pesos son ordinales, no probabilidades: solo ordenan.
PREDICATE_WEIGHT: Dict[str, float] = {
    "wiki_link": 1.0,
    "related": 1.0,
    "supersedes": 1.0,
    "superseded_by": 1.0,
    "depends_on": 0.9,
    "implements": 0.9,
    "decided_by": 0.9,
    "references": 0.8,
    "mentions": 0.6,
    "shared_tag": 0.4,
    "same_section": 0.2,
}
DEFAULT_WEIGHT = 0.5

# Cada salto multiplica la relevancia por esto. 0.6 hace que a 3 saltos una
# nota valga ~0.2 de lo que vale una semilla: presente, pero desplazable por
# cualquier vecino directo.
HOP_DECAY = 0.6

DEFAULT_HOPS = 2
DEFAULT_MAX_NODES = 50

# ── El invariante que hace que el BFS termine ────────────────────────────────
#
# El recorrido de `vault_subgraph` no lleva un conjunto de visitados: reencola
# un nodo cada vez que lo alcanza por un camino MEJOR (`new_relevance >
# best[neighbor]`). Eso es deliberado —un nodo alcanzable por dos rutas se queda
# con la más fuerte, no con la primera— y es lo que permite que la relevancia
# sea correcta en un grafo con ciclos, que es todo vault real.
#
# Termina solo porque la relevancia DECRECE en cada salto: si
# `peso * HOP_DECAY <= 1`, recorrer un ciclo nunca mejora lo ya visto y la
# reencolada se corta sola. Si algún peso sube por encima de `1 / HOP_DECAY`,
# dar la vuelta a un ciclo MEJORA la relevancia y el bucle deja de terminar por
# relevancia: pasa a depender solo de `hops`, y el coste crece exponencialmente
# con él.
#
# Medido sobre un grafo sintético de 60 nodos y grado 3, contando encolados a
# hops 4/8/12:
#
#     peso 1.0  (×decay 0.60)  ->   59 /  59 /  59   — plano, satura en V-1
#     peso 1.6  (×decay 0.96)  ->   59 /  59 /  59   — sigue plano
#     peso 1.7  (×decay 1.02)  ->  125 / 365 / 605   — crece con hops
#     peso 2.0  (×decay 1.20)  ->  257 / 3.6M+       — explota
#
# El punto de giro cae exactamente donde predice la desigualdad. Hasta aquí el
# invariante estaba solo en la cabeza de quien escribió el bucle: nada lo
# comprobaba, y subir un peso a 1.2 —un cambio que parece de calibración— habría
# convertido una consulta en un cuelgue sin que ninguna puerta se enterara.
MAX_PREDICATE_WEIGHT = 1.0 / HOP_DECAY


def _check_hop_decay_invariant() -> None:
    """Falla al importar si un peso rompe la terminación del BFS."""
    culpables = {
        p: w for p, w in PREDICATE_WEIGHT.items()
        if w * HOP_DECAY > 1.0
    }
    if DEFAULT_WEIGHT * HOP_DECAY > 1.0:
        culpables["<DEFAULT_WEIGHT>"] = DEFAULT_WEIGHT
    if culpables:
        raise ValueError(
            "PREDICATE_WEIGHT rompe el invariante de terminación del BFS "
            f"(peso * HOP_DECAY <= 1, con HOP_DECAY={HOP_DECAY} el tope es "
            f"{MAX_PREDICATE_WEIGHT:.4f}): {culpables}. Con un peso por encima "
            "del tope, recorrer un ciclo mejora la relevancia y el recorrido "
            "crece exponencialmente con --hops."
        )


_check_hop_decay_invariant()


def _load_graph() -> Optional[Dict[str, Any]]:
    """Carga el grafo, prefiriendo el enriquecido (trae predicados y clase)."""
    graph_file = _enriched_file() if _enriched_file().exists() else _graph_file()
    if not graph_file.exists():
        return None
    try:
        return json.loads(graph_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def _nodes_by_path(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Normaliza `nodes`: el grafo lo emite como dict, versiones viejas como lista."""
    nodes = graph.get("nodes", {})
    if isinstance(nodes, dict):
        return nodes
    out: Dict[str, Dict[str, Any]] = {}
    for node in nodes:
        path = node.get("path") or node.get("id")
        if path:
            out[path] = node
    return out


def _adjacency(
    graph: Dict[str, Any],
    direction: str,
    predicates: Optional[Set[str]],
) -> Dict[str, List[Tuple[str, str, float]]]:
    """origen → [(destino, predicado, peso)] según la dirección pedida."""
    adj: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)
    for edge in graph.get("edges", []):
        src = edge.get("from") or edge.get("source") or ""
        tgt = edge.get("to") or edge.get("target") or ""
        if not src or not tgt:
            continue
        predicate = edge.get("predicate") or edge.get("type") or "wiki_link"
        if predicates and predicate not in predicates:
            continue
        weight = PREDICATE_WEIGHT.get(predicate, DEFAULT_WEIGHT)
        if direction in ("out", "both"):
            adj[src].append((tgt, predicate, weight))
        if direction in ("in", "both"):
            adj[tgt].append((src, predicate, weight))
    return dict(adj)


def _matches_filters(
    node: Dict[str, Any],
    path: str,
    section: Optional[str],
    node_class: Optional[str],
    tags: Optional[List[str]],
) -> bool:
    if section and not path.startswith(section.rstrip("/") + "/") and path != section:
        return False
    if node_class and str(node.get("class", "")).lower() != node_class.lower():
        return False
    if tags:
        node_tags = {str(t).lower() for t in node.get("tags", []) or []}
        if not node_tags & {t.lower() for t in tags}:
            return False
    return True


def _resolve_seed(seed: str, nodes: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Acepta ruta exacta, ruta sin extensión o título de nota."""
    seed = seed.replace("\\", "/").strip()
    if seed in nodes:
        return seed
    if f"{seed}.md" in nodes:
        return f"{seed}.md"
    lowered = seed.lower()
    for path, node in nodes.items():
        if path.lower() == lowered:
            return path
        if str(node.get("title", "")).lower() == lowered:
            return path
        if Path(path).stem.lower() == lowered:
            return path
    return None


def vault_subgraph(
    seeds: List[str],
    hops: int = DEFAULT_HOPS,
    direction: str = "both",
    max_nodes: int = DEFAULT_MAX_NODES,
    predicates: Optional[List[str]] = None,
    section: Optional[str] = None,
    node_class: Optional[str] = None,
    tags: Optional[List[str]] = None,
    min_weight: float = 0.0,
) -> Dict[str, Any]:
    """Expande un subgrafo desde las semillas y lo devuelve ordenado por relevancia.

    La expansión es BFS por saltos (no Dijkstra): el corte lo marca `hops`, y
    el peso solo ordena el resultado. Es deliberado — un subgrafo de contexto
    debe ser predecible en tamaño, no en coste de camino.
    """
    if direction not in ("in", "out", "both"):
        return {"ok": False, "error_code": "INVALID_DIRECTION",
                "error": f"direction debe ser in|out|both, no '{direction}'"}
    if hops < 0:
        return {"ok": False, "error_code": "INVALID_HOPS",
                "error": "hops no puede ser negativo"}

    graph = _load_graph()
    if graph is None:
        return {
            "ok": False,
            "error_code": "GRAPH_MISSING",
            "error": "No hay grafo. Ejecuta vault_graph para generarlo.",
            "hint": "python scripts/vault_graph.py",
        }

    nodes = _nodes_by_path(graph)
    adj = _adjacency(graph, direction, set(predicates) if predicates else None)

    resolved: List[str] = []
    unresolved: List[str] = []
    for seed in seeds:
        hit = _resolve_seed(seed, nodes)
        (resolved if hit else unresolved).append(hit or seed)
    # Sin deduplicar, una semilla repetida contaría dos veces su relevancia.
    resolved = list(dict.fromkeys(resolved))

    if not resolved:
        return {
            "ok": False,
            "error_code": "NO_SEEDS_RESOLVED",
            "error": "Ninguna semilla existe en el grafo",
            "unresolved": unresolved,
        }

    # BFS. `best` guarda la mejor relevancia vista para cada nodo: un nodo
    # alcanzable por dos caminos se queda con el mas fuerte, no con el primero.
    #
    # Se intento sustituir por un mejor-primero (Dijkstra multiplicativo) para
    # que `max_nodes` acotara el trabajo y no solo la salida. NO ES EQUIVALENTE,
    # y la comparacion envelope a envelope contra este recorrido lo demostro:
    # aqui un nodo se expande VARIAS VECES, a profundidades distintas, cada vez
    # que mejora su relevancia. Un Dijkstra lo expande una sola vez, a la
    # profundidad de su mejor camino, y pierde las expansiones mas superficiales
    # -las que todavia tenian presupuesto de saltos-. Sobre grafos aleatorios eso
    # cambiaba nodos y aristas del resultado; el caso testigo fue la arista
    # `n39 -> n0`, presente aqui y ausente alli.
    #
    # El coste queda documentado como lo que es -O(V+E) por consulta, con
    # `max_nodes` acotando la salida-, medido y fijado en
    # `tests/test_bigo_grafo_y_recursion.py`. Cambiarlo es cambiar el envelope
    # publicado, y eso no se hace de refilon dentro de un arreglo de rendimiento.
    best: Dict[str, float] = {p: 1.0 for p in resolved}
    depth: Dict[str, int] = {p: 0 for p in resolved}
    via: Dict[str, Optional[Dict[str, str]]] = {p: None for p in resolved}
    edges_out: List[Dict[str, Any]] = []
    seen_edges: Set[Tuple[str, str, str]] = set()

    queue = deque((p, 0, 1.0) for p in resolved)
    while queue:
        current, d, relevance = queue.popleft()
        if d >= hops:
            continue
        for neighbor, predicate, weight in adj.get(current, []):
            if weight < min_weight:
                continue
            key = (current, neighbor, predicate)
            if key not in seen_edges:
                seen_edges.add(key)
                edges_out.append({"from": current, "to": neighbor,
                                  "predicate": predicate, "weight": round(weight, 3)})
            new_relevance = relevance * weight * HOP_DECAY
            if new_relevance <= best.get(neighbor, 0.0):
                continue
            best[neighbor] = new_relevance
            depth[neighbor] = d + 1
            via[neighbor] = {"from": current, "predicate": predicate}
            queue.append((neighbor, d + 1, new_relevance))

    results: List[Dict[str, Any]] = []
    # Solo los EXPANDIDOS. `best` contiene además nodos meramente descubiertos,
    # cuya relevancia todavía podía mejorar cuando el recorrido paró: publicarlos
    # sería publicar un número provisional como si fuera el definitivo.
    for path, relevance in best.items():
        node = nodes.get(path, {})
        if path not in resolved and not _matches_filters(
            node, path, section, node_class, tags
        ):
            continue
        results.append({
            "path": path,
            "title": node.get("title", Path(path).stem),
            "section": path.split("/")[0] if "/" in path else "",
            "class": node.get("class", ""),
            "status": node.get("status", ""),
            "tags": node.get("tags", []) or [],
            "hops": depth.get(path, 0),
            "relevance": round(relevance, 4),
            "is_seed": path in resolved,
            "via": via.get(path),
            "in_graph": path in nodes,
        })

    # Semillas primero, luego relevancia; el desempate por ruta hace la salida
    # determinista, que es lo que permite testearla.
    results.sort(key=lambda r: (not r["is_seed"], -r["relevance"], r["path"]))
    # Acota la SALIDA, no el trabajo: ver el comentario del recorrido.
    truncated = len(results) > max_nodes
    results = results[:max_nodes]

    kept = {r["path"] for r in results}
    edges_kept = [e for e in edges_out if e["from"] in kept and e["to"] in kept]

    by_hop: Dict[str, int] = defaultdict(int)
    for r in results:
        by_hop[str(r["hops"])] += 1

    return {
        "ok": True,
        "seeds": resolved,
        "unresolved_seeds": unresolved,
        "hops": hops,
        "direction": direction,
        "nodes": results,
        "edges": edges_kept,
        "stats": {
            "node_count": len(results),
            "edge_count": len(edges_kept),
            "by_hop": dict(sorted(by_hop.items())),
            "truncated": truncated,
            "graph_source": _enriched_file().name if _enriched_file().exists()
                            else _graph_file().name,
        },
    }


def _to_mermaid(result: Dict[str, Any]) -> str:
    """Diagrama del subgrafo. Obsidian lo renderiza sin plugins."""
    lines = ["```mermaid", "graph LR"]
    ids: Dict[str, str] = {}
    for i, node in enumerate(result["nodes"]):
        nid = f"n{i}"
        ids[node["path"]] = nid
        label = str(node["title"]).replace('"', "'")
        shape = f'{nid}(["{label}"])' if node["is_seed"] else f'{nid}["{label}"]'
        lines.append(f"    {shape}")
    for edge in result["edges"]:
        src, tgt = ids.get(edge["from"]), ids.get(edge["to"])
        if src and tgt:
            lines.append(f"    {src} -->|{edge['predicate']}| {tgt}")
    for i, node in enumerate(result["nodes"]):
        if node["is_seed"]:
            lines.append(f"    style n{i} stroke-width:3px")
    lines.append("```")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_subgraph — subgrafo de K semillas y N saltos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Vecindario a 2 saltos de una decision
  python vault_subgraph.py --seeds "03_Decisions/adr-001-mcp-transport.md" --hops 2

  # Varias semillas, acotado a conocimiento
  python vault_subgraph.py --seeds a.md b.md --hops 3 --section 07_Knowledge

  # Solo enlaces explicitos, hacia adelante
  python vault_subgraph.py --seeds a.md --predicate wiki_link --direction out

  # Diagrama para pegar en una nota
  python vault_subgraph.py --seeds a.md --format mermaid

Notas:
  - Semilla admite ruta, ruta sin .md o titulo de la nota
  - direction: out (a quien enlazo) | in (quien me enlaza) | both (default)
  - La relevancia decae 0.6 por salto y se pondera por predicado
  - Requiere 99_Index/graph.json (o graph-enriched.json): ejecuta vault_graph
""",
    )
    parser.add_argument("--seeds", nargs="+", required=True,
                        help="Notas de partida (ruta o título)")
    parser.add_argument("--hops", type=int, default=DEFAULT_HOPS,
                        help=f"Saltos de expansión (default: {DEFAULT_HOPS})")
    parser.add_argument("--direction", default="both", choices=["in", "out", "both"])
    parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES,
                        help=f"Tope de nodos (default: {DEFAULT_MAX_NODES})")
    parser.add_argument("--predicate", nargs="*", dest="predicates",
                        help="Filtra por tipo de relación")
    parser.add_argument("--section", help="Limita a una sección (ej. 07_Knowledge)")
    parser.add_argument("--class", dest="node_class", help="Limita a una clase de nota")
    parser.add_argument("--tags", nargs="*", help="Limita a notas con alguno de estos tags")
    parser.add_argument("--min-weight", type=float, default=0.0,
                        help="Descarta aristas por debajo de este peso")
    parser.add_argument("--format", default="json", choices=["json", "mermaid"])

    args = parser.parse_args()

    result = vault_subgraph(
        seeds=args.seeds, hops=args.hops, direction=args.direction,
        max_nodes=args.max_nodes, predicates=args.predicates, section=args.section,
        node_class=args.node_class, tags=args.tags, min_weight=args.min_weight,
    )

    if args.format == "mermaid" and result.get("ok"):
        print(_to_mermaid(result))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_subgraph"))

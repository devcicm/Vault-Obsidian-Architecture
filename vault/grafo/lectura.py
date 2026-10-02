"""El grafo que leen las consultas: el básico, con lo que solo sabe el enriquecido.

`graph.json` se refresca en cada escritura (AP-47) y `graph-enriched.json` solo
cuando alguien ejecuta `vault_graph_merge`. Las consultas elegían uno de los dos
cada una con su criterio —`vault_subgraph` el enriquecido si no era más viejo,
`vault_impact` siempre el enriquecido— y con cualquiera de los dos se perdía
algo: el básico no trae predicados tipados ni `class`, y el enriquecido viejo
no trae las notas escritas después (AP-57: un criterio, un dueño).

Aquí se decide una vez. La base es el básico, que es el que está al día; del
enriquecido se toman solo las aristas tipadas cuyos dos extremos siguen en la
base y la `class` de los nodos que siguen existiendo. Lo que se tomó y lo que
se descartó se publica en `overlay` (AP-37): una superposición parcial no se
presenta como completa.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .aristas import PREDICADO_WIKILINK, id_de_arista, predicado_de
from .repositorio import RepositorioGrafo

__all__ = ["grafo_para_consulta", "nodos_por_ruta", "superponer"]


def nodos_por_ruta(grafo: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """`nodes` como dict ruta → nodo: el grafo lo emite así, versiones viejas como lista."""
    nodes = grafo.get("nodes", {})
    if isinstance(nodes, dict):
        return nodes
    out: Dict[str, Dict[str, Any]] = {}
    for node in nodes:
        path = node.get("path") or node.get("id")
        if path:
            out[path] = node
    return out


def superponer(basico: Dict[str, Any], enriquecido: Dict[str, Any]) -> Dict[str, Any]:
    """El básico con las aristas tipadas y la `class` del enriquecido.

    Los wikilinks del enriquecido no se toman: el básico ya los tiene y los
    suyos son los del disco. Una arista tipada con un extremo que la base no
    conoce se descarta y se cuenta: apunta a una nota borrada o renombrada
    después del último `vault_graph_merge`.
    """
    nodes = {ruta: dict(nodo) for ruta, nodo in nodos_por_ruta(basico).items()}
    clases = 0
    for ruta, nodo in nodos_por_ruta(enriquecido).items():
        if ruta in nodes and "class" in nodo and "class" not in nodes[ruta]:
            nodes[ruta]["class"] = nodo["class"]
            clases += 1
    edges = list(basico.get("edges", []))
    vistas = {id_de_arista(e) for e in edges}
    tomadas = descartadas = 0
    for arista in enriquecido.get("edges", []):
        if predicado_de(arista) == PREDICADO_WIKILINK:
            continue
        if arista.get("from") not in nodes or arista.get("to") not in nodes:
            descartadas += 1
            continue
        if id_de_arista(arista) in vistas:
            continue
        vistas.add(id_de_arista(arista))
        edges.append(arista)
        tomadas += 1
    return {
        **basico,
        "nodes": nodes,
        "edges": edges,
        "overlay": {"applied": True, "typed_edges": tomadas,
                    "dropped_edges": descartadas, "classes": clases},
    }


def grafo_para_consulta(repo: RepositorioGrafo) -> Optional[Dict[str, Any]]:
    """El grafo de las consultas, o `None` si no hay ninguno.

    Un básico ilegible propaga su excepción: la tool que consulta la convierte
    en su error, como hacía. Un enriquecido ilegible no tumba la consulta —el
    básico basta—, pero se declara en `overlay`.
    """
    basico, enriquecido = Path(repo.grafo), Path(repo.grafo_enriquecido)
    if not basico.exists():
        if not enriquecido.exists():
            return None
        grafo = json.loads(enriquecido.read_text(encoding="utf-8"))
        return {**grafo, "overlay": {"applied": False, "reason": "graph_missing",
                                     "source": enriquecido.name}}
    grafo = json.loads(basico.read_text(encoding="utf-8"))
    if not enriquecido.exists():
        return {**grafo, "overlay": {"applied": False, "reason": "enriched_missing"}}
    try:
        extra = json.loads(enriquecido.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        return {**grafo, "overlay": {"applied": False, "reason": "enriched_unreadable",
                                     "error": f"{type(exc).__name__}: {exc}"}}
    if not isinstance(extra, dict):
        return {**grafo, "overlay": {"applied": False, "reason": "enriched_unreadable"}}
    return superponer(grafo, extra)

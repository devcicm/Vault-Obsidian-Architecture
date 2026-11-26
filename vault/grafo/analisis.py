"""Análisis estructural determinista del grafo del vault (stdlib puro).

Implementa de forma nativa —sin bases de datos, sin embeddings y sin librerías
externas como NetworkX o igraph— las capacidades de análisis estructural y
navegación de bajo consumo de tokens inspiradas en Graphify:

- Desglose epistémico de aristas (`EXTRACTED`, `INFERRED`, `AMBIGUOUS`).
- Detección de *God Nodes* (nodos hub de alta centralidad de grado).
- Detección determinista de comunidades/clústeres mediante *Label Propagation*
  ponderado y puentes entre comunidades.
- Consulta de camino más corto (`camino_mas_corto`, estilo `path`).
- Explicación compacta de vecindario (`explicar_nodo`, estilo `explain`).
- Reporte resumido `GRAPH_REPORT` en JSON y Markdown (`reporte_grafo`).
- Lector opcional de solo lectura para interoperar con `graphify-out/graph.json`.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from .aristas import (
    CONFIANZA_EPISTEMICA,
    clasificar_arista_epistemica,
    predicado_de,
)

__all__ = [
    "camino_mas_corto",
    "detectar_comunidades",
    "detectar_god_nodes",
    "explicar_nodo",
    "formatear_reporte_markdown",
    "importar_grafo_graphify",
    "reporte_grafo",
    "resumen_epistemico",
]

_PESO_PREDICADO_BASE: Dict[str, float] = {
    "wiki_link": 1.0,
    "related": 1.0,
    "supersedes": 1.0,
    "superseded_by": 1.0,
    "contradicts": 1.0,
    "depends_on": 0.9,
    "implements": 0.9,
    "decided_by": 0.9,
    "calls": 0.9,
    "imports": 0.9,
    "inherits": 0.9,
    "references": 0.8,
    "mentions": 0.6,
    "shared_tag": 0.4,
    "same_section": 0.2,
}


def _nodos_normalizados(grafo: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    raw = grafo.get("nodes", {})
    if isinstance(raw, dict):
        return raw
    out: Dict[str, Dict[str, Any]] = {}
    for nodo in raw or []:
        if not isinstance(nodo, dict):
            continue
        ruta = nodo.get("path") or nodo.get("id")
        if ruta:
            out[str(ruta)] = nodo
    return out


def _aristas_validas(
    grafo: Dict[str, Any],
    nodos: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    salida: List[Dict[str, Any]] = []
    for arista in grafo.get("edges", []) or []:
        if not isinstance(arista, dict):
            continue
        src = arista.get("from") or arista.get("source") or ""
        tgt = arista.get("to") or arista.get("target") or ""
        if not src or not tgt or tgt == "__deleted__":
            continue
        if src not in nodos or tgt not in nodos:
            continue
        etiqueta, confianza = clasificar_arista_epistemica(arista)
        salida.append({
            "from": str(src),
            "to": str(tgt),
            "predicate": predicado_de(arista),
            "epistemic": etiqueta,
            "confidence": confianza,
            "occurrences": int(arista.get("occurrences", 1) or 1),
        })
    return salida


def _resolver_nodo(referencia: str, nodos: Dict[str, Dict[str, Any]]) -> Optional[str]:
    ref = str(referencia or "").replace("\\", "/").strip()
    if not ref:
        return None
    if ref in nodos:
        return ref
    if f"{ref}.md" in nodos:
        return f"{ref}.md"
    low = ref.lower()
    for ruta in sorted(nodos):
        nodo = nodos[ruta]
        if ruta.lower() == low:
            return ruta
        if str(nodo.get("title", "")).lower() == low:
            return ruta
        if Path(ruta).stem.lower() == low:
            return ruta
    return None


def resumen_epistemico(aristas: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """Cuenta aristas por etiqueta epistémica (`EXTRACTED`, `INFERRED`, `AMBIGUOUS`)."""
    conteo = {k: 0 for k in CONFIANZA_EPISTEMICA}
    for arista in aristas:
        if not isinstance(arista, dict):
            continue
        etiqueta, _ = clasificar_arista_epistemica(arista)
        conteo[etiqueta] = conteo.get(etiqueta, 0) + 1
    return conteo


def _grados(
    nodos: Dict[str, Dict[str, Any]],
    aristas: List[Dict[str, Any]],
) -> Tuple[Dict[str, int], Dict[str, int]]:
    entrada: Dict[str, int] = {r: 0 for r in nodos}
    salida: Dict[str, int] = {r: 0 for r in nodos}
    for e in aristas:
        salida[e["from"]] = salida.get(e["from"], 0) + 1
        entrada[e["to"]] = entrada.get(e["to"], 0) + 1
    return entrada, salida


def detectar_god_nodes(
    grafo: Dict[str, Any],
    *,
    top_k: int = 10,
    min_degree: int = 2,
) -> List[Dict[str, Any]]:
    """Identifica los nodos hub (*God Nodes*) de mayor centralidad de grado.

    Calcula `in_degree`, `out_degree`, `total_degree`, participación relativa y
    `z_score` respecto al grado medio del grafo, ordenados de forma determinista.
    """
    nodos = _nodos_normalizados(grafo)
    if not nodos:
        return []
    aristas = _aristas_validas(grafo, nodos)
    entrada, salida = _grados(nodos, aristas)
    totales = {r: entrada[r] + salida[r] for r in nodos}
    valores = list(totales.values())
    media = sum(valores) / len(valores) if valores else 0.0
    varianza = sum((v - media) ** 2 for v in valores) / len(valores) if valores else 0.0
    desv = math.sqrt(varianza)
    denom_aristas = max(1, len(aristas))

    candidatos = []
    for ruta, deg in totales.items():
        if deg < min_degree:
            continue
        nodo = nodos[ruta]
        z = (deg - media) / desv if desv > 0 else 0.0
        candidatos.append({
            "path": ruta,
            "title": str(nodo.get("title", Path(ruta).stem)),
            "section": ruta.split("/", 1)[0] if "/" in ruta else "",
            "in_degree": entrada[ruta],
            "out_degree": salida[ruta],
            "total_degree": deg,
            "degree_share": round(deg / (2 * denom_aristas), 4),
            "z_score": round(z, 2),
            "is_outlier": deg > (media + desv) if desv > 0 else False,
        })

    candidatos.sort(key=lambda x: (-x["total_degree"], -x["in_degree"], x["path"]))
    return candidatos[: max(0, int(top_k))]


def detectar_comunidades(
    grafo: Dict[str, Any],
    *,
    max_iter: int = 20,
    top_communities: int = 15,
    top_bridges: int = 15,
) -> Dict[str, Any]:
    """Agrupa nodos en comunidades usando *Label Propagation* determinista.

    No usa aleatoriedad ni librerías externas: recorre nodos en orden léxico
    estable y desempata frecuencias por etiqueta más pequeña, garantizando
    resultados 100 % reproducibles. También reporta puentes entre comunidades.
    """
    nodos = _nodos_normalizados(grafo)
    if not nodos:
        return {
            "total_communities": 0,
            "isolated_nodes": 0,
            "communities": [],
            "node_to_community": {},
            "bridges": [],
        }

    aristas = _aristas_validas(grafo, nodos)
    vecinos: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    for e in aristas:
        if e["from"] == e["to"]:
            continue
        peso = _PESO_PREDICADO_BASE.get(e["predicate"], 0.5) * e["confidence"]
        vecinos[e["from"]].append((e["to"], peso))
        vecinos[e["to"]].append((e["from"], peso))

    etiqueta: Dict[str, str] = {ruta: ruta for ruta in sorted(nodos)}
    orden_nodos = sorted(nodos)

    for _ in range(max(1, int(max_iter))):
        cambios = 0
        for u in orden_nodos:
            ady = vecinos.get(u)
            if not ady:
                continue
            puntuaciones: Dict[str, float] = defaultdict(float)
            for v, peso in ady:
                puntuaciones[etiqueta[v]] += peso
            # Orden determinista: mayor peso total, desempate por etiqueta léxica
            mejor = min(
                puntuaciones.items(),
                key=lambda kv: (-round(kv[1], 6), kv[0]),
            )[0]
            if mejor != etiqueta[u]:
                etiqueta[u] = mejor
                cambios += 1
        if cambios == 0:
            break

    grupos_raw: Dict[str, List[str]] = defaultdict(list)
    for ruta in orden_nodos:
        grupos_raw[etiqueta[ruta]].append(ruta)

    entrada, salida = _grados(nodos, aristas)
    # Solo comunidades con >= 2 nodos se numeran como clústeres activos;
    # los nodos sin conexiones se contabilizan como aislados.
    activos = [m for m in grupos_raw.values() if len(m) >= 2]
    aislados = sum(1 for m in grupos_raw.values() if len(m) == 1)
    activos.sort(key=lambda m: (-len(m), m[0]))

    node_to_comm: Dict[str, str] = {}
    for idx, miembros in enumerate(activos, start=1):
        cid = f"C{idx}"
        for ruta in miembros:
            node_to_comm[ruta] = cid

    internas: Dict[str, int] = defaultdict(int)
    externas: Dict[str, int] = defaultdict(int)
    puentes_raw: List[Dict[str, Any]] = []

    for e in aristas:
        c_src = node_to_comm.get(e["from"])
        c_tgt = node_to_comm.get(e["to"])
        if c_src and c_tgt:
            if c_src == c_tgt:
                internas[c_src] += 1
            else:
                externas[c_src] += 1
                externas[c_tgt] += 1
                puentes_raw.append({
                    "from": e["from"],
                    "from_community": c_src,
                    "to": e["to"],
                    "to_community": c_tgt,
                    "predicate": e["predicate"],
                    "epistemic": e["epistemic"],
                    "confidence": e["confidence"],
                })

    comunidades: List[Dict[str, Any]] = []
    for idx, miembros in enumerate(activos[: max(0, int(top_communities))], start=1):
        cid = f"C{idx}"
        secciones = Counter(r.split("/", 1)[0] if "/" in r else "root" for r in miembros)
        sec_dom = secciones.most_common(1)[0][0]
        hub = min(
            miembros,
            key=lambda r: (-(entrada[r] + salida[r]), -entrada[r], r),
        )
        ie = internas[cid]
        ee = externas[cid]
        cohesion = round(ie / (ie + ee), 3) if (ie + ee) > 0 else 0.0
        comunidades.append({
            "community_id": cid,
            "size": len(miembros),
            "dominant_section": sec_dom,
            "hub_node": hub,
            "hub_title": str(nodos[hub].get("title", Path(hub).stem)),
            "internal_edges": ie,
            "external_edges": ee,
            "cohesion": cohesion,
            "sample_members": miembros[:8],
        })

    puentes_raw.sort(
        key=lambda b: (-b["confidence"], b["from_community"], b["to_community"], b["from"], b["to"])
    )

    return {
        "total_communities": len(activos),
        "isolated_nodes": aislados,
        "communities": comunidades,
        "node_to_community": node_to_comm,
        "bridges": puentes_raw[: max(0, int(top_bridges))],
    }


def camino_mas_corto(
    grafo: Dict[str, Any],
    origen: str,
    destino: str,
    *,
    direction: str = "both",
    predicates: Optional[Set[str]] = None,
    resolver: Optional[Callable[[str, Dict[str, Dict[str, Any]]], Optional[str]]] = None,
) -> Dict[str, Any]:
    """Encuentra el camino más corto en saltos entre dos nodos del grafo (estilo `path`)."""
    nodos = _nodos_normalizados(grafo)
    res_fn = resolver or _resolver_nodo
    src_path = res_fn(origen, nodos)
    tgt_path = res_fn(destino, nodos)
    if not src_path or not tgt_path:
        faltantes = [x for x, r in ((origen, src_path), (destino, tgt_path)) if not r]
        return {
            "ok": False,
            "error_code": "NO_SEEDS_RESOLVED",
            "error": f"No se resolvieron los nodos en el grafo: {faltantes}",
            "unresolved": faltantes,
        }

    if src_path == tgt_path:
        return {
            "ok": True,
            "mode": "path",
            "found": True,
            "from": src_path,
            "to": tgt_path,
            "direction": direction,
            "hops": 0,
            "nodes": [src_path],
            "edges": [],
            "trace": src_path,
        }

    aristas = _aristas_validas(grafo, nodos)
    adj: Dict[str, List[Tuple[str, Dict[str, Any]]]] = defaultdict(list)
    for e in aristas:
        if predicates and e["predicate"] not in predicates:
            continue
        if direction in ("out", "both"):
            adj[e["from"]].append((e["to"], e))
        if direction in ("in", "both"):
            adj[e["to"]].append((e["from"], e))

    # Orden determinista por peso descendente y destino léxico
    for u in adj:
        adj[u].sort(
            key=lambda item: (
                -_PESO_PREDICADO_BASE.get(item[1]["predicate"], 0.5),
                item[0],
                item[1]["predicate"],
            )
        )

    visitados: Set[str] = {src_path}
    previo: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    cola: deque[str] = deque([src_path])
    hallado = False

    while cola:
        actual = cola.popleft()
        if actual == tgt_path:
            hallado = True
            break
        for sig, arista in adj.get(actual, []):
            if sig in visitados:
                continue
            visitados.add(sig)
            previo[sig] = (actual, arista)
            if sig == tgt_path:
                hallado = True
                break
            cola.append(sig)
        if hallado:
            break

    if not hallado:
        return {
            "ok": True,
            "mode": "path",
            "found": False,
            "from": src_path,
            "to": tgt_path,
            "direction": direction,
            "hops": None,
            "nodes": [],
            "edges": [],
            "trace": "",
        }

    ruta_nodos: List[str] = [tgt_path]
    ruta_aristas: List[Dict[str, Any]] = []
    cur = tgt_path
    while cur != src_path:
        ant, arista = previo[cur]
        ruta_nodos.append(ant)
        ruta_aristas.append(arista)
        cur = ant
    ruta_nodos.reverse()
    ruta_aristas.reverse()

    partes_traza = [ruta_nodos[0]]
    for idx, ar in enumerate(ruta_aristas):
        partes_traza.append(f"--[{ar['predicate']}|{ar['epistemic']}]-->")
        partes_traza.append(ruta_nodos[idx + 1])

    return {
        "ok": True,
        "mode": "path",
        "found": True,
        "from": src_path,
        "to": tgt_path,
        "direction": direction,
        "hops": len(ruta_aristas),
        "nodes": ruta_nodos,
        "edges": ruta_aristas,
        "trace": " ".join(partes_traza),
    }


def explicar_nodo(
    grafo: Dict[str, Any],
    objetivo: str,
    *,
    max_neighbors: int = 15,
    resolver: Optional[Callable[[str, Dict[str, Dict[str, Any]]], Optional[str]]] = None,
) -> Dict[str, Any]:
    """Ficha compacta de un nodo: grado, comunidad, god-node y vecindario epistémico."""
    nodos = _nodos_normalizados(grafo)
    res_fn = resolver or _resolver_nodo
    ruta = res_fn(objetivo, nodos)
    if not ruta:
        return {
            "ok": False,
            "error_code": "NO_SEEDS_RESOLVED",
            "error": f"No se encontró el nodo en el grafo: '{objetivo}'",
            "unresolved": [objetivo],
        }

    aristas = _aristas_validas(grafo, nodos)
    god_nodes = detectar_god_nodes(grafo, top_k=15)
    god_paths = {g["path"] for g in god_nodes}
    com_info = detectar_comunidades(grafo, top_communities=len(nodos), top_bridges=0)
    node_to_comm = com_info["node_to_community"]
    cid = node_to_comm.get(ruta)
    comm_obj = next(
        (c for c in com_info["communities"] if c["community_id"] == cid),
        None,
    )

    entrantes = [e for e in aristas if e["to"] == ruta]
    salientes = [e for e in aristas if e["from"] == ruta]
    entrantes.sort(key=lambda e: (-e["confidence"], e["from"], e["predicate"]))
    salientes.sort(key=lambda e: (-e["confidence"], e["to"], e["predicate"]))

    vecinos_ep = resumen_epistemico(entrantes + salientes)
    cruces = [
        {
            "direction": "out" if e["from"] == ruta else "in",
            "peer": e["to"] if e["from"] == ruta else e["from"],
            "peer_community": node_to_comm.get(e["to"] if e["from"] == ruta else e["from"]),
            "predicate": e["predicate"],
            "epistemic": e["epistemic"],
        }
        for e in (salientes + entrantes)
        if cid and node_to_comm.get(e["to"] if e["from"] == ruta else e["from"]) not in (None, cid)
    ]

    meta = nodos[ruta]
    return {
        "ok": True,
        "mode": "explain",
        "node": {
            "path": ruta,
            "title": str(meta.get("title", Path(ruta).stem)),
            "section": ruta.split("/", 1)[0] if "/" in ruta else "",
            "status": meta.get("status", ""),
            "tags": meta.get("tags", []) or [],
            "in_degree": len(entrantes),
            "out_degree": len(salientes),
            "total_degree": len(entrantes) + len(salientes),
            "is_god_node": ruta in god_paths,
        },
        "community": comm_obj,
        "epistemic_breakdown": vecinos_ep,
        "incoming": [
            {
                "from": e["from"],
                "title": str(nodos[e["from"]].get("title", Path(e["from"]).stem)),
                "predicate": e["predicate"],
                "epistemic": e["epistemic"],
                "confidence": e["confidence"],
            }
            for e in entrantes[: max(0, int(max_neighbors))]
        ],
        "outgoing": [
            {
                "to": e["to"],
                "title": str(nodos[e["to"]].get("title", Path(e["to"]).stem)),
                "predicate": e["predicate"],
                "epistemic": e["epistemic"],
                "confidence": e["confidence"],
            }
            for e in salientes[: max(0, int(max_neighbors))]
        ],
        "cross_community_links": cruces[: max(0, int(max_neighbors))],
        "truncated": {
            "incoming": len(entrantes) > max_neighbors,
            "outgoing": len(salientes) > max_neighbors,
        },
    }


def reporte_grafo(
    grafo: Dict[str, Any],
    *,
    top_god_nodes: int = 10,
    top_communities: int = 10,
    top_bridges: int = 10,
) -> Dict[str, Any]:
    """Genera un resumen estructural compacto (estilo `GRAPH_REPORT.md`)."""
    nodos = _nodos_normalizados(grafo)
    aristas = _aristas_validas(grafo, nodos)
    god_nodes = detectar_god_nodes(grafo, top_k=top_god_nodes)
    comunidades = detectar_comunidades(
        grafo,
        top_communities=top_communities,
        top_bridges=top_bridges,
    )
    return {
        "ok": True,
        "mode": "report",
        "summary": {
            "total_nodes": len(nodos),
            "total_edges": len(aristas),
            "epistemic": resumen_epistemico(aristas),
            "total_communities": comunidades["total_communities"],
            "isolated_nodes": comunidades["isolated_nodes"],
            "god_nodes_count": len(god_nodes),
            "bridges_count": len(comunidades["bridges"]),
        },
        "god_nodes": god_nodes,
        "communities": comunidades["communities"],
        "bridges": comunidades["bridges"],
    }


def formatear_reporte_markdown(reporte: Dict[str, Any]) -> str:
    """Renderiza `reporte_grafo()` en Markdown compacto (bajo consumo de tokens)."""
    s = reporte.get("summary", {})
    ep = s.get("epistemic", {})
    lines = [
        "# Reporte Estructural del Grafo (GRAPH_REPORT)",
        "",
        f"- **Nodos:** {s.get('total_nodes', 0)} · **Aristas activas:** {s.get('total_edges', 0)} · "
        f"**Comunidades:** {s.get('total_communities', 0)} · **Aislados:** {s.get('isolated_nodes', 0)}",
        f"- **Confianza epistémica:** `EXTRACTED`={ep.get('EXTRACTED', 0)} · "
        f"`INFERRED`={ep.get('INFERRED', 0)} · `AMBIGUOUS`={ep.get('AMBIGUOUS', 0)}",
        "",
        "## God Nodes (hubs estructurales)",
        "",
        "| Nodo | Sección | Grado (in/out) | Share | Outlier |",
        "|---|---|---:|---:|---|",
    ]
    for g in reporte.get("god_nodes", []):
        lines.append(
            f"| `{g['path']}` | {g['section']} | **{g['total_degree']}** "
            f"({g['in_degree']}/{g['out_degree']}) | {g['degree_share']:.2%} | "
            f"{'sí' if g['is_outlier'] else 'no'} |"
        )
    if not reporte.get("god_nodes"):
        lines.append("| _(ninguno con grado >= 2)_ | — | 0 | 0% | — |")

    lines += [
        "",
        "## Comunidades (Label Propagation determinista)",
        "",
        "| ID | Tamaño | Sección dominante | Hub | Cohesión |",
        "|---|---:|---|---|---:|",
    ]
    for c in reporte.get("communities", []):
        lines.append(
            f"| {c['community_id']} | {c['size']} | `{c['dominant_section']}` | "
            f"`{c['hub_node']}` | {c['cohesion']:.2f} |"
        )
    if not reporte.get("communities"):
        lines.append("| _(sin comunidades de tamaño >= 2)_ | 0 | — | — | 0.00 |")

    bridges = reporte.get("bridges", [])
    if bridges:
        lines += [
            "",
            "## Puentes entre comunidades",
            "",
            "| Origen | Destino | Predicado | Epistémica |",
            "|---|---|---|---|",
        ]
        for b in bridges:
            lines.append(
                f"| `{b['from']}` ({b['from_community']}) | `{b['to']}` ({b['to_community']}) | "
                f"`{b['predicate']}` | `{b['epistemic']}` |"
            )

    return "\n".join(lines) + "\n"


def importar_grafo_graphify(ruta_json: Path) -> Dict[str, Any]:
    """Lee un `graphify-out/graph.json` (NetworkX node-link) en solo lectura.

    Permite interoperar opcionalmente con proyectos que ya generan un grafo de
    Graphify (40+ lenguajes vía Tree-sitter) sin convertirlo en dependencia.
    """
    ruta = Path(ruta_json)
    bruto = json.loads(ruta.read_text(encoding="utf-8"))
    raw_nodes = bruto.get("nodes", [])
    raw_edges = bruto.get("links") or bruto.get("edges") or []

    nodes: Dict[str, Dict[str, Any]] = {}
    for n in raw_nodes:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or n.get("path") or "").strip()
        if not nid:
            continue
        nodes[nid] = {
            "title": str(n.get("label") or n.get("name") or n.get("title") or nid),
            "type": str(n.get("type") or n.get("kind") or "external"),
            "file": str(n.get("file") or n.get("source_file") or ""),
            "tags": list(n.get("tags", [])) if isinstance(n.get("tags"), list) else [],
            "status": "active",
        }

    edges: List[Dict[str, Any]] = []
    for e in raw_edges:
        if not isinstance(e, dict):
            continue
        src = str(e.get("source") or e.get("from") or "").strip()
        tgt = str(e.get("target") or e.get("to") or "").strip()
        if not src or not tgt:
            continue
        etiqueta_raw = str(e.get("confidence_label") or e.get("epistemic") or "").upper()
        conf_val = e.get("confidence")
        arista = {
            "from": src,
            "to": tgt,
            "predicate": str(e.get("relation") or e.get("predicate") or e.get("type") or "related"),
            **({"epistemic": etiqueta_raw} if etiqueta_raw in CONFIANZA_EPISTEMICA else {}),
            **({"confidence": float(conf_val)} if isinstance(conf_val, (int, float)) else {}),
        }
        etiqueta, confianza = clasificar_arista_epistemica(arista)
        arista["epistemic"] = etiqueta
        arista["confidence"] = confianza
        edges.append(arista)

    return {
        "nodes": nodes,
        "edges": edges,
        "source_format": "graphify",
        "stats": {
            "totalNodes": len(nodes),
            "totalEdges": len(edges),
            "epistemic": resumen_epistemico(edges),
        },
    }

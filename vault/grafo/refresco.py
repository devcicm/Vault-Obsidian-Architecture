"""El grafo de wikilinks, nota a nota (AP-47).

`graph.json` solo lo escribía `vault_graph` recorriendo el vault entero, así que
una nota escrita por cualquier tool no existía para `vault_subgraph` hasta la
siguiente reconstrucción. Aquí vive lo que la reconstrucción y el refresco de
una nota comparten —el nodo y el ensamblado del grafo—, para que no puedan
discrepar sobre qué es `graph.json` (AP-57), y el servicio que refresca una nota.

El refresco no lee más nota que la escrita. Los nodos guardan `aliases` y
`links`, que es todo lo que la resolución necesita: con ellos se repite en
memoria para el vault entero, y por eso una nota nueva arregla los enlaces rotos
de otras que no se vuelven a leer, y una homónima vuelve ambiguo un enlace que
antes resolvía (AP-17). Leer y resolver son del dueño del escaneo
(`vault_lib.leer_notas_de_grafo` / `resolver_enlaces`), que se inyecta: este
paquete no importa `scripts/`.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List

from ..kernel.enumeracion import es_nota_indexable
from ..kernel.fallos import FalloDeDominio
from .aristas import consolidar_aristas
from .repositorio import RepositorioGrafo

#: El tipo de las aristas que salen de un wikilink. Las demás (`deleted-node`)
#: las añade la reconstrucción comparando con el grafo anterior, y el refresco
#: las conserva tal cual.
TIPO_WIKILINK = "wiki-link"

PISTA_RECONSTRUIR = "python scripts/vault_graph.py"


def nodo_de_nota(rel: str, nota: Dict[str, Any]) -> Dict[str, Any]:
    """El nodo de `graph.json` para una nota leída por `leer_notas_de_grafo`."""
    return {
        "title": nota["title"],
        "type": rel.split("/")[0] if "/" in rel else "other",
        "tags": nota["tags"],
        "aliases": nota["aliases"],
        "links": nota["links"],
        "linkCount": len(nota["links"]),
        "status": "active",
    }


def ensamblar_grafo(
    nodes: Dict[str, Dict[str, Any]],
    resuelto: Dict[str, Any],
    extras: List[Dict[str, Any]],
    colisiones: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """`graph.json` a partir de los nodos y de su resolución.

    Una arista por relación (`consolidar_aristas`); huérfana es la nota sin
    entrantes fuera de `00_System/`; `extras` se añade después de contar
    huérfanas, como hacía la reconstrucción.
    """
    edges = consolidar_aristas(
        [{"from": a["from"], "to": a["to"], "type": TIPO_WIKILINK} for a in resuelto["aristas"]]
    )
    entrantes: Dict[str, List[str]] = defaultdict(list)
    for edge in edges:
        entrantes[edge["to"]].append(edge["from"])
    orphans = [
        {"path": path, "title": node["title"], "type": node["type"]}
        for path, node in nodes.items()
        if path not in entrantes and not path.startswith("00_System/")
    ]
    edges = edges + list(extras)
    broken_links = resuelto["rotos"]
    ambiguous_links = resuelto["ambiguos"]
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "totalNodes": len(nodes),
            "totalEdges": len(edges),
            "orphanNotes": len(orphans),
            "brokenLinks": len(broken_links),
            "ambiguousLinks": len(ambiguous_links),
            "nameCollisions": len(colisiones),
            "deletedNodes": sum(1 for n in nodes.values() if n.get("status") == "deleted"),
            "movedNodes": sum(1 for n in nodes.values() if n.get("status") == "moved"),
        },
        "orphans": orphans,
        "brokenLinks": broken_links,
        "ambiguousLinks": ambiguous_links,
        "nameCollisions": colisiones,
    }


class ServicioRefrescoGrafo:
    """Pone UNA nota en `graph.json` con el criterio de la reconstrucción."""

    def __init__(
        self,
        repo: RepositorioGrafo,
        leer_notas: Callable[[Dict[str, str]], Dict[str, Dict[str, Any]]],
        resolver: Callable[[Dict[str, Dict[str, Any]]], Dict[str, Any]],
        colisiones: Callable[[List[str]], List[Dict[str, Any]]],
    ) -> None:
        self._repo = repo
        self._leer_notas = leer_notas
        self._resolver = resolver
        self._colisiones = colisiones

    def refrescar(self, ruta: Path, *mas: Path) -> Dict[str, Any]:
        """Inserta, sustituye o retira las notas y repite la resolución en memoria.

        `mas` son notas que cambiaron en la misma escritura sin pasar por el
        gancho —los `index.md` que regenera el índice de sección—: van en la
        misma lectura y escritura del grafo.

        No crea el grafo: sin `graph.json` no hay nada que refrescar y una
        reconstrucción a medias no sería el grafo del vault. Un grafo sin
        `aliases` en sus nodos (anterior a este refresco) tampoco se toca:
        resolver con él perdería los alias de las notas que no se leen, y eso
        se declara en vez de adivinarse (AP-37). Uno ilegible levanta
        `FalloDeDominio("INDICE_ILEGIBLE")`.
        """
        repo = self._repo
        secciones = repo.ctx.secciones.ordenadas()
        # `resolve()`: en Windows una ruta corta 8.3 (`CARLOS~1`) no es relativa
        # a la raíz resuelta, y la nota se daba por «no nota» sin error.
        rutas = [Path(r).resolve() for r in (ruta, *mas)]
        if not es_nota_indexable(rutas[0], repo.raiz, secciones):
            return {"ok": True, "refreshed": False, "reason": "not_a_note"}
        rutas = [r for r in rutas if es_nota_indexable(r, repo.raiz, secciones)]
        destino = repo.grafo
        with repo.ctx.escritor.bloquear(destino):
            try:
                grafo = json.loads(repo.ctx.lector.leer(destino))
            except FileNotFoundError:
                return {"ok": True, "refreshed": False, "reason": "graph_missing",
                        "hint": PISTA_RECONSTRUIR}
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                # Ilegible no es ausente: refrescar sobre un grafo vacío
                # escribiría uno con una sola nota encima del que hay (AP-52:
                # el dominio nombra la causa; el envelope lo escribe la tool).
                raise FalloDeDominio(
                    "INDICE_ILEGIBLE",
                    f"graph.json no se puede leer como JSON: {type(exc).__name__}: {exc}",
                    path=repo.relativa(destino), hint=PISTA_RECONSTRUIR,
                ) from exc
            nodes = grafo.get("nodes") if isinstance(grafo, dict) else None
            if not isinstance(nodes, dict) or any(
                not isinstance(n, dict) or "aliases" not in n or "links" not in n
                for n in nodes.values()
            ):
                return {"ok": True, "refreshed": False, "reason": "graph_without_aliases",
                        "hint": PISTA_RECONSTRUIR}
            for r in rutas:
                rel = repo.relativa(r)
                if repo.ctx.lector.existe(r):
                    contenido = repo.ctx.lector.leer(r)
                    nodes[rel] = nodo_de_nota(rel, self._leer_notas({rel: contenido})[rel])
                else:
                    nodes.pop(rel, None)
            resuelto = self._resolver(nodes)
            extras = [e for e in grafo.get("edges", []) if e.get("type") != TIPO_WIKILINK]
            repo.ctx.escritor.escribir_json(
                destino, ensamblar_grafo(nodes, resuelto, extras, self._colisiones(list(nodes)))
            )
        return {"ok": True, "refreshed": True, "path": repo.relativa(rutas[0]),
                "paths": [repo.relativa(r) for r in rutas]}

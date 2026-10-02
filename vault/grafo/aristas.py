"""Identidad de una arista del grafo: `(from, predicate, to)`.

Una arista es una relación entre dos notas, no una aparición del enlace. Los
productores del grafo añadían una por cada `[[…]]` escrito, así que tres
menciones eran tres aristas iguales y `totalEdges` contaba apariciones. Aquí se
declara una vez qué hace a dos aristas la misma, para que los dos productores
—`vault_graph` y `vault_graph_merge`— no lo decidan cada uno por su cuenta
(AP-57).
"""

from typing import Any, Dict, Iterable, List

__all__ = [
    "PREDICADO_WIKILINK",
    "TIPO_WIKILINK",
    "consolidar_aristas",
    "id_de_arista",
    "predicado_de",
]

#: El wikilink tiene dos nombres: `graph.json` escribe `type: "wiki-link"`
#: (legacy, lo leen los consumidores y no se reescribe) y `graph-enriched.json`
#: `predicate: "wiki_link"`. Quien consulta el grafo los lee con `predicado_de`.
TIPO_WIKILINK = "wiki-link"
PREDICADO_WIKILINK = "wiki_link"
_TIPOS_LEGACY = {TIPO_WIKILINK: PREDICADO_WIKILINK}


def predicado_de(arista: Dict[str, Any]) -> str:
    """El predicado canónico de una arista de cualquiera de los dos grafos (AP-57).

    Las consultas leían `predicate or type` sin traducir: sobre `graph.json`
    la tabla de pesos no encontraba `wiki-link` y un filtro por `wiki_link`
    devolvía vacío. Un `type` que no es legacy pasa tal cual (`deleted-node`).
    """
    predicado = arista.get("predicate") or arista.get("type") or PREDICADO_WIKILINK
    return _TIPOS_LEGACY.get(predicado, predicado)

# Lo que identifica a la arista y lo que cuenta sus apariciones: ninguno de
# los dos es un atributo que pueda variar entre declaraciones.
_CAMPOS_DE_IDENTIDAD = ("id", "from", "to", "predicate", "type", "occurrences", "variants")


def id_de_arista(arista: Dict[str, Any]) -> str:
    """`from|predicate|to`. `type` es el nombre legacy del predicado en graph.json."""
    predicado = arista.get("predicate") or arista.get("type") or ""
    return f"{arista.get('from', '')}|{predicado}|{arista.get('to', '')}"


def consolidar_aristas(aristas: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Una arista por relación, en el orden de su primera aparición.

    `occurrences` cuenta cuántas veces se escribió. Si una declaración repetida
    trae otro valor en un atributo (`label`, `cardinality`, `project`…), lo
    distinto se guarda en `variants` —una entrada por combinación, sin
    repetir—: quedarse con la primera en silencio es perder lo que otro
    fichero de relaciones afirmó. No se llama `weight` porque `vault_subgraph`
    ya usa ese nombre para el peso del predicado.

    Es idempotente: consolidar aristas ya consolidadas suma sus `occurrences`
    y une sus `variants`, así que un productor puede consolidar por fuente y
    después el conjunto.
    """
    unicas: Dict[str, Dict[str, Any]] = {}
    for arista in aristas:
        ident = id_de_arista(arista)
        previa = unicas.get(ident)
        if previa is None:
            unicas[ident] = {"id": ident, **arista, "occurrences": arista.get("occurrences", 1)}
            if "variants" in arista:
                unicas[ident]["variants"] = list(arista["variants"])
            continue
        previa["occurrences"] += arista.get("occurrences", 1)
        distinto = {
            k: v for k, v in arista.items()
            if k not in _CAMPOS_DE_IDENTIDAD and previa.get(k) != v
        }
        for variante in ([distinto] if distinto else []) + list(arista.get("variants", [])):
            if variante not in previa.setdefault("variants", []):
                previa["variants"].append(variante)
    return list(unicas.values())


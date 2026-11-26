"""Identidad de una arista del grafo: `(from, predicate, to)`.

Una arista es una relación entre dos notas, no una aparición del enlace. Los
productores del grafo añadían una por cada `[[…]]` escrito, así que tres
menciones eran tres aristas iguales y `totalEdges` contaba apariciones. Aquí se
declara una vez qué hace a dos aristas la misma, para que los dos productores
—`vault_graph` y `vault_graph_merge`— no lo decidan cada uno por su cuenta
(AP-57).
"""

from typing import Any, Dict, Iterable, List, Tuple

__all__ = [
    "CONFIANZA_EPISTEMICA",
    "PREDICADO_WIKILINK",
    "TIPO_WIKILINK",
    "clasificar_arista_epistemica",
    "consolidar_aristas",
    "estampar_epistemica",
    "id_de_arista",
    "predicado_de",
]

#: El wikilink tiene dos nombres: `graph.json` escribe `type: "wiki-link"`
#: (legacy, lo leen los consumidores y no se reescribe) y `graph-enriched.json`
#: `predicate: "wiki_link"`. Quien consulta el grafo los lee con `predicado_de`.
TIPO_WIKILINK = "wiki-link"
PREDICADO_WIKILINK = "wiki_link"
_TIPOS_LEGACY = {TIPO_WIKILINK: PREDICADO_WIKILINK}

#: Vocabulario cerrado de confianza epistémica por arista (AP-45 / AP-31):
#: EXTRACTED (evidencia explícita en markdown o AST, confianza 1.0),
#: INFERRED (relación deducida por contexto/co-ocurrencia, 0.70–0.90),
#: AMBIGUOUS (relación sugerida o predicado no reconocido, < 0.70).
CONFIANZA_EPISTEMICA: Tuple[str, ...] = ("EXTRACTED", "INFERRED", "AMBIGUOUS")

_PREDICADOS_EXTRACTED = frozenset({
    "wiki_link",
    "related",
    "supersedes",
    "superseded_by",
    "contradicts",
    "depends_on",
    "implements",
    "decided_by",
    "references",
    "calls",
    "imports",
    "inherits",
    "defines",
    "contains",
    "tests",
    "mitigates",
    "triggers",
    "owns",
    "produces",
    "consumes",
    "deleted-node",
})

_CONFIANZA_INFERRED: Dict[str, float] = {
    "mentions": 0.8,
    "shared_tag": 0.75,
    "similar_to": 0.75,
    "co_occurs": 0.72,
    "same_section": 0.7,
}


def clasificar_arista_epistemica(arista: Dict[str, Any]) -> Tuple[str, float]:
    """Devuelve `(etiqueta, confianza)` en `CONFIANZA_EPISTEMICA` para una arista (AP-80).

    Si la arista ya trae un sello epistémico válido y confianza numérica en
    `[0.0, 1.0]`, se preserva. En caso contrario se deriva de forma determinista
    desde el predicado canónico sin inventar evidencia (AP-45, AP-80).
    """
    existente = arista.get("epistemic")
    conf_raw = arista.get("confidence")
    if (
        isinstance(existente, str)
        and existente in CONFIANZA_EPISTEMICA
        and isinstance(conf_raw, (int, float))
        and not isinstance(conf_raw, bool)
        and 0.0 <= float(conf_raw) <= 1.0
    ):
        return existente, round(float(conf_raw), 2)

    pred = predicado_de(arista)
    if pred in _PREDICADOS_EXTRACTED:
        return "EXTRACTED", 1.0
    if pred in _CONFIANZA_INFERRED:
        return "INFERRED", _CONFIANZA_INFERRED[pred]
    if isinstance(conf_raw, (int, float)) and not isinstance(conf_raw, bool):
        c = max(0.0, min(1.0, float(conf_raw)))
        if c >= 0.95:
            return "EXTRACTED", round(c, 2)
        if c >= 0.7:
            return "INFERRED", round(c, 2)
        return "AMBIGUOUS", round(c, 2)
    return "AMBIGUOUS", 0.5


def estampar_epistemica(arista: Dict[str, Any]) -> Dict[str, Any]:
    """Devuelve una copia de la arista con `epistemic` y `confidence` canónicos."""
    etiqueta, confianza = clasificar_arista_epistemica(arista)
    if arista.get("epistemic") == etiqueta and arista.get("confidence") == confianza:
        return dict(arista)
    return {**arista, "epistemic": etiqueta, "confidence": confianza}


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
_CAMPOS_DE_IDENTIDAD = (
    "id", "from", "to", "predicate", "type",
    "occurrences", "variants", "epistemic", "confidence",
)


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
        etiqueta, confianza = clasificar_arista_epistemica(arista)
        previa = unicas.get(ident)
        if previa is None:
            unicas[ident] = {
                "id": ident,
                **arista,
                "epistemic": etiqueta,
                "confidence": confianza,
                "occurrences": arista.get("occurrences", 1),
            }
            if "variants" in arista:
                unicas[ident]["variants"] = list(arista["variants"])
            continue
        previa["occurrences"] += arista.get("occurrences", 1)
        if confianza > previa.get("confidence", 0.0):
            previa["epistemic"] = etiqueta
            previa["confidence"] = confianza
        distinto = {
            k: v for k, v in arista.items()
            if k not in _CAMPOS_DE_IDENTIDAD and previa.get(k) != v
        }
        for variante in ([distinto] if distinto else []) + list(arista.get("variants", [])):
            if variante not in previa.setdefault("variants", []):
                previa["variants"].append(variante)
    return list(unicas.values())


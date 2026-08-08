"""Coste algorítmico del recorrido de grafo y de la recursión sobre dato externo.

El estándar recorre grafos y parsea frontmatter arbitrario, y las dos cosas son
recursivas. Este módulo fija las tres condiciones que hacen que eso termine:

1. **El invariante de terminación del BFS.** `vault_subgraph` no lleva conjunto
   de visitados: reencola un nodo cuando lo alcanza por un camino mejor. Termina
   solo porque `peso * HOP_DECAY <= 1` hace que dar la vuelta a un ciclo nunca
   mejore lo ya visto. Subir un peso por encima de `1 / HOP_DECAY` —un cambio que
   parece de calibración— convierte una consulta en un cuelgue. Medido: con peso
   1.6 el recorrido encola 59 a hops 4, 8 y 12; con 1.7, encola 125/365/605.

2. **El coste real del recorrido.** Es O(V+E) por consulta y `max_nodes` recorta
   la SALIDA, no el trabajo. Se fija como característica medida, no como
   promesa: quien documente `max_nodes` como si abaratara la consulta miente.

3. **La pila frente a dato externo.** El parser de PyYAML es recursivo y el
   frontmatter lo escribe cualquiera. Una nota con `x: [[[[…` y 500 corchetes
   desbordaba la pila dentro de `safe_load` y mataba la auditoría del vault
   entero, no la lectura de esa nota.
"""

import collections
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import vault_lib  # noqa: E402
import vault_subgraph as VS  # noqa: E402


# ── 1. El invariante de terminación ──────────────────────────────────────────


def test_ningun_peso_rompe_la_terminacion_del_bfs():
    """Todo peso publicado respeta `peso * HOP_DECAY <= 1`."""
    tope = 1.0 / VS.HOP_DECAY
    culpables = {
        p: w for p, w in VS.PREDICATE_WEIGHT.items() if w * VS.HOP_DECAY > 1.0
    }
    assert not culpables, (
        f"pesos por encima del tope {tope:.4f}: {culpables}. Con uno de estos, "
        "recorrer un ciclo mejora la relevancia y el BFS crece exponencialmente "
        "con --hops."
    )
    assert VS.DEFAULT_WEIGHT * VS.HOP_DECAY <= 1.0


def test_el_invariante_se_comprueba_al_importar():
    """El guard no es decorativo: un peso malo hace fallar la comprobación."""
    original = dict(VS.PREDICATE_WEIGHT)
    try:
        VS.PREDICATE_WEIGHT["wiki_link"] = 1.0 / VS.HOP_DECAY + 0.1
        with pytest.raises(ValueError, match="invariante de terminación"):
            VS._check_hop_decay_invariant()
    finally:
        VS.PREDICATE_WEIGHT.clear()
        VS.PREDICATE_WEIGHT.update(original)
    VS._check_hop_decay_invariant()  # restaurado, vuelve a pasar


def test_el_peso_nunca_lo_pone_la_arista():
    """El invariante cubre todo el recorrido porque el peso sale de la tabla.

    Si `_adjacency` leyera `edge["weight"]`, un grafo con una arista de peso 5
    saltaría el invariante sin tocar `PREDICATE_WEIGHT`.
    """
    grafo = {
        "nodes": [{"path": "07_K/a.md"}, {"path": "07_K/b.md"}],
        "edges": [{"from": "07_K/a.md", "to": "07_K/b.md",
                   "predicate": "wiki_link", "weight": 99.0}],
    }
    adj = VS._adjacency(grafo, "out", None)
    (_, _, peso), = adj["07_K/a.md"]
    assert peso == VS.PREDICATE_WEIGHT["wiki_link"], (
        "el peso de la arista del fichero se coló en el recorrido"
    )


# ── 2. El coste del recorrido ────────────────────────────────────────────────


def _grafo_ciclico(n):
    """Anillo con cuerdas: todos los nodos en un ciclo, densidad controlada."""
    nodes = [{"path": f"07_K/n{i}.md", "title": f"n{i}", "class": "note",
              "status": "active", "tags": []} for i in range(n)]
    edges = []
    for i in range(n):
        for salto in (1, 7):
            j = (i + salto) % n
            edges.append({"from": f"07_K/n{i}.md", "to": f"07_K/n{j}.md",
                          "predicate": "wiki_link"})
    return {"nodes": nodes, "edges": edges}


def _grafo_mixto(n, semilla=0):
    """Como el anillo, pero con predicados de peso distinto en cada arista."""
    import random

    r = random.Random(semilla)
    predicados = list(VS.PREDICATE_WEIGHT)
    nodes = [{"path": f"07_K/n{i}.md", "title": f"n{i}", "class": "note",
              "status": "active", "tags": []} for i in range(n)]
    edges = []
    for i in range(n):
        for salto in (1, 7, 13):
            j = (i + salto) % n
            edges.append({"from": f"07_K/n{i}.md", "to": f"07_K/n{j}.md",
                          "predicate": r.choice(predicados)})
    return {"nodes": nodes, "edges": edges}


def _encolados(grafo, hops, max_nodes):
    """Cuenta cuántas veces el BFS mete algo en la cola."""
    cuenta = {"n": 0}
    original = VS.deque
    original_load = VS._load_graph

    class Contador(original):
        def append(self, x):
            cuenta["n"] += 1
            if cuenta["n"] > 200_000:
                raise AssertionError("el recorrido no termina en tiempo acotado")
            super().append(x)

    VS.deque = Contador
    VS._load_graph = lambda: grafo
    try:
        r = VS.vault_subgraph(seeds=["07_K/n0.md"], hops=hops, max_nodes=max_nodes)
    finally:
        VS.deque = original
        VS._load_graph = original_load
    return cuenta["n"], r


def test_el_recorrido_no_crece_con_los_saltos_en_un_grafo_ciclico():
    """Con ciclos por todas partes, subir --hops no multiplica el trabajo.

    Esta es la propiedad que el invariante compra. Sin él, cada salto extra
    multiplicaría los encolados.
    """
    grafo = _grafo_ciclico(200)
    medidas = {h: _encolados(grafo, h, 10)[0] for h in (2, 4, 8, 16)}
    assert max(medidas.values()) <= 2 * 200, (
        f"encolados por saltos: {medidas} — el recorrido crece con --hops"
    )


def test_max_nodes_acota_la_salida_pero_no_el_trabajo():
    """Característica medida, no promesa. Si esto cambia, la doc también.

    Bajar `max_nodes` no abarata la consulta: el recorrido ya ocurrió entero y
    solo se recorta al final. Documentarlo como un tope de coste sería mentir.
    """
    grafo = _grafo_ciclico(200)
    pocos, r_pocos = _encolados(grafo, 6, 5)
    muchos, r_muchos = _encolados(grafo, 6, 1_000)
    # A 6 saltos el anillo alcanza 67 de los 200 nodos; con max_nodes=5 se
    # devuelven 5. Los dos recorridos visitaron lo mismo.
    assert len(r_pocos["nodes"]) == 5
    assert len(r_muchos["nodes"]) == 67
    assert pocos == muchos, (
        f"max_nodes cambió el trabajo ({pocos} vs {muchos}): si ahora SÍ acota "
        "el recorrido, actualiza el comentario del truncado y este test"
    )
    assert r_pocos["stats"]["truncated"] is True


def test_un_nodo_se_expande_varias_veces_a_profundidades_distintas():
    """Por qué `max_nodes` no puede acotar el trabajo sin cambiar el resultado.

    Se intentó: sustituir el recorrido por un mejor-primero (Dijkstra
    multiplicativo) para poder parar en cuanto hubiera `max_nodes` nodos
    finalizados. **No es equivalente.** Aquí un nodo se expande cada vez que se
    alcanza por un camino de más relevancia, y esas expansiones ocurren a
    profundidades distintas: la más superficial todavía tiene presupuesto de
    saltos y llega a sitios que la profunda ya no alcanza. Un Dijkstra expande
    cada nodo UNA vez, a la profundidad de su mejor camino, y pierde el resto.
    Comparado envelope a envelope sobre 3.600 casos aleatorios, cambiaban nodos
    y aristas; el testigo fue una arista presente aquí y ausente allí.

    Este test fija la propiedad que lo causa. Si alguna vez deja de cumplirse
    —porque el recorrido pase a llevar conjunto de visitados— entonces el
    mejor-primero SÍ sería equivalente y el tope de trabajo se vuelve posible.
    """
    # Con un solo predicado la relevancia solo depende de la profundidad, el
    # mejor camino es siempre el más corto y nunca hay reexpansión. Hace falta
    # mezclar pesos: un camino largo de aristas fuertes puede batir a uno corto
    # de aristas débiles, y ahí es donde el nodo se vuelve a expandir.
    grafo = _grafo_mixto(60)
    profundidades = collections.defaultdict(set)
    original = VS.deque
    original_load = VS._load_graph

    class Espia(original):
        def popleft(self):
            item = super().popleft()
            profundidades[item[0]].add(item[1])
            return item

    VS.deque = Espia
    VS._load_graph = lambda: grafo
    try:
        VS.vault_subgraph(seeds=["07_K/n0.md"], hops=6, max_nodes=1_000)
    finally:
        VS.deque = original
        VS._load_graph = original_load

    repetidos = {n: sorted(d) for n, d in profundidades.items() if len(d) > 1}
    assert repetidos, (
        "ningún nodo se expandió a dos profundidades: si el recorrido cambió a "
        "expansión única, un mejor-primero ya sería equivalente y `max_nodes` "
        "puede pasar a acotar el trabajo — revisa el comentario del recorrido"
    )


# ── 3. La pila frente a dato externo ─────────────────────────────────────────


@pytest.mark.parametrize("profundidad", [100, 500, 5_000, 50_000])
def test_el_frontmatter_anidado_no_desborda_la_pila(profundidad):
    """Una nota hostil se lee como frontmatter malformado, no mata el proceso."""
    nota = "---\nx: " + "[" * profundidad + "]" * profundidad + "\n---\ncuerpo\n"
    fm = vault_lib.parse_frontmatter(nota)
    assert isinstance(fm, dict)


@pytest.mark.parametrize("profundidad", [500, 50_000])
def test_el_cuerpo_sobrevive_al_frontmatter_hostil(profundidad):
    """La variante con cuerpo devuelve el texto, no lo pierde por el camino."""
    nota = "---\nx: " + "[" * profundidad + "]" * profundidad + "\n---\ncuerpo\n"
    fm, cuerpo = vault_lib.parse_frontmatter_with_body(nota)
    assert isinstance(fm, dict)
    assert "cuerpo" in cuerpo


def test_una_nota_hostil_no_impide_leer_las_demas():
    """El defecto que esto fija: UNA nota mataba la auditoría del vault entero."""
    hostil = "---\nx: " + "[" * 5_000 + "]" * 5_000 + "\n---\n"
    sanas = ["---\ntitle: A\n---\n", "---\ntitle: B\n---\n"]
    leidas = [vault_lib.parse_frontmatter(n) for n in [sanas[0], hostil, sanas[1]]]
    assert [d.get("title") for d in leidas] == ["A", None, "B"]

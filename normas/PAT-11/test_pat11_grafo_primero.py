"""Tests de paquete de la ID norma PAT-11 (navegación Grafo primero)."""

from vault.grafo.analisis import camino_mas_corto, explicar_nodo, reporte_grafo


def test_pat11_reporte_path_y_explain():
    grafo = {
        "nodes": {
            "03_Decisions/a.md": {"title": "A", "tags": []},
            "07_Knowledge/b.md": {"title": "B", "tags": []},
            "07_Knowledge/c.md": {"title": "C", "tags": []},
        },
        "edges": [
            {"from": "03_Decisions/a.md", "to": "07_Knowledge/b.md", "type": "wiki-link"},
            {"from": "07_Knowledge/b.md", "to": "07_Knowledge/c.md", "type": "wiki-link"},
        ],
    }
    assert reporte_grafo(grafo)["summary"]["total_nodes"] == 3
    assert camino_mas_corto(grafo, "a", "c")["hops"] == 2
    assert explicar_nodo(grafo, "b")["node"]["total_degree"] == 2

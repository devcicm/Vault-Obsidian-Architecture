# PAT-11 — Navegación Grafo primero y análisis estructural compacto

## Por qué existe

Recorrer un repositorio o vault con búsquedas ciegas (`grep`/`Glob`) llena la
ventana del agente con ruido. Consultar primero los *God Nodes*, las comunidades
y los caminos mínimos sobre el grafo local entrega un mapa preciso en cientos de
tokens en lugar de decenas de miles.

## Las caras

- **Análisis estructural**: `vault/grafo/analisis.py::reporte_grafo`
- **Camino y explicación**: `vault/grafo/analisis.py::camino_mas_corto`, `vault/grafo/analisis.py::explicar_nodo`
- **Consulta CLI/MCP**: `vault/consulta/subgraph.py::vault_subgraph_report`
- **Entrega a clientes**: `scripts/vault_preferences.py::_cuerpo_adapter`
- **Tests**: `tests/test_grafo_analisis_graphify.py` y `normas/PAT-11/test_pat11_grafo_primero.py`

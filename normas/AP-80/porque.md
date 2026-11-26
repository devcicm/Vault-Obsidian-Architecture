# AP-80 — Arista de grafo sin sello epistémico ni confianza

## Por qué existe

Sin distinguir si una arista del grafo salió de un enlace explícito (`EXTRACTED`),
de una co-ocurrencia heurística (`INFERRED`) o de un predicado no reconocido
(`AMBIGUOUS`), un agente confía por igual en evidencia dura y en suposiciones.

## Las caras

- **Clasificador canónico**: `vault/grafo/aristas.py::clasificar_arista_epistemica`
- **Consolidación**: `vault/grafo/aristas.py::consolidar_aristas`
- **Ensamblado de grafo**: `vault/grafo/refresco.py::ensamblar_grafo`
- **Consulta**: `vault/consulta/subgraph.py::vault_subgraph_report`
- **Tests**: `tests/test_grafo_analisis_graphify.py` y `normas/AP-80/test_ap80_epistemica.py`

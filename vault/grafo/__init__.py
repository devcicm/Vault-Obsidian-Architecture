"""Contexto **Grafo**: el vault visto como nodos y aristas.

Lenguaje ubicuo: nodo, arista, wikilink, huérfano, componente, predicado.
Es dueño de `99_Index/graph.json` y `graph-enriched.json`, del índice de código
`11_Code/.code-index.json`, del registro de etiquetas de código y de los
diagramas derivados de `06_Diagrams/entity/`.

Once módulos derivaban esas ubicaciones por su cuenta al importarse —dieciocho
constantes congeladas, cuatro de ellas la misma ruta calculada en sitios
distintos—. Aquí se declaran una vez y se resuelven al usarse (AP-49, AP-05).
"""

from .repositorio import RepositorioGrafo

__all__ = ["RepositorioGrafo"]

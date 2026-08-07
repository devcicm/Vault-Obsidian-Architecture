"""Contexto **Consulta** (Grupo 34): del vault a un paquete de contexto.

Lenguaje ubicuo: intención, subgrafo, paquete de contexto, preferencia, presupuesto
de tokens. Es dueño de `17_Preferences/`, de `00_System/token-usage/` y del
contador `.tool-tokens.json`.

**No es dueño del grafo.** `99_Index/graph.json` lo escribe el contexto Grafo;
Consulta solo lo lee, y por eso la ubicación se le **inyecta** en vez de
derivarla: si la derivara, habría dos sitios que deciden dónde vive el grafo y
el día que se mueva solo se enteraría uno (AP-05).

Sin base de datos, sin embeddings y sin servicio externo — esa restricción es
normativa, no una limitación pendiente de resolver.
"""

from .repositorio import RepositorioConsulta

__all__ = ["RepositorioConsulta"]

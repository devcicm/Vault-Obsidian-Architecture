"""Hoja canónica de las capacidades que realizan el servicio del estándar.

Los datos vivían en `scripts/vault_servicio.py`, que sigue publicándolos
(`vault_servicio.CAPACIDADES` es este mismo objeto). Se sacaron a una hoja en
v41.3 por AP-58: `vault_mcp_catalog` deriva de aquí qué grupos no se exponen a
MCP, y `vault_servicio` ya importa `vault_mcp_catalog` —leerlos de allí habría
cerrado un ciclo—. Es el mismo movimiento que llevó `NATURALEZAS` a
`vault.meta_toolkit.naturalezas`.

`grupos` son ids de la numeración de `scripts/README.md`, que es la fuente única
que `vault_mcp_catalog.mapa_de_grupos()` deriva. **No hay una numeración propia
de este módulo**: reintroducirla sería estrenar la divergencia que v40.8 cerró.
"""

from typing import Any, Dict

CAPACIDADES: Dict[str, Dict[str, Any]] = {
    "escritura_a_gobernanza": {
        "titulo": "Escritura → gobernanza",
        "resultado": (
            "Lo que el agente captura queda escrito una sola vez, normalizado contra "
            "las normas, versionado y auditable después."
        ),
        "sirve_a": "memoria_documental_gobernada",
        "grupos": [
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17,
            18, 19, 20, 21, 22, 23, 24, 25, 27, 28, 29, 30, 31, 32, 33,
            36, 37,
        ],
    },
    "consulta_a_contexto": {
        "titulo": "Consulta → contexto",
        "resultado": (
            "Una pregunta del agente se convierte en un paquete de contexto acotado "
            "y presupuestado, recorriendo el grafo del vault sin índice externo."
        ),
        "sirve_a": "memoria_documental_gobernada",
        "grupos": [26, 34],
        "nota": (
            "El grupo 26 (Tokens) cae en el rango 1–33 que `AGENTS.md` atribuye al "
            "primer eje, pero sus tres tools viven en el contexto `consulta` y existen "
            "para que el paquete quepa en la ventana. El rango es cronológico, no "
            "clasificatorio."
        ),
    },
    "gobernanza_del_estandar": {
        "titulo": "Gobernanza del estándar",
        "resultado": (
            "El estándar cumple lo que publica: registro canónico primero, doc "
            "derivada, guard que falla si divergen. Ninguna de estas tools toca las "
            "notas de un usuario."
        ),
        "sirve_a": "memoria_documental_gobernada",
        "grupos": [35],
        "nota": (
            "Tercera capacidad que `AGENTS.md` no nombraba. Existía desde que se "
            "escribió la primera puerta; declararla es lo que impide que sus tools "
            "se cuenten como si sirvieran a la memoria del agente."
        ),
    },
}

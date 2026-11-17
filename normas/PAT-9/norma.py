"""PAT-9 — the catalog entry, in its package.

Data only: `vault_norms_catalog` reads this file with `ast.literal_eval` and
does not import it. The faces are in `porque.md`.
"""

NORMA = {
    "code": "PAT-9",
    "distinguido_de": {
        "PAT-8": (
            "PAT-8 es la capa del wiki: lo que el agente aprende vuelve como "
            "página. PAT-9 es la capa del esquema: el fichero que el agente "
            "lee para saber cómo se trabaja en el vault, entre ellas cuándo "
            "guardar una respuesta."
        ),
    },
    "name": "Esquema del agente generado",
    "type": "pattern",
    "category": "structure",
    "severity": "N/A",
    "enforcement": "recommended",
    "description": (
        "El fichero que un agente lee en cada tarea —`AGENTS.md`, "
        "`CLAUDE.md`…— se genera desde los registros del vault y no se "
        "escribe a mano: el mapa de carpetas, la regla de nombres (CN-01), "
        "dónde viven las decisiones, el comando de pruebas que el dueño "
        "declara y el protocolo de sesión. Es la capa de esquema de la LLM "
        "Wiki de Karpathy, y el AGENTS.md corto que dice dónde viven las "
        "decisiones de Torti Code. Tiene un presupuesto de líneas: un "
        "esquema largo se lee en diagonal."
    ),
    "signal": (
        "`vault_preferences --adapters` escribe los adaptadores con la "
        "política derivada y, si alguno pasaría de `LINEAS_MAXIMAS_ADAPTER` "
        "líneas, no escribe ninguno y lo dice con `VALIDATION_FAILED`."
    ),
    "prevention": (
        "N/A — es el patrón correcto. Lo que crece con el vault —las "
        "preferencias del dueño— se recorta apuntando a la lista completa; "
        "si la parte derivada sola no cabe, se acorta el registro que la "
        "produce, no el presupuesto. El adaptador es entrega, no enforcing: "
        "la política se aplica en la frontera de mutación."
    ),
    "tools_enforcing": [],
    "tools_detecting": [],
    "tools_del_patron": ["vault_preferences"],
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-17",
}

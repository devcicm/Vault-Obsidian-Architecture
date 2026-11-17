"""PAT-8 — the catalog entry, in its package.

Data only: `vault_norms_catalog` reads this file with `ast.literal_eval` and
does not import it. The faces are in `porque.md`.
"""

NORMA = {
    "code": "PAT-8",
    "distinguido_de": {
        "AP-71": (
            "AP-71 señala el concepto que varias notas mencionan y ninguna "
            "define. PAT-8 es cómo nace una página a partir de una pregunta "
            "ya respondida: la síntesis vuelve al wiki citando las notas de "
            "las que salió. Una página de PAT-8 puede saldar un AP-71, pero "
            "su origen es la consulta, no la mención repetida."
        ),
        "PAT-9": (
            "PAT-8 es la capa del wiki: lo que el agente aprende vuelve como "
            "página. PAT-9 es la capa del esquema: el fichero que el agente "
            "lee para saber cómo se trabaja en el vault, entre ellas cuándo "
            "guardar una respuesta."
        ),
    },
    "name": "Respuesta compilada en el wiki",
    "type": "pattern",
    "category": "linking",
    "severity": "N/A",
    "enforcement": "recommended",
    "description": (
        "Una respuesta que sintetiza varias notas y valdrá en otra sesión se "
        "guarda como página del vault en vez de perderse con la conversación. "
        "Es la consulta de la LLM Wiki de Karpathy: las buenas respuestas "
        "vuelven al wiki con sus citas. `vault_ingest --desde-pack` la "
        "escribe como un solo borrador que cita en `related:` y en el cuerpo "
        "las notas del paquete de `vault_context_pack` del que salió."
    ),
    "signal": (
        "Una nota `type: ingested` en `draft` cuyo envelope de escritura "
        "declara `pattern: PAT-8` y cuyo `related:` son las notas del paquete. "
        "El protocolo de sesión lo propone en el momento «Para recordar»."
    ),
    "prevention": (
        "N/A — es el patrón correcto. La síntesis nace en `draft` y con "
        "integridad baja: no vale como conocimiento revisado hasta que una "
        "persona la revise. Un paquete que no incluye ninguna nota del vault "
        "se rechaza: una síntesis sin fuentes no es una página del wiki."
    ),
    "tools_enforcing": [],
    "tools_detecting": [],
    "tools_del_patron": ["vault_ingest"],
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-17",
}

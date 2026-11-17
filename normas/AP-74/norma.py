"""AP-74 — the catalog entry, in its package.

Data only: `vault_norms_catalog` reads this file with `ast.literal_eval` and
does not import it, so there is room for neither an import nor an expression
that needs executing. The faces are in `porque.md`.
"""

NORMA = {
    "code": "AP-74",
    "name": "Operación sin fila en la bitácora",
    "type": "antipattern",
    "category": "process",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "Una nota que entró por `vault_ingest --commit` no tiene la fila "
        "`ingested` de la pasada que la escribió en `00_System/.change-log.json`. "
        "La bitácora es la historia de las operaciones del vault —qué entró, "
        "cuándo y quién lo trajo—, y una ingesta sin su fila es material sin "
        "procedencia operativa: la nota existe y nadie puede decir en qué "
        "operación llegó. Es el log append-only de la LLM Wiki de Karpathy."
    ),
    "signal": (
        "Una nota con `type: ingested` cuyo `ingest_pass` no aparece en "
        "ninguna fila `ingested` del change log. Una nota ingerida antes de "
        "que existiera `ingest_pass` se cuenta como no verificable: enlazarla "
        "por una ventana de tiempo sería adivinar."
    ),
    "prevention": (
        "`vault_ingest` escribe el mismo id de pasada en cada nota y en la "
        "fila `ingested` que anota por el puerto `bitacora_cambios`; si la "
        "fila no se pudo anotar, su envelope lo dice en `change_log_error`. "
        "`vault_audit` lista en `ingestsWithoutLog` las notas cuya pasada no "
        "tiene fila. Solo lectura: la bitácora no se repara reescribiéndola."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_audit"],
    "distinguido_de": {
        "AP-73": (
            "Las dos vigilan la ingesta. AP-73 mira lo que entró —que la "
            "fuente siga siendo la que llegó—; AP-74, que la operación que "
            "la trajo quedó anotada en el change log."
        ),
    },
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-17",
}

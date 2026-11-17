"""AP-73 — the catalog entry, in its package.

Data only: `vault_norms_catalog` reads this file with `ast.literal_eval` and
does not import it, so there is room for neither an import nor an expression
that needs executing. The faces are in `porque.md`.
"""

NORMA = {
    "code": "AP-73",
    "name": "Fuente archivada modificada",
    "type": "antipattern",
    "category": "process",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Una fuente que `vault_ingest --archivar-fuente` guardó literal en "
        "`10_Migrated/fuentes/` se reescribe. Esa capa es el registro de lo "
        "que llegó: las notas derivadas la citan en `source:` como prueba de "
        "dónde salió lo que afirman, y una fuente editada después convierte "
        "la cita en una afirmación que nadie puede comprobar. Es la capa "
        "cruda de la LLM Wiki de Karpathy: el modelo la lee y nunca la edita."
    ),
    "signal": (
        "Una nota de `10_Migrated/fuentes/` con `type: migrated` y "
        "`status: archived` (`vault.kernel.contenido.es_fuente_archivada`) "
        "cuyo cuerpo ya no tiene la huella `sha256_cuerpo` que se registró "
        "al archivarla, o una escritura que intenta cambiarla."
    ),
    "prevention": (
        "El dueño de la escritura (`vault_io.atomic_write_text`) rechaza "
        "cualquier reescritura de una fuente archivada con `IMMUTABLE_NOTE` y "
        "la pista de ingerirla como fuente nueva; escribir los mismos bytes "
        "no es reescribir. Lo que cambie fuera del dueño —un editor, un "
        "script— lo ve `vault_audit` en `archivedSourcesModified`, comparando "
        "con la huella que `vault_ingest` registró al archivar. Una fuente "
        "archivada antes de que existiera la huella sale como no verificable, "
        "no como intacta."
    ),
    "tools_enforcing": ["vault_io"],
    "tools_detecting": ["vault_audit"],
    "distinguido_de": {
        "AP-75": (
            "Las dos son reescribir lo que debía conservarse. AP-73 es la "
            "fuente cruda, que no se edita nunca y no tiene sucesora: otra "
            "versión es otra fuente. AP-75 es la decisión cerrada, que sí "
            "cambia, pero escribiendo su sucesora y enlazándola."
        ),
        "AP-74": (
            "Las dos vigilan la ingesta. AP-73 mira lo que entró —que la "
            "fuente siga siendo la que llegó—; AP-74, que la operación que "
            "la trajo quedó anotada en el change log."
        ),
    },
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-17",
}

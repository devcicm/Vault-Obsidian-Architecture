"""AP-77 — the catalog entry, in its package.

Data only: `vault_norms_catalog` reads this file with `ast.literal_eval` and
does not import it, so there is room for neither an import nor an expression
that needs executing. The faces are in `porque.md`.
"""

NORMA = {
    "code": "AP-77",
    "name": "Registro con la conservación vencida sin disposición",
    "type": "antipattern",
    "category": "content-quality",
    "severity": "low",
    "enforcement": "audit",
    "description": (
        "Un registro lleva más tiempo sin actividad que el plazo de "
        "conservación de su clase de documento y nadie ha decidido su "
        "disposición (ISO 15489-1:2016). Un registro que se acumula sin "
        "calendario deja de distinguirse de la evidencia vigente: el agente "
        "consulta igual lo que ya cumplió su plazo que lo que sigue rigiendo."
    ),
    "signal": (
        "La última actividad del registro —la más reciente de `revisado_en`, "
        "`updatedAt` y `createdAt`— más el plazo de "
        "`vault_registry.conservacion_de(sección)` es anterior a hoy, con la "
        "aritmética de las normas (`vault_norms_catalog.estado_de_revision`), "
        "y su disposición es `revisar` o `archivar` sin aplicar: un registro "
        "en `status: archived` ya la tiene, y uno `permanente` no vence."
    ),
    "prevention": (
        "`vault_drift_detect --mode conservacion` publica la lista de trabajo "
        "(`pendientes`, con su disposición y su responsable) sin poner `ok` en "
        "falso. Revisar es releer el registro y poner `revisado_en` con la "
        "fecha del día; archivar es pasar su `status` a `archived`. La tool "
        "nunca borra ni mueve un registro: la disposición es un acto de la "
        "organización y destruir no es una de las disposiciones del estándar."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_drift_detect"],
    "distinguido_de": {
        "AP-76": (
            "AP-76 es una nota viva que declaró cuándo se revisó y lleva más "
            "que su cadencia sin releerse: pide comprobar que sigue siendo "
            "cierta. AP-77 mide el plazo de conservación de la clase de "
            "documento desde la última actividad, también en registros que "
            "nunca declararon `revisado_en`, y pide decidir qué se hace con "
            "el registro —revisarlo o archivarlo—, no si sigue siendo cierto."
        ),
    },
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-18",
}

"""AP-76 — the catalog entry, in its package.

Data only: `vault_norms_catalog` reads this file with `ast.literal_eval` and
does not import it, so there is room for neither an import nor an expression
that needs executing. The faces are in `porque.md`.
"""

NORMA = {
    "code": "AP-76",
    "name": "Nota viva con la revisión vencida",
    "type": "antipattern",
    "category": "content-quality",
    "severity": "low",
    "enforcement": "audit",
    "description": (
        "Una nota que declara cuándo se revisó (`revisado_en`) lleva más "
        "tiempo sin releerse que su cadencia. Torti Code: la documentación "
        "desactualizada es peor que ninguna, y lo que la evita es un dueño, "
        "una fecha de revisión y una herramienta que avise. Vencer no es "
        "estar mal: es que nadie ha comprobado que siga siendo cierta."
    ),
    "signal": (
        "`revisado_en` más `cadencia_dias` (la de la nota, o la de la "
        "llamada) es anterior a hoy, con la aritmética de las normas "
        "(`vault_norms_catalog.estado_de_revision`). Una nota sin "
        "`revisado_en` no se juzga: se cuenta en `sin_fecha`."
    ),
    "prevention": (
        "`vault_drift_detect --mode antiguedad` publica la lista de trabajo "
        "(`vencidas`, con su responsable) sin poner `ok` en falso. Revisar es "
        "releer la nota contra lo que describe y poner `revisado_en` con la "
        "fecha del día; la cadencia se declara en `cadencia_dias`."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_drift_detect"],
    "distinguido_de": {
        "AP-08": (
            "AP-08 es la nota que ya describe algo que cambió —el código que "
            "documenta se tocó después que ella—. AP-76 no mira el código: "
            "dice que nadie ha comprobado la nota en su plazo, cambiara algo "
            "o no. Una revisión vencida puede seguir siendo cierta."
        ),
        "AP-77": (
            "AP-77 es el plazo de conservación de la clase de documento, "
            "medido desde la última actividad del registro aunque nunca "
            "declarase `revisado_en`, y pide decidir su disposición —revisar "
            "o archivar—. AP-76 solo mira notas que declaran `revisado_en` y "
            "pide comprobar que siguen siendo ciertas."
        ),
    },
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-17",
}

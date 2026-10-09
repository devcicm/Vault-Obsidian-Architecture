"""CN-01 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "CN-01",
    "distinguido_de": {
        "CN-02": (
            "Las dos son convenciones de ubicación y nombre. CN-01 rige el nombre "
            "del fichero —minúsculas con guiones—; CN-02 rige el destino —las "
            "secciones numeradas—. Un fichero bien nombrado en la carpeta "
            "equivocada incumple solo CN-02."
        ),
        "CN-04": (
            "CN-01 rige el nombre del fichero, que lee quien navega el árbol; "
            "CN-04, el H1 con que abre la nota, que lee quien ya está dentro. "
            "Un fichero en kebab-case sin H1 incumple solo CN-04."
        ),
    },
    "name": "Kebab-case filenames — nombres de archivo en minúsculas con guiones",
    "type": "antipattern",
    "category": "convention",
    "severity": "high",
    "enforcement": "guard",
    "description": (
        "Los archivos .md del vault deben usar kebab-case: minúsculas, palabras separadas "
        "por guiones, sin espacios ni caracteres especiales. "
        "vault_write aplica slugify() automáticamente al título para generar el filename. "
        "Ej: 'ADR-001 Auth Decision' → adr-001-auth-decision.md."
    ),
    "signal": "Archivos con espacios, mayúsculas o caracteres especiales en el nombre.",
    "prevention": "Siempre usar vault_write para crear notas. Nunca crear archivos .md directamente.",
    "tools_enforcing": ["vault_write"],
    # Hasta v41.2 ninguna tool auditaba los nombres ya escritos. Desde
    # entonces `vault_audit` los mide con el criterio de `slugify`
    # (`issues.cn01NotKebab`), sin peso: el enforcement sigue `guard` hasta
    # que el usuario decida si penaliza (deuda #13).
    "tools_detecting": ["vault_audit"],
    "introduced_version": "v30",
}

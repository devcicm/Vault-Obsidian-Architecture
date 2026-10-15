"""PAT-1 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "PAT-1",
    "distinguido_de": {
        "AP-05": (
            "AP-05 es el defecto: el mismo dato con valores distintos en varias "
            "notas del mismo ámbito. PAT-1 es el patrón que lo cierra: una nota "
            "canónica declara el dato y las demás la enlazan. Se declaran aparte "
            "porque PAT-1 se aplica también donde AP-05 aún no ha ocurrido."
        ),
    },
    "name": "Canonical source anchoring",
    "type": "pattern",
    "category": "structure",
    "severity": "N/A",
    "enforcement": "recommended",
    "description": (
        "Un dominio = una nota canónica rica. Todas las referencias desde otros contextos "
        "son [[wiki-links]] a esa nota canónica, nunca copias del contenido."
    ),
    "signal": "vault_audit muestra 0 canonicalShadow y 0 crossFolderDuplicates.",
    "prevention": "N/A — es el patrón correcto. Aplicar siempre al crear documentación.",
    "tools_enforcing": [],
    "tools_detecting": [],
    "tools_del_patron": ["vault_audit"],
    "introduced_version": "v25",
    "revisado_en": "2026-10-09",
}

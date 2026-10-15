"""AP-02 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-02",
    "distinguido_de": {
        "AP-17": (
            "AP-02 son varias versiones del mismo documento conviviendo, cada una "
            "con su nombre. AP-17 es la duplicación canónico-sombra: hay un "
            "canónico declarado y una copia que lo sigue mal. El discriminador es "
            "si existe un canónico designado."
        ),
        "PAT-3": (
            "AP-02 es el defecto: la cadena de versiones duplicadas. PAT-3 es el "
            "procedimiento que la resuelve, eligiendo canónico y anotando el "
            "resto sin borrarlo. Saldar AP-02 es aplicar PAT-3."
        ),
    },
    "name": "Proliferación de versiones del mismo documento",
    "type": "antipattern",
    "category": "structure",
    "severity": "high",
    "enforcement": "audit",
    "description": (
        "Múltiples notas describiendo la misma entidad: status-v1.md, status-v2.md, "
        "status-final.md, status-final2.md. Variantes: same-folder (AP-02), "
        "cross-folder (AP-18), canonical-shadow (AP-17)."
    ),
    "signal": (
        "vault_audit reporta sameFolderVersions (AP-02); sus hermanas, "
        "canonicalShadow (AP-17) y crossFolderDuplicates (AP-18)."
    ),
    "prevention": "Una nota por entidad. Usar .history/ para versiones anteriores (vault_write lo gestiona automáticamente).",
    "tools_enforcing": [],
    "tools_detecting": ["vault_audit"],
    "cobertura_parcial": (
        "Estuvo descubierta desde v40.11: las hermanas AP-17 y AP-18 se "
        "medían y la variante same-folder no la veía nadie, porque "
        "`status-v1.md` y `status-v2.md` no son idénticos por hash ni "
        "tienen por qué pasar el umbral de título. Ahora "
        "`vault_audit._detect_same_folder_versions` mide **la parte que el "
        "nombre declara**: dos ficheros de la misma carpeta cuyo tronco "
        "coincide al quitar un sufijo de versión (`-v2`, `-final`, `-old`, "
        "`-copia`…). Lo que sigue sin medir es la versión que no lo dice "
        "(`status-actualizado.md`) y `04_Sessions/`, excluida porque allí el "
        "sufijo nombra una release, no una copia. Se informa sin pesar en el "
        "healthIndex: medida contra trece consumidores dio cero tras excluir "
        "sesiones, y un peso no se fija con un solo dato."
    ),
    "introduced_version": "v19",
    "revisado_en": "2026-10-09",
}

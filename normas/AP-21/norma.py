"""AP-21 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-21",
    "distinguido_de": {
        "AP-14": (
            "Las dos son wikilinks defectuosos, y el discriminador es a cuántas "
            "notas resuelve el destino con el criterio de Obsidian —nombre de "
            "fichero, sufijo de ruta y `aliases:`—. A ninguna: AP-14, el link "
            "está roto. A una, pero con una carpeta que el nombre solo no "
            "necesita, o a varias porque falta la carpeta que desambigua: AP-21, "
            "la forma del enlace no fija la identidad. Un `[[carpeta/nota]]` que "
            "resuelve a una sola nota cuyo nombre se repite no es ninguna de las "
            "dos. Solapan en un caso, la ruta escrita que no resuelve a ninguna "
            "nota: `vault_write` la rechaza como AP-21 (`path_anchored_wikilinks`) "
            "porque la carpeta es lo que se escribió, y `vault_audit` la cuenta en "
            "`brokenLinks` como AP-14 porque no tiene destino. Mover la nota no "
            "rompe ninguna de las dos: `vault_move` reescribe los `[[nota]]` y "
            "`[[carpeta/nota]]` entrantes."
        ),
    },
    "name": "Path-anchored wiki-links",
    "type": "antipattern",
    "category": "linking",
    "severity": "critical",
    "enforcement": "guard+audit",
    # Precisada en v40.35. Decía «Obsidian no resuelve paths, solo stems»,
    # que no es cierto: Obsidian resuelve el sufijo de ruta y, con su formato
    # por defecto, escribe [[demo/overview]] cuando el nombre se repite. La
    # prohibición total dejaba [[overview]] como único enlace a dos notas.
    # El criterio vive en `vault_lib.ruta_necesaria`.
    "description": (
        "[[carpeta/nota]] cuando la carpeta no fija la identidad: la ruta no "
        "resuelve, o sobra porque el nombre ya es único. Con dos notas del "
        "mismo nombre la ruta más corta que desambigua es legítima."
    ),
    "signal": "vault_write rechaza con error_code: path_anchored_wikilinks.",
    "prevention": "[[stem]] si el nombre es único; si se repite, la ruta más corta que resuelve a una sola nota (vault_lib.destino_mas_corto).",
    "tools_enforcing": ["vault_write"],
    # v40.35: vault_audit mide el otro lado de la regla precisada, el
    # [[nombre]] que resuelve a varias notas (issues.ambiguousLinks).
    "tools_detecting": ["vault_audit"],
    "introduced_version": "v25",
}

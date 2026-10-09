"""AP-20 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-20",
    "distinguido_de": {
        "AP-11": (
            "AP-11 es el cuerpo vacío: no hay nada que leer y se nota. AP-20 es "
            "el esqueleto engañoso: hay estructura y campos, y las listas están "
            "vacías, así que la nota pasa por completa ante cualquier medida que "
            "cuente secciones. El discriminador es si el vacío es visible o está "
            "disfrazado."
        ),
        "AP-45": (
            "AP-45 es la nota que existe para que la sección no aparezca vacía: "
            "la cobertura se afirma sin evidencia detrás. AP-20 es la nota que "
            "tiene estructura y listas vacías. AP-45 se mide contra lo que la "
            "nota dice cubrir; AP-20, contra su propio contenido."
        ),
    },
    "name": "Deceptive skeleton (empty-list)",
    "type": "antipattern",
    "category": "content-quality",
    "severity": "critical",
    "enforcement": "guard",
    "description": (
        "Nota que pasa el content gate de 3 líneas porque tiene bullets, "
        "pero >50% de los bullets están vacíos (- , - [ ], - []). "
        "Variante de AP-11 que evade el guard básico."
    ),
    "signal": "vault_write rechaza con error_code: content_empty_list.",
    "prevention": "vault_write rechaza si empty_bullets/total_bullets > 0.5. Completar los bullets antes de guardar.",
    "tools_enforcing": ["vault_write"],
    "tools_detecting": [],
    "introduced_version": "v25",
}

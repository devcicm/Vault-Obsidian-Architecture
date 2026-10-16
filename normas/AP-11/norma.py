"""AP-11 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-11",
    "distinguido_de": {
        "AP-06": (
            "AP-06 es la plantilla que nadie instanció: el fichero es un template "
            "y su función es serlo. AP-11 es la nota real con frontmatter válido "
            "y cuerpo vacío, que se presenta como contenido. El discriminador es "
            "si el fichero se declara plantilla."
        ),
        "AP-20": (
            "AP-11 es el cuerpo vacío: no hay nada que leer y se nota. AP-20 es "
            "el esqueleto engañoso: hay estructura y campos, y las listas están "
            "vacías, así que la nota pasa por completa ante cualquier medida que "
            "cuente secciones. El discriminador es si el vacío es visible o está "
            "disfrazado."
        ),
        "AP-23": (
            "Son los dos extremos del mismo eje. AP-11 es defecto de contenido "
            "—la nota no dice nada—; AP-23 es exceso —la nota supera el techo de "
            "complejidad y debería partirse—. Ninguna nota puede incurrir en las "
            "dos."
        ),
    },
    "name": "Skeleton files — frontmatter válido, contenido vacío",
    "type": "antipattern",
    "category": "content-quality",
    "severity": "critical",
    "enforcement": "guard",
    "description": (
        "Nota creada con frontmatter correcto pero cuerpo vacío o solo con TODO/placeholders. "
        "El agente indexa la nota pero no recibe información útil de ella. "
        "Distinción con AP-03: AP-11 = 0 líneas reales; AP-03 = ≥3 líneas reales pero incompleto."
    ),
    "signal": "vault_write rechaza con error_code: content_too_short.",
    "prevention": "vault_write exige ≥3 líneas de contenido real (00_System exempt). No crear notas que no estén listas.",
    "tools_enforcing": ["vault_write"],
    "tools_detecting": ["vault_norms"],
    "introduced_version": "v19",
    "revisado_en": "2026-10-09",
}

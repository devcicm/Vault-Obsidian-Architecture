"""AP-63 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-63",
    "name": "El nombre de un proyecto como texto libre",
    "type": "antipattern",
    "category": "consistency",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "El nombre de un proyecto es **identidad**, y hasta v40.34 era "
        "texto libre: cada `--project` escribía su valor tal cual, así que "
        "una errata, una variante de mayúsculas o un ejemplo del manifiesto "
        "**fundaban** un proyecto con su carpeta. Medido en solo lectura "
        "contra un vault consumidor (regla 7): cuatro proyectos fantasma "
        "—`mi-api`, `mi-proyecto`, `demo`, `website-demo`— que eran los "
        "ejemplos del estándar copiados por un agente.\n\n"
        "El registro existe sin que nadie lo declare: la carpeta "
        "`01_Projects/<slug>/` registra el slug. La ficha opcional "
        "`project.md` aporta `aliases`, `title` y `status`. Un nombre "
        "resuelve a **un** slug o falla: `PROJECT_NOT_FOUND` con "
        "sugerencias, `PROJECT_AMBIGUOUS` si un alias lo reclaman dos."
    ),
    "signal": (
        "Dos carpetas en `01_Projects/` que solo difieren en mayúsculas o "
        "guiones; notas con `project:` que no corresponde a ninguna "
        "carpeta; claves `proyecto:` o `Project:` junto a `project:`; la "
        "ruta local de un repositorio escrita dentro de una nota."
    ),
    "prevention": (
        "`vault_project` es la puerta de entrada: `--add` registra y "
        "rechaza un alias que ya es de otro proyecto, `--resolve` devuelve "
        "el slug o el código de error, `--audit` lista fantasmas y claves "
        "no canónicas sin escribir nada. La ruta local va a "
        "`00_System/.local/project-paths.json`, con su propio "
        "`.gitignore`: es de una máquina, no del proyecto.\n\n"
        "Límites declarados: las tools con `--project` todavía no pasan "
        "por el resolutor, así que la escritura sigue pudiendo fundar un "
        "fantasma que el audit verá después; y el audit no mira el cuerpo "
        "de las notas, donde los ejemplos del manifiesto citan nombres "
        "que no son proyectos."
    ),
    "tools_enforcing": ["vault_project"],
    "tools_detecting": ["vault_project"],
    "distinguido_de": {
        "AP-05": (
            "AP-05 es el mismo dato con valores distintos en varias notas. "
            "AP-63 es anterior: el **nombre** que decide a qué ámbito "
            "pertenece una nota. Si el nombre se bifurca, AP-05 ni siquiera "
            "puede ver el conflicto, porque las dos notas parecen de "
            "proyectos distintos."
        ),
        "AP-17": (
            "AP-17 es una nota sombra de un canónico declarado. AP-63 es "
            "el proyecto entero sin canónico: no hay sombra porque nadie "
            "dijo cuál era el original, y la corrección empieza por "
            "registrarlo, no por fusionar notas."
        ),
    },
    "introduced_version": "v40.34",
}

"""AP-44 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-44",
    "name": "Verificación autoconsistente — la tool se certifica a sí misma",
    "type": "antipattern",
    "category": "quality",
    "severity": "critical",
    "enforcement": "guard+audit",
    "description": (
        "Una tool escribe o mide con un criterio propio y verifica el resultado "
        "con ESE MISMO criterio, en vez de con el que usa el consumidor real "
        "—Obsidian al resolver un enlace, el parser de Mermaid al dibujar, YAML "
        "al leer un frontmatter, el audit del propio estándar al juzgar la nota "
        "que otra tool acaba de escribir. La tool queda internamente coherente y "
        "por eso mismo ciega a su propio fallo: no puede detectar el error porque "
        "lo comete en los dos lados de la comparación. Es más caro que un bug "
        "normal, porque el guard sale en verde y dirige el trabajo hacia donde no "
        "hay problema: reescribir enlaces que funcionan, 'corregir' diagramas "
        "válidos, retaguear notas ya etiquetadas."
    ),
    "signal": (
        "Dos tools del estándar dan cifras distintas para lo mismo (146 vs 86 "
        "enlaces rotos); un hallazgo desaparece al normalizar y reaparece al "
        "abrir el vault; el generador de una nota produce metadatos que el audit "
        "del mismo estándar reprueba; un 'arreglo' se declara aplicado y el "
        "usuario sigue viendo el problema; el 100% de una categoría de hallazgos "
        "resulta falsa al inspeccionarla a mano."
    ),
    "prevention": (
        "Verificar con el criterio del consumidor, no con el propio: resolver "
        "wikilinks por nombre de fichero y `aliases:` —nunca por `title:`, que "
        "Obsidian no mira—, leer frontmatter con `yaml.safe_load` y no con un "
        "regex por líneas, y validar Mermaid contra su gramática real. Toda tool "
        "que escribe reevalúa el resultado releyendo del disco. Un frontmatter "
        "ilegible devuelve error explícito, nunca `{}` silencioso, que es lo que "
        "hace que un write path anteponga un segundo bloque y corrompa la nota. "
        "Y toda medida se contrasta contra un vault preexistente ajeno al "
        "estándar: `vault-sandbox/` lo genera el propio estándar y comparte sus "
        "supuestos, así que no puede exhibir este fallo."
    ),
    # v40.28 — la gramática de Mermaid se mudó a `vault_mermaid_reglas`
    # (AP-62), y con ella el sitio que aplica AP-44: validar contra la
    # gramática real y no contra el criterio del generador. Se nombra al
    # dueño, no a la fachada, porque la traza tiene que llevar al código.
    "tools_enforcing": ["vault_audit", "vault_graph_fix", "vault_mermaid_reglas"],
    "tools_detecting": ["vault_norms", "vault_audit"],
    "distinguido_de": {
        "AP-55": (
            "AP-44 se comete al verificar: la tool mide con su propia "
            "normalización y queda ciega a su error. AP-55 está en el dato "
            "antes de que nadie verifique: dos registros canónicos afirman "
            "cosas distintas sobre el mismo hecho. Un catálogo puede ser "
            "coherente y estar verificado por un guard autoconsistente "
            "(AP-44 solo), o ser incoherente aunque el guard mire fuera "
            "(AP-55 solo). Se dieron juntos en v40.10, que es por lo que "
            "conviene tenerlos separados por escrito."
        )
    },
    "introduced_version": "v39",
    "revisado_en": "2026-10-09",
}

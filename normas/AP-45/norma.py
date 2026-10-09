"""AP-45 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-45",
    "distinguido_de": {
        "AP-20": (
            "AP-45 es la nota que existe para que la sección no aparezca vacía: "
            "la cobertura se afirma sin evidencia detrás. AP-20 es la nota que "
            "tiene estructura y listas vacías. AP-45 se mide contra lo que la "
            "nota dice cubrir; AP-20, contra su propio contenido."
        ),
        "CN-04": (
            "AP-45 mide si el cuerpo tiene evidencia; CN-04, solo si la nota "
            "abre diciendo qué es. Poner el H1 no salda AP-45: una nota con "
            "título y sin evidencia sigue incumpliéndola."
        ),
    },
    "name": "Cobertura sin evidencia — la nota existe para llenar la sección",
    "type": "antipattern",
    "category": "quality",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Una nota se crea porque una sección estaba vacía, no porque hubiera algo "
        "que afirmar. Su cuerpo son encabezados y marcadores de pendiente "
        "—`_Pendiente_`, `TODO`, `— No detectados`— y no enlaza con nada. Sube la "
        "cobertura y baja la fiabilidad: el conteo de notas dice que la sección "
        "está cubierta, el health score la cuenta como nota real, y el siguiente "
        "lector la abre esperando contenido. Es más caro que la ausencia, porque "
        "la ausencia sí se ve: un hueco invita a llenarlo, un relleno declara que "
        "ya está hecho. El generador que la escribió creía estar documentando."
    ),
    "signal": (
        "Notas cuyo cuerpo bajo el frontmatter, quitados encabezados y "
        "marcadores, queda vacío y sin wikilinks salientes; secciones que pasan "
        "de 0 a N notas en una sola ejecución de una tool; ADRs numerados sin "
        "nombre; conceptos cuyo cuerpo entero remite a leer otra fuente."
    ),
    "prevention": (
        "No escribir la nota sin evidencia detrás. Un generador que no encuentra "
        "contenido real para una sección lo declara en `warnings` y en "
        "`next_steps` —que es información útil— en vez de emitir un stub, que es "
        "desinformación. El andamiaje declarado sí es legítimo: los primers de "
        "vault_init llevan `status: template` y quedan exentos, porque anuncian "
        "lo que son. Secciones dirigidas por eventos (18_Bugs, 19_Audits, "
        "20_Quarantine) se quedan vacías hasta que ocurre el evento."
    ),
    "tools_enforcing": ["vault_onboard", "vault_write"],
    "tools_detecting": ["vault_norms", "vault_audit"],
    "introduced_version": "v39",
}

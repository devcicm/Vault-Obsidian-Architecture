"""AP-15 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-15",
    "distinguido_de": {
        "AP-67": (
            "AP-15 es material ajeno **dentro** de la raiz del vault. AP-67 es material **fuera** del vault que el agente opera y del que no hay ninguna nota. Aqui el material esta de mas; alla lo que falta es la nota que lo apunta."
        ),
        "AP-36": (
            "AP-15 es material ajeno depositado dentro del vault. AP-36 es lo "
            "contrario: side-effects de las tools que salen del vault o no quedan "
            "rastreados. El discriminador es la dirección del cruce de la "
            "frontera."
        ),
        "CN-02": (
            "CN-02 es la nota colocada en una carpeta que no toca, dentro del "
            "esquema. AP-15 es el fichero externo depositado en la raíz del "
            "vault, que ni siquiera es una nota. El discriminador es si el "
            "fichero forma parte del material del vault."
        ),
    },
    "name": "Archivos externos depositados en la raíz del vault",
    "type": "antipattern",
    "category": "structure",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Archivos .md colocados directamente en vault-{nombre}/ en lugar de en secciones "
        "numeradas. vault_graph parsea sus [[wiki-links]] como broken links reales del proyecto."
    ),
    "signal": "vault_graph reporta decenas de orphans y broken links falsos.",
    "prevention": (
        "vault_write y vault_move no aceptan la raíz como destino "
        "(vault_registry.motivo_de_destino_invalido) y vault_section_index rechaza un "
        "--folder en la raíz; vault_norms --audit lista los ficheros sueltos. Las "
        "secciones válidas las dice el registro (vault_section --list), no esta línea. "
        "El toolkit y el estándar viven fuera del vault, como hermanos de su carpeta."
    ),
    "tools_enforcing": ["vault_write", "vault_move", "vault_section_index"],
    "tools_detecting": ["vault_norms"],
    "introduced_version": "v20",
    "revisado_en": "2026-10-09",
}

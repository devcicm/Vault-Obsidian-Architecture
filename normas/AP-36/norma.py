"""AP-36 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-36",
    "distinguido_de": {
        "AP-15": (
            "AP-15 es material ajeno depositado dentro del vault. AP-36 es lo "
            "contrario: side-effects de las tools que salen del vault o no quedan "
            "rastreados. El discriminador es la dirección del cruce de la "
            "frontera."
        ),
        "SP-04": (
            "AP-36 mira **adónde** escribe una tool; SP-04 mira **quién** puede "
            "pedírselo. Contener la escritura no protege de un invocador "
            "ilegítimo, y autenticarlo no legitima una ruta fuera del vault."
        ),
    },
    "name": "Contención e idempotencia — side-effects fuera del vault o no rastreables",
    "type": "antipattern",
    "category": "structure",
    "severity": "critical",
    "enforcement": "guard+audit",
    "description": (
        "Toda operación de tooling debe: (1) escribir ÚNICAMENTE dentro del vault root "
        "(backups, traces, locks, stubs, logs incluidos); (2) ser idempotente — ejecutarla "
        "dos veces no duplica artefactos ni carpetas; (3) dejar sus artefactos indexados o "
        "en ubicaciones registradas (vault_registry) para rastreabilidad. Casos históricos: "
        "vault-backups escrito en el abuelo del repo, 00_System/99_Index generados fuera "
        "del vault por detección de root defectuosa, .bak junto a nodos de contenido."
    ),
    "signal": (
        "Carpetas vault-backups/00_System/99_Index como hermanos del vault; archivos .bak/.tmp "
        "dentro de secciones de contenido; secciones sin index.md."
    ),
    "prevention": (
        "Rutas de salida derivadas SIEMPRE de VAULT_ROOT (nunca de __file__ ni cwd). "
        "Artefactos de mantenimiento van a 02_Observability/maintenance/ o 00_System/. "
        "vault_norms --audit detecta artefactos sueltos y secciones sin índice."
    ),
    "tools_enforcing": ["vault_section_index", "vault_io.assert_within_vault"],
    "tools_detecting": ["vault_norms"],
    "introduced_version": "v38",
}

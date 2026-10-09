"""AP-04 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-04",
    "distinguido_de": {
        "AP-01": (
            "Las dos documentan algo que el código no hace. AP-01 es la "
            "afirmación inventada: no hay implementación ni intención de tenerla, "
            "y el discriminador es que no existe rastro en el repo. AP-04 es el "
            "roadmap escrito en presente: la feature está planeada y la nota la "
            "presenta como ya entregada. Una se corrige borrando la afirmación; "
            "la otra, marcando el estado."
        ),
        "AP-08": (
            "Las dos son documentación desalineada del código, en sentidos "
            "opuestos. AP-04 va por delante —describe lo que aún no existe—; "
            "AP-08 va por detrás —describe una versión que ya pasó—. El "
            "discriminador es la dirección del desfase respecto a la versión "
            "viva."
        ),
        "AP-42": (
            "AP-04 mide la nota: describe como entregado algo que no lo está. "
            "AP-42 mide la tool: está publicada en el catálogo y nunca se "
            "ejecutó. El discriminador es el sujeto medido —texto frente a "
            "artefacto ejecutable—, y por eso una la detecta el audit de "
            "contenido y la otra el smoke."
        ),
    },
    "name": "Features aspiracionales documentadas como implementadas",
    "type": "antipattern",
    "category": "content-quality",
    "severity": "high",
    "enforcement": "audit",
    "description": (
        "Documentar comportamientos futuros o planeados como si ya existieran. "
        "Confunde al agente sobre el estado real del sistema."
    ),
    "signal": "Notas sin campo status o con status:planned que describen funcionalidad en presente.",
    "prevention": "Usar status: planned/in-progress/implemented. Nunca describir en presente algo que no está deployado.",
    "tools_enforcing": [],
    "tools_detecting": [],
    "cobertura_descubierta": (
        "Ninguna tool la detecta. `vault_drift_detect` compara hashes y git; "
        "distinguir «lo describe en presente» de «ya está deployado» exige leer el "
        "cuerpo de la nota contra el estado real, que hoy no hace nadie. "
        "Probado en v41.3 al reformular AP-01: la única señal decidible —la "
        "nota declara en `files:` un fichero que no está en el repo— ya sale "
        "como AP-01 en `codigo_inexistente`, y lo que separa las dos normas "
        "es la intención (planeada frente a inventada), que no está escrita "
        "en ningún campo. Nombrarla AP-04 también sería contar el mismo "
        "hallazgo dos veces con un criterio adivinado. La hipótesis de que "
        "la intención quedara escrita en la **historia** del `status` —una "
        "nota entregada que en git tuvo antes un estado planificado— se "
        "midió el 2026-10-09 contra la copia de /ans, la única con git, "
        "normalizando con `normalize_status`: 12 notas entregadas, las 12 "
        "con historia, ninguna con un estado previo de la clase planificada. "
        "Señal nula: queda descubierta por eso, no por no haberla probado."
    ),
    "introduced_version": "v19",
}

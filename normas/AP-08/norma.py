"""AP-08 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-08",
    "distinguido_de": {
        "AP-04": (
            "Las dos son documentación desalineada del código, en sentidos "
            "opuestos. AP-04 va por delante —describe lo que aún no existe—; "
            "AP-08 va por detrás —describe una versión que ya pasó—. El "
            "discriminador es la dirección del desfase respecto a la versión "
            "viva."
        ),
    },
    "name": "Documentación anclada a versiones obsoletas",
    "type": "antipattern",
    "category": "content-quality",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "Notas que mencionan versiones específicas de librerías, APIs o protocolos que ya "
        "fueron actualizadas, sin indicar que el contenido puede estar desactualizado."
    ),
    "signal": (
        "Notas con versiones hardcodeadas (v1.2.3) y updatedAt > 90 días. "
        "Desde v41.3, ejecutable: una nota que declara su código en `files:` "
        "y cuyo `updatedAt` es anterior al último commit que tocó esos "
        "ficheros (`vault_drift_detect --mode vigencia`)."
    ),
    "prevention": (
        "Declarar en `files:` los ficheros que la nota documenta y pasar "
        "`vault_drift_detect --mode vigencia` al cerrar la sesión. Quien "
        "comprueba que una nota sigue siendo cierta sin cambiarla lo deja en "
        "`revisado_en:` (contrato v41), que cuenta como acompañar al cambio. Agregar "
        "campo version_pinned al frontmatter con la versión referenciada."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_drift_detect"],
    "cobertura_parcial": (
        "Estuvo descubierta hasta v41.3. `vault_drift_detect --mode vigencia` "
        "mide **la mitad que la nota declara**: compara su `updatedAt` con el "
        "último commit de los ficheros que lista en `files:`, y cuenta aparte "
        "las notas sin `files:` y los `files:` que git no conoce, para que el "
        "silencio no pase por vigencia. Sigue sin medir la otra mitad de la "
        "señal —el número de versión escrito en el cuerpo— y la nota que "
        "documenta código sin declararlo: la relación no se adivina por el "
        "nombre del fichero. La vía decidible para el cuerpo era el "
        "`version_pinned:` que pide la `prevention`, cruzado con el "
        "manifiesto del repo declarado; medido el 2026-10-09 en las copias "
        "de ocho vaults consumidores, ninguna nota lo declara, y los "
        "`version:` que sí aparecen son la versión de la propia nota "
        "(`v1.01`), no la de un paquete. Un detector sobre un universo vacío "
        "saldría verde sin medir nada (AP-60), así que no se escribe hasta "
        "que alguna tool emita el campo."
    ),
    "introduced_version": "v19",
}

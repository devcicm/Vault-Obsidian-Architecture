"""AP-01 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-01",
    "distinguido_de": {
        "AP-04": (
            "Las dos documentan algo que el código no hace. AP-01 es la "
            "afirmación inventada: no hay implementación ni intención de tenerla, "
            "y el discriminador es que no existe rastro en el repo. AP-04 es el "
            "roadmap escrito en presente: la feature está planeada y la nota la "
            "presenta como ya entregada. Una se corrige borrando la afirmación; "
            "la otra, marcando el estado."
        ),
    },
    "name": "Documentación alucinada",
    "type": "antipattern",
    "category": "content-quality",
    "severity": "high",
    "enforcement": "audit",
    "description": (
        "Documentar herramientas, endpoints, funciones o comportamientos que no existen "
        "en el código real. El agente genera información convincente pero incorrecta."
    ),
    "signal": "Referencias a scripts/tools que no existen en el repo; funciones con firmas que no coinciden con el código.",
    "prevention": "Verificar existencia real antes de documentar. vault_read + grep sobre el código fuente.",
    "tools_enforcing": [],
    "tools_detecting": ["vault_drift_detect"],
    "cobertura_parcial": (
        "Estuvo descubierta hasta v41.3. `vault_drift_detect --mode vigencia` "
        "mide **la parte que la nota declara**: un fichero listado en `files:` "
        "que no existe en el repo sale en `codigo_inexistente` con la norma "
        "nombrada. Desde v41.3 mide también la ruta de código citada entre "
        "backticks en el cuerpo, que sale en `prosa_inexistente` sin entrar "
        "en `action_required`: fuera quedan los bloques de código, las notas "
        "de clase `registro`/`indice`, la documentación del estándar y la "
        "ruta cuyo nombre de fichero sí está en otro sitio del repo, que se "
        "cuenta aparte como base ambigua. Sigue sin medir lo que no es una "
        "ruta —un endpoint o una función citados en el cuerpo— y la firma que "
        "no coincide: verlas exige interpretar el texto."
    ),
    "introduced_version": "v19",
}

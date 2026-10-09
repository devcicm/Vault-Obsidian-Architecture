"""AP-56 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-56",
    "name": "Frontmatter presente que el consumidor no puede leer",
    "type": "antipattern",
    "category": "metadata-completeness",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "La nota abre `---`, escribe sus claves y, para `yaml.safe_load`, "
        "no tiene frontmatter: ni id, ni tags, ni tipo, ni estado. El "
        "bloque **se ve** al abrir el fichero, y por eso nadie lo revisa. "
        "El dato parece estar y no está.\n\n"
        "No es AP-28, que es la nota que nunca tuvo bloque y se cuenta "
        "sola. Aquí el hueco es invisible a ojo y solo aparece al medir "
        "con el parser real (AP-44).\n\n"
        "Dos causas, medidas sobre doce notas de cuatro vaults "
        "consumidores: **escalar sin escapar** —`title: Overview: demo` no "
        "es un mapeo, nueve de las doce— y **delimitador sin cerrar**, las "
        "otras tres, donde el bloque nunca se cierra y el parser se traga "
        "la nota entera hasta reventar cientos de líneas más abajo, en un "
        "bloque de código. El mensaje de YAML señala ahí, que no es donde "
        "está el fallo; por eso llevaban meses así.\n\n"
        "v40.2 arregló la prevención: `yaml_scalar` escapa antes de "
        "escribir. Lo que faltaba era la otra mitad — nada reparaba lo que "
        "ya estaba en disco, y `vault_fix_brackets` llevaba versiones "
        "haciendo exactamente eso para AP-22/AP-24."
    ),
    "signal": (
        "`vault_frontmatter_heal` lo cuenta en `unparseable_total`; "
        "`vault_foreign_check` lo publica como `frontmatter_unparseable` "
        "al medir un vault ajeno."
    ),
    "prevention": (
        "Escribir por tool, nunca a mano (SP-04): el write path pasa todo "
        "escalar por `yaml_scalar` desde v40.2. Lo ya escrito se repara "
        "con `vault_frontmatter_heal --apply`, que solo toca las dos "
        "causas mecánicas y se niega a adivinar el resto: completar un "
        "YAML truncado inventa dato, que es peor que el hueco."
    ),
    "tools_enforcing": ["vault_write", "vault_frontmatter_heal"],
    "tools_detecting": ["vault_frontmatter_heal", "vault_foreign_check"],
    "distinguido_de": {
        "AP-28": (
            "AP-28 es la nota sin bloque: el hueco se ve y se cuenta. "
            "AP-56 es la nota con bloque que no parsea, que para toda "
            "métrica es idéntica a AP-28 pero para un humano parece "
            "correcta. Se separan porque solo una de las dos se repara "
            "sin escribir metadatos nuevos."
        )
    },
    "introduced_version": "v40.12",
}

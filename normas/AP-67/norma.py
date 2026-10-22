"""AP-67 — el material que el agente opera, sin nota que lo apunte (deuda #10).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-67",
    "distinguido_de": {
        "AP-15": (
            "AP-15 es material ajeno **dentro** de la raíz del vault: ficheros "
            "sueltos que ni siquiera son notas. AP-67 es material **fuera** del "
            "vault —el código del proyecto, sus scripts de prueba, sus "
            "artefactos— que el agente opera y del que el vault no tiene "
            "ninguna nota. El discriminador es dónde está el material y qué "
            "le falta: en AP-15 sobra fuera de sitio; en AP-67 falta la nota "
            "que lo apunta."
        ),
        "AP-36": (
            "AP-36 mide los **efectos** de una tool: que no salgan del vault o "
            "que no quede rastro de ellos. AP-67 mide el **conocimiento**: que "
            "el vault no sepa qué material existe. Una tool puede tener "
            "efectos perfectamente contenidos y registrados (AP-36) y aun así "
            "dejar el vault sin saber qué se operó (AP-67)."
        ),
        "AP-05": (
            "AP-05 es el dato repetido: la misma verdad en dos sitios. AP-67 "
            "es el dato que no está en ninguno: el vault declara un proyecto y "
            "no tiene ni una nota de su código. Son las dos direcciones del "
            "mismo encargo —una sola fuente de verdad—: la de la copia y la "
            "de la ausencia."
        ),
    },
    "name": "El material que el agente opera, sin nota que lo apunte",
    "type": "antipattern",
    "category": "consistency",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "El agente opera material que vive fuera del vault —el código del "
        "proyecto, sus scripts de prueba, sus prompts, sus artefactos— y el "
        "vault no tiene ninguna nota que lo apunte. El trabajo se pierde al "
        "cerrar la sesión: la memoria no sabe qué se tocó, ni qué se probó, "
        "ni qué se decidió, y el material sigue fuera sin que ninguna puerta "
        "lo advierta. Medido el 2026-10-21 en un vault real: se ejecutaron "
        "cinco scripts de prueba del TTS y se documentaron sus resultados en "
        "el vault; los scripts quedaron fuera, sin nota que los apuntara, y "
        "el proyecto estaba enlazado al vault con cero notas de código. "
        "El caso es también el del acomodo: lo que entra al vault tiene que "
        "entrar por las tools —que son las que dejan el registro— y lo que "
        "queda fuera, enlazado."
    ),
    "signal": (
        "`vault_code_sync` informa `proyecto_sin_conocimiento` (un proyecto "
        "enlazado al vault sin una sola nota de su código) y "
        "`fuente_sin_nota` (los ficheros del repositorio que ninguna nota "
        "apunta, con recuento y muestra). `vault_audit` informa, en la misma "
        "dirección, del material sin nota a través de `missing_type` y "
        "`missingContract`: una nota que la tool escribió a medias es "
        "conocimiento a medias."
    ),
    "prevention": (
        "El proyecto se declara (`vault_project --add` y `--link`), y su "
        "material se documenta con las tools que dejan rastro: "
        "`vault_code_module` (nota de módulo con `source_file:`), "
        "`vault_test_save` (técnica de prueba), `vault_write` (concepto), "
        "`vault_move` (lo que se reubica, que deja `move-log.json`). El "
        "enlace va en los dos sentidos: la nota declara `source_file:` y el "
        "fichero lleva su `@vault:` — `vault_code_sync --fix` inyecta la mitad "
        "que falta. Lo que entra al vault entra por una tool; lo que sale, con "
        "ella."
    ),
    "tools_enforcing": ["vault_code_sync"],
    "tools_detecting": ["vault_code_sync"],
    "introduced_version": "v41.15",
    "revisado_en": "2026-10-21",
}

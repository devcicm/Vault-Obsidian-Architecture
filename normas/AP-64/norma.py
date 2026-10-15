"""AP-64 — la entrada del catálogo, en su paquete (deuda #10, segunda en migrar).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; el porqué de cada
cara está en `porque.md`.
"""

NORMA = {
    "code": "AP-64",
    "name": "Decisión cerrada sin responsable",
    "type": "antipattern",
    "category": "process",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "Un ADR aprobado es lo que un agente consulta antes de actuar: «esto "
        "se decidió así y por esto». Si nadie responde de ese porqué, el "
        "agente no distingue una decisión que tomó una persona de una que "
        "otro agente escribió y dio por buena. Medido en solo lectura contra "
        "un vault consumidor (regla 7, 2026-10-08): ninguno de sus ADR "
        "aceptados declara quién responde de él, y la mayoría tampoco "
        "declara `agent`.\n\n"
        "El criterio tiene dueño en `vault.kernel.contenido."
        "falta_de_responsable` y lo leen el scan y la auditoría. El régimen "
        "del estado lo deriva `vault_registry.regimen_de_estado`, así que "
        "`accepted` cuenta como `approved`."
    ),
    "signal": (
        "ADR (`es_adr`, la misma definición que AP-07) en un estado de "
        "régimen `cerrado` —salvo `template`— sin `responsable:` en el "
        "frontmatter, o con `responsable:` igual a su `agent:` cuando ese "
        "agente no es `human`."
    ),
    "prevention": (
        "Al cerrar una decisión, escribir `responsable:` con la persona que "
        "responde de ella (campo opcional del contrato v41). Un agente "
        "puede redactar el ADR y dejarlo en `draft` o `review`; aprobarlo "
        "con su propio nombre como responsable es lo que la norma marca. "
        "La guía de vault_audit propone el ADR con `meta_adr()` —en `draft`, "
        "sin `responsable` de relleno, que pasaría la norma sin nadie detrás—.\n\n"
        "Límites declarados: la norma no puede saber si el valor de "
        "`responsable` es de verdad una persona —solo que no es el agente "
        "que la escribió—, y solo mira los ADR de `03_Decisions/`; las "
        "decisiones de IA de `16_AI_Governance/` llevan su propio "
        "`human_approved`."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_norms"],
    "distinguido_de": {
        "AP-07": (
            "Las dos miran el mismo ADR. AP-07 pregunta si el porqué está "
            "escrito —contexto, decisión, consecuencias—; AP-64, si alguien "
            "responde de él. Un ADR puede tener las tres secciones y que "
            "nadie lo firme, o estar firmado y sin contexto."
        ),
        "AP-16": (
            "AP-16 registra quién **escribió** la nota; AP-64, quién "
            "**responde** de una decisión cerrada. Coinciden solo si la "
            "escribió una persona: un `agent: claude` con "
            "`responsable: claude` es el agente firmándose su propio porqué."
        ),
        "AP-65": (
            "Las dos piden a una decisión algo más que su porqué. AP-64 mira "
            "los ADR de `03_Decisions/` y pregunta quién responde de ellos; "
            "AP-65 mira las decisiones de IA de `16_AI_Governance/` y "
            "pregunta a quién afectan."
        ),
    },
    "introduced_version": "v41.3",
    "revisado_en": "2026-10-09",
}

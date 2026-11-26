"""SP-07 — Compactación adaptativa en 5 umbrales y recordatorios JIT por eventos (SPEC-06).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval`.
"""

NORMA = {
    "code": "SP-07",
    "distinguido_de": {
        "AP-81": (
            "AP-81 prohíbe saturar la ventana sin presupuesto ni offloading ni "
            "hard caps. SP-07 especifica el protocolo operativo por turno para "
            "ambos modos (Harness Nativo y Standalone CLI/MCP): la escalera de "
            "5 umbrales (70/80/85/90/99%) y los recordatorios JIT deduplicados "
            "disparados por eventos (`tool_error`, `consecutive_reads >= 5`, "
            "`post_code_edit`)."
        ),
    },
    "name": "Compactación adaptativa en 5 umbrales y recordatorios JIT por eventos",
    "type": "antipattern",
    "category": "session-protocol",
    "severity": "medium",
    "enforcement": "guard",
    "description": (
        "Esperar a que la ventana se llene al 100% para resumir 'todo o nada' "
        "y confiar únicamente en el system prompt inicial tras 15–20 llamadas "
        "degrada al agente en sesiones largas. SP-07 aplica una escalera "
        "progresiva en 5 umbrales (`70%` telemetría, `80%` enmascarado a "
        "punteros ~15 tokens, `85%` poda rápida sin LLM, `90%` enmascarado "
        "agresivo, `99%` volcado íntegro + compactación preservando turnos "
        "recientes) e inyecta recordatorios breves disparados por eventos "
        "(`tool_error`, `consecutive_reads >= 5`, `post_code_edit`) con "
        "`role='user'` en Harness Nativo y en `vault_says` en Standalone."
    ),
    "signal": (
        "`evaluar_presion_contexto` clasifica niveles 1..5 y `evaluar_triggers_jit` "
        "emite directivas acotadas a `max_active_jit_reminders` sin duplicados."
    ),
    "prevention": (
        "Invocar `vault.kernel.presupuesto_contexto.compactar_observaciones` y "
        "`evaluar_triggers_jit` en cada turno del harness o vía `vault_context_pack` "
        "y `vault_voice`."
    ),
    "tools_enforcing": ["vault_context_pack", "vault_voice"],
    "tools_detecting": [],
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-26",
}

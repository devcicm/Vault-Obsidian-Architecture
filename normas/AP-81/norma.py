"""AP-81 — Saturación de contexto sin presupuesto ni offloading a puntero (SPEC-06).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval`.
"""

NORMA = {
    "code": "AP-81",
    "distinguido_de": {
        "SP-07": (
            "AP-81 persigue la acumulación descontrolada de salidas pesadas y "
            "estructuras sin tope (hard caps) dentro de la ventana de contexto "
            "sin presupuesto ni offloading a punteros compactos. SP-07 define el "
            "protocolo de sesión completo que opera sobre ese presupuesto: la "
            "escalera adaptativa de 5 umbrales (70/80/85/90/99%) y los "
            "recordatorios JIT disparados por eventos con rol user."
        ),
    },
    "name": "Saturación de contexto sin presupuesto ni offloading a puntero",
    "type": "antipattern",
    "category": "process",
    "severity": "high",
    "enforcement": "guard",
    "description": (
        "Tratar la ventana de contexto de un agente LLM como un registro "
        "ilimitado en lugar de un presupuesto finito provoca que salidas "
        "masivas de terminal, lecturas completas y estructuras sin tope "
        "entierren las reglas críticas y colapsen la sesión tras 15–20 turnos. "
        "Toda consulta empaquetada respeta `budget_tokens` (`vault_context_pack`) "
        "y toda observación pesada se externaliza bajo `00_System/context-offload/` "
        "a un puntero compacto (~15 tokens) respetando `HARD_CAPS_CONTEXTO` "
        "(Modo A Harness Nativo y Modo B Standalone CLI/MCP)."
    ),
    "signal": (
        "Un paquete supera `budget_tokens` sin descartar/truncar notas enteras, "
        "o las observaciones/recordatorios de sesión crecen sin `HARD_CAPS_CONTEXTO` "
        "ni offloading a puntero."
    ),
    "prevention": (
        "Usar `vault_context_pack --budget` y las primitivas "
        "`vault.kernel.presupuesto_contexto.evaluar_presion_contexto` / "
        "`offload_texto_a_puntero` respetando `HARD_CAPS_CONTEXTO` y contención AP-36."
    ),
    "tools_enforcing": ["vault_context_pack"],
    "tools_detecting": [],
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-26",
}

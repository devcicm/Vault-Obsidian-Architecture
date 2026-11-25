"""SP-05 — Fábrica de Conocimiento en circuito cerrado (SPEC-04, Fase Q).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval`.
"""

NORMA = {
    "code": "SP-05",
    "distinguido_de": {
        "SP-04": (
            "SP-04 exige credencial y origen válidos para abrir la sesión MCP. "
            "SP-05 separa los privilegios dentro de esa sesión en circuito cerrado: "
            "el agente ejecutor (`ejecutor`) solo lee y levanta banderas `FLAG-NNN` "
            "en `vault_ronda --flag`, mientras únicamente el curador (`operador`) "
            "aplica cambios al conocimiento canónico vía `vault_propagate --curate-apply`."
        ),
        "SP-06": (
            "SP-05 gobierna la separación ejecutor↔curador y la cola de banderas "
            "`FLAG-NNN` sobre el conocimiento canónico del vault. SP-06 gobierna la "
            "disciplina opt-in de ingeniería XP (`xp_level: 1..4`) sobre requisitos "
            "(`buffer`, compuerta TDD) y revisión de código (`vault_code_review`)."
        ),
    },
    "name": "Separación Ejecutor-Curador y trazabilidad de banderas en la Fábrica de Conocimiento",
    "type": "antipattern",
    "category": "session-protocol",
    "severity": "high",
    "enforcement": "guard",
    "description": (
        "Un agente ejecutor que edita directamente el conocimiento canónico "
        "(`03_Decisions/`, `07_Knowledge/`, `08_Runbooks/`, `17_Preferences/`) "
        "durante una tarea en caliente introduce deriva, contradicciones "
        "silenciosas y vector de envenenamiento. SP-05 formaliza el circuito "
        "cerrado Ejecutor → Bandera (`00_System/.flags.jsonl`, `FLAG-NNN` con "
        "`scan_poison`) → Curador batch (`vault_propagate --curate-plan/--curate-apply`, "
        "estampado de `source_flags`/`trace_ref`, `PAT-7` para desacuerdos y "
        "reporte en `19_Audits/curation/`)."
    ),
    "signal": (
        "Un agente con perfil `ejecutor` intenta invocar tools de mutación canónica "
        "(`vault_write`, `vault_delete`, `vault_propagate`), una bandera contiene "
        "prompt injection, o una curación batch muta notas sin `source_flags` ni "
        "fila `curated` en `00_System/.change-log.jsonl`."
    ),
    "prevention": (
        "Asignar `VAULT_MCP_ROL=ejecutor` (stdio) o `VAULT_MCP_TOKENS=ejecutor:<t>` "
        "(HTTP/SSE) a agentes ejecutores: solo acceden a herramientas `lector` y "
        "señales acotadas (`vault_ronda`, `vault_log_error`). Levantar señales "
        "con `vault_ronda --flag` (pre-vuelo `scan_poison` obligatorio) y curar en "
        "lote bajo perfil `operador` con `vault_propagate --curate-plan` / "
        "`--curate-apply` / `--mark-contradicts`."
    ),
    "tools_enforcing": ["vault_ronda", "vault_propagate"],
    "tools_detecting": [],
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-25",
}

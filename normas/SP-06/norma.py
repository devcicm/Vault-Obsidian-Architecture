"""SP-06 — Madurez progresiva XP / Augmented Coding (`xp_level: 1..4`, SPEC-03, Fase R).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval`.
"""

NORMA = {
    "code": "SP-06",
    "distinguido_de": {
        "SP-05": (
            "SP-05 separa privilegios ejecutor↔curador y gobierna la cola de banderas "
            "`FLAG-NNN` sobre el conocimiento canónico del vault. SP-06 gobierna la "
            "disciplina de ingeniería y verificación del código en proyectos opt-in "
            "(`xp_level: 1..4` en `00_System/reglas.json`): holgura explícita de "
            "historias (`buffer: critical|optional`), compuerta TDD obligatoria "
            "antes de `implemented`/`verified` (Nivel 2+), detección de diffs "
            "monolíticos y revisor humano en pareja (Nivel 3+), y bloqueo de "
            "salto directo a Trunk-Based (Nivel 4 sin `xp_prerequisites`)."
        ),
    },
    "name": "Madurez progresiva XP y disciplina Augmented Coding (opt-in)",
    "type": "antipattern",
    "category": "session-protocol",
    "severity": "high",
    "enforcement": "guard",
    "description": (
        "Adoptar velocidad de generación asistida por LLM sin progresión de "
        "prácticas XP (holgura explícita, TDD rojo-verde-refactor, iteraciones "
        "pequeñas con revisión humana) convierte la IA en un multiplicador de "
        "deuda técnica y regresiones. SP-06 activa de forma opt-in `xp_level: 1..4` "
        "en `00_System/reglas.json` (validación O(1) fail-closed): Nivel 1 "
        "habilita clasificación `buffer: critical|optional` en requisitos; Nivel 2 "
        "bloquea pasar requisitos a `implemented`/`verified` sin evidencia "
        "`test_result: pass` en `15_Tests/` y escala `NO_TESTS_TOUCHED` a "
        "`blocker` en `vault_code_review`; Nivel 3 avisa ante diffs monolíticos "
        "y exige revisor humano válido (`AP-64`); Nivel 4 exige `xp_prerequisites` "
        "verificados (`tdd_pass: true`, `human_pair_review: true`)."
    ),
    "signal": (
        "`00_System/reglas.json` declara `xp_level` fuera de `1..4` o Nivel 4 "
        "sin `xp_prerequisites` verificados; o bajo `xp_level >= 2` un requisito "
        "pasa a `implemented`/`verified` sin test en verde en `15_Tests/`, o "
        "`vault_code_review` detecta código sin pruebas (`NO_TESTS_TOUCHED`), "
        "iteración monolítica (`XP_MONOLITHIC_DIFF`) o revisor no humano "
        "(`XP_REVIEWER_INVALID`)."
    ),
    "prevention": (
        "Declarar `xp_level` (1..4) en `00_System/reglas.json` solo cuando el "
        "proyecto adopta progresivamente XP; clasificar historias con "
        "`vault_requirement_save --buffer critical|optional`; registrar evidencia "
        "de tests en `15_Tests/` antes de cerrar requisitos; revisar diffs "
        "incrementales con `vault_code_review --reviewer <persona>` y emitir "
        "cláusula compacta en adaptadores con `vault_preferences --adapters`."
    ),
    "tools_enforcing": ["vault_requirement_save", "vault_code_review", "vault_preferences"],
    "tools_detecting": [],
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-25",
}

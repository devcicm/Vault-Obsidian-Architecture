# SP-06 — Madurez progresiva XP y disciplina Augmented Coding (opt-in)

## Por qué existe

Formaliza `SPEC-03` (Augmented Coding / XP progresivo) sobre la arquitectura
100 % Markdown + JSON + Git sin terceros, sin bases de datos ni embeddings:
protege contra la generación monolítica sin pruebas y contra el salto
prematuro a Trunk-Based (Nivel 4) mediante una política opt-in O(1) en
`00_System/reglas.json` (`xp_level: 1..4`) que solo se aplica a los vaults que
la declaran.

## Las caras

- **Aplica** (`tools_enforcing`): `scripts/vault_requirement_save.py::vault_requirement_save`, `scripts/vault_code_review.py::vault_code_review`, `scripts/vault_preferences.py::vault_preferences_adapters`, `vault/kernel/normativa/xp.py::validar_politica_xp`.
- **Tests** (`tests/`): `normas/SP-06/test_sp06.py::test_sp06_politica_xp_y_compuerta_tdd`, `tests/test_xp_augmented_coding_fase_r.py::test_r_escalera_xp_niveles_1_a_4_y_retrocompatibilidad`.

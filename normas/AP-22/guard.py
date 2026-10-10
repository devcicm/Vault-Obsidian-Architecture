"""AP-22 — las caras que la aplican y la detectan (deuda #10).

Derivado, no escrito: cada `ruta::símbolo` es una función de una tool de
`tools_enforcing`, `tools_detecting` o `tools_del_patron` que nombra la
norma en su cuerpo. El criterio sigue con su dueño; aquí solo se apunta a
él. `vault_norms --check-framework` falla si esto deja de ser lo que sale
de derivarlo; se regenera con `vault_norms_engine.escribir_caras_derivadas`.
"""

GUARD = [
    'scripts/vault_write.py::_check_content_gate',
    'scripts/vault_write.py::_content_gate_reason',
    'scripts/vault_write.py::_check_bracket_balance',
    'scripts/vault_write.py::vault_write',
    'scripts/vault_audit.py::_detect_malformed_wikilinks',
    'scripts/vault_audit.py::vault_audit',
    'scripts/vault_fix_brackets.py::_analyze_note',
    'scripts/vault_fix_brackets.py::main',
]

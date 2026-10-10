"""AP-26 — las caras que la aplican y la detectan (deuda #10).

Derivado, no escrito: cada `ruta::símbolo` es una función de una tool de
`tools_enforcing`, `tools_detecting` o `tools_del_patron` que nombra la
norma en su cuerpo. El criterio sigue con su dueño; aquí solo se apunta a
él. `vault_norms --check-framework` falla si esto deja de ser lo que sale
de derivarlo; se regenera con `vault_norms_engine.escribir_caras_derivadas`.
"""

GUARD = [
    'scripts/vault_write.py::vault_write',
    'scripts/vault_ingest.py::_build_note',
    'scripts/vault_preferences.py::vault_preferences_set',
    'scripts/vault_frontmatter_completar.py::_valor',
    'scripts/vault_audit.py::vault_audit',
]

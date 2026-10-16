"""AP-15 — las caras que la aplican y la detectan (deuda #10).

Derivado, no escrito: cada `ruta::símbolo` es una función de una tool de
`tools_enforcing`, `tools_detecting` o `tools_del_patron` que nombra la
norma en su cuerpo. El criterio sigue con su dueño; aquí solo se apunta a
él. `vault_norms --check-framework` falla si esto deja de ser lo que sale
de derivarlo; se regenera con `vault_norms_engine.escribir_caras_derivadas`.
"""

GUARD = [
    'scripts/vault_write.py::vault_write',
    'scripts/vault_move.py::_destino_invalido',
    'scripts/vault_section_index.py::vault_section_index',
    'vault/gobernanza/auditoria_runtime.py::auditar_runtime',
]

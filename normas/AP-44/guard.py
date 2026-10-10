"""AP-44 — las caras que la aplican y la detectan (deuda #10).

Derivado, no escrito: cada `ruta::símbolo` es una función de una tool de
`tools_enforcing`, `tools_detecting` o `tools_del_patron` que nombra la
norma en su cuerpo. El criterio sigue con su dueño; aquí solo se apunta a
él. `vault_norms --check-framework` falla si esto deja de ser lo que sale
de derivarlo; se regenera con `vault_norms_engine.escribir_caras_derivadas`.
"""

GUARD = [
    'scripts/vault_audit.py::_build_indexes',
    'scripts/vault_audit.py::_detect_broken_links',
    'scripts/vault_audit.py::_detect_missing_metadata',
    'scripts/vault_audit.py::vault_audit',
    'scripts/vault_audit.py::_audit_external_path',
    'vault/grafo/graph_fix.py::_add_stems',
    'scripts/vault_norms.py::vault_norms_scan',
    'scripts/vault_norms.py::vault_norms_apply',
]

"""CN-02 — las caras que la aplican y la detectan (deuda #10).

Derivado, no escrito: cada `ruta::símbolo` es una función de una tool de
`tools_enforcing`, `tools_detecting` o `tools_del_patron` que nombra la
norma en su cuerpo. El criterio sigue con su dueño; aquí solo se apunta a
él. `vault_norms --check-framework` falla si esto deja de ser lo que sale
de derivarlo; se regenera con `vault_norms_engine.escribir_caras_derivadas`.
"""

GUARD = [
    'scripts/vault_write.py::problemas_de_meta',
    'scripts/vault_write.py::vault_write',
    'vault/indices/registro_de_secciones.py::listar',
    'vault/indices/registro_de_secciones.py::main',
    'scripts/vault_move.py::_destino_invalido',
    'scripts/vault_move.py::_reclasificacion',
    'scripts/vault_move.py::move_folder',
    'scripts/vault_section_index.py::vault_section_index',
    'scripts/vault_norms.py::main',
    'vault/kernel/norms_catalog.py::compute_norm_refs',
    'vault/gobernanza/auditoria_runtime.py::auditar_runtime',
]

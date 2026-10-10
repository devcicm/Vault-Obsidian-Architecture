"""AP-63 — las caras que la reparan en una nota que ya existe (deuda #10).

Derivado, no escrito: las tools salen de `vault_norms_catalog.SANADORES`
y cada `ruta::símbolo` es una función suya que nombra la norma en su
cuerpo. `vault_norms --check-framework` falla si esto deja de ser lo que
sale de derivarlo.
"""

HEAL = [
    'scripts/vault_project.py::auditar',
    'scripts/vault_project.py::sanar',
    'scripts/vault_project.py::_ficha_nueva',
    'scripts/vault_project.py::main',
]

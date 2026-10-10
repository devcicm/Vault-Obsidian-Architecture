"""AP-12 — las caras que la reparan en una nota que ya existe (deuda #10).

Derivado, no escrito: las tools salen de `vault_norms_catalog.SANADORES`
y cada `ruta::símbolo` es una función suya que nombra la norma en su
cuerpo. `vault_norms --check-framework` falla si esto deja de ser lo que
sale de derivarlo.
"""

HEAL = [
    'vault/autoria/frontmatter_completar.py::_valor',
]

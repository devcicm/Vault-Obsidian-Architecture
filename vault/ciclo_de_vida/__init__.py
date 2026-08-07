"""Contexto **Ciclo de vida**: cómo nace, migra y se sana un vault.

Lenguaje ubicuo: versión, migración, sanación, arranque, propagación, staging,
rollback. Es dueño de `standard-version.json`, de `identity.md`, de
`10_Migrated/` con su `_staging/` y de la cola de propagación.

Es el único contexto que se ejecuta **contra vaults ajenos** por diseño: el modo
agéntico de sanación apunta con `VAULT_ROOT` a un vault que no construyó este
estándar. Por eso la raíz que recibe y la que el proceso detecta casi nunca
coinciden, y por eso congelarla aquí es más caro que en ningún otro sitio —
`vault_sanacion` medía las fases 2, 4 y 12 contra el vault equivocado
devolviendo un plan verosímil, sin excepción que lo delatara.
"""

from .repositorio import RepositorioCicloDeVida

__all__ = ["RepositorioCicloDeVida"]

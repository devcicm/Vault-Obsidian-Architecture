"""Contexto **Autoría**: la nota y todo lo que se escribe dentro de ella.

Lenguaje ubicuo: nota, frontmatter, slug, sección, alias, historial.

Es el contexto grande —38 módulos, los 17 `*_save` entre ellos— y el último en
migrarse por eso mismo. Concentraba **los 31 vínculos congelados restantes de
AP-49**: al llegar aquí, el 100% de la deuda. Los otros ocho contextos ya
estaban a cero.

La causa es visible en el diff: cada `*_save` nació copiando el de al lado, y
con él copió `SECCION_DIR = VAULT_ROOT / "0X_Loquesea"` evaluado en tiempo de
import. Veinticinco módulos derivando a mano una ruta que `vault_registry`
declara. Por eso `RepositorioAutoria` no enumera secciones: las pide por nombre
y valida contra `ORDERED_SECTIONS`.
"""

from .repositorio import RepositorioAutoria

__all__ = ["RepositorioAutoria"]

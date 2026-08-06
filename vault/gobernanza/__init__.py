"""Contexto **Gobernanza**: la norma y su cumplimiento.

Lenguaje ubicuo: norma, guard, enforcement, severidad, violación, puntuación de
calidad, deriva. Es dueño del registro de normas, del índice de calidad, de la
instantánea de sesión y de `02_Observability/vulnerabilities/`.

Es el contexto con más acoplamiento entrante del estándar: veintisiete módulos
de siete contextos importan `vault_norms`. Eso no se salda aquí —son los
consumidores quienes tienen que pasar por el puerto— y sigue declarado como
deuda en la baseline de `vault_arch`.
"""

from .repositorio import RepositorioGobernanza

__all__ = ["RepositorioGobernanza"]

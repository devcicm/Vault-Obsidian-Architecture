"""Contexto acotado **Durabilidad**: backup, restauración, cuarentena, manifiesto.

Piloto del refactor. Se eligió éste porque es pequeño (966 líneas), porque
atraviesa los dos runtimes —que es donde vivió AP-48— y porque v39.6 acababa de
darle tests reales que sirven de red.

Lo que cambia: la decisión —dónde vive un backup, qué entra y qué no, si una
ruta está contenida— sale de los scripts y pasa a estar aquí, expresada una vez.
Lo que **no** cambia: argv y envelope de las cuatro tools, byte a byte. Eso lo
vigila `tests/test_durabilidad_caracterizacion.py`, capturado antes de mover
nada; si falla, el refactor rompió un contrato y se revierte.

El dominio recibe un `VaultContext` y no importa `VAULT_ROOT` (AP-49). Por eso
dos vaults pueden vivir en el mismo intérprete sin contaminarse, que es lo que
`cli/runner.py` compensa hoy con un subproceso por tool.
"""

from .modelo import Backup, RegistroBackups
from .repositorio import RepositorioDurabilidad

__all__ = ["Backup", "RegistroBackups", "RepositorioDurabilidad"]

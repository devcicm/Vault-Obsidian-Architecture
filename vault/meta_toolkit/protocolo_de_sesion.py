"""Reexportación: el protocolo de sesión vive en `vault.kernel.protocolo_de_sesion`.

superseded_by: vault.kernel.protocolo_de_sesion (2026-11-16). Es una hoja sin
dependencias que también lee la consulta (`vault_preferences --adapters` publica
los pasos en el adaptador de cliente), y desde aquí ese lector habría abierto un
cruce consulta -> meta_toolkit. El contrato no cambia: los mismos nombres, del
mismo objeto.
"""

import sys

import vault.kernel.protocolo_de_sesion as _dueno

# El mismo módulo, no una copia de sus nombres: un `import *` dejaría fuera lo
# privado (`_tools_del_protocolo`, que lee `vault_servicio`) y daría dos objetos
# que divergen en cuanto alguien parchee uno.
sys.modules[__name__] = _dueno

"""Reexportación: la selección de tests por impacto vive en `vault.meta_toolkit.estandar.test_scope`.

superseded_by: vault.meta_toolkit.estandar.test_scope (B-3 de la reestructura,
2026-10-31). Sigue en el contexto meta_toolkit, dentro del subpaquete que no
viaja en la wheel; este alias tampoco viaja. El contrato no cambia: los mismos
nombres, del mismo objeto, y `python -m vault.meta_toolkit.test_scope` corre el
`__main__` del dueño.
"""

import sys

if __name__ == "__main__":
    # Ejecutado como módulo, el `__main__` es el del dueño: un alias en
    # `sys.modules` no lo correría, porque el dueño se carga con su nombre.
    import runpy

    runpy.run_module("vault.meta_toolkit.estandar.test_scope", run_name="__main__", alter_sys=True)
else:
    import vault.meta_toolkit.estandar.test_scope as _dueno

    # El mismo módulo, no una copia de sus nombres: un `import *` dejaría fuera
    # lo privado y daría dos objetos que divergen en cuanto alguien parchee uno.
    sys.modules[__name__] = _dueno

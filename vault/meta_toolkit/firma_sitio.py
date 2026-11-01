"""Reexportación: la firma de sitio vive en `vault.meta_toolkit.estandar.firma_sitio`.

superseded_by: vault.meta_toolkit.estandar.firma_sitio (B-3 de la reestructura,
2026-10-31). Sigue en el contexto meta_toolkit, dentro del subpaquete que no
viaja en la wheel; este alias tampoco viaja. El contrato no cambia: los mismos
nombres, del mismo objeto.
"""

import sys

import vault.meta_toolkit.estandar.firma_sitio as _dueno

# El mismo módulo, no una copia de sus nombres: un `import *` dejaría fuera lo
# privado y daría dos objetos que divergen en cuanto alguien parchee uno.
sys.modules[__name__] = _dueno

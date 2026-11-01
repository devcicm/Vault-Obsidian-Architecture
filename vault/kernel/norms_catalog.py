"""Reexportación: el catálogo de normas AP/PAT/SP/CN y su enforcement vive en `vault.kernel.normativa.norms_catalog`.

superseded_by: vault.kernel.normativa.norms_catalog (B-1 de la reestructura,
2026-10-31). Sigue en el kernel, dentro del subpaquete de la normativa. El
contrato no cambia: los mismos nombres, del mismo objeto.
"""

import sys

from .normativa import norms_catalog as _dueno

# El mismo módulo, no una copia de sus nombres: un `import *` dejaría fuera lo
# privado y daría dos objetos que divergen en cuanto alguien parchee uno.
sys.modules[__name__] = _dueno

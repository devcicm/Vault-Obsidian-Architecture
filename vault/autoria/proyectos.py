"""Reexportación: el registro de proyectos vive en `vault.kernel.proyectos`.

superseded_by: vault.kernel.proyectos (v40.34, AP-63). El nombre de un
proyecto es identidad que leen todos los contextos, no vocabulario de Autoría;
desde aquí cada tool de otro contexto que resolviera su `--project` sumaba un
cruce. El contrato no cambia: los mismos nombres, del mismo objeto.
"""

import sys

from ..kernel import proyectos as _dueno

# El mismo módulo, no una copia de sus nombres: un `import *` dejaría fuera lo
# privado y daría dos objetos que divergen en cuanto alguien parchee uno.
sys.modules[__name__] = _dueno

"""Reexport de no-derogación: la cola de banderas `SP-05` vive en `vault.kernel.banderas`."""

from ..kernel.banderas import (  # noqa: F401
    ESTADOS_BANDERA,
    FICHERO_FLAGS,
    TIPOS_BANDERA,
    actualizar_estado_bandera,
    levantar_bandera,
    listar_banderas,
)

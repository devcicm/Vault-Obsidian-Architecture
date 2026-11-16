"""The producer of the `bitacora_cambios` port (`vault.kernel.puertos.BitacoraCambios`).

Consulta (`vault_ingest`) and gobernanza (`vault_audit`) need to write the
operation log, and ingest needs to apply the appends it proposes. Both writers
are autoria's: `vault_change_log_add` and `vault_append`. Importing them from
another context is a crossing `vault_arch` refuses, so this module offers
them through the kernel's producer registry on import, and `vault.runtime`
composes it on demand — the same mechanism as `indices` (`vault_section_index`)
and `tags` (`vault_tags`).

It adds no logic of its own: each operation is the owner's function with the
owner's envelope. A second implementation of the append or of the log row
would be AP-57; here there is none.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from vault.autoria.append import vault_append
from vault_change_log import vault_change_log_add


class _BitacoraDeCambios:
    """Adapter: the port's two operations, delegated to their owners."""

    def anotar(self, accion: str, ruta: str, motivo: str, agente: str) -> Dict[str, Any]:
        return vault_change_log_add(accion, ruta, motivo, agent=agente)

    def anexar(self, ruta: str, contenido: str, seccion: Optional[str] = None,
               con_fecha: bool = True) -> Dict[str, Any]:
        return vault_append(ruta, contenido, seccion, con_fecha)


def _ofrecer() -> None:
    """Offers itself to the kernel's producer registry."""
    from vault.kernel.productores import registrar

    registrar("bitacora_cambios", _BitacoraDeCambios())


_ofrecer()

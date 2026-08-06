"""Las rutas del contexto Ciclo de vida, derivadas del contexto inyectado.

Cuatro vínculos los contaba el guard de AP-49 y cuatro más no, por derivar de
ellos sin nombrar `VAULT_ROOT`: `STAGING_DIR = MIGRATED_DIR / "_staging"`,
`VERSION_FILE`, `IDENTITY_FILE` y `PROPAGATION_QUEUE`.

`propagation-queue.json` la escribe también `vault_audit`, que es de Gobernanza.
No se unifica aquí a propósito: el fichero es de Gobernanza —quien lo declara es
`RepositorioGobernanza.cola_propagacion`— y `vault_propagate` lo recibe de allí.
Declararlo dos veces sería AP-05 recién estrenado en el refactor que existe para
cerrarlo.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..kernel.contexto import VaultContext

CARPETA_SISTEMA = "00_System"
CARPETA_MIGRADOS = "10_Migrated"
CARPETA_INDICES = "99_Index"
SUBCARPETA_STAGING = "_staging"

FICHERO_VERSION = "standard-version.json"
FICHERO_IDENTIDAD = "identity.md"
FICHERO_INDICE_BUSQUEDA = "search-index.json"


class RepositorioCicloDeVida:
    """Único sitio del contexto que resuelve rutas y toca disco."""

    def __init__(self, ctx: VaultContext) -> None:
        self._ctx = ctx

    @property
    def ctx(self) -> VaultContext:
        return self._ctx

    @property
    def raiz(self) -> Path:
        return self._ctx.raiz

    # ── Rutas, todas contenidas por `ctx.ruta()` (AP-36) ─────────────────────

    @property
    def dir_sistema(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA)

    @property
    def dir_migrados(self) -> Path:
        return self._ctx.ruta(CARPETA_MIGRADOS)

    @property
    def dir_staging(self) -> Path:
        return self._ctx.ruta(CARPETA_MIGRADOS, SUBCARPETA_STAGING)

    @property
    def dir_indices(self) -> Path:
        return self._ctx.ruta(CARPETA_INDICES)

    @property
    def fichero_version(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_VERSION)

    @property
    def fichero_identidad(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_IDENTIDAD)

    @property
    def indice_busqueda(self) -> Path:
        return self._ctx.ruta(CARPETA_INDICES, FICHERO_INDICE_BUSQUEDA)

    # ── Lectura tolerante ────────────────────────────────────────────────────

    def relativa(self, ruta: Path) -> str:
        return str(Path(ruta).relative_to(self.raiz)).replace("\\", "/")

    def leer_json(self, ruta: Path) -> dict:
        try:
            datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError, json.JSONDecodeError, OSError):
            return {}
        return datos if isinstance(datos, dict) else {}

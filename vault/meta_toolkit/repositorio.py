"""Las rutas del contexto Meta-toolkit, derivadas del contexto inyectado.

Solo dos ficheros son suyos: `tools-manifest.json` y `spec-memory.json`. Los
otros cuatro que `vault_spec_memory` derivaba —`quality-index.json`,
`propagation-queue.json`, `.change-log.json`, `standard-version.json`— son de
Gobernanza y de Ciclo de vida, y se leen de allí. Declararlos aquí habría hecho
que `quality-index.json` se calculara en cuatro módulos de tres contextos: AP-05
multiplicado, no un atajo.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..kernel.contexto import VaultContext

CARPETA_SISTEMA = "00_System"

FICHERO_MANIFIESTO_TOOLS = "tools-manifest.json"
FICHERO_MEMORIA_SPEC = "spec-memory.json"


class RepositorioMetaToolkit:
    """Único sitio del contexto que resuelve rutas y toca disco."""

    def __init__(self, ctx: VaultContext) -> None:
        self._ctx = ctx

    @property
    def ctx(self) -> VaultContext:
        return self._ctx

    @property
    def raiz(self) -> Path:
        return self._ctx.raiz

    @property
    def dir_sistema(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA)

    @property
    def manifiesto_tools(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_MANIFIESTO_TOOLS)

    @property
    def memoria_spec(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_MEMORIA_SPEC)

    # ── Lectura tolerante ────────────────────────────────────────────────────

    def relativa(self, ruta: Path) -> str:
        return str(Path(ruta).relative_to(self.raiz)).replace("\\", "/")

    def leer_json(self, ruta: Path) -> dict:
        try:
            datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError, json.JSONDecodeError, OSError):
            return {}
        return datos if isinstance(datos, dict) else {}

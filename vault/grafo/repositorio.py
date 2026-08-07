"""Las rutas del contexto Grafo, derivadas del contexto inyectado.

Las dieciocho constantes que había repartidas entre once módulos no eran
dieciocho ubicaciones: eran once. `GRAPH_FILE` se calculaba en tres ficheros,
`CODE_DIR` en cinco y `ENTITY_DIR` en dos. Cada copia era una oportunidad de
que una se moviera y las otras no (AP-05), y todas se congelaban al importar
(AP-49).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..kernel.contexto import VaultContext

#: Nombres en disco. Son contrato con quien los lee desde fuera —Obsidian, el
#: servidor MCP, otro vault—, así que se declaran, no se derivan.
CARPETA_INDICES = "99_Index"
CARPETA_SISTEMA = "00_System"
CARPETA_CODIGO = "11_Code"
CARPETA_DIAGRAMAS = "06_Diagrams"
CARPETA_INFRA = "09_Infrastructure"
SUBCARPETA_ENTIDADES = "entity"

FICHERO_GRAFO = "graph.json"
FICHERO_GRAFO_ENRIQUECIDO = "graph-enriched.json"
FICHERO_INDICE_CODIGO = ".code-index.json"
FICHERO_REGISTRO_ETIQUETAS_CODIGO = "code-tag-registry.json"
FICHERO_BITACORA_MOVIMIENTOS = "move-log.json"


class RepositorioGrafo:
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
    def dir_indices(self) -> Path:
        return self._ctx.ruta(CARPETA_INDICES)

    @property
    def dir_sistema(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA)

    @property
    def dir_codigo(self) -> Path:
        return self._ctx.ruta(CARPETA_CODIGO)

    @property
    def dir_diagramas(self) -> Path:
        return self._ctx.ruta(CARPETA_DIAGRAMAS)

    @property
    def dir_entidades(self) -> Path:
        return self._ctx.ruta(CARPETA_DIAGRAMAS, SUBCARPETA_ENTIDADES)

    @property
    def dir_infra(self) -> Path:
        return self._ctx.ruta(CARPETA_INFRA)

    @property
    def grafo(self) -> Path:
        return self._ctx.ruta(CARPETA_INDICES, FICHERO_GRAFO)

    @property
    def grafo_enriquecido(self) -> Path:
        return self._ctx.ruta(CARPETA_INDICES, FICHERO_GRAFO_ENRIQUECIDO)

    @property
    def indice_codigo(self) -> Path:
        return self._ctx.ruta(CARPETA_CODIGO, FICHERO_INDICE_CODIGO)

    @property
    def registro_etiquetas_codigo(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_REGISTRO_ETIQUETAS_CODIGO)

    @property
    def bitacora_movimientos(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_BITACORA_MOVIMIENTOS)

    @property
    def bitacora_cambios(self) -> Path:
        """La bitácora es de Gobernanza. `vault_impact` la lee, no la define."""
        from ..gobernanza.repositorio import RepositorioGobernanza

        return RepositorioGobernanza(self._ctx).bitacora_cambios

    # ── Lectura tolerante ────────────────────────────────────────────────────

    def relativa(self, ruta: Path) -> str:
        """Ruta relativa al vault con separador POSIX.

        El grafo lo consume Obsidian y el MCP; un `\\` lo deja sin resolver en
        otra plataforma.
        """
        return str(Path(ruta).relative_to(self.raiz)).replace("\\", "/")

    def leer_json(self, ruta: Path) -> dict:
        """`{}` si falta o está corrupto. Quien necesite distinguir los dos
        casos mira `ruta.exists()`: aquí degradar en silencio sería AP-37."""
        try:
            datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError, json.JSONDecodeError, OSError):
            return {}
        return datos if isinstance(datos, dict) else {}

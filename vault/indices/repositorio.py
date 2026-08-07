"""Las rutas del contexto Índices, todas derivadas del contexto inyectado.

Aquí vivían ocho constantes de nivel de módulo repartidas entre
`vault_folder_registry`, `vault_master_index`, `vault_reindex` y `vault_tags`,
cada una haciendo `VAULT_ROOT / "99_Index" / ...` al importarse. Eso es AP-49 en
su forma literal: `set_vault_root()` no podía reapuntarlas porque ya estaban
calculadas, y el guard las contaba una por una.

No es una simplificación cosmética. Que cuatro módulos derivaran la misma
ubicación por su cuenta es también AP-05: cuando `hash-index.json` cambió de
sitio hubo que acordarse de los cuatro.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..kernel.contexto import VaultContext

#: Nombres de fichero del contexto. Se declaran aquí y no en cada servicio
#: porque son contrato con quien los lee desde fuera (Obsidian, el MCP, otro
#: vault): renombrarlos rompe ficheros que ya existen en disco.
CARPETA_INDICES = "99_Index"
CARPETA_SISTEMA = "00_System"
CARPETA_AUDITORIAS = "19_Audits"

FICHERO_BUSQUEDA = "search-index.json"
FICHERO_HASHES = "hash-index.json"
FICHERO_INDICE_MAESTRO = "index.md"
FICHERO_INDICE_ETIQUETAS = "tag-index.md"
FICHERO_REGISTRO_CARPETAS = "custom-folders.json"
FICHERO_REGISTRO_ETIQUETAS = "tag-registry.json"
FICHERO_BITACORA_ETIQUETAS = "tag-ledger.json"


class RepositorioIndices:
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
    def dir_vocabulario(self) -> Path:
        return self._ctx.ruta(CARPETA_AUDITORIAS, "vocabulary")

    @property
    def indice_busqueda(self) -> Path:
        return self._ctx.ruta(CARPETA_INDICES, FICHERO_BUSQUEDA)

    @property
    def indice_hashes(self) -> Path:
        return self._ctx.ruta(CARPETA_INDICES, FICHERO_HASHES)

    @property
    def grafo(self) -> Path:
        """El grafo lo construye Grafo. Índices lo lee para cruzarlo."""
        from ..grafo.repositorio import RepositorioGrafo

        return RepositorioGrafo(self._ctx).grafo

    @property
    def indice_maestro(self) -> Path:
        return self._ctx.ruta(CARPETA_INDICES, FICHERO_INDICE_MAESTRO)

    @property
    def indice_etiquetas(self) -> Path:
        return self._ctx.ruta(CARPETA_INDICES, FICHERO_INDICE_ETIQUETAS)

    @property
    def registro_carpetas(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_REGISTRO_CARPETAS)

    @property
    def registro_etiquetas(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_REGISTRO_ETIQUETAS)

    @property
    def bitacora_etiquetas(self) -> Path:
        return self.dir_vocabulario / FICHERO_BITACORA_ETIQUETAS

    def relativa(self, ruta: Path) -> str:
        """La forma en que el estándar escribe una ruta: relativa y con `/`.

        Está aquí y no en cada servicio porque el separador viaja al JSON: un
        índice escrito en Windows con `\\` es un índice que el consumidor de
        otra plataforma no puede resolver.
        """
        return str(Path(ruta).relative_to(self.raiz)).replace("\\", "/")

    # ── Lectura tolerante ────────────────────────────────────────────────────

    def leer_json(self, ruta: Path) -> dict:
        """Un JSON ilegible es «no hay», nunca una excepción hacia arriba.

        Es el mismo criterio que el repositorio de Durabilidad, y por la misma
        razón: quien reconstruye un índice ya tiene un problema, y reventar por
        un fichero corrupto es justo cuando más daño hace. Lo que **no** hace es
        silenciar el desfase: `coherencia_indice()` distingue `index_missing` de
        `index_corrupt` precisamente para que la degradación se vea (AP-37).
        """
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError, json.JSONDecodeError, OSError):
            return {}
        return datos if isinstance(datos, dict) else {}

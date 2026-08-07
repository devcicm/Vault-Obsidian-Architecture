"""Las rutas del contexto Gobernanza, derivadas del contexto inyectado.

Siete vínculos congelados que el guard contaba, más ocho derivados de ellos que
no contaba porque no mencionaban `VAULT_ROOT` —`QUALITY_INDEX = SYSTEM_DIR /
"quality-index.json"`— pero se evaluaban en el mismo import y quedaban igual de
inertes.

Dos ubicaciones se calculaban en dos módulos cada una: `quality-index.json` en
`vault_audit` y `vault_quality_check`, `.change-log.json` en
`vault_fundamentals` y `vault_quality_check` (y una tercera vez en
`vault_impact`, que es del contexto Grafo y por eso no se unifica aquí).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..kernel.contexto import VaultContext

CARPETA_SISTEMA = "00_System"
CARPETA_OBSERVABILIDAD = "02_Observability"
SUBCARPETA_VULNERABILIDADES = "vulnerabilities"

FICHERO_REGISTRO_NORMAS = "norm-registry.json"
FICHERO_INDICE_CALIDAD = "quality-index.json"
FICHERO_COLA_PROPAGACION = "propagation-queue.json"
FICHERO_INSTANTANEA_SESION = ".session-snapshot.json"
FICHERO_BITACORA_CAMBIOS = ".change-log.json"
FICHERO_FUNDAMENTOS_JSON = "data-fundamentals.json"
FICHERO_FUNDAMENTOS_MD = "data-fundamentals.md"
FICHERO_MARCO_JSON = "data-framework.json"
FICHERO_MARCO_MD = "data-framework.md"


class RepositorioGobernanza:
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
    def dir_observabilidad(self) -> Path:
        return self._ctx.ruta(CARPETA_OBSERVABILIDAD)

    @property
    def dir_vulnerabilidades(self) -> Path:
        return self._ctx.ruta(CARPETA_OBSERVABILIDAD, SUBCARPETA_VULNERABILIDADES)

    @property
    def registro_normas(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_REGISTRO_NORMAS)

    @property
    def registro_etiquetas(self) -> Path:
        """El vocabulario de etiquetas lo mantiene Índices; aquí se audita."""
        from ..indices.repositorio import RepositorioIndices

        return RepositorioIndices(self._ctx).registro_etiquetas

    @property
    def indice_calidad(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_INDICE_CALIDAD)

    @property
    def cola_propagacion(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_COLA_PROPAGACION)

    @property
    def instantanea_sesion(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_INSTANTANEA_SESION)

    @property
    def bitacora_cambios(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_BITACORA_CAMBIOS)

    @property
    def fundamentos_json(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_FUNDAMENTOS_JSON)

    @property
    def fundamentos_md(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_FUNDAMENTOS_MD)

    @property
    def marco_json(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_MARCO_JSON)

    @property
    def marco_md(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_MARCO_MD)

    # ── Lectura tolerante ────────────────────────────────────────────────────

    def relativa(self, ruta: Path) -> str:
        return str(Path(ruta).relative_to(self.raiz)).replace("\\", "/")

    def leer_json(self, ruta: Path) -> dict:
        try:
            datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError, json.JSONDecodeError, OSError):
            return {}
        return datos if isinstance(datos, dict) else {}

"""Las rutas del contexto Consulta, derivadas del contexto inyectado.

Seis constantes congeladas repartidas entre cinco módulos, más una séptima que
el guard de AP-49 no veía porque se calculaba llamando a una función en el
import (`vault_compact_contracts.SYSTEM_DIR = _resolve_output_dir()`). Esa es la
forma que más caro sale: parece resolución tardía y no lo es.

Lo que **no** está aquí es el grafo. Consulta lo lee, no lo escribe; la
ubicación es del contexto Grafo y se recibe.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..kernel.contexto import VaultContext

CARPETA_SISTEMA = "00_System"
CARPETA_PREFERENCIAS = "17_Preferences"
SUBCARPETA_USO_TOKENS = "token-usage"

_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"

#: Nombres que este módulo publicaba y ya no declara, con quién los declara ahora.
#: No-derogación: siguen importables (`__getattr__`), pero el valor es del dueño.
SUPERSEDED = {
    "FICHERO_TOKENS": {
        "superseded_by": "vault_errors_trace.FICHERO_TOKENS",
        "why": "El contador de tokens lo escribe el kernel; Consulta solo lo lee "
               "(deuda #3, residuo, 2026-10-08: dueño = único escritor).",
    },
}


def _contador_de_tokens():
    """`vault_errors_trace`, importado tarde: `vault/` no exige `scripts/` al importar."""
    from vault_toolkit.loading import import_toolkit_module

    return import_toolkit_module("vault_errors_trace", legacy_scripts=_SCRIPTS)


def __getattr__(nombre: str):
    if nombre == "FICHERO_TOKENS":
        return _contador_de_tokens().FICHERO_TOKENS
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")
FICHERO_CONTRATOS_JSON = "tool-contracts.json"
FICHERO_CONTRATOS_MD = "tool-contracts.md"


class RepositorioConsulta:
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
    def dir_preferencias(self) -> Path:
        return self._ctx.ruta(CARPETA_PREFERENCIAS)

    @property
    def dir_uso_tokens(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, SUBCARPETA_USO_TOKENS)

    @property
    def dir_flujos_tokens(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, SUBCARPETA_USO_TOKENS, "flows")

    @property
    def pid_servicio_tokens(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, SUBCARPETA_USO_TOKENS, "token-service.pid")

    @property
    def puerto_servicio_tokens(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, SUBCARPETA_USO_TOKENS, "token-service.port")

    @property
    def token_servicio_tokens(self) -> Path:
        """Credencial del servicio (SP-04): junto al puerto, dentro del vault,
        para que solo la lea quien ya puede leer el vault."""
        return self._ctx.ruta(CARPETA_SISTEMA, SUBCARPETA_USO_TOKENS, "token-service.token")

    @property
    def fichero_tokens(self) -> Path:
        """Se lee aquí; lo declara y lo escribe el kernel (`vault_errors_trace`)."""
        return self._ctx.ruta(CARPETA_SISTEMA, _contador_de_tokens().FICHERO_TOKENS)

    @property
    def contratos_json(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_CONTRATOS_JSON)

    @property
    def contratos_md(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_CONTRATOS_MD)

    @property
    def version_estandar(self) -> Path:
        """La versión aplicada la sella Ciclo de vida. Consulta la lee y la cita."""
        from ..ciclo_de_vida.repositorio import RepositorioCicloDeVida

        return RepositorioCicloDeVida(self._ctx).fichero_version

    # ── Lectura tolerante ────────────────────────────────────────────────────

    def relativa(self, ruta: Path) -> str:
        """Ruta relativa al vault con separador POSIX: el paquete de contexto lo
        consume un agente, que no tiene por qué correr en la misma plataforma."""
        return str(Path(ruta).relative_to(self.raiz)).replace("\\", "/")

    def leer_json(self, ruta: Path) -> dict:
        try:
            datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError, json.JSONDecodeError, OSError):
            return {}
        return datos if isinstance(datos, dict) else {}

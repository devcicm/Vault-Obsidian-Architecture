"""Las rutas del contexto Gobernanza, derivadas del contexto inyectado.

Siete vínculos congelados que el guard contaba, más ocho derivados de ellos que
no contaba porque no mencionaban `VAULT_ROOT` —`QUALITY_INDEX = SYSTEM_DIR /
"quality-index.json"`— pero se evaluaban en el mismo import y quedaban igual de
inertes.

Dos ubicaciones se calculaban en dos módulos cada una: `quality-index.json` en
`vault_audit` y `vault_quality_check`, `.change-log.json` en
`vault_fundamentals` y `vault_quality_check` (y una tercera vez en
`vault_impact`, que es del contexto Grafo y por eso no se unifica aquí).

La bitácora de cambios es append-only desde bigo-inmutabilidad: este módulo es
su único lector (`leer_bitacora_cambios`, los dos formatos) y su único escritor
(`anexar_bitacora_cambios`, una línea por entrada en `.change-log.jsonl`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Tuple

from ..kernel.contexto import VaultContext

CARPETA_SISTEMA = "00_System"
CARPETA_OBSERVABILIDAD = "02_Observability"
SUBCARPETA_VULNERABILIDADES = "vulnerabilities"
CARPETA_SEGURIDAD = "security"
SUBCARPETA_OWASP = "owasp"

FICHERO_REGISTRO_NORMAS = "norm-registry.json"
FICHERO_INDICE_CALIDAD = "quality-index.json"
FICHERO_COLA_PROPAGACION = "propagation-queue.json"
FICHERO_INSTANTANEA_SESION = ".session-snapshot.json"
#: The change log as it was until the append-only log: one JSON array, read
#: whole and rewritten on every row. Frozen: still read, never written again.
FICHERO_BITACORA_CAMBIOS = ".change-log.json"
#: The append-only change log (bigo-inmutabilidad, S3): one JSON object per
#: line, appended under the same lock, never rewritten.
FICHERO_BITACORA_CAMBIOS_LINEAS = ".change-log.jsonl"
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
    def dir_seguridad(self) -> Path:
        return self._ctx.ruta(CARPETA_OBSERVABILIDAD, CARPETA_SEGURIDAD)

    @property
    def dir_owasp(self) -> Path:
        return self._ctx.ruta(CARPETA_OBSERVABILIDAD, CARPETA_SEGURIDAD, SUBCARPETA_OWASP)

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

    def escribir_cola_propagacion(self, datos: dict, timeout: float = 30.0) -> None:
        """Único escritor de `propagation-queue.json`: el dueño (deuda #3, residuo).

        Hasta 2026-10-08 lo escribía `vault_propagate`, de Ciclo de vida, con
        `atomic_write_json` bajo `file_lock`. Ciclo de vida delega aquí por el
        par `ciclo_de_vida → gobernanza`, permanente en el presupuesto. El lock
        y su espera son los de siempre; `vault_audit` solo la lee.
        """
        with self._ctx.escritor.bloquear(self.cola_propagacion, timeout):
            self._ctx.escritor.escribir_json(self.cola_propagacion, datos)

    @property
    def instantanea_sesion(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_INSTANTANEA_SESION)

    @property
    def bitacora_cambios(self) -> Path:
        """The frozen legacy log (a JSON array). Read by `leer_bitacora_cambios`."""
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_BITACORA_CAMBIOS)

    @property
    def bitacora_cambios_lineas(self) -> Path:
        """The append-only log (JSON Lines). Written by `anexar_bitacora_cambios`."""
        return self._ctx.ruta(CARPETA_SISTEMA, FICHERO_BITACORA_CAMBIOS_LINEAS)

    def hay_bitacora_cambios(self) -> bool:
        """True when the vault holds a change log in either format."""
        return self.bitacora_cambios.exists() or self.bitacora_cambios_lineas.exists()

    def leer_bitacora_cambios(self) -> "LecturaBitacora":
        """Every change-log entry, legacy first and then the appended lines, in order.

        The only reader of both formats: no consumer opens either file itself
        (bigo-inmutabilidad, S6). The legacy array keeps the errors its readers
        always handled — `OSError`, `UnicodeDecodeError`, `json.JSONDecodeError`
        propagate as `json.loads(read_text())` raised them, and a JSON value that
        is not a list is a `TypeError`. Legacy entries come back as they are.

        A line that does not decode or parse is a torn append (a crash between
        the first byte and the newline): it is left out of `entradas` and named
        in `lineas_rotas`, never merged with its neighbour. A line that parses
        to something other than an object cannot come from the writer, so it is
        a `TypeError`, like a legacy file that is not a list.
        """
        entradas: list = []
        legado = self.bitacora_cambios
        if legado.exists():
            datos = json.loads(legado.read_text(encoding="utf-8"))
            if not isinstance(datos, list):
                raise TypeError(f"se esperaba una lista, hay {type(datos).__name__}")
            entradas.extend(datos)
        rotas = []
        lineas = self.bitacora_cambios_lineas
        if lineas.exists():
            for numero, cruda in enumerate(lineas.read_bytes().split(b"\n"), start=1):
                if not cruda.strip():
                    continue
                try:
                    entrada = json.loads(cruda.decode("utf-8"))
                except ValueError:  # UnicodeDecodeError and JSONDecodeError
                    rotas.append(numero)
                    continue
                if not isinstance(entrada, dict):
                    raise TypeError(
                        f"{FICHERO_BITACORA_CAMBIOS_LINEAS}:{numero}: se esperaba un objeto, "
                        f"hay {type(entrada).__name__}")
                entradas.append(entrada)
        return LecturaBitacora(entradas, tuple(rotas))

    def anexar_bitacora_cambios(self, entrada: dict) -> None:
        """The only writer of the change log: one line, appended (O(1) per row).

        Until bigo-inmutabilidad (S3) this rewrote the whole `.change-log.json`
        with `escribir` — O(h) per row. The caller holds the log lock. String
        values go through the write channel's sanitation **before** the line is
        serialized: sanitizing the serialized JSON folded typographic quotes
        into bare `"` and broke the record; the stored values are the ones the
        old whole-file sanitation intended.
        """
        limpia = _sanear_valores(entrada, self._ctx.escritor.sanear)
        self._ctx.escritor.anexar_linea(
            self.bitacora_cambios_lineas, json.dumps(limpia, ensure_ascii=False),
            continua=self.bitacora_cambios)

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


@dataclass(frozen=True)
class LecturaBitacora:
    """One read of the change log: its entries and the torn lines left out."""

    entradas: list
    lineas_rotas: Tuple[int, ...] = ()


def _sanear_valores(valor: Any, sanear: Callable[[str], str]) -> Any:
    """`valor` with every string sanitized by the write channel, recursively."""
    if isinstance(valor, str):
        return sanear(valor)
    if isinstance(valor, dict):
        return {clave: _sanear_valores(v, sanear) for clave, v in valor.items()}
    if isinstance(valor, list):
        return [_sanear_valores(v, sanear) for v in valor]
    return valor

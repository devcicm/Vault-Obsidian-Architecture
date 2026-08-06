"""Las rutas del contexto Autoría, derivadas del contexto inyectado.

Es el contexto más grande —38 módulos— y el que concentraba **los 31 vínculos
congelados que quedaban**: el 100% de la deuda de AP-49 al llegar aquí. No es
casualidad. Cada `*_save` abrió su fichero copiando el de al lado, y con él
copió `SECCION_DIR = VAULT_ROOT / "05_Patterns"` evaluado al importar.

Por eso aquí las secciones **no se enumeran**: se piden por nombre a
`seccion()`, y el nombre se valida contra `vault_registry.ORDERED_SECTIONS`,
que es la fuente única declarada (AP-05). Veintidós constantes copiadas en
veinticinco módulos era la vigésima segunda copia del mismo dato; un typo en
cualquiera de ellas creaba una carpeta nueva en el vault del usuario sin que
nada lo notara.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..kernel.contexto import VaultContext

CARPETA_SISTEMA = "00_System"
CARPETA_INDICES = "99_Index"
CARPETA_HISTORIAL = ".history"

FICHERO_INDICE_PALABRAS = "keywords-index.json"
FICHERO_NOTAS_PALABRAS = "notes-keywords.json"


class RepositorioAutoria:
    """Único sitio del contexto que resuelve rutas y toca disco."""

    def __init__(self, ctx: VaultContext) -> None:
        self._ctx = ctx

    @property
    def ctx(self) -> VaultContext:
        return self._ctx

    @property
    def raiz(self) -> Path:
        return self._ctx.raiz

    # ── Secciones ────────────────────────────────────────────────────────────

    def seccion(self, nombre: str) -> Path:
        """La carpeta de una sección, validada contra el registro canónico.

        Falla ruidosamente ante un nombre desconocido: el modo silencioso sería
        crear una carpeta huérfana en el vault del usuario, que es exactamente
        el fallo que AP-37 llama no-op silencioso.
        """
        import vault_registry

        if nombre not in vault_registry.ORDERED_SECTIONS:
            raise ValueError(
                f"'{nombre}' no es una sección del estándar. Las secciones son "
                f"vault_registry.ORDERED_SECTIONS — no se declaran aquí."
            )
        return self._ctx.ruta(nombre)

    @property
    def dir_sistema(self) -> Path:
        return self._ctx.ruta(CARPETA_SISTEMA)

    @property
    def dir_indices(self) -> Path:
        return self._ctx.ruta(CARPETA_INDICES)

    @property
    def dir_historial(self) -> Path:
        return self._ctx.ruta(CARPETA_HISTORIAL)

    # ── Ficheros ─────────────────────────────────────────────────────────────

    # Cuatro rutas que Autoría **lee y actualiza pero no define**: el índice de
    # búsqueda, el de hashes y el registro de etiquetas los construye Índices; el
    # grafo, Grafo. Declararlas aquí habría sido la cuarta copia de
    # `search-index.json` en el paquete de dominio — y las delató la puerta nueva
    # `vault_arch.rutas_duplicadas()`, no una revisión a ojo (AP-05).

    @property
    def indice_busqueda(self) -> Path:
        from ..indices.repositorio import RepositorioIndices

        return RepositorioIndices(self._ctx).indice_busqueda

    @property
    def registro_etiquetas(self) -> Path:
        from ..indices.repositorio import RepositorioIndices

        return RepositorioIndices(self._ctx).registro_etiquetas

    @property
    def grafo(self) -> Path:
        from ..grafo.repositorio import RepositorioGrafo

        return RepositorioGrafo(self._ctx).grafo

    @property
    def indice_hashes(self) -> Path:
        from ..indices.repositorio import RepositorioIndices

        return RepositorioIndices(self._ctx).indice_hashes

    @property
    def indice_palabras(self) -> Path:
        return self._ctx.ruta(CARPETA_INDICES, FICHERO_INDICE_PALABRAS)

    @property
    def notas_palabras(self) -> Path:
        return self._ctx.ruta(CARPETA_INDICES, FICHERO_NOTAS_PALABRAS)

    def indice_de_seccion(self, nombre: str) -> Path:
        """`05_Patterns/index.json` y sus hermanos, que cada `*_save` derivaba."""
        return self.seccion(nombre) / "index.json"

    # ── Lectura tolerante ────────────────────────────────────────────────────

    def relativa(self, ruta: Path) -> str:
        return str(Path(ruta).relative_to(self.raiz)).replace("\\", "/")

    def leer_json(self, ruta: Path) -> dict:
        try:
            datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError, json.JSONDecodeError, OSError):
            return {}
        return datos if isinstance(datos, dict) else {}

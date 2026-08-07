"""Implementaciones reales de los puertos, apoyadas en el kernel existente.

Esto es la frontera con `scripts/`: el único fichero de `vault/` al que se le
permite importar `vault_io`, `vault_registry` y `vault_norms`. Se hace por
delegación y no por copia — la garantía atómica, el bloqueo y el catálogo de
normas siguen siendo los de siempre, que llevan versiones probados. Reimplementar
aquí sería AP-48 (implementación paralela) recién estrenada.

El import de `scripts/` se resuelve **dentro** de la función, no al cargar el
módulo: es la propia AP-49 que este paquete existe para eliminar.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence

from .contexto import VaultContext

_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"


def _kernel():
    """`vault_io`, importado tarde y una sola vez por proceso."""
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    import vault_io

    return vault_io


class EscritorAtomico:
    """Delega en `vault_io.atomic_write_text` y `file_lock`."""

    def escribir(self, ruta: Path, texto: str) -> None:
        io = _kernel()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        io.atomic_write_text(ruta, texto)

    def escribir_json(self, ruta: Path, datos: dict) -> None:
        io = _kernel()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        io.atomic_write_json(ruta, datos)

    @contextmanager
    def bloquear(self, objetivo: Path, timeout: float = 30.0) -> Iterator[Path]:
        io = _kernel()
        with io.file_lock(objetivo, timeout=timeout) as lock:
            yield lock


class LectorDisco:
    def leer(self, ruta: Path) -> str:
        return Path(ruta).read_text(encoding="utf-8")

    def existe(self, ruta: Path) -> bool:
        return Path(ruta).exists()

    def listar(self, patron: str) -> Sequence[Path]:
        raise NotImplementedError(
            "listar() necesita la raíz: se resuelve en el repositorio del "
            "contexto, que sí la tiene. Ver vault/durabilidad/."
        )


class SeccionesDelRegistro:
    """`vault_registry.ORDERED_SECTIONS`, tras un puerto.

    La raíz se guarda en la instancia y no se importa: es lo que permite que dos
    contextos con raíces distintas coexistan en el mismo intérprete.
    """

    def __init__(self, raiz: Path) -> None:
        self._raiz = raiz

    def _registro(self):
        if str(_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(_SCRIPTS))
        import vault_registry

        return vault_registry

    def ordenadas(self) -> Sequence[str]:
        return list(self._registro().ORDERED_SECTIONS)

    def existe(self, carpeta: str) -> bool:
        return carpeta in self.ordenadas()

    def ruta_de(self, carpeta: str) -> Path:
        if not self.existe(carpeta):
            raise ValueError(
                f"{carpeta!r} no está en ORDERED_SECTIONS. Las secciones son un "
                f"vocabulario cerrado; inventar una es AP-05."
            )
        return self._raiz / carpeta


class NormasDelCatalogo:
    def _catalogo(self):
        if str(_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(_SCRIPTS))
        import vault_norms

        return vault_norms.NORM_CATALOG

    def por_codigo(self, codigo: str) -> dict | None:
        return next((n for n in self._catalogo() if n["code"] == codigo), None)

    def vigentes(self) -> Sequence[dict]:
        return [n for n in self._catalogo() if not n.get("superseded_by")]


class RelojUTC:
    def ahora(self) -> datetime:
        return datetime.now(timezone.utc)

    def marca(self) -> str:
        """Delegado en `vault_lib.utcnow()`, no reimplementado.

        El formato lleva versiones escrito en manifiestos y ledgers en disco.
        Copiar aquí el `strftime` sería tener dos fuentes de un mismo formato
        (AP-05) y descubrir la divergencia el día que una de las dos cambie.
        """
        if str(_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(_SCRIPTS))
        import vault_lib

        return vault_lib.utcnow()


def contexto_real(raiz: str | Path | None = None) -> VaultContext:
    """El contexto que usan los adaptadores en producción.

    Si no se pasa raíz se pregunta al kernel —autodetección, que en este repo
    devuelve `vault-sandbox/`—, pero se pregunta **ahora**, en la llamada, no al
    importar. Ésa es toda la diferencia que AP-49 describe.
    """
    io = _kernel()
    if raiz is None:
        resuelta = Path(io.get_vault_root())
        origen = io.vault_root_origin()
    else:
        resuelta = Path(raiz).resolve()
        origen = "explicit_argument"
    return VaultContext(
        raiz=resuelta,
        origen=origen,
        secciones=SeccionesDelRegistro(resuelta),
        normas=NormasDelCatalogo(),
        escritor=EscritorAtomico(),
        lector=LectorDisco(),
        reloj=RelojUTC(),
    )

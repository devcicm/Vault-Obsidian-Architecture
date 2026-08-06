"""Los puertos del kernel: interfaces estrechas que el dominio consume.

Son `typing.Protocol` a propósito. Sin herencia, sin registro, sin framework y
sin una sola dependencia nueva —la restricción de stdlib + PyYAML es normativa,
no una comodidad—. El dominio depende del `Protocol`; el kernel provee la
implementación real (`adaptadores.py`); un test inyecta un doble que no toca
disco. Eso es DIP e ISP con lo que ya hay en la caja.

Por qué estrechos: `vault_io` expone hoy unos 40 símbolos y el módulo medio usa
cinco. Importarlo entero acopla a un módulo con 35 cosas que no le incumben, y
es la razón de que su acoplamiento entrante sea 99. Un puerto declara lo que el
dominio de verdad necesita, y esa lista corta es también la documentación de qué
puede hacer.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterator, Protocol, Sequence, runtime_checkable


@runtime_checkable
class Escritor(Protocol):
    """Toda escritura del dominio pasa por aquí.

    Existe porque hay **37 llamadas a `.write_text(` fuera de `vault_io`**, cada
    una saltándose la garantía atómica del kernel. Con un puerto, «escribir sin
    atomicidad» deja de ser posible por construcción en vez de ser algo que un
    revisor tiene que cazar leyendo diffs.
    """

    def escribir(self, ruta: Path, texto: str) -> None:
        """Escribe de forma atómica, saneando la codificación."""

    def bloquear(self, objetivo: Path, timeout: float = 30.0) -> Iterator[Path]:
        """Bloqueo de directorio junto al objetivo, para índices compartidos."""


@runtime_checkable
class Lector(Protocol):
    """Lectura separada de escritura: la mayoría del dominio solo lee.

    Partirlo es ISP literal — una tool de consulta que recibe un `Escritor` es
    una tool de consulta con permiso de escritura que nadie le pidió.
    """

    def leer(self, ruta: Path) -> str: ...

    def existe(self, ruta: Path) -> bool: ...

    def listar(self, patron: str) -> Sequence[Path]: ...


@runtime_checkable
class RegistroSecciones(Protocol):
    """Las secciones canónicas del vault.

    `vault_registry.ORDERED_SECTIONS` es la fuente única declarada, y aun así
    hay **487 literales de sección** repartidos por el repo (AP-05). El puerto
    es lo que hace que preguntar salga más barato que escribir `"07_Knowledge"`.
    """

    def ordenadas(self) -> Sequence[str]: ...

    def existe(self, carpeta: str) -> bool: ...

    def ruta_de(self, carpeta: str) -> Path: ...


@runtime_checkable
class CatalogoNormas(Protocol):
    """Las normas AP/PAT/SP/CN, sin importar `vault_norms`.

    Hoy lo importan 21 módulos de siete contextos distintos: es la frontera más
    cruzada del repo, y la razón por la que Gobernanza no puede evolucionar sin
    arrastrar a todos.
    """

    def por_codigo(self, codigo: str) -> dict | None: ...

    def vigentes(self) -> Sequence[dict]: ...


@runtime_checkable
class Reloj(Protocol):
    """El tiempo, inyectado.

    Hoy es `datetime.utcnow()` llamado directamente en el sitio donde se usa, lo
    que hace intesteable todo lo que dependa de una marca temporal: un test solo
    puede comprobar que el campo existe, nunca que valga lo que debe.
    """

    def ahora(self) -> datetime: ...

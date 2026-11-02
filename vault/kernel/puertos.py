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

    def escribir_json(self, ruta: Path, datos: dict) -> None:
        """Escribe un JSON con el formato del estándar (indent 2, sin escapes).

        Está en el puerto y no en el dominio porque el formato es contrato: un
        manifiesto o un ledger reescrito con otro `indent` cambia byte a byte un
        fichero que ya existe en disco de los usuarios.
        """

    def bloquear(self, objetivo: Path, timeout: float = 30.0) -> Iterator[Path]:
        """Bloqueo de directorio junto al objetivo, para índices compartidos."""

    def sanear(self, texto: str) -> str:
        """El texto tal como quedaría en disco tras el saneo de escritura.

        Nadie fuera del canal de escritura debe reimplementar el saneo (AP-57):
        un comparador que contraste su texto compuesto contra un fichero ya en
        disco necesita la MISMA forma que ese fichero recibió. El pleg
        em-dash→`--` es el ejemplo: un índice regenerado que compone `—` y
        compara contra el disco (`--`) nunca será "igual" y reescribe en
        cada corrida sin haber cambiado nada.
        """


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
class CatalogoTools(Protocol):
    """El catálogo de tools, sin importar el meta-toolkit.

    El dueño es `vault.meta_toolkit.catalogo_producto` y Gobernanza lo recibe
    inyectado por la raíz de composición —`vault.product_cli`, que no pertenece
    a ningún contexto y por eso puede cruzar—. Hasta A-5 (2026-11-01) era
    `vault/gobernanza/tool.py` quien importaba el adaptador del meta-toolkit, y
    eso era todo el par `gobernanza -> meta_toolkit`.
    `vault.gobernanza.base.ToolsCatalog` lo refina con sus tipos.
    """

    def por_nombre(self, name: str) -> object | None: ...

    def todas(self) -> Sequence[object]: ...

    def por_grupo(self, group: str) -> Sequence[object]: ...


@runtime_checkable
class Reloj(Protocol):
    """El tiempo, inyectado.

    Hoy es `datetime.utcnow()` llamado directamente en el sitio donde se usa, lo
    que hace intesteable todo lo que dependa de una marca temporal: un test solo
    puede comprobar que el campo existe, nunca que valga lo que debe.
    """

    def ahora(self) -> datetime: ...

    def marca(self) -> str:
        """El instante en el formato con el que el estándar lo escribe.

        Es `vault_lib.utcnow()` —`2026-08-06T10:15:00.000Z`— tras el puerto. Se
        publica formateado y no solo como `datetime` porque el formato viaja a
        ficheros ya escritos: reformatearlo «de paso» rompería a quien los lee.
        """


@runtime_checkable
class Voz(Protocol):
    """La voz del estándar: el recordatorio que acompaña a cada envelope.

    `vault_errors` la invoca en cada envelope que emite, y hoy lo hace
    importando `vault.autoria.voz` **en el import** —el cruce `kernel ->
    autonomia` que la auditoría nombró como A-04—. Con el puerto, el kernel
    habla con una abstracción y quien la implementa se ofrece al importarse.
    """

    def speak(self, tool: str, payload: Optional[Dict[str, Any]] = None,
              writes: Optional[Dict[str, int]] = None) -> Optional[Dict[str, Any]]:
        """El recordatorio, o `None` si no hay nada que decir."""


@runtime_checkable
class RegeneradorIndices(Protocol):
    """Quien regenera el índice de una sección tras escribir una nota.

    `vault_io` lo invoca en cada escritura —es el «único punto de
    responsabilidad» que evita que cada tool regenere el suyo— y hoy lo hace
    importando `vault_section_index` de forma diferida. Con el puerto, el
    kernel no conoce al productor: lo pide por el puerto y quien lo implementa
    se ofrece al importarse.
    """

    def regenerar(self, seccion: str, rutas: Sequence[Path],
                  nombres: Optional[Dict[str, List[str]]] = None) -> Sequence[str]:
        """Regenera el índice de `seccion` y devuelve los `index.md` que creó."""

    def refrescar_busqueda(self, rutas: Sequence[Path]) -> None:
        """Mete las notas escritas en el índice de búsqueda (AP-47).

        Va aparte de `regenerar` a propósito: son dos cosas distintas y
        confundirlas cambia el contrato de quien las llama. `vault_move`
        llama a `refrescar_indice_de_seccion` —que rehace el `index.md` de la
        sección— y NO pone la nota movida en la búsqueda: la búsqueda la
        actualiza la tool, que es quien sabe de dónde a dónde se movió. Si el
        índice de sección se llevara la búsqueda de arrastre, la nota movida
        entraría en el índice de búsqueda por la puerta de atrás.
        """


@runtime_checkable
class BitacoraTags(Protocol):
    """Quien anota en la bitácora de vocabulario los tags de una nota (AP-39).

    El gancho vive en `vault_io` porque es el único punto por el que pasan
    todas las escrituras —catorce writers distintos::
    `atomic_write_text`—, y hoy lo hace importando `vault_tags` de forma
    diferida. Con el puerto, el kernel no conoce al productor.
    """

    def anotar(self, texto: str, ruta_relativa: str) -> None:
        """Anota los tags de `texto` en la bitácora, bajo `ruta_relativa`."""


"""El escritor único de frontmatter (AP-46), en el núcleo.

La historia —diecisiete `*_save` con tres criterios de escapado conviviendo—
está en `vault/autoria/frontmatter.py`, que es donde nació y que sigue
reexportando este nombre.

## Por qué en el núcleo

Porque lo escriben todos los contextos y solo depende del núcleo. Mientras vivió
en Autoría, cada escritor de Grafo, Infraestructura o Ciclo de vida que dejaba
de montar su bloque a mano para cumplir AP-46 estrenaba un cruce de frontera
hacia Autoría: seis en una sola tanda, todos por la misma clase. Cumplir una
norma no puede costar deuda en otra. Su otra mitad —leer el bloque y decidir el
escapado (`yaml_scalar`, `es_instante`)— ya era del núcleo desde v40.34
(`frontmatter_parsing`); ahora lo son las dos.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, List, Tuple

from .frontmatter_parsing import es_instante, yaml_scalar


class Frontmatter:
    """Un frontmatter en construcción. Ordenado, escapado en un solo sitio.

    El orden de inserción es el orden de salida: los diecisiete tienen su
    propio orden de campos y cambiarlo movería cada nota del vault sin que
    nadie lo hubiera pedido. Unificar el orden es otra tanda, y se decide
    mirando el resultado, no de paso en un refactor de escapado.
    """

    def __init__(self) -> None:
        self._lineas: List[str] = []

    @classmethod
    def editar(cls, bloque: str) -> "Frontmatter":
        """Un frontmatter que ya existe, para cambiarle campos (AP-46).

        Los editores —revocar una preferencia, marcar una propagación, anotar
        una fusión, añadir una norma— montaban el bloque a mano igual que los
        creadores, cada uno con su escapado: `json.dumps` en uno, comillas
        literales en otro, un `re.sub` por línea en un tercero. Este es el mismo
        dueño en modo edición: lo que no se toca se conserva línea a línea, y lo
        que se toca pasa por `set`, que es el único que decide el escapado.

        `bloque` es lo que devuelve `separar_frontmatter`: sin delimitadores.
        Las líneas vacías del final se descartan; el cierre `---` va justo
        detrás del último campo, que es como lo dejaban los editores.
        """
        fm = cls()
        lineas = bloque.split("\n") if bloque else []
        while lineas and not lineas[-1].strip():
            lineas.pop()
        fm._lineas = lineas
        return fm

    def _tramo(self, clave: str) -> "Tuple[int, int] | None":
        """`(inicio, fin)` de las líneas de `clave`, continuación incluida.

        Una clave de nivel superior ocupa su línea y las que la continúan: las
        sangradas y los `- item` de una lista en bloque, que YAML acepta a
        columna cero bajo su clave. Reemplazar solo la primera dejaría los
        ítems viejos colgando del valor nuevo.
        """
        patron = re.compile(rf"^{re.escape(clave)}\s*:(\s|$)")
        for i, linea in enumerate(self._lineas):
            if patron.match(linea):
                fin = i + 1
                while fin < len(self._lineas) and (
                    self._lineas[fin][:1] in (" ", "\t")
                    or self._lineas[fin] == "-"
                    or self._lineas[fin].startswith("- ")
                ):
                    fin += 1
                return i, fin
        return None

    # ── Escritura ────────────────────────────────────────────────────────────

    def set(
        self,
        clave: str,
        valor: Any,
        omitir_vacio: bool = False,
        vacio_citado: bool = False,
        texto: bool = False,
    ) -> "Frontmatter":
        """Añade `clave: valor`, escapado según el criterio único.

        `omitir_vacio` reproduce el `if valor:` que hoy rodea a la mitad de
        las llamadas — un campo vacío no se escribe, no se escribe vacío.

        `vacio_citado` es la otra mitad de la misma pregunta, y es un dato,
        no un escapado: hay notas que escriben `resolved_at: ` —que YAML lee
        como `null`, "todavía no ha pasado"— y otras que escriben
        `owner: ""` —cadena vacía, "no hay dueño asignado"—. Parecen lo
        mismo y no lo son, así que el punto de uso lo declara en vez de que
        este escritor elija por todos. Unificarlo es otra tanda: se decide
        mirando qué lee cada consumidor, no de paso aquí.

        `texto` declara que el valor es texto aunque YAML lo leyera como
        fecha: sale exactamente como lo decide `yaml_scalar`, que lo cita.
        La excepción de los instantes existe para `createdAt` y compañía; un
        proyecto, un título o una ruta llamados `2026-10-02` no son un
        instante, y sin esto el lector los recibía como `datetime.date`.
        Es lo que escribían los sitios que llamaban a `yaml_scalar` a mano,
        así que migrarlos con `texto=True` no cambia un byte.

        Si la clave ya está —un bloque abierto con `editar`—, su línea y su
        continuación se reemplazan en el sitio: una clave duplicada la lee
        YAML como «gana la última» y Obsidian no siempre, así que el orden y
        la unicidad se conservan aquí en vez de confiar en el lector.
        """
        if omitir_vacio and valor in (None, "", [], {}):
            return self
        if texto:
            linea = f"{clave}: {yaml_scalar(valor)}"
        elif valor == "" and not isinstance(valor, (list, dict)) and not vacio_citado:
            # `clave: ` a secas, que es lo que se escribe hoy y lo que YAML
            # lee como `null`. Citarlo a `""` convertiría un campo ausente en
            # una cadena vacía, y hay notas que ya distinguen las dos cosas
            # —`resolved_at` de un incidente sin resolver, por ejemplo—.
            # Cambiar eso no es unificar el escapado, es cambiar el dato.
            linea = f"{clave}: "
        elif es_instante(valor):
            linea = f"{clave}: {valor}"
        else:
            linea = f"{clave}: {yaml_scalar(valor)}"
        tramo = self._tramo(clave)
        if tramo is None:
            self._lineas.append(linea)
        else:
            self._lineas[tramo[0]:tramo[1]] = [linea]
        return self

    def quitar(self, clave: str) -> "Frontmatter":
        """Retira `clave` con su continuación; no hace nada si no está."""
        tramo = self._tramo(clave)
        if tramo is not None:
            del self._lineas[tramo[0]:tramo[1]]
        return self

    def lineas(self, lineas: Iterable[str]) -> "Frontmatter":
        """Inserta líneas ya construidas por otro registro canónico.

        Existe para `vault_norms.status_frontmatter_lines()`, que es la fuente
        única del campo `status` desde v39 y ya decide su propio escapado. Que
        este escritor las volviera a escapar sería tomar dos veces la misma
        decisión, que es justo lo que viene a quitar.
        """
        self._lineas.extend(lineas)
        return self

    # ── Salida ───────────────────────────────────────────────────────────────

    def campos(self) -> Tuple[str, ...]:
        return tuple(self._lineas)

    def render(self) -> str:
        """El bloque completo, delimitadores incluidos, sin salto final.

        Sin salto al final a propósito: los diecisiete lo concatenan con su
        cuerpo usando separadores distintos (`"\\n\\n"`, `"\\n"`, un
        `"\\n\\n".join`), y añadirlo aquí cambiaría el cuerpo de cada nota.
        """
        return "\n".join(["---", *self._lineas, "---"])

    def __str__(self) -> str:  # pragma: no cover - conveniencia
        return self.render()

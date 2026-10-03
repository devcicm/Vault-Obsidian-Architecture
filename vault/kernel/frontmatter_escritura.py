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

    # ── Escritura ────────────────────────────────────────────────────────────

    def set(
        self,
        clave: str,
        valor: Any,
        omitir_vacio: bool = False,
        vacio_citado: bool = False,
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
        """
        if omitir_vacio and valor in (None, "", [], {}):
            return self
        if valor == "" and not isinstance(valor, (list, dict)) and not vacio_citado:
            # `clave: ` a secas, que es lo que se escribe hoy y lo que YAML
            # lee como `null`. Citarlo a `""` convertiría un campo ausente en
            # una cadena vacía, y hay notas que ya distinguen las dos cosas
            # —`resolved_at` de un incidente sin resolver, por ejemplo—.
            # Cambiar eso no es unificar el escapado, es cambiar el dato.
            self._lineas.append(f"{clave}: ")
        elif es_instante(valor):
            self._lineas.append(f"{clave}: {valor}")
        else:
            self._lineas.append(f"{clave}: {yaml_scalar(valor)}")
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

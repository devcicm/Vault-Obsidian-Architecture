"""El escritor único de frontmatter. AP-46, cumplida en el punto de uso.

Diecisiete `*_save` construían su frontmatter concatenando f-strings, 116
líneas en total, con **tres criterios de escapado conviviendo en el mismo
vault**:

    vault_bibliography_save →  title: Guía de diseño          (yaml_scalar)
    vault_pattern_save      →  title: "Repositorio por..."    (json.dumps)
    vault_runbook_save      →  trigger: Cada noventa días     (f-string crudo)

Los tres parecen correctos en su fichero. Juntos no lo son: el mismo campo se
escribe de tres maneras, `json.dumps` sin `ensure_ascii=False` guarda un título
acentuado como `Rotaci\\u00f3n` —que Obsidian muestra literal, con la barra— y
el f-string crudo produce YAML inválido en cuanto el valor lleva `: `, en cuyo
caso la nota pierde **todo** el frontmatter al leerse: sin id, sin tags, sin
tipo, y sin error en ninguna parte.

AP-46 dice que el frontmatter no se escribe a mano y llevaba tiempo declarada,
pero no tenía dónde cumplirse: no existía un sitio donde escribirlo. Este es
ese sitio. La decisión de cómo se escapa un campo se toma **una vez**, aquí, y
los diecisiete la consumen (AP-50).

## Por qué `yaml_scalar` y no `json.dumps`

Porque cita solo si hace falta, y el criterio de "hace falta" es el del
consumidor y no el propio (AP-44): se comprueba que el parser real devuelva
exactamente el mismo texto, y solo si no, se cita. Lo que hoy se escribe sin
comillas se sigue escribiendo sin comillas.

## La excepción declarada: las fechas

`yaml_scalar("2026-08-07T08:42:44Z")` citaría, porque YAML lee ese texto como
un instante y no como la cadena que se le pasó. Citarlo cambiaría lo que
recibe todo lo que ya lee estas notas —un `datetime` pasaría a ser un `str`—
por un problema que no existe: un instante ISO no puede contener nada que
rompa el YAML. Se emite sin comillas, y se declara aquí en vez de dejarlo como
un caso raro de `yaml_scalar` que nadie sabría explicar.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path
from typing import Any, Iterable, List, Tuple

# Los `*_save` viven en `scripts/` y no se mueven de ahí; el paquete se importa
# desde la raíz del repo, que ellos mismos ponen en el path.
_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:  # pragma: no cover - depende del invocador
    sys.path.insert(0, str(_SCRIPTS))

from vault_lib import yaml_scalar  # noqa: E402


def _es_instante(valor: Any) -> bool:
    """`True` si YAML leería este texto como fecha u hora.

    Solo entonces se emite crudo. La comprobación se hace con el parser real
    —no con un regex de forma ISO— por lo mismo que todo lo demás aquí: quien
    decide qué es una fecha en un frontmatter es el que lo lee.
    """
    if not isinstance(valor, str) or not valor:
        return False
    import yaml

    try:
        vuelta = yaml.safe_load(f"k: {valor}")
    except yaml.YAMLError:
        return False
    return isinstance(vuelta, dict) and isinstance(
        vuelta.get("k"), (_dt.datetime, _dt.date)
    )


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
        elif _es_instante(valor):
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

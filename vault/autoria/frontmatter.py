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

# Los `*_save` viven en `scripts/` y no se mueven de ahí; el paquete se importa
# desde la raíz del repo, que ellos mismos ponen en el path.
# superseded_by: vault.kernel.frontmatter_parsing.yaml_scalar (v40.34, AP-57).
# Era una copia idéntica de la de `vault_lib`; el nombre se conserva aquí
# porque es la API que consumen los `*_save`.
from ..kernel.frontmatter_parsing import es_instante, yaml_scalar  # noqa: E402,F401


# superseded_by: vault.kernel.frontmatter_parsing.es_instante (v40.34, AP-57).
# El cuerpo pasó al núcleo para que `valor_de_frontmatter` —los sitios que aún
# montan la línea a mano— decida igual que `Frontmatter.set`. Se conserva el
# nombre: dos criterios de "qué es una fecha" serían el AP-57 que esto cierra.
_es_instante = es_instante


# superseded_by: vault.kernel.frontmatter_escritura.Frontmatter (AP-46, AP-59).
# La clase pasó al núcleo con su contrato intacto: la escriben todos los
# contextos, y aquí cada escritor de fuera de Autoría que la adoptaba estrenaba
# un cruce de frontera. Se conserva el nombre porque es la API que importan los
# `*_save`; una segunda clase sería el AP-57 que esto cierra.
from ..kernel.frontmatter_escritura import Frontmatter  # noqa: E402,F401

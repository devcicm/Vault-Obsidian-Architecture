# AP-79 — Nota sin entrada autosuficiente

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nace de una observación del dueño (`odd/tasks/nota-escalonada.md`, S1): las notas
del vault tenían una o tres líneas cortas, y eso no le sirve a un auditor humano ni
a un agente externo que no conoce el contexto. Medido el 2026-11-19 (S5): en un
vault brownfield generado por el producto, la mediana era de 5 líneas y 28
palabras por nota, con un 12 % de notas de tres líneas o menos. La referencia del
dueño es el artículo enciclopédico: una entrada que funciona como resumen
ejecutivo, debajo la síntesis y el informe, y el informe corto de dos o tres
líneas solo como registro de un evento que enlaza con el artículo completo.

## Las caras

- **Criterio**: `vault/kernel/contenido.py::profundidad_de_nota`, el mismo que
  usan los generadores al componer con `nota_escalonada` (AP-57: un criterio para
  quien escribe y quien lee).
- **Audit**: `scripts/vault_audit.py::_detect_profundidad`, publicado en
  `notesDepth`, `issues.notesWithoutLead`, `stats.notesWithoutLead` y, las
  primeras, en `nextActions` (`note_without_lead`).
- **Tests**: `tests/test_ap79_profundidad_audit.py` y `test_ap79_norma.py`.

## Por qué no es una puerta

Las notas que ya existen se informan para subirlas, nunca se rechazan: una puerta
en `vault_write` rompería a quien hoy escribe notas cortas y haría que lo barato
fuese rellenar la entrada para pasarla, que es AP-45 cometido al cumplir AP-79.
Por la misma razón no pesa en el `healthScore` ni en el `healthIndex`: no tiene
fila en `PENALIZACIONES`.

## Por qué el registro de evento puede ser corto

Una sesión, un incidente o una ejecución de QA ocurren en una fecha y se anotan
cuando ocurren (clase de documento `registro`). Su valor está en enlazar con la
nota que los explica, como el portal de actualidad enlaza con el artículo. Por eso
un registro solo cuenta cuando no tiene ni entrada ni ningún wikilink.

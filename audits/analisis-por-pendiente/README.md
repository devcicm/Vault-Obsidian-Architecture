# Análisis por pendiente

Lo que se aparta de la rama viva porque **no está en uso**, con la evidencia de
por qué. Nada se borra sin dejar su rastro: lo que está aquí se puede restaurar
(o volver a integrar) cuando alguien lo revise.

## Documentos generados (no se editan a mano)

| Documento | Instrumento | Qué mide |
|---|---|---|
| [`DARK-DATA-2026-11-05.md`](DARK-DATA-2026-11-05.md) | `generar_dark_data.py` | El barrido de **todo** el repo versionado: qué está vivo, qué está declarado por un contrato, qué es derivado y qué está muerto (y los "casi", con su riesgo). |
| [`DEFECTOS-PRODUCTO-2026-11-05.md`](DEFECTOS-PRODUCTO-2026-11-05.md) | `generar_defectos_producto.py` | Los defectos que sufre **quien consume** (credencial que se commitea, cifras publicadas que no son ciertas, remediaciones con nombre propio), los candidatos con su coste y los gaps negativos: lo que ninguna puerta mide. |
| [`../reestructura/CORAZON-V41.26.md`](../reestructura/CORAZON-V41.26.md) | `../reestructura/generar_corazon.py` | El corazón de v41.26 por fan-in (el umbral del propio estándar), las tres capas, la tabla de fachadas → dueño y la huella viva de cada generación de refactor. |

Se regeneran con `python audits/analisis-por-pendiente/generar_dark_data.py`,
`python audits/analisis-por-pendiente/generar_defectos_producto.py --vault <vault real>`
y `python audits/reestructura/generar_corazon.py`. El segundo mide el versionado
de un vault ajeno **en solo lectura** (`git ls-files` y su `.gitignore`).

### Correcciones al instrumento (v41.26)

Un documento generado vale lo que vale su instrumento, y el de dark data se
equivocó dos veces en el primer "casi" —el de los adaptadores—:

1. **Decía «sin generador en el repo»** cuando el generador existía
   (`scripts/vault_distribution_sync.py`). El detector pedía `write_text` o
   `escribir` en el texto y el dueño escribe con `write_bytes`. El instrumento
   se midió con su propia normalización (AP-44) y no vio lo que buscaba.
2. **Se contaba a sí mismo** al citar la frase de la plantilla en un comentario.
   Ahora la señal es sintáctica: una asignación cuyo valor es la plantilla.

Lo que sí faltaba —y se cerró— es que **nadie ejecutaba** ese generador: los
adaptadores se regeneraban a mano. Es un paso de `vault_fix_all` desde v41.26, y
`vault_distribution_sync --check` es la puerta.


## 1. `stash-product-readiness-b306719.patch`

El contenido de la rama remota `archivo/stash-product-readiness-b306719`, que
era un **stash** de un trabajo anterior (`WIP on product/product-readiness`,
sobre el commit `b306719`) guardado como rama. Se aparta aquí para dejar el
repositorio con **una sola rama** (`main`), sin perder el trabajo: el parche
completo tiene 23 ficheros y 296 líneas de cambio.

Para revisarlo: `git apply --stat audits/analisis-por-pendiente/stash-product-readiness-b306719.patch`.
Para recuperar solo un fichero: `git apply --include=<ruta> <parche>`.

## 2. Análisis de archivos sin uso (2026-11-04)

Se midió el repositorio entero (1.929 ficheros) buscando **módulos Python que
nadie importa y ningún catálogo declara**, y ficheros cuyo nombre no se menciona
en ningún sitio. Resultado: **no hay código muerto**.

Los dos únicos candidatos que el barrido por nombre marcó son un alias
declarado, no código muerto:

| Fichero | Por qué se queda |
|---|---|
| `vault/meta_toolkit/carriles.py` | Alias en `sys.modules` del dueño (`vault.meta_toolkit.estandar.carriles`), con `superseded_by:` escrito (B-3 de la reestructura). No-derogación: el nombre viejo sigue importable. |
| `vault/meta_toolkit/estandar/carriles.py` | El registro real de carriles: lo importan `vault_gate`, `vault_test_scope` y sus tests. |

Reglas que dejó el análisis (para que no haya que repetirlo a ciegas):

- Un `scripts/vault_*.py` **no es un módulo importable**: es una tool, y se usa
  ejecutándose. Que nadie la importe no significa nada.
- Un test de `tests/` o de `normas/*/test_*.py` se descubre por **colección de
  pytest**, no por nombre. No cuenta como huérfano.
- `audits/` es el registro histórico del proyecto: **no se mueve nada** de ahí.
- Un alias con `superseded_by:` es contrato, no deuda.
- `index.md`, `README.md`, `conftest.py`, `__init__.py` y `.gitkeep` son
  convenciones de descubrimiento.

Conclusión: **todo lo que hay está en uso o declarado**; lo único que se aparta
es el stash de la rama vieja. Ese es el criterio con el que se dejó el
repositorio en una sola rama.

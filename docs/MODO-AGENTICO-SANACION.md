# Modo agéntico de sanación

Procedimiento para tomar un vault **preexistente** —creado sin el estándar, o con
una versión vieja— y dejarlo gobernado, sin perder nada de lo que ya decía.

No es una tool. Es el orden en que se aplican las tools que ya existen, y las
decisiones que ninguna tool puede tomar sola.

Derivado de una ejecución real y completa sobre el vault de BuilderX (232 notas,
`healthScore` 0). Todas las cifras que aparecen abajo son de esa ejecución.

---

## Las tres reglas que gobiernan el modo

**1. Se sana la copia, nunca el original.** La copia intacta es la única forma de
medir. Y las dos se auditan **con el mismo código**: auditar el "antes" con la
herramienta vieja y el "después" con la nueva mide la herramienta, no el vault.

**2. El subagente propone, no escribe.** Un subagente puede leer el repo de código
asociado, clasificar notas, proponer tags o detectar duplicados. La escritura pasa
siempre por una tool del estándar, con su guard. Un subagente con permiso de
escritura es un segundo autor sin norma que lo gobierne — y su error no queda en
`.change-log.json` como error de nadie.

**3. Nada se borra.** Lo que estorba se **anota**: `superseded_by:`,
`status: archived`, o una nota de sanación que explique por qué. Un vault sanado
que perdió información no está sanado, está podado.

---

## Las 12 fases

| # | Fase | Tool principal | Decisión que la tool no toma |
|---|---|---|---|
| 1 | Copiar el vault; congelar el original | — | dónde vive la copia (fuera de git si hay datos ajenos) |
| 2 | Inventario: qué hay y qué falta | `vault_audit` | — |
| 3 | Estructura: secciones numeradas | `vault_init` | qué carpeta suelta corresponde a qué sección |
| 4 | Frontmatter mínimo en notas sin él | `vault_write` | de dónde se infiere: ruta, H1, `mtime` |
| 5 | Encoding y mojibake | `vault_encoding` | — |
| 6 | Normas: pasada de `vault_norms --audit` | `vault_norms` | cuáles son deuda real y cuáles ruido de la tool |
| 7 | Reubicar lo que está fuera de estructura | `vault_move` | **exige mapa de rollback** (AP-10) |
| 8 | Enlaces rotos | `vault_graph_fix --classify` | qué es una nota ausente y qué un símbolo de código |
| 9 | Diagramas | `vault_mermaid_check` | — |
| 10 | Tags y vocabulario | `vault_tags` | el vocabulario propio del dominio |
| 11 | Índices y grafo | `vault_reindex`, `vault_graph` | — |
| 12 | Re-audit y contraste contra la baseline | `vault_audit` | qué deltas son avance y cuáles son artefacto |

---

## Las decisiones que ninguna tool toma

Son la parte cara del modo, y la razón de que no sea un script.

### Un enlace roto no siempre es una nota que falta

`[[interpolate]]`, `[[editHandler]]`, `[[AliasMap]]` no eran notas ausentes: eran
referencias a **símbolos del código fuente**. El vault nunca tuvo esas notas.
`vault_graph_fix` proponía 14 `partial_match` para ellas, y aplicarlos habría
enlazado una nota de error con una nota de concepto que no habla del mismo tema —
degradando el vault para bajar un contador.

La reparación fue convertirlos en `` `código` ``. Regla: **antes de crear la nota
que falta, comprobar que el destino es una nota.**

### Un enlace roto dentro de un archivo archivado se queda roto

36 de los 37 enlaces rotos finales viven en `10_Migrated/legacy-root-index.md`,
una instantánea de lo que el vault decía antes. Repararlos sería reescribir
evidencia: una versión corregida ya no prueba nada. Se declaran intencionales en
la propia nota, para que ninguna pasada futura los cuente como deuda viva.

Es el mismo criterio que impide "corregir" una nota dentro de `vault-backups/`.

### Un enlace a una nota planificada no es un error

`[[dsl-evolution-spec]]` apunta a una nota que su origen marca como *"pendiente de
crear"*. En Obsidian, un enlace a una nota inexistente **es** la forma de declarar
trabajo futuro. Un contador que lo cuente como roto pide que se borre una
intención.

### El `status` de una nota vieja no se inventa

Al completar 102 notas sin `status`, el valor por defecto fue `draft`: declara
"escrito, sin revisar", que es exactamente lo que se sabe. Poner `implemented`
habría afirmado una revisión que nadie hizo — y el vault habría quedado peor que
incompleto: **incorrecto y con aspecto de correcto**.

El `type` sí se deriva, pero del **uso mayoritario que la propia carpeta ya
tiene**, no de una tabla inventada. Si `02_Observability/errors/` tiene 34 notas
con `type: error`, la 35ª es un `error`.

### Una métrica que empeora al medir mejor no es una regresión

`stale` subió de 167 a 185. Las 26 notas que no tenían frontmatter no eran
*evaluables* para actualidad; al ganarlo entraron por primera vez en el chequeo, y
son viejas. La deuda no apareció con la sanación: estaba oculta tras una deuda
mayor. **Anotar esto es obligatorio** — sin la explicación, el siguiente lector
concluye que la sanación empeoró el vault.

---

## Los contadores discrepan, y la discrepancia informa

Durante la sanación, tres tools daban tres cifras de enlaces rotos. No era un bug
aislado: cada una **normalizaba distinto**, y la diferencia entre ellas era la
lista de trabajo real.

- `vault_graph_fix` indexaba destinos por `title:`. Obsidian **nunca** resuelve
  por `title:`.
- `vault_audit` hacía lo mismo, y además contaba enlaces dentro de
  `vault-backups/`.
- El recuento manual, resolviendo por nombre de fichero y `aliases:` —como resuelve
  Obsidian—, daba 49 menos.

Esto se formalizó como **AP-44 — verificación autoconsistente**. Ante contadores
que discrepan, la regla es: **gana el criterio del consumidor real**, no el de la
tool.

Y la reparación fue añadir el título a los `aliases:` de las 46 notas destino, no
reescribir los 46 puntos de llamada: el texto legible de un enlace es contenido.

---

## Por qué hace falta un vault ajeno

Cinco defectos del estándar salieron en esta sanación y **ninguno se habría visto
contra `vault-sandbox/`**:

| Tool | Fallo | Efecto |
|---|---|---|
| `vault_norms`, `vault_mermaid_check` | auditaban `vault-backups/` | 194/216 violaciones y 46/69 errores en instantáneas |
| `vault_mermaid_check` | patrones anclados con `^` | 23/23 `undefined_node` falsos, −2 pts cada uno |
| `vault_audit` | mini-parser ciego a listas YAML | 45 notas etiquetadas, reportadas sin tags |
| `vault_audit`, `vault_graph_fix` | resolvían por `title:` | 49 enlaces sanos marcados como rotos |
| `vault_init` | primers sin `status` | 18/18 reprobados por el audit del mismo estándar |

`vault-sandbox/` lo genera el propio estándar y **comparte sus supuestos**: escribe
los alias que sus tools esperan, los diagramas que su parser reconoce, el
frontmatter que su lector entiende. Un vault que nunca discrepa no puede revelar
una discrepancia.

**Corolario:** toda medida nueva se contrasta al menos una vez contra un vault
preexistente ajeno al estándar.

---

## Resultado de la ejecución de referencia

| | Antes | Después |
|---|---:|---:|
| `healthScore` | 0 | 54 |
| `nextActions` | 161 | 43 |
| Violaciones de norma | 216 | 1 |
| Enlaces rotos | 146 | 37 (36 intencionales + 1 planificada) |
| Errores Mermaid | 69 | 0 |
| Notas sin frontmatter | 27 | 0 |
| Notas sin `status` / `type` / `tags` | 94 / 76 / 43 | 0 / 0 / 0 |
| Notas totales | 232 | 235 (3 informes; **ninguna borrada**) |

---

## Limitaciones conocidas

- **`--wizard` no sirve en modo agéntico**: pide `stdin`, y un agente no lo tiene.
  Toda fase debe ser invocable de forma no interactiva.
- ~~Los huérfanos de `vault_audit` no ven los enlaces añadidos en la misma pasada.~~
  **Corregido.** No era un problema de orden: `PLACEHOLDER_PATTERNS` descartaba
  enlaces por prefijo, y `patron` es uno de los prefijos. Los 3 patrones tenían 6,
  8 y 2 enlaces entrantes que el extractor tiraba antes de indexarlos. Sexto caso
  de AP-44 — decidir con criterio propio en vez de preguntar al vault si el
  destino existe. Regla nueva: **un enlace cuyo destino existe nunca es un
  placeholder.** Huérfanos 3 → 0, `healthScore` 54 → 60.
- **`vault_tags` cuenta notas de backup en `total_tagged_notes`**: deliberado bajo
  AP-39 (la memoria de vocabulario sí quiere recordar términos ya usados, aunque la
  nota esté archivada), pero es la única excepción a la exclusión de instantáneas y
  conviene tenerla presente al leer esa cifra.

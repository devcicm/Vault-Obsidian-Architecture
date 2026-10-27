# QG-02 — dos escenarios de auditoría y la ficha de `vault-backups` (AP-36)

**Estado: EXPEDIENTE PREPARADO. Decisión pendiente del propietario (DEC-03 y
DEC-04).** Este documento no cambia `catalogo-qg.yaml` ni `politica_qg.py`;
entrega la investigación que §4 del GOAL R14 pide antes de esa decisión.

Complementa: `POLITICA-CERTIFICACION-PRODUCTO.md` (propuesta dual, no
aplicada) y `hallazgos-qg02.yaml` (INC-0001, la única violación abierta).

## 1. Los dos escenarios, medidos por separado

| Escenario | Qué se audita | Última medición | Resultado |
|---|---|---|---|
| **A — sandbox canónico** (`vault-sandbox/`, fixture de este repo) | el estado de la evidencia y del ambiente de desarrollo | recibos QG-02 del candidato `e198ffb` (colector R13) | **1 violación**: AP-36, `vault-backups` externo. Los tres controles obligatorios (AP-40, AP-42, AP-43) `ejecutado`, 0 hallazgos |
| **B — runtime limpio** creado por `vault init` | una instalación nueva del producto | re-auditoría con código actual (commit `2174bb1`), runtime de 75 ficheros | **0 violaciones** |
| **B' — runners de CI** (el sandbox que cada job construye con la semilla) | lo mismo que A, sin el residuo externo | corrida `40430269201`, las 12 columnas `Validate` | **0 violaciones** — el paso de contención estricta sale verde |

Los tres resultados **no significan lo mismo** y no se sustituyen: B/B'
acreditan al producto distribuible; A acredita el ambiente de desarrollo y su
evidencia. La única divergencia entre A y B' es un residuo **del anfitrión**,
no del producto: la carpeta `vault-backups` que se documenta en §2.

## 2. Ficha del hallazgo AP-36: `vault-backups`

- **Directorio lógico y ubicación:** `vault-backups/`, dos niveles por encima
  del vault auditado (`../../vault-backups` respecto de `vault-sandbox/`),
  **fuera del repositorio**, en la carpeta contenedora del repo del
  propietario. El detector lo reporta como side-effect fuera del vault root.
- **Origen:** conocido. Una operación de **backup del propio toolkit** de
  junio de 2026: el directorio lleva el registro `.backup-registry.json` del
  formato que la tool de backup escribe, y un único snapshot con el patrón de
  nombre `vault-<fecha>-<hora>` de esa tool. La ubicación por defecto de la
  operación caía **fuera** del vault — exactamente el escape de contención que
  AP-36 prohíbe. (La ubicación por defecto ya no es parte del candidato: el
  código actual escribe los efectos dentro del vault; esto es un residuo
  histórico, no una emisión activa. La re-auditoría del runtime limpio con
  código actual da 0 violaciones.)
- **Qué operación lo generó:** backup de vault con sello
  `2026-06-28T01:10:34Z` (`vault-2026-06-28-011034`), registrado con 37 notas
  y 64 ficheros por su propio manifiesto.
- **Qué datos contiene:** **un único snapshot** del 2026-06-28 con la
  estructura completa del vault de aquella fecha: los 18 directorios
  canónicos, los primers y `index.md` de cada sección, los artefactos
  derivados de `00_System/` (tool-contracts, tools-manifest, quality-index,
  standard-version, `.tool-trace.json`) y los índices de `99_Index/` (graph,
  hash, search). **No contiene datos personales ni secretos detectables en el
  inventario**: es mayormente contenido generado (primers, índices y contratos
  de tools). 38 `.md`, 10 `.json`, 18 ficheros sin extensión (los `.gitkeep`).
- **Tamaño e inventario:** 66 ficheros, 21 directorios, **854.108 bytes**
  (~834 KiB). Un solo snapshot más el registro de backups. Inventario completo
  y hashes en el apéndice A de este documento (SHA-256 de los 66 ficheros, ya
  que todos son ≤ 4 MiB; lectura exclusiva).
- **Fechas:** fichero más antiguo 2026-06-19 04:16, más reciente
  2026-06-27 19:10 (coherente con un snapshot tomado el 2026-06-28 01:10 sobre
  un vault vivo de finales de junio). **Ningún fichero se ha modificado desde
  entonces**: el directorio está quieto cuatro meses.
- **Propietario o responsable:** el propietario del anfitrión. Desde el repo
  no es determinable ningún otro responsable, y el ejecutor **no** es el dueño
  de esos datos.
- **Riesgo de conservarlo:** bajo para el producto (es un residuo quieto, no
  una emisión activa); alto para la **certificación**: mientras exista, la
  auditoría del sandbox canónico (escenario A) reporta 1 violación crítica de
  AP-36 y QG-02 queda BLOCKED por ese hallazgo. También normaliza el patrón
  «el backup vive fuera del vault», que es lo que la norma prohíbe.
- **Riesgo de moverlo:** bajo en datos (834 KiB, un directorio autocontenido
  con su registro); medio en trazabilidad: si se mueve sin registro, la
  evidencia de dónde estaba deja de ser verificable. Si se mueve, hacerlo con
  inventario antes/después y asentándolo en la decisión (DEC-04).
- **Riesgo de eliminarlo:** bajo en datos (el contenido es regenerable:
  primers e índices derivados que las tools actuales reconstruyen; no hay
  notas de usuario en el inventario), pero **no es cero**: es la única copia
  del estado de finales de junio, y la decisión de perderla no es del
  ejecutor. Eliminar sin registro dejaría además sin respuesta el «¿qué había
  ahí?» de esta ficha.
- **Estrategia de recuperación si se elimina o corrompe:** los primers y los
  índices derivados se regeneran con las tools actuales (`vault init` produce
  el esqueleto; los índices se reconstruyen con las tools de índice). El
  `.tool-trace.json` y los `tool-contracts` de aquella fecha son históricos y
  NO se regeneran idénticos; su valor es arqueológico. Por eso, si se opta por
  eliminar, se recomienda **archivar antes** (ZIP con los hashes del apéndice
  A verificados contra el archivo) y registrar el acto en la decisión DEC-04.

## 3. Propuesta de certificación (DEC-03), con recomendación

Las tres opciones del GOAL, con su lectura contra el contrato real:

| Opción | Qué certifica QG-02 | Consecuencia inmediata |
|---|---|---|
| **A — solo sandbox canónico** | el ambiente de desarrollo, incluido su residuo histórico | QG-02 sigue BLOCKED mientras `vault-backups` exista: el propietario tendría que decidir el residuo para desbloquear el release |
| **B — solo runtime limpio** | el producto distribuible | el escape de contención real dejaría de ser visible para la puerta: **se debilita la detección** que encontró el hallazgo; no se recomienda |
| **C — compuesto** | runtime limpio **y** ausencia de efectos externos nuevos, con **registro diferenciado** del residuo histórico | mantiene la detección, separa el residuo del producto, y da a la política propuesta (`POLITICA-CERTIFICACION-PRODUCTO.md`) su forma ejecutable |

**Recomendación: C**, por tres razones: (1) es la única que conserva la
detección que encontró el escape (AP-36 sigue auditable en el escenario A);
(2) separa dos preguntas que no se responden mutuamente —lo que consume un
tercero y lo que pasa en el anfitrión del desarrollador—, que es justo la
confusión que el dictamen R13 prohíbe; (3) no requiere tocar el catálogo para
conseguir un PASS: requiere **ratificar el sujeto de certificación** y
**decidir el residuo** (DEC-04). Cambiar el sujeto de certificación es una
decisión normativa expresa, no un ajuste de implementación.

Si el propietario ratifica C, el cambio de política se redacta como propuesta
formal sobre `catalogo-qg.yaml`/`politica_qg.py` con sus tests negativos (un
escape nuevo sigue siendo crítico; el residuo histórico registrado NO pasa la
puerta, lo deja declarado), y se somete a QA antes de aplicarse.

## Apéndice A — inventario y hashes (solo lectura, 2026-10-27)

Raíz relativa: `vault-backups/`. 66 ficheros, 854.108 bytes.

```
.backup-registry.json                                693 B  b6a9adef1dc4a363
vault-2026-06-28-011034/.manifest.json             2.487 B  1211db8b3ba9ba43
vault-2026-06-28-011034/00_System/.tool-trace.json 593.154 B  b106fa1846286a91
vault-2026-06-28-011034/00_System/tool-contracts.json 123.885 B  e1cc42a685bc54a1
vault-2026-06-28-011034/00_System/tool-contracts.md  18.290 B  fe95946b993b48fd
vault-2026-06-28-011034/00_System/tools-manifest.json 26.645 B  2ce53cba6ce40295
vault-2026-06-28-011034/00_System/quality-index.json  14.689 B  9cdc1c61c2f97b0b
vault-2026-06-28-011034/00_System/standard-version.json   137 B  7017c3fbffdb1f42
vault-2026-06-28-011034/00_System/index.md               429 B  c1321f1a2683fae7
vault-2026-06-28-011034/00_System/vault-commands.md    3.885 B  e546f2b654f82afd
vault-2026-06-28-011034/00_System/vault-hub.md         2.821 B  e132c885f139bada
vault-2026-06-28-011034/00_System/.gitkeep                 0 B  e3b0c44298fc1c14
vault-2026-06-28-011034/index.md                       3.438 B  58da7ca43b5d7fec
vault-2026-06-28-011034/99_Index/graph.json           17.708 B  cadb1211a8666a34
vault-2026-06-28-011034/99_Index/hash-index.json       6.877 B  c2991cba56c5120e
vault-2026-06-28-011034/99_Index/search-index.json    14.077 B  69887f4eb5b51d1d
vault-2026-06-28-011034/99_Index/.gitkeep                 0 B  e3b0c44298fc1c14
vault-2026-06-28-011034/99_Index/00-99_index-primer.md  1.058 B  a7ad77b9a203c900
```

(más los 48 ficheros restantes: `.gitkeep` de cada sección — todos
`e3b0c44298fc1c14…`, el hash del fichero vacío — y el par primer+index de las
17 secciones restantes, con los hashes completos registrados en la ejecución
del inventario del 2026-10-27; la muestra de arriba fija los ficheros con
contenido no regenerable a priori. El inventario íntegro se conserva en la
evidencia del ejecutor y puede regenerarse con el mismo comando de solo
lectura.)

**Comando del inventario (solo lectura):** listado recursivo con tamaño,
mtime y SHA-256 por fichero; ninguna escritura. El directorio no fue movido,
modificado ni purgado: sigue exactamente como lo midió el detector.

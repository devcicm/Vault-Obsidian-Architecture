# Modo agéntico de onboarding

Procedimiento para tomar un **proyecto de código que nunca tuvo vault** y poblarle
uno que respete las normas desde la primera nota.

No es una tool. `vault_onboard` hace el trabajo mecánico; esto es el orden en que
se aplica, y las decisiones que ninguna tool puede tomar sola.

Contraparte de [`MODO-AGENTICO-SANACION.md`](MODO-AGENTICO-SANACION.md), que
resuelve el problema contrario: un vault que ya existe y está sin gobernar.

Derivado de una ejecución real y completa sobre el repositorio de BuilderX
(626 commits, solo lectura). Todas las cifras de abajo son de esa ejecución.

---

## La diferencia con la sanación, que es toda

En sanación hay contenido previo y la regla es **nada se borra**: lo que estorba se
anota, porque alguien lo escribió por algo y el vault sanado que perdió información
no está sanado, está podado.

En onboarding no hay contenido previo que perder. La regla que ocupa ese lugar es
**nada se inventa**.

Y es más difícil de cumplir, porque el incentivo empuja al revés. Sanar tiene un
freno natural: borrar duele, se nota. Poblar no tiene ninguno — una nota de más no
rompe nada, sube el conteo, sube el health score, y el generador que la escribió
creía estar documentando. Por eso la norma que gobierna este modo es
[AP-45](../vault-obsidian-architecture.md) y no una de las de sanación: **una nota
se escribe porque hay algo que afirmar, no porque una sección esté vacía.**

Un hueco visible invita a llenarlo. Un hueco tapado con `_Pendiente_` declara que
ya está hecho, y nadie vuelve.

---

## Las tres reglas que gobiernan el modo

**1. El proyecto se lee, nunca se escribe.** El onboarding tiene una sola
superficie de escritura, y es el vault destino. El repositorio de origen no se
toca: ni un fichero de configuración, ni un README, ni un `.gitignore`. Si hace
falta cambiar algo en el proyecto, eso es otro trabajo con otra autorización.

**2. Nada se inventa.** Toda nota tiene una evidencia localizable detrás: un
fichero, un commit, una entrada de manifiesto, una sección de README. Lo que no la
tiene no se escribe — se **declara omitido**, que es información útil, mientras que
una nota de relleno es información falsa.

**3. Lo reconstruido nace `stub` o `draft`, nunca `implemented`.** Una nota deducida
del código no ha sido revisada por nadie. Ponerle `implemented` afirma una revisión
que no ocurrió, y el siguiente lector no tiene forma de distinguirla de una nota
que sí se revisó.

---

## El orden

| # | Fase | Tool | Decisión que la tool no toma |
|---|---|---|---|
| 0 | Confirmar que el proyecto **no** tiene vault | — | si lo que hay es un vault viejo, esto no aplica: es sanación |
| 1 | Copiar / apuntar al proyecto en solo lectura | — | dónde vive el vault destino (fuera de git si el proyecto es ajeno) |
| 2 | Crear el vault vacío | `vault_init` | la versión objetivo del estándar |
| 3 | **Documentación suelta preexistente** | `vault_migrate_docs` | qué `.md` del repo es documentación y cuál es andamiaje |
| 4 | Poblar desde el código y la historia | `vault_onboard` | el alcance: `--skip`, `--max-commits`, `--max-modules` |
| 5 | Verificar con el criterio del consumidor | `vault_audit`, `vault_norms --audit`, `vault_mermaid_check` | qué hallazgo es deuda real y cuál es artefacto de la medida |
| 6 | Escribir a mano lo que se declaró omitido | `vault_write` y las `*_save` | todo: esta fase es la que no se automatiza |
| 7 | Índices, grafo y vocabulario | `vault_reindex`, `vault_graph`, `vault_tags` | el vocabulario propio del dominio |

La fase 3 va **antes** que la 4 a propósito. Si el proyecto ya tenía documentación
suelta y se corre el onboard primero, el onboard vuelve a escribir desde el código
lo que ya estaba escrito a mano — y lo escribe peor, porque lo deduce en vez de
saberlo. Migrar primero deja el contenido humano como base y el onboard rellena
alrededor.

La fase 6 es la que decide si el vault sirve. Las fases 2–5 producen el esqueleto
verificable; lo que hace útil un vault es lo que solo sabe quien conoce el
proyecto, y eso ninguna tool lo extrae del código.

---

## Las decisiones que ninguna tool toma

Es la parte cara del modo, y la razón de que no sea un script.

### Un commit no es un ADR

La primera versión generaba un ADR retroactivo por cada commit que pareciera
importante, y salieron cinco llamados `adr-002-retroactivo` … `adr-006-retroactivo`.
Nombres que no distinguen una decisión de otra: AP-07 por la vía del nombre.

Un ADR documenta una decisión de arquitectura **con alternativas descartadas**. Un
commit documenta un cambio. La mayoría de los commits importantes no cambiaron
ninguna decisión: implementaron una que ya estaba tomada. Esos son historia y van a
`04_Sessions`.

Regla operativa: si del mensaje del commit no sale un título que nombre la decisión
—`adr-004-playwright-sobre-puppeteer`, no `adr-004-retroactivo`—, es que no hay
decisión que documentar. Un `wip` no se convierte en un ADR por insistir.

### Un `TODO` en el código no es una nota de observabilidad

Un repo mediano tiene decenas. Una nota por cada uno produce decenas de notas cuyo
cuerpo entero es el `TODO` copiado, que ya estaba en el código y donde se lee mejor.

Lo que sí es una nota es el **inventario**: cuántos hay, dónde se concentran, qué
dice que estén ahí. Eso es una observación sobre el proyecto y no está en ningún
fichero.

### Un módulo no merece nota por existir

`--max-modules` acota cuántos la reciben, pero el tope no es el criterio — es solo
un tope. El criterio es que **otra cosa lo referencie**: que aparezca en un flujo,
en un diagrama, en una decisión, en un test que lo nombre. Un módulo que solo se
menciona a sí mismo produce una nota que solo se enlaza a sí misma, y una nota sin
aristas no es memoria: es un fichero.

Además, dos ficheros pueden ser un solo módulo para Obsidian: `browserManager.ts` y
`browser-manager.ts` resuelven al mismo wikilink. Se deduplican por
`vault_io.normalize_stem`, que es el criterio que usa el resto del estándar — no
por comparación de cadenas, que es el criterio propio del generador (AP-44).

### El tope de historia es un parámetro, no un hecho

`--max-commits 500` sobre un repo de 626 commits devolvía `total_commits: 500` con
`warnings: []`. La cifra era del comando, no del proyecto, y nada lo decía.

Peor: con la ventana truncada, la reconstrucción de fases veía cinco meses de
historia continua y devolvía **una** fase. La conclusión era falsa y parecía un
dato. Ahora el tope alcanzado se declara en `warnings`, y las fases se separan por
**tags** —que es donde el proyecto dijo «aquí cambió algo»— en vez de por huecos en
el calendario, que en un proyecto de desarrollo continuo no existen.

### Las secciones dirigidas por eventos se quedan vacías

`18_Bugs`, `19_Audits` y `20_Quarantine` no se pueblan nunca en un onboard.
Poblarlas sería inventar bugs, auditorías y cuarentenas que no han ocurrido.

Esto entró en conflicto con `AP-03` (`emptyIndexes`), que penalizaba exactamente ese
estado. El conflicto era real y estaba en el estándar: una norma pedía llenar lo que
otra prohíbe inventar. Se resolvió a favor de AP-45 —`vault_audit._SECCIONES_POR_EVENTO`—
y la salida del onboard las declara en `sections_left_empty_by_design`, para que su
vacío se lea como estado correcto y no como trabajo pendiente.

El vacío declarado es información. El vacío sin declarar es ambiguo, y por eso se
rellena.

---

## Por qué un proyecto ajeno, otra vez

La regla 7 de `AGENTS.md` dice que toda medida nueva se contrasta al menos una vez
contra material ajeno al estándar. Aquí se cumplió, y pagó.

`vault_onboard` llevaba versiones publicado en el manifiesto, con su contrato
documentado, y **no se había ejecutado nunca**: AP-42 literal. La primera ejecución
real, contra un repo de fuera, devolvió nueve defectos — y el peor no era ninguno
de ellos por separado. Era que las 54 notas producidas nacían **todas** en
`missingType`: el estándar suspendía lo que su propia tool acababa de escribir.

Ninguno de los nueve habría salido contra `vault-sandbox/`, porque el sandbox lo
genera este repo y comparte los supuestos de las tools que iban a medirlo.

---

## Resultado de la ejecución de referencia

| | antes | después |
|---|---|---|
| Notas creadas | 54 | 57 |
| `healthScore` | ~54 | **96** |
| Deuda de metadatos (`missingType`) | 54 | **0** |
| Violaciones de norma | varias | **0** |
| Notas de relleno | 8 conceptos + 5 ADRs sin nombre | **0** (declaradas en `skipped_no_evidence`) |
| Commits leídos | 500 (tope, sin avisar) | **626** (reales) |
| Fases reconstruidas | 1 | **3**, con nombre |
| Secciones tocadas | 12 de 22 | 17, más 3 vacías por diseño y declaradas |
| Diagramas validados | no | sí (`vault_mermaid_check`) |

Criterio de aceptación, y es uno solo: **un vault recién onboardeado no necesita
sanación.** Está fijado en `tests/test_vault_onboard.py`, que corre la tool contra
un repositorio con git real y afirma sobre el vault resultante —el audit, las
normas, Mermaid— y no sobre el `ok: true` de la propia tool.

---

## Limitaciones conocidas

- **`canonicalShadow` reporta falsos positivos** con títulos legítimamente
  parecidos (`npm run studio` vs `npm run studio:dev`). El umbral de similitud es
  0.875 y no se ha bajado: ajustar un guard para que la salida propia parezca
  limpia es exactamente lo que AP-44 prohíbe.
- **La calidad del onboard depende del repo.** Un proyecto sin README, sin tags y
  con mensajes de commit de una palabra produce un esqueleto correcto y pobre. La
  tool no puede inventar lo que el repo no dice — y ese es el diseño, no el límite.
- **Nada sustituye la fase 6.** Lo que hace útil un vault es lo que solo sabe quien
  trabajó en el proyecto.

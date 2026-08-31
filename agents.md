# AGENTS.md — instrucciones para agentes en este repo

Este repositorio **no es un vault**: es el **estándar** que define cómo se construyen los
vaults. Es spec + toolkit. Confundir ambas cosas es el error más caro que se puede cometer aquí.

---

## Qué contiene

| Ruta | Qué es |
|---|---|
| `vault-obsidian-architecture.md` | **El manifiesto.** Representación pública del estándar (~6.000 líneas). Fuente normativa. |
| `scripts/*.py` | ~152 scripts, 116 tools activas en 37 grupos. Sin dependencias fuera de stdlib + PyYAML. |
| `scripts/README.md` | Referencia de tools por grupo, con ejemplos de CLI. |
| `tests/` | Suite pytest (3085 tests). Toda norma con guard debe tener test. |
| `cli/` | CLI consolidada + `safety.py` (guards anti-poison, `scan_content`). |
| `mcp/nodejs/` | Servidor MCP monolítico + `tools-catalog.json` (sincronizado desde Python). |
| `vault-sandbox/` | **Único** vault de pruebas del repo. Todo runtime va aquí. |
| `docs/` | SDD, skills, `MODO-AGENTICO-SANACION.md` (12 fases para sanar un vault preexistente) y `MODO-AGENTICO-ONBOARDING.md` (7 fases para poblar uno desde un proyecto sin vault). Allí la regla es *nada se borra*; aquí, **nada se inventa**. |

---

## El servicio y sus tres capacidades

**Fuente única: `scripts/vault_servicio.py`** (`SERVICIO` + `CAPACIDADES`). Lo de aquí
abajo es la lectura en prosa de ese registro, no una segunda declaración: si divergen,
manda el registro y esta sección se corrige. Qué capacidad realiza cada grupo lo dice
`python scripts/vault_servicio.py --trace`, y una puerta falla si algún grupo se queda
sin ninguna.

El servicio es uno: **dar a un agente LLM memoria documental persistente, auditable y
gobernada sobre markdown plano**, sin base de datos, sin embeddings y sin servicio
externo. Esa restricción es una decisión de producto, no una limitación pendiente de
resolver: el vault tiene que seguir siendo legible con un editor de texto y sobrevivir a
que este toolkit desaparezca.

Lo realizan tres capacidades, y una tool nueva pertenece a exactamente una:

- **escritura → gobernanza** (el grueso del catálogo): capturar, normalizar, versionar,
  auditar. Cuántos grupos exactamente lo dice `--trace`, no esta línea.
- **consulta → contexto** (grupos 26 y 34, v39): `vault_query_parse` → `vault_subgraph`
  → `vault_context_pack`, con `vault_preferences` (contexto estable en
  `17_Preferences/`) y `vault_ingest` (única con superficie de escritura, con preflight
  anti-poison no desactivable vía `cli/safety.py`). El **grupo 26 (Tokens)** cae en el
  rango 1–33 por orden de llegada, pero sus tres tools viven en el contexto `consulta` y
  existen para que el paquete quepa en la ventana.
- **gobernanza del estándar** (grupo 35): `vault_gate`, `vault_doc_sync`, `vault_arch`,
  `vault_changelog_check`, los tres audits con baseline y el resto del meta-toolkit.
  **No tocan las notas de nadie**: comprueban que este repo cumple lo que publica.
  Hasta v40.9 esta capacidad no tenía nombre y sus tools se contaban como si
  sirvieran a la memoria del agente — que es como un catálogo empieza a crecer por
  acumulación.

---

## Reglas no negociables

1. **`vault-sandbox/` para cualquier ejecución.** Ninguna tool se ejecuta contra la raíz del
   repo ni contra vaults reales del usuario. `--root` lo aceptan **dos conjuntos distintos**,
   y confundirlos es lo que hacía que esta línea llevase versiones diciendo «solo 4» mientras
   había un quinto: las que **escriben** en el vault que se les señala (`vault_norms`,
   `vault_graph_fix`, `vault_graph_inspect`, `vault_section_index`) y las que existen **para
   el contraste de la regla 7** y por eso miden un vault ajeno **en solo lectura**
   (`vault_foreign_check`, que además lo exige y rechaza rutas dentro de este repo, y
   `vault_fuente_unica`). El resto
   resuelve el vault por autodetección (`vault_io._detect_vault_root()`), que en este repo ya
   devuelve `vault-sandbox/` con origen `spec_repo_sandbox`. Para forzar un destino usa la
   variable de entorno `VAULT_ROOT`; para que una detección insegura falle en vez de caer a la
   raíz del repo, exporta `VAULT_STRICT_ROOT=1`. Verifica con `vault_io.vault_root_origin()`.

2. **No-derogación.** No se elimina ninguna tool, grupo, norma ni sección del manifiesto. Lo
   reemplazado se anota `superseded_by:` conservando su contrato. Si algo parece obsoleto,
   anótalo — no lo borres. Esto está declarado como política en el manifiesto
   (`### Política de no-derogación`).

3. **Registro canónico primero, doc después.** Un concepto que solo existe en el manifiesto no
   existe. El orden es: registro en código → doc derivada → guard que falla si divergen → test.
   Documentar sin código ejecutable es el fallo histórico que el estándar ya cometió una vez.

4. **Ciclo obligatorio ante un síntoma:** `síntoma → norma (AP/PAT/SP/CN) → guard + audit +
   heal → test`. Una corrección puntual sin norma que la sostenga se vuelve a romper.

5. **Enforcement real.** Ninguna norma nueva puede tener enforcement `manual`. Debe ser
   `guard`, `audit`, `guard+audit` o `recommended`, y el catálogo lo verifica.

6. **Escrituras atómicas y contenidas (AP-36).** Todo side-effect (backups, traces, locks,
   stubs) vive DENTRO del vault. Rutas siempre derivadas de `vault_io.get_vault_root()`,
   nunca de `__file__` ni del CWD.

7. **Verificar con el criterio del consumidor, no con el propio (AP-44).** Una tool que
   mide con su misma normalización se certifica a sí misma y queda ciega a su error: los
   wikilinks se resuelven por nombre de fichero y `aliases:` —nunca por `title:`, que
   Obsidian no mira—, el frontmatter con `yaml.safe_load` y no con un regex por líneas.
   Corolario: **toda medida nueva se contrasta al menos una vez contra un vault
   preexistente ajeno al estándar.** `vault-sandbox/` lo genera este repo y comparte sus
   supuestos, así que no puede exhibir este fallo — cinco defectos reales salieron solo al
   ejecutar contra un vault de fuera. Ver `docs/MODO-AGENTICO-SANACION.md`.

8. **No propagar tools a otros repos** salvo petición explícita. Los vaults consumidores se
   sincronizan por decisión del usuario, no como efecto colateral de un cambio aquí.

---

## Fuentes únicas de verdad

Si necesitas un dato de estos, léelo del registro — no lo redefinas ni lo copies:

| Dato | Fuente |
|---|---|
| Normas AP/PAT/SP/CN y su enforcement | `scripts/vault_norms_catalog.py` — **hoja del núcleo desde v40.27**. Importa de aquí si solo necesitas el dato; `vault_norms` sigue reexportándolo, pero entrar por la fachada arrastra el motor y sus once dependencias |
| Dirección de cada frontera entre contextos | `vault_arch.PRESUPUESTO_DE_CRUCES` (un par nuevo bloquea la puerta) |
| Vocabulario de `status` (12 valores) | `vault_norms.STATUS_VOCAB` |
| Fundamentos F1–F8 y dimensiones DQ | `scripts/vault_fundamentals_catalog.py` — hoja del núcleo desde v40.28 (AP-62); `vault_fundamentals` lo reexporta, pero entrar por ahí arrastra el verificador |
| Tríada CIA, FAIR, V's del Big Data, cobertura ISO, matriz de trazabilidad | `vault_fundamentals_catalog.FRAMEWORK_REGISTRIES` |
| Versión vigente del estándar (en código) | `vault_version.CURRENT_VERSION` — hoja del núcleo desde v40.28. El banner, la tabla de versiones, el badge y `pyproject.toml` son documentación y los vigila `vault_doc_counts` |
| Criterio «esto es documentación del estándar, no una nota» y tabla de penalizaciones | `vault_audit_catalog` — hoja del núcleo desde v40.28 |
| Gramática de Mermaid (tipos y validadores) | `vault_mermaid_reglas` — hoja del núcleo desde v40.28; `vault_mermaid_check` es el que recorre el vault aplicándola |
| Causa de un fallo del **dominio** (vocabulario, 7 entradas) | `vault/kernel/fallos.py` — `CAUSAS` + `FalloDeDominio`. Hoja del núcleo: sin un solo import fuera de `typing`. El dominio nombra qué pasó; **no** construye el envelope ni conoce `ERROR_CATALOG` |
| Traducción causa del dominio → código del catálogo | `vault_errors.MAPA_DE_FALLOS`, emitida por `emit_fallo`. Un solo sitio: repartirla entre adaptadores es AP-57 cometido al cumplir AP-52 |
| Catálogo de tools expuesto por MCP | `scripts/vault_mcp_catalog.py` → `mcp/nodejs/tools-catalog.json` |
| Raíz del vault en runtime | `vault_io.get_vault_root()` / `set_vault_root()` |
| Cómo se detectó esa raíz (confianza) | `vault_io.vault_root_origin()` / `vault_root_is_confident()` |
| Contrato de tools (`tool-spec.json`) | `vault_io.tool_spec_path()` → `<vault>/00_System/`; `resolve_tool_spec()` con fallback legacy |

---

## Comandos habituales

```bash
# Pre-commit hook — activa el cierre automático de drift (recomendado)
# Instalar (una vez): cp .git/hooks/pre-commit.sample .git/hooks/pre-commit
# Automáticamente ejecuta vault_fix_all antes de cada commit.

# Suite completa — debe quedar en verde antes de cerrar cualquier cambio
python -m pytest tests/ --tb=short

# Normas y marco de datos
python scripts/vault_norms.py --audit --root vault-sandbox   # audita el vault contra las normas
python scripts/vault_norms.py --check-framework              # guard anti-drift registro ↔ manifiesto
python scripts/vault_fundamentals.py --framework             # exporta el marco (JSON + MD)
python scripts/vault_fundamentals.py --matrix                # matriz concepto → métrica → tool

# Catálogo MCP
python scripts/vault_mcp_catalog.py --check                  # falla si Python y JSON divergen
python scripts/vault_mcp_catalog.py --sync                   # regenera el JSON

# Salud del vault de pruebas — sin `--root`: solo lo aceptan las cuatro tools
# de la regla 1, y en este repo la autodetección ya resuelve `vault-sandbox/`.
# Para forzar otro destino, `VAULT_ROOT`.
python scripts/vault_audit.py                    # healthIndex + healthProfile por familia
python scripts/vault_quality_check.py --min-score 0.7
```

---

## Antes de cerrar un cambio

**Las puertas y la suite, las dos.** Las puertas son rápidas y la suite no; verde en las
puertas no es verde en la suite. Cuántas puertas hay lo dice el registro `PUERTAS`, no
este documento — escribir aquí el número lo convierte en una cifra a mano, que es AP-47.
El pre-commit hook ejecuta `vault_fix_all` automáticamente; si está instalado, el ciclo de
drift se cierra en cada commit sin intervención manual.

- [ ] Pre-commit hook instalado: `cp .git/hooks/pre-commit.sample .git/hooks/pre-commit`
- [ ] `python scripts/vault_gate.py --strict` → todas verdes.
- [ ] `python -m pytest tests/ --tb=short` en verde.
- [ ] `git diff --stat vault-obsidian-architecture.md` sin borrados netos de contenido.
- [ ] Si tocaste una versión: banner del manifiesto, tabla de versiones, entrada de
      changelog con hash real, badge del `README.md` y `version` de `pyproject.toml`.
- [ ] Si añadiste una norma o un id de registro: guard + test que fallen cuando falte.

### Las puertas, una a una

**Este bloque es derivado.** Sale de `vault_gate.PUERTAS`, se regenera con
`python scripts/vault_gate.py --fix-doc` y `--check-doc` falla si diverge; lo que se
escriba a mano aquí se pierde. Hasta v40.16 cada puerta llevaba su propio párrafo: una
segunda descripción de lo que el registro ya decía, envejeciendo en la dirección cómoda.
El **porqué** de cada decisión no cabe en un campo y no está aquí — está en el docstring
de cada tool, que es donde lo lee quien la abre. Lo que no se deriva de ninguna parte va
abajo, en «Cuatro cosas que el registro no puede decirte».

<!-- puertas:inicio — generado por vault_gate.py --fix-doc -->

- [ ] `python scripts/vault_norms.py --check-framework`
      El manifiesto documenta todo id del marco de datos y toda norma catalogada tiene sección propia.
- [ ] `python scripts/vault_mcp_catalog.py --check`
      El catálogo Python y tools-catalog.json no divergen.
      *Se arregla con:* python scripts/vault_mcp_catalog.py --sync
- [ ] `python scripts/vault_mcp_catalog.py --check-contracts`
      Toda tool del catálogo tiene entrada en tool-spec.json, y toda entrada que ya no está declara su status en vez de borrarse.
- [ ] `python scripts/vault_doc_counts.py --check --strict`
      Ninguna cifra de la documentación está escrita a mano (AP-47).
      *Se arregla con:* python scripts/vault_doc_counts.py --fix
- [ ] `python scripts/vault_doc_sync.py --check --strict`
      Toda tool tiene sección en scripts/README.md y el índice una fila por grupo.
      *Se arregla con:* python scripts/vault_doc_sync.py --fix  (solo el índice; las secciones se escriben a mano)
- [ ] `python scripts/vault_noop_audit.py --check --strict`
      AP-37 — ninguna tool con side effects devuelve ok: true sin indicador de trabajo.
      *Se arregla con:* saldar la deuda y luego --freeze
- [ ] `python scripts/vault_blame_audit.py --check --strict`
      AP-51 — ningún handler amplio devuelve un vacío indistinguible de un resultado legítimo.
      *Se arregla con:* saldar la deuda y luego --freeze
- [ ] `python scripts/vault_error_contract.py --check --strict`
      AP-52 — ningun envelope de error nuevo se emite fuera del contrato de ERROR_CATALOG.
      *Se arregla con:* emitir por emit_error y luego --freeze
- [ ] `python scripts/vault_spec_catalog_check.py --check-fields --strict`
      Contrato de campos con los repos consumidores: ningún campo estable desaparece sin quedar anotado en superseded_fields.
      *Se arregla con:* anotar el campo en superseded_fields (superseded_by + why) o volver a emitirlo; --freeze-fields solo tras revisar
- [ ] `python scripts/vault_changelog_check.py --check --strict`
      El changelog no contradice a git: hash existente, fecha igual a la del commit, ningún `pending` de una versión ya cerrada.
      *Se arregla con:* python scripts/vault_changelog_check.py --fijar-hash  (cierra la versión en curso); corregir la fecha contra su commit
- [ ] `python scripts/vault_arch.py --check --strict`
      Contextos acotados: fronteras, puertos, vocabularios con dueño, entorno declarado, AP-49 en cero.
- [ ] `python scripts/vault_servicio.py --check --strict`
      Trazabilidad tool → grupo → capacidad → servicio: todo grupo pertenece a una capacidad y toda capacidad tiene tool viva.
      *Se arregla con:* clasificar el grupo en la capacidad a la que sirve; si no sirve a ninguna, la pregunta es por qué existe el grupo
- [ ] `python scripts/vault_blueprint.py --check --strict`
      El plano de docs/BLUEPRINT.md no diverge de los registros, y ninguna norma estrena falta de puerta y test a la vez.
      *Se arregla con:* python scripts/vault_blueprint.py --blueprint  (regenera el plano); una norma nueva sin cobertura se cubre con un test, no se congela
- [ ] `python scripts/vault_norms_coherence.py --check --strict`
      El catálogo de normas no se contradice ni con el código que lo aplica ni con las penalizaciones que lo pesan (AP-55).
      *Se arregla con:* que el código nombre la norma en el sitio que la aplica, o que el catálogo retire la cobertura que no tiene; ampliar la baseline no es una de las dos
- [ ] `python scripts/vault_criterios.py --check --strict`
      Ningún módulo que clasifica notas reescribe un criterio que ya tiene dueño canónico (AP-57).
      *Se arregla con:* importar al dueño en vez de decidir por cuenta propia; la baseline solo encoge
- [ ] `python scripts/vault_fuente_unica.py --check --strict`
      El mismo dato tipado no tiene valores distintos en varias notas del mismo ámbito (AP-05).
      *Se arregla con:* PAT-1: una nota canónica declara el dato y las demás la enlazan; verde solo cubre la parte decidible sin interpretar
- [ ] `python scripts/vault_ciclos.py --check --strict`
      Ningún ciclo de importación nuevo se esquiva metiendo el import dentro de una función (AP-58).
      *Se arregla con:* invertir la dependencia: el módulo de bajo nivel deja de pedirle el módulo entero al de alto; subir el import o ampliar la baseline no son la solución, solo esconden dónde
- [ ] `python scripts/vault_kernel.py --check --strict`
      La lista del núcleo no contradice a la forma medida del grafo: K1 delegada, fan-in/fan-out contra el escalón derivado y churn contra la mediana del dominio (AP-59).
      *Se arregla con:* sacar el módulo del kernel o darle forma de núcleo —fan-out abajo, consumidores reales—; los umbrales se derivan del escalón y se publican, así que ajustarlos para pasar no es una opción, y la baseline solo encoge
- [ ] `python scripts/vault_excepcion_declarada.py --check --strict`
      Ningún handler captura la excepción que una librería declara dejando escapar la que lanza de verdad (AP-61).
      *Se arregla con:* delegar en el dueño que ya la contuvo —para el frontmatter, vault_lib.parse_frontmatter— o nombrar la excepción citando al dueño; ampliar la tupla en trece sitios sin dueño es AP-57 cometido al arreglar AP-61
- [ ] `python scripts/vault_recursos.py --check --strict`
      Ningún consumidor cruza una frontera de contexto para leer un recurso que no necesita el fan-out del productor (AP-62).
      *Se arregla con:* partir el productor en catálogo y motor y repuntar a los consumidores al dueño; partir el fichero solo no mueve la cifra —lo enseñó v40.27—, y reclasificar el productor al núcleo sin medirle el fan-out lo vería AP-59
- [ ] `python scripts/vault_produccion.py --check --strict`
      Toda promesa hecha a quien instala esto —versión mínima, dependencia, plataforma, superficie de red— tiene a alguien que la ejerza, y los huecos están declarados con su motivo.
      *Se arregla con:* añadir el ejecutor que falta, o declarar la promesa como descubierta con el motivo escrito; las otras veinte puertas miden el repo contra sí mismo y en esa sala no está el consumidor, que es como >=3.9 pasó en verde sin que ninguna máquina ejecutara 3.9
- [ ] `python scripts/vault_doc_staleness.py --check --strict`
      Todos los artefactos derivados del vault (data-framework.json, norm-registry.json, quality-index.json, etc.) existen y contienen JSON válido.
      *Se arregla con:* Regenerar con: vault_fundamentals --framework && vault_norms --rebuild && vault_compact_contracts && vault_quality_check && vault_tags

<!-- puertas:fin -->

## Cuatro cosas que el registro no puede decirte

Lo que sigue no sale de ningún campo y por eso está escrito: son decisiones y trampas
que costaron una tanda cada una.

**1. Un guard verde dice menos de lo que parece, y cada uno declara cuánto menos.**
`vault_criterios` (AP-57) mide dos cosas con alcances distintos. **En Python**, solo los
módulos que nombran `*.md` —lo publica en `modules_measured`/`modules_skipped`— y por
copia sintáctica: un módulo puede reimplementar un criterio sin repetir una constante y no
lo verá. **En las fronteras de lenguaje** (v40.19) mide los ficheros de `FRONTERAS` —el
`.mjs`, la CI, el `Makefile`, el `.ps1`— y allí la exención no es importar al dueño, que no
se puede, sino **leer la pasarela**: el artefacto derivado por el que el criterio cruza.
El alcance se declara: un ejecutable de otro lenguaje fuera de toda zona sale como
`frontera_no_declarada`, porque un sitio donde una copia no se vería vale tanto como una
copia. Lo que sigue sin ver es el `.mjs` que reimplemente la decisión sin escribir la
constante. `vault_fuente_unica`
(AP-05) cubre el dato **tipado** escrito como `clave: valor`; la divergencia en prosa y
la del sinónimo (`ip:` frente a `direccion_ip:`) no las mide nadie, y por eso el catálogo
declara `cobertura_parcial` en vez de dar la norma por cubierta. `vault_norms_coherence`
(AP-55) mide **traza**, no enforcement: que la afirmación se pueda seguir hasta el código.

**2. Una cobertura se salda nombrando la norma en la función que la cumple.** No en la
cabecera del módulo —desde v40.16 el guard la descuenta— y no ampliando la baseline. Si
de verdad no la mide nadie, se declara `cobertura_descubierta` con el motivo escrito: una
norma que declara su hueco no cuenta como deuda nueva, porque declararse honestamente no
puede salir más caro que callarse. Y el grep sirve para **descartar**, nunca para
confirmar: `vault_audit` emite `"norm": "CN-01"` sobre un hallazgo de *scaffold*, así que
cerrar CN-01 con ese grep habría sido usar el criterio del propio guard — el AP-44 que
esa tool existe para detectar.

**3. Lo derivado no se edita a mano.** `docs/BLUEPRINT.md`, el índice de
`scripts/README.md`, las cifras de la documentación y el bloque de puertas de arriba se
regeneran (`--blueprint`, `--fix`, `--fix-doc`). Que lo escrito a mano se pierda es lo
que los mantiene honestos. Las secciones de `scripts/README.md` sí se escriben a mano.

**4. Una deuda que se salda no se borra.** Pasa a `saldada` con la versión que la cerró
(capa 7 del plano), y una baseline que encoge deja el fichero en pie con la lista vacía.
Una entrada borrada no se distingue de una que nadie volvió a mirar.

---

## Trabajar con las baselines (leer antes de tocarlas)

Varios guards llevan **baseline que solo puede encoger** — `vault_noop_audit` (AP-37),
`vault_blame_audit` (AP-51), `vault_error_contract` (AP-52), `vault_criterios` (AP-57),
`vault_ciclos` (AP-58), `vault_kernel` (AP-59) y la capa 4 de `vault_blueprint`, entre
otras. **Cuántas son exactamente lo dice `vault_blueprint._BASELINES`, no esta línea**:
hasta v40.20 aquí ponía «cinco» y ya eran diez, que es AP-47 cometido en el documento que
explica el mecanismo anti-drift. Derivar el conteo es el movimiento 2, declarado en la
capa 7 del plano. Todas aparecen en la capa 6, y una puerta falla si alguna baseline del
repo no está listada ahí: una deuda congelada que el plano no publica es una deuda que
nadie revisa.

1. **Se indexan por firma de sitio, no por línea** (desde v40.6). La firma es
   `módulo::función::hash del código normalizado`, y el hash sale de `ast.unparse`, así que
   comentarios, sangrado y posición desaparecen antes de hashearse. Desplazar un sitio ya
   **no** lo reporta como deuda nueva; cambiar el cuerpo del handler sí, y debe.

   Hasta v40.5 el índice era `módulo:línea` y esto era la trampa más cara del repo: insertar
   diez líneas de comentario encima de un sitio conocido lo reportaba como *nuevo* y al viejo
   como *resuelto*, y había que verificar tres condiciones a mano antes de cada `--freeze`.
   Pasó tres veces en una semana. **Esa receta manual ya no hace falta y no debe reintroducirse:**
   un guard cuya corrección depende de que una persona ejecute bien tres pasos no es un guard.

   Consecuencia directa: `--freeze` **se niega** a congelar sitios sin precedente y devuelve
   `DEBT_WOULD_GROW`. Congelar deuda nueva exige `--freeze --admitir-nuevos`, que además la
   lista en el envelope. Una baseline en formato viejo emite `MIGRATION_REQUIRED` en vez de
   leerse como vacía —que habría estrenado la deuda entera como nueva— y se migra con
   `--migrate`.

2. **Los detectores tienen falsos positivos por clase.** No conviertas a ciegas lo que
   listan. Medido en la tanda de v40.5, AP-52 marca al menos dos cosas que **no** son
   envelopes de error de una tool:
   - **Filas de un informe** — `vault_smoke` devuelve `{"tool": …, "ok": False, "problem": …}`
     por cada tool que falla el smoke. Es el dato del informe, no el fallo de `vault_smoke`.
   - **Cuerpos HTTP** — `vault_token_service` responde `self._send(404, {"ok": False, …})`.
     El contrato ahí es el de HTTP, no el del catálogo de errores.

   Convertir cualquiera de las dos rompería al consumidor en nombre de cumplir la norma.

3. **Una norma nueva sin cobertura no se congela: se le escribe el test.** La baseline
   existe para la deuda que ya estaba. Y desde v40.16 la capa 4 no acepta una mención de
   pasada como prueba: el código de la norma tiene que aparecer en el cuerpo de una
   función `test_*`.

---

## La regla 7 en la práctica

`vault_foreign_check --root <vault ajeno>` es la forma ejecutable de la regla 7. Exige
`--root` explícito y **rechaza cualquier ruta dentro de este repo**: con autodetección
caería en `vault-sandbox/` y saldría verde justo en el caso que la regla existe para
detectar. Sin un vault ajeno a mano, `--self-test` verifica que las cuatro negativas siguen
en pie.

Lo que ha destapado hasta ahora, ninguno reproducible en `vault-sandbox/`:

- Siete títulos de frontmatter compuestos sin escapar (v40.2), uno de ellos roto siempre.
- El criterio de "esto es documentación, no una nota" comparaba el **nombre exacto** del
  manifiesto, así que una copia archivada con sufijo de versión —que es lo que la
  no-derogación pide a los consumidores— aportaba decenas de enlaces rotos falsos (v40.5).
- Dos conflictos reales de AP-05 —`host_ip` y `pve_version` con valores distintos en dos
  notas del mismo servidor— que `vault-sandbox/`, generado por este repo, no puede
  exhibir (v40.15). `vault_fuente_unica` acepta `--root` para eso, en solo lectura.

Cuando midas un vault ajeno, **solo lectura**. Ninguna tool de escritura se ejecuta contra
material que no generó este repo sin que el dueño lo pida.

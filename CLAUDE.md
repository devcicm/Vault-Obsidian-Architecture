# CLAUDE.md — instrucciones para agentes en este repo

Este repositorio **no es un vault**: es el **estándar** que define cómo se construyen los
vaults. Es spec + toolkit. Confundir ambas cosas es el error más caro que se puede cometer aquí.

---

## Qué contiene

| Ruta | Qué es |
|---|---|
| `vault-obsidian-architecture.md` | **El manifiesto.** Representación pública del estándar (~6.000 líneas). Fuente normativa. |
| `scripts/*.py` | ~123 scripts, 100 tools activas en 37 grupos. Sin dependencias fuera de stdlib + PyYAML. |
| `scripts/README.md` | Referencia de tools por grupo, con ejemplos de CLI. |
| `tests/` | Suite pytest (2553 tests). Toda norma con guard debe tener test. |
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
  Hasta v40.9 esta capacidad no tenía nombre y sus 14 tools se contaban como si
  sirvieran a la memoria del agente — que es como un catálogo empieza a crecer por
  acumulación.

---

## Reglas no negociables

1. **`vault-sandbox/` para cualquier ejecución.** Ninguna tool se ejecuta contra la raíz del
   repo ni contra vaults reales del usuario. **Solo 4 tools aceptan `--root`**
   (`vault_norms`, `vault_graph_fix`, `vault_graph_inspect`, `vault_section_index`); el resto
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
| Normas AP/PAT/SP/CN y su enforcement | `scripts/vault_norms.py` |
| Vocabulario de `status` (12 valores) | `vault_norms.STATUS_VOCAB` |
| Fundamentos F1–F8 y dimensiones DQ | `vault_fundamentals.FUNDAMENTALS` |
| Tríada CIA, FAIR, V's del Big Data, cobertura ISO, matriz de trazabilidad | `vault_fundamentals.FRAMEWORK_REGISTRIES` |
| Catálogo de tools expuesto por MCP | `scripts/vault_mcp_catalog.py` → `mcp/nodejs/tools-catalog.json` |
| Raíz del vault en runtime | `vault_io.get_vault_root()` / `set_vault_root()` |
| Cómo se detectó esa raíz (confianza) | `vault_io.vault_root_origin()` / `vault_root_is_confident()` |
| Contrato de tools (`tool-spec.json`) | `vault_io.tool_spec_path()` → `<vault>/00_System/`; `resolve_tool_spec()` con fallback legacy |

---

## Comandos habituales

```bash
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

- [ ] **`python scripts/vault_gate.py --strict` → todas verdes.** Corre las puertas de golpe;
      cuántas son lo dice el registro `PUERTAS`, no este checklist —escribir aquí
      el número lo convierte en una cifra a mano, que es AP-47— y
      `--check-doc` falla si alguna puerta no aparece aquí. Los ítems siguientes las
      detallan una a una — están para saber qué mide cada una y cómo se arregla, no
      para correrlas por separado. **No sustituye a la suite.**
- [ ] `python -m pytest tests/ --tb=short` en verde.
- [ ] `python scripts/vault_norms.py --check-framework` → `ok: true`. Además de los ids
      del marco, exige que toda norma de `NORM_CATALOG` tenga **sección propia** en el
      manifiesto: una mención de pasada en un changelog no cuenta.
- [ ] `python scripts/vault_mcp_catalog.py --check` → sincronizado.
- [ ] `python scripts/vault_doc_counts.py --check --strict` → `ok: true`. Ninguna
      cifra de la documentación se escribe a mano: si cambió un conteo, `--fix`.
- [ ] `python scripts/vault_doc_sync.py --check --strict` → `ok: true`. Toda tool del
      catálogo tiene sección en `scripts/README.md` y el índice tiene una fila por grupo.
      Si solo cambió el índice, `--fix`; las secciones se escriben a mano.
- [ ] `python scripts/vault_mcp_catalog.py --check-contracts` → `ok: true`. Toda tool del
      catálogo tiene entrada en `<vault>/00_System/tool-spec.json`; toda entrada que ya no
      está en el catálogo declara `status: archived | internal | orphan` (no se borra: se
      anota). `group` y `group_id` se derivan de `GROUPS` y de la numeración de
      `scripts/README.md` — no hay una numeración propia del tool-spec.
- [ ] `python scripts/vault_spec_catalog_check.py --check-fields --strict` → `ok: true`.
      El contrato de campos con los repos consumidores: un campo `stable` no
      desaparece. Puede pasar a `superseded_fields` —con `superseded_by` y un motivo,
      y siguiendo o no emitiéndose según el caso— pero no evaporarse, que rompe en
      silencio a quien lo leía. `--fields-table` publica la clasificación derivada del
      tool-spec; `--freeze-fields` solo después de revisar qué se está prometiendo.
- [ ] `python scripts/vault_noop_audit.py --check --strict` → `ok: true` (AP-37).
      Toda tool nueva con side effects declara un indicador de trabajo: la baseline
      solo puede encoger. Tras saldar deuda, `--freeze`.
- [ ] `python scripts/vault_blame_audit.py --check --strict` → `ok: true` (AP-51).
      Ningún handler amplio (`except Exception`, `except:`) devuelve un vacío
      indistinguible de un resultado legítimo: el fallo de la tool no se presenta como
      ausencia en el dato. Baseline que solo puede encoger; tras saldar deuda, `--freeze`.
- [ ] `python scripts/vault_error_contract.py --check --strict` → `ok: true` (AP-52).
      Ningún envelope de error nuevo se construye a mano: el fallo sale por
      `emit_error` con `error_code` y `recovery`, que es lo que el consumidor mira
      para decidir. Baseline que solo puede encoger; tras saldar deuda, `--freeze`.
- [ ] `python scripts/vault_changelog_check.py --check --strict` → `ok: true`. El
      changelog del manifiesto no contradice a git: el hash citado existe, la fecha
      es la del commit —de **autoría**, que un rebase no reescribe— y ninguna
      versión ya cerrada sigue publicando `git: pending`. Cerrar una versión ya no
      es un commit manual de ritual: `--fijar-hash` sustituye el `pending` por el
      hash real y corrige la fecha de paso, que es justo el dato que se
      desincronizó once días en v39.0.
- [ ] `python scripts/vault_arch.py --check --strict` → `ok: true`. Contextos acotados:
      fronteras, puertos, vocabularios con dueño, entorno declarado, AP-49 en cero.
      Desde v40.7 mide también **AP-54** en `unsynced_writes`: ningún handler
      responde a un `file_lock` fallido escribiendo igual. El `TimeoutError`
      significa que otro lo tiene tomado **ahora mismo**, así que esa escritura
      no es una carrera improbable — es la única situación en la que ese código
      corre. Omitir la escritura sí es correcto y no se marca.
- [ ] `python scripts/vault_servicio.py --check --strict` → `ok: true`. El pilar:
      todo grupo del catálogo pertenece a **exactamente una** capacidad y toda
      capacidad tiene al menos una tool viva. Sin baseline a propósito — una
      baseline aquí permitiría añadir un grupo sin decidir a qué sirve, que es
      justo el vacío que el registro cierra. Los `group_id` salen de
      `mapa_de_grupos()`; no hay numeración propia.
- [ ] `python scripts/vault_blueprint.py --check --strict` → `ok: true`. El plano
      de `docs/BLUEPRINT.md` no diverge de los registros. **Es derivado: no se
      edita a mano** — se regenera con `--blueprint`, y lo escrito a mano se
      pierde, que es lo que lo mantiene honesto. Su capa 4 —norma → puerta →
      test— es la única con baseline: nació con 16 normas sin puerta **ni** test,
      y exigir cero el primer día habría hecho nacer la puerta en rojo. Una
      norma nueva sin cobertura no se congela: se le escribe el test.
      Su capa 7 es el registro de **deuda declarada**, y desde v40.11 toda
      entrada dice `estado` (`pendiente` | `saldada`) y `desde` qué versión se
      arrastra. Una deuda que se salda **no se borra**: pasa a `saldada` con la
      versión que la cerró, porque una entrada borrada no se distingue de una
      que nadie volvió a mirar. No hay `en_curso` a propósito — o se puede citar
      la versión que la cerró, o sigue pendiente; un estado intermedio sería una
      promesa, y una promesa no es un dato verificable. Hoy hay **siete
      pendientes**, y la que encabeza la lista es **AP-05**: la única norma
      `critical` sin detector, que ninguna tanda ha escrito todavía.
- [ ] `python scripts/vault_norms_coherence.py --check --strict` → `ok: true` (AP-55).
      El catálogo de normas no se contradice con el código que lo aplica ni con
      `vault_audit.PENALIZACIONES`, que es la otra mitad canónica del mismo hecho.
      Seis medidas, todas en cero desde v40.11. La quinta —afirmaciones de
      cobertura que ningún módulo respalda— conserva su baseline **vacía**: el
      fichero se queda en pie con `claims: []`, que es lo que distingue una deuda
      saldada de una medida retirada. **La traza no demuestra enforcement**:
      demuestra que la afirmación no es seguible hasta el código, que es lo
      verificable. Se salda nombrando la norma **en la función que la cumple** —no
      en la cabecera del módulo, que pasa la medida sin llevar a nadie al sitio— o
      retirando la cobertura y declarando `cobertura_descubierta` con el motivo
      escrito; ampliar la baseline no es la tercera forma. La sexta (C6) es el
      espejo: ninguna entrada de `PENALIZACIONES` resta del healthIndex sin
      declarar su norma o declararse `metrica_sin_norma`. **Sin baseline a
      propósito** — una permitiría añadir una penalización sin decidir qué la
      sostiene.

      Al saldar una afirmación, el grep sirve para **descartar** (si nadie la
      nombra, nadie puede seguirla), nunca para **confirmar**: `vault_audit` emite
      `"norm": "CN-01"` sobre un hallazgo de *scaffold*, así que cerrar CN-01
      reatribuyéndosela habría sido usar el criterio del propio guard — el AP-44
      que esta tool existe para detectar.
- [ ] `python scripts/vault_doc_sync.py --check --strict` cubre además, desde v40.4, que
      **todo comando que la documentación publica exista y acepte sus flags**. `CLAUDE.md`
      publicaba los dos comandos de salud con `--root`, que ninguna de las dos tools
      acepta: el comando que un agente copia para medir el vault moría en
      `unrecognized arguments`. El manifiesto queda **fuera** de esa comprobación a
      propósito — su changelog cita comandos rotos como prueba del defecto que describe.
- [ ] `git diff --stat vault-obsidian-architecture.md` sin borrados netos de contenido.
- [ ] Si tocaste una versión: banner del manifiesto, tabla de versiones, entrada de changelog
      con hash real, badge del `README.md` y `version` de `pyproject.toml` coherentes.
- [ ] Si añadiste una norma o un id de registro: guard + test que fallen cuando falte.

---

## Trabajar con las baselines (leer antes de tocarlas)

Tres guards —`vault_noop_audit` (AP-37), `vault_blame_audit` (AP-51) y
`vault_error_contract` (AP-52)— llevan una **baseline que solo puede encoger**.

1. **Se indexan por firma de sitio, no por línea** (desde v40.6). La firma es
   `módulo::función::hash del código normalizado`, y el hash sale de `ast.unparse`, así que
   comentarios, sangrado y posición desaparecen antes de hashearse. Desplazar un sitio ya
   **no** lo reporta como deuda nueva; cambiar el cuerpo del handler sí, y debe.

   Hasta v40.5 el índice era `módulo:línea` y esto era la trampa más cara del repo: insertar
   diez líneas de comentario encima de un sitio conocido lo reportaba como *nuevo* y al viejo
   como *resuelto*, y había que verificar tres condiciones a mano antes de cada `--freeze`.
   Pasó tres veces en una semana. **Esa receta manual ya no hace falta y no debe reintroducirse:**
   un guard cuya corrección depende de que una persona ejecute bien tres pasos no es un guard.

   Consecuencia directa: `--freeze` ahora **se niega** a congelar sitios sin precedente y
   devuelve `DEBT_WOULD_GROW`. Congelar deuda nueva exige `--freeze --admitir-nuevos`, que
   además la lista en el envelope. Si te encuentras una baseline en formato viejo, el audit
   emite `MIGRATION_REQUIRED` en vez de leerla como vacía — que habría estrenado la deuda
   entera como nueva — y se migra con `--migrate`.

2. **Los detectores tienen falsos positivos por clase.** No conviertas a ciegas lo que
   listan. Medido en la tanda de v40.5, AP-52 marca al menos dos cosas que **no** son
   envelopes de error de una tool:
   - **Filas de un informe** — `vault_smoke` devuelve `{"tool": …, "ok": False, "problem": …}`
     por cada tool que falla el smoke. Es el dato del informe, no el fallo de `vault_smoke`.
   - **Cuerpos HTTP** — `vault_token_service` responde `self._send(404, {"ok": False, …})`.
     El contrato ahí es el de HTTP, no el del catálogo de errores.

   Convertir cualquiera de las dos rompería al consumidor en nombre de cumplir la norma.

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

Cuando midas un vault ajeno, **solo lectura**. Ninguna tool de escritura se ejecuta contra
material que no generó este repo sin que el dueño lo pida.

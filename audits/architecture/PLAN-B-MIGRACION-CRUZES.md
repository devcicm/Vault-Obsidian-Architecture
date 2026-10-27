# Plan B — migración compatible de los cinco cruces fuera de puerto

**Estado: PREPARADO, NO EJECUTADO.** El ejecutor no ratifica deuda ni la
declara aceptada. Este documento entrega lo que la alternativa B necesita para
poder ejecutarse en cuanto el propietario la ratifique: las interfaces que
existen, los contratos nuevos, la compatibilidad de CLI y MCP, los riesgos, las
pruebas, el orden de commits, el rollback y el resultado esperado del
reconciliador.

Base: `audits/architecture/QA-RC-03-CRUZES.md` (análisis y alternativas A/B/C) y
el registro de cruces `vault_arch.PRESUPUESTO_DE_CRUCES`, donde los dos pares
que hay que eliminar están declarados con `objetivo: a_eliminar` y
`fecha_limite: 2027-06-30`.

---

## 1. Los dos pares y su dirección legal

| Par | Situación actual | Objetivo | Dirección **legal** (ya presupuestada) |
|---|---|---|---|
| `gobernanza → meta_toolkit` | `scripts/vault_norms.py` importa `vault_mcp_catalog` y `vault_smoke` para componer AP-40 y AP-42 | `a_eliminar` (2027-06-30) | `meta_toolkit → gobernanza` es permanente: «quien verifica depende de lo verificado, nunca al revés» |
| `gobernanza → autoria` | `scripts/vault_norms.py` importa `vault_voice` para componer AP-43 | `a_eliminar` (2027-06-30) | `autoria → gobernanza` es permanente: validar al escribir es el cableado del dominio |

**LaAlternativa A del análisis de QA («el meta-toolkit expone un punto de
composición y gobernanza consume ese puerto») no sirve tal cual**: ese puerto
sería precisamente el cruce que hay que eliminar. `gobernanza → meta_toolkit`
está prohibido; por eso el puerto no puede vivir en meta-toolkit con gobernanza
como consumidor. Esta es la corrección que el plan B introduce respecto del
análisis de QA-RC-03, y la razón por la que el plan no se limita a «mover tres
funciones».

## 2. Interfaz que existe hoy

`scripts/vault_norms.py` (fachada de mantenimiento del contexto *gobernanza*):

| Símbolo | Qué hace | Verificador al que cruza |
|---|---|---|
| `_control_ap40(flag) -> int` | recorre los problemas de `check_params()` y los marca en el audit | `vault_mcp_catalog` (meta_toolkit) |
| `_control_ap42(flag) -> int` | recorre la baseline de `vault_smoke` y las tools sin invocación derivable | `vault_smoke` (meta_toolkit) |
| `_control_ap43(flag) -> int` | recorre las normas `silent` de `vault_voice.coverage()` | `vault_voice` (autoría) |
| `_checks_estandar(flag, registrar=None) -> list` | compone los tres con `vault.gobernanza.controles.ejecutar_control` y registra su estado de ejecución (TD-0003) | — |
| `vault_norms_audit(root=None)` | llama al motor `vault_norms_engine.auditar_runtime(root, insertar_checks_estandar=_checks_estandar)` | — |

El motor **no** importa los verificadores: los recibe por callback. El adeudado
está en la fachada, y por eso el movimiento `667a6a5` (motor → fachada) no lo
eliminó: mudó el sitio del cruce, no su dirección.

## 3. Contrato nuevo (el puerto)

Un puerto de **datos**, no de símbolos, publicado por el dueño de cada control
y leído por gobernanza sin importarlo. Vive en el **núcleo** (`vault/kernel/`),
que es la capa inferior que todos los contextos pueden leer.

`vault/kernel/controles.py` (nuevo, hoja del núcleo, sin imports de contexto):

```python
CONTROL = {
    "codigo": "AP-40",
    "dueno": "meta_toolkit",
    "superficie": {"script": "vault_mcp_catalog", "argv": ["--check-params"]},
    "severidad": "medium",
}
```

- **El dueño publica; el ejecutor lee el dato y lanza la superficie pública del
  dueño** (`python scripts/vault_mcp_catalog.py --check-params`) como
  **proceso**, no como import. Un proceso no es una arista del grafo de
  imports: el cruce desaparece del grafo sin esconderlo.
- La evidencia la produce el dueño (su tool, su exit code, su envelope JSON),
  que es justo lo que AP-43 y el modelo de «quién verifica depende de lo
  verificado» piden.
- El registro guarda **datos**, no código: el analizador de contextos puede
  leerlo y declarar el puerto, en vez de encontrar un import dinámico
  (AP-58: esconder el cruce moviéndolo dentro de una función es exactamente el
  fallo que ese guard persigue).

### 3.1 Alternativa de registro por Python (si el proceso no encaja)

Si el propietario prefiere que el dueño se registre en el núcleo al importarse
(`registrar_control("AP-40", control_ap40)`), el snag es conocido y hay que
declararlo: quien compone tiene que **forzar** la importación del dueño, y esa
importación es una arista de vuelta. Por eso la variante de proceso es la
recomendada: no depende de quién importa a quién.

## 4. Compatibilidad CLI y MCP

| Superficie | Efecto | Por qué |
|---|---|---|
| CLI `vault run vault_norms --audit --strict` | **Sin cambios de contrato**: el envelope sigue teniendo `checks[]` con `control`, `estado`, `detalle` y `hallazgos` | el puerto cambia QUIÉN ejecuta el control, no QUÉ se publica |
| MCP `vault_norms` | igual por el mismo camino (misma función, mismo envelope) | la pasarela es el catálogo, y el catálogo no cambia |
| `vault_norms_engine.auditar_runtime` | **no cambia su firma**: sigue recibiendo `insertar_checks_estandar` | compatibilidad con los fixtures que lo llaman |
| `_control_ap40/42/43` | **se conservan como compat deprecada** durante una versión: delegan en el puerto y emiten un aviso | ventana de compatibilidad; sin esto, un consumidor que los importe rompe |
| Los tres controles obligatorios | siguen ejecutándose y con estado (`ejecutado`) | TD-0003: el envelope tiene que seguir declarando el estado de ejecución |

## 5. Riesgos

| # | Riesgo | Mitigación | Quién decide |
|---|---|---|---|
| R1 | El control deja de ejecutarse y el envelope no lo declara (el fallo de TD-0003) | el puerto es **obligatorio**: sin registro del control, el audit falla con `CONTROL_OBLIGATORIO_NO_VERIFICADO`, no con silencio | ejecutor (implementación) |
| R2 | La evidencia cambia de forma (JSON del proceso frente a la que se marcaba en memoria) | el dueño publica el contrato de su salida; el puerto traduce; prueba de equivalencia de ambos caminos | ejecutor |
| R3 | Coste: tres procesos más por audit | medir el coste real; si es alto, el registro por Python (3.1) con la arista declarada | propietario (el criterio de coste) |
| R4 | Se declara un cruce nuevo por el camino inverso (el motor o la fachada piden al dueño) | el guard `vault_arch` mide el grafo después del cambio: cualquier par nuevo bloquea la puerta | ejecutor |
| R5 | La baseline de cruces no puede crecer | no se toca: el par desaparece, la baseline encoge | ejecutor |
| R6 | Romper consumidores de `vault_norms.audit` (CLI `--audit --strict`, puerta de coherencia, fixture del colector) | las tres funciones privadas se conservan una versión; la puerta de coherencia mide el resultado, no la implementación | ejecutor |

## 6. Pruebas

### 6.1 Criterio de independencia — semántico, no solo ausencia de aristas

El dictamen QA (R13) tiene razón sobre el riesgo de este plan: **reemplazar
imports de símbolos por invocaciones de procesos puede ESCONDER una dependencia
real en vez de quitarla**. Un import que desaparece del grafo no es prueba de
independencia: puede ser el mismo acoplamiento con otro disfraz. Por eso el
criterio se enuncia como lo que tiene que ser VERDAD, no como lo que tiene que
faltar:

| # | Criterio | Cómo se comprueba | Qué prohíbe |
|---|---|---|---|
| I1 | **Independencia semántica**: el contexto que consume puede decidir *si* verifica sin saber *cómo* verifica el dueño. No conoce sus internos, ni su fichero, ni su módulo. | Un test que comprueba que el lado de gobernanza referencia SOLO el contrato publicado (los datos del puerto) y que ningún símbolo del verificador es importable desde él (chequeo estático de la dirección) | Un puerto que, para servir, reexporte los nombres del verificador |
| I2 | **Independencia operacional**: la frontera sobrevive al empaquetado. La superficie consumida existe en el artefacto INSTALADO, con el mismo contrato que en el checkout. | Un test que construye la wheel, la instala en un venv limpio FUERA del checkout y ejecuta el control por la superficie publicada | Un puerto que solo exista en el checkout (el mismo defecto que `vault_norms_engine` tenía con los módulos excluidos) |
| I3 | **Retorno observable**: el resultado del control llega como DATO comprobable (código, hallazgos, detalle), no como efecto sobre una estructura compartida. | Un test que corre el control dos veces y compara los datos recibidos, y que verifica que los hallazgos llevan la identidad del dueño (quién verificó) | Un puerto que devuelve «se ejecutó» sin decir qué encontró |
| I4 | **Efectos laterales declarados**: todo lo que el control escribe es parte del contrato publicado (qué rutas toca, qué locks toma, qué deja detrás). | Un test que ejecuta el control e inventaría las escrituras, comparándolas con la lista declarada | Un control que escribe fuera de su alcance «porque es un subproceso» |
| I5 | **Fail-closed**: si el verificador falta, está roto o le falta su dependencia, el control NO se ejecuta y la puerta lo dice. | Un test negativo que retira el verificador y comprueba que la puerta reporta el control como no ejecutado, no como ejecutado | Un subproceso que «sale bien» porque no pudo arrancar |

**Lo que esto cambia en el plan:** el puerto de §3 no es solo una estructura de
datos: es un contrato publicado con dueño, efectos laterales declarados,
retorno observable y camino fail-closed. Y el test de equivalencia de §6.2 no
basta: pasaría igual si los dos caminos estuvieran mal del mismo modo. Los
tests de I1-I5 son los que distinguen «la dependencia se fue» de «la
dependencia se mudó».

### 6.2 Las pruebas de la migración

1. **Equivalencia**: el mismo vault produce el mismo conjunto de hallazgos por
   el camino viejo (import) y por el nuevo (puerto), comparados como conjuntos
   de `(norm, path, detail)`. **Necesaria, no suficiente** (ver §6.1).
2. **Negativa de la negativa** (I5): sin verificador disponible, el control
   se declara NO ejecutado y la puerta se pone roja — el fallo que se vio en
   R12 (un control que no podía cargar su dependencia informaba cero
   hallazgos y parecía verde).
3. **Grafo**: `vault_arch --check --strict` verde y `off_port_total` de 5 a 3
   (los dos pares eliminados), sin ampliaciar ninguna baseline.
4. **Reconciliador**: `audits/fase2/reconciliar_archify.py --check` en verde
   **sin retocar el snapshot** (el objetivo de la alternativa B).
5. **Suite**: la suite completa verde, y el gate `toolkit_audit` verde (los
   ejemplos documentados de las tools se ejecutan de verdad).
6. **Producto**: E2E desde la wheel (`recorrido_terceros_r07.py`), porque el
   audit por puerto tiene que funcionar con la instalación empaquetada, donde
   `vault_mcp_catalog` vive en `_impl/` (I2).
7. **Efectos laterales**: el inventario de escrituras del control se compara
   con el declarado, en el checkout y en el artefacto instalado (I4).

## 7. Orden de commits (propuesta, a ejecutar tras la ratificación)

```
1. feat(kernel): puerto de controles como dato (registry + contrato)
2. test: equivalencia del camino viejo y el nuevo
3. refactor(meta_toolkit): publica AP-40 y AP-42 en el puerto
4. refactor(autoria): publica AP-43 en el puerto
5. refactor(gobernanza): la fachada consume el puerto; las tres funciones
   privadas quedan como compat deprecada
6. refactor(gobernanza): la compat se retira en la versión siguiente
7. chore: reconciliador conforme (sin tocar el snapshot)
```

El paso 6 es el que cierra la deuda `a_eliminar`: mientras la compat exista, el
cruce sigue en el grafo y la baseline no puede bajar. Por eso B «deja el cierre
verificable»: la ventana de compatibilidad tiene fecha, y esa fecha es la
misma `fecha_limite` que ya declara el registro.

## 8. Rollback

- Cada commit es reversible por sí mismo: el puerto es aditivo y la fachada
  sigue teniendo sus tres funciones.
- Si el puerto falla en producción, se vuelve al commit 1 (el puerto existe
  pero nadie lo consume) y el audit sigue funcionando por el camino viejo.
- **No se toca el snapshot de Archify en ningún punto**: si algo va mal, el
  reconciliador sigue reportando las 10 divergencias exactamente como ahora, y
  el estado del repo es el de hoy.

## 9. Resultado esperado del reconciliador

| Medida | Hoy | Tras B (esperado) |
|---|---|---|
| Divergencias del reconciliador | 10 (DIV-01..10) | **0** (las cinco parejas de contexto quedan conformes) |
| Pares de contexto fuera de puerto | 5 | **3** |
| `off_port_baseline` | 5 | 3 (la baseline **encoge**; no se amplía) |
| Snapshot de Archify | sin tocar | **sin tocar** |
| QG-00 / QG-01 | BLOCKED por falta de ratificación | evaluables de nuevo |

**Lo que este plan NO hace**: no declara aceptada ninguna divergencia, no
amplía baselines, no toca el snapshot, no reescribe historia y no cambia la
superficie pública de CLI ni MCP.

---

## 11. Apéndice R14 — identidad de las divergencias, coste y la evidencia I2

Añadido para el GOAL R14 (§3.1): lo que la decisión del propietario necesita
medido, no prometido. Nada de esto ejecuta el plan.

### 11.1 Identidad exacta de DIV-01..10 (fuente: `divergencias-archify.yaml`)

Una causa raíz común: el movimiento `667a6a5` (la composición pasó de
`vault_norms_engine` a la fachada `vault_norms`) no está conciliado con el
snapshot de Archify (`f049b1bd`). Las diez divergencias son cosvisibilidades
de ESE movimiento, no diez problemas:

| ID | Tipo | Clave | Naturaleza | Riesgo de actualizar el inventario |
|---|---|---|---|---|
| DIV-01 | ficha de par | `[gobernanza, autoria]` | ficha desactualizada: el adeudado NO cambió | bajo |
| DIV-02 | ficha de par | `[gobernanza, meta_toolkit]` | ficha desactualizada: el adeudado NO cambió | bajo |
| DIV-03 | acceso | `vault_norms_engine -> vault_mcp_catalog.check_params` | movimiento (mismo par, otro módulo) | bajo |
| DIV-04 | acceso | `vault_norms_engine -> vault_smoke.SIN_SMOKE` | movimiento | bajo |
| DIV-05 | acceso | `vault_norms_engine -> vault_smoke.invocation` | movimiento | bajo |
| DIV-06 | acceso | `vault_norms_engine -> vault_smoke.load_baseline` | movimiento | bajo |
| DIV-07 | acceso | `vault_norms_engine -> vault_voice.coverage` | movimiento | bajo |
| DIV-08 | dependencia (fichero) | `vault_norms_engine -> vault_mcp_catalog` | movimiento; granularidad del snapshot ≠ del registro | medio |
| DIV-09 | dependencia (fichero) | `vault_norms_engine -> vault_smoke` | movimiento; ídem | medio |
| DIV-10 | dependencia (fichero) | `vault_norms_engine -> vault_voice` | movimiento; ídem | medio |

Las diez declaran `accion_requerida: ratificacion del propietario` y
`ratificado: false`. Los cruces reales que B elimina son los DOS pares de §1
(que hoy producen **5** aristas fuera de puerto `off_port_total=5`,
`off_port_baseline=5`): la eliminación de los pares hace converger también el
inventario (DIV-01..10 → 0, §9), sin tocar el snapshot.

### 11.2 Evidencia I2 medida: el puerto propuesto NO funciona fuera del checkout tal como está escrito

El criterio I2 (§6.1) exige que la superficie consumida exista en el artefacto
INSTALADO. Medido el 2026-10-27 contra la wheel del candidato `e198ffb`
instalada en un venv limpio fuera del checkout (el `paridad-venv` de los
recibos R13):

- Los tres dueños de control son tools de clase **`maintenance`** con
  **`installed: false`** en la instalación: `vault_mcp_catalog`,
  `vault_smoke` y `vault_voice` salen en `vault tools list` con
  `"installed": false`.
- Invocar la superficie de AP-40 por el CLI instalado falla:
  `vault run vault_mcp_catalog --check-params` → exit 3,
  `INVALID_ACTION`, `tool desconocida: vault_mcp_catalog`.
- El MÓDULO sí viaja en la wheel, pero como interno:
  `site-packages/vault_toolkit/_impl/vault_mcp_catalog.py`. Consumir esa ruta
  sería depender de la maquetación interna (viola I1).
- La superficie runtime de gobernanza SÍ está publicada
  (`vault_gobernanza.exe`, validación de contenido), pero no es la
  composición de auditoría que el puerto quiere mover.

**Consecuencia para el plan:** la §3 tal cual (`superficie: {"script":
"vault_mcp_catalog", "argv": ["--check-params"]}` ejecutada como proceso)
**fallaría I2 en la instalación empaquetada**. Es exactamente el defecto que
§6.1 prohíbe: un puerto que solo existe en el checkout. Antes de ejecutar B,
el propietario tiene que elegir una de estas enmiendas:

1. **Publicar la superficie de mantenimiento en la wheel** (clase
   `maintenance` con entry point real, p. ej. `vault run --maintenance ...`):
   decisión de empaquetado — cambia el producto, no solo el puerto.
2. **Declarar el entorno operativo del puerto** = distribución de
   mantenimiento (checkout o instalación editable), dejando I2 satisfecho
   «por definición de sujeto»: honesto, pero hay que escribirlo en el
   contrato del puerto y en DEC-02.
3. **La variante de registro del §3.1** (el dueño se registra en el núcleo al
   importarse), asumiendo la arista de vuelta declarada que allí se describe.

La recomendación sigue siendo B, **condicionada a esta elección**; sin ella,
la migración podría pasar los guards del checkout y seguir sin funcionar donde
un tercero instala.

### 11.3 Coste operativo medido del mecanismo propuesto (R3)

Medido el 2026-10-27 con el mismo intérprete, sin carga paralela, mediana de
tres corridas por comando (máquina del ejecutor, Windows):

| Mecanismo | Mediana |
|---|---|
| Referencia: arranque de Python sin trabajo | 0,21 s |
| AP-40 como subproceso (`vault_mcp_catalog --check-params`) | 1,97 s |
| AP-42 como subproceso (`vault_smoke --check`) | **147,22 s** |
| AP-43 como subproceso (`vault_voice --tool vault_norms`) | 0,21 s |
| **Suma del camino propuesto (tres subprocesos)** | **≈ 149,4 s** |
| Camino actual (audit completo con los tres controles en proceso) | **2,42 s** |

**Lectura:** el puerto de proceso, tal cual lo especifica la §3, multiplicaría
el coste del audit por ~60: el dominante es AP-42, porque `vault_smoke
--check` NO es una lectura de baseline sino el smoke completo (ejecuta las
tools del catálogo — es el paso de ~2,5 min que la puerta `noop` ya corre).
Además, ninguna de las dos superficies de AP-42 que el control realmente
necesita (baseline y tools sin invocación derivable) está publicada hoy como
argv: el plan tendría que **crear esas superficies** (p. ej. `vault_smoke
--baseline-check`), que es trabajo del dueño, no del consumidor.

**Enmiendas posibles para DEC-02** (elegir ANTES de ratificar B):

1. **Superficies ligeras por dueño**: publicar en `vault_smoke` un argv de
   solo-baseline (lectura + verificación, sin ejecutar tools). Coste
   esperado del audit por puerto: ~2,5 s (tres arranques + lecturas).
   Requiere commit del dueño (meta_toolkit).
2. **Ejecución diferida**: el audit declara el control con su identidad y su
   estado, y la EJECUCIÓN pesada se hace en la puerta (que ya corre el smoke
   completo); el envelope del audit no miente (declara `ejecutado_en_puerta`)
   — requiere un cambio de contrato del envelope (TD-0003 vecinos).
3. **La variante de registro del §3.1** (in-proceso con arista de vuelta
   declarada): coste ~0, pero conserva el cruce en el grafo con la arista
   pública — no lo elimina, lo formaliza; solo sirve si el propietario
   re-clasifica el par.

Con esta medición, la recomendación B queda **condicionada también a la
elección de coste**, además de a la enmienda I2 de §11.2: sin ellas, B
canjea una deuda arquitectónica por un coste operativo de ~60× en cada audit.

---

## 12. Propuesta B revisada — lista para decisión formal (R16)

El anexo del propietario (`proposal/dec-02b-dec-03c-dec-04pending-20261026`,
commit `cc05eab`) registra la preferencia **B condicionada** y exige elegir
EXPRESAMENTE la enmienda I2 y la de coste antes de implementar. Esta §12
entrega esa elección servida: cada subopción con su viabilidad, coste,
riesgos y pruebas, para que la decisión sea firmar una fila, no diseñar.

### 12.1 La enmienda I2 (cómo llega el contrato al paquete instalado)

| Subopción | Qué es | Viabilidad medida/analizada | Coste | Riesgos | Pruebas que exigiría |
|---|---|---|---|---|---|
| **I2-a** Publicar la superficie de mantenimiento en la wheel (p. ej. entry point `vault-maintenance` o `vault run --maintenance`) | los tres dueños (AP-40/42/43) quedan invocables desde la instalación | factible: son módulos que YA viajan en `_impl/`; lo que falta es el entry point y su clase de catálogo | empaquetado + contrato de catálogo (`installed: false` → nueva clase `maintenance_publicada`); sin cambios de producto runtime | ampliar la superficie pública del paquete (decisión de producto); tests de instalación | I2 con venv limpio: invocar las tres superficies desde la wheel (el fallo actual exit 3/`tool desconocida` debe desaparecer) |
| **I2-b** Restringir el puerto a la distribución de mantenimiento (checkout/editable), declarándolo en el contrato del puerto | el puerto NO pretende funcionar desde la wheel; la auditoría de gobernanza no es superficie de terceros | ya es la realidad medida: `vault_norms` es `maintenance`/`installed: false` y el audit solo corre en desarrollo | cero de empaquetado | el dictamen puede objetar que I2 queda satisfecho «por definición de sujeto»; hay que escribirlo en el contrato y aceptarlo | I2 redefinido: mismo contrato en checkout e instalación editable (módulos idénticos), documentado en el manifiesto del puerto |
| **I2-c** Registro en proceso con arista declarada (§3.1) | el dueño se registra en el núcleo al importarse; sin subprocesos | factible con el snag conocido: quien compone fuerza importar al dueño → la arista vuelve al grafo | coste ~0 en latencia | NO elimina el cruce: lo formaliza; contradice el `objetivo: a_eliminar` salvo que el propietario re-clasifique el par | I1/I2 reinterpretados; el guard seguiría viendo la arista (requeriría reclasificar el par → otra decisión) |

### 12.2 La enmienda de coste (cómo no pagar ~60× por audit)

| Subopción | Qué es | Coste esperado | Riesgos | Pruebas que exigiría |
|---|---|---|---|---|
| **COST-a** Superficie ligera por dueño: `vault_smoke` publica un argv de solo-baseline (lectura + verificación, SIN ejecutar tools); análogo para voice/mcp_catalog si hace falta | el audit lanza tres subprocesos ligeros | ~2,5-4 s por audit (tres arranques + lecturas); medición obligatoria antes de cerrar | nueva superficie pública del dueño (meta_toolkit); riesgo de divergencia entre la lectura ligera y el smoke completo → prueba de equivalencia entre ambas | benchmark antes/después; equivalencia hallazgos-ligero vs smoke-completo en un sandbox |
| **COST-b** Ejecución diferida: el audit declara identidad+estado y la ejecución pesada vive en la puerta (que ya corre el smoke) | el audit no lanza procesos; el envelope declara `ejecutado_en_puerta` | ~0 adicional | cambio de contrato del envelope (vecino de TD-0003); el consumidor del audit debe aceptar el nuevo estado; QA debe revisar que no falsee `ejecutado` | tests del envelope con el estado nuevo; negativa: puerta que no corrió → `no_ejecutado`, nunca PASS |
| **COST-c** No migrar AP-42, migrar solo AP-40/43 (los baratos) y dejar el par `gobernanza→meta_toolkit` parcialmente | elimina 1 de 2 pares | intermedio | deja la deuda a medias: `off_port_total` 5→4, no 3; el `a_eliminar` del par de AP-42 sigue | igual que B con alcance menor |

### 12.3 Recomendación sustentada y valores propuestos (NO son la decisión)

La recomendación técnica sigue siendo **B**, pero condicionada a la elección
expresa de una subopción I2 y una de coste. Con lo medido:

- **I2-a** es la única que permite acreditar el producto DISTRIBUIDO (publicar
  la superficie de mantenimiento en la wheel). Es la que el anexo del
  propietario prefiere si se quiere compatibilidad con terceros.
- **COST-a** (superficie ligera de baseline) es la que devuelve el audit a
  su orden de magnitud actual; COST-b además toca el contrato del envelope.
- **I2-c** no elimina el cruce real (lo formaliza) y **COST-c** deja deuda a
  medias: ambas contradicen el `objetivo: a_eliminar` y la fecha límite
  2027-06-30, salvo que el propietario lo re-clasifique expresamente.

**Valores propuestos** (para que la decisión se tome sobre cifras, no sobre
sensaciones; los firma quien decide):

| Parámetro | Valor propuesto | Por qué |
|---|---|---|
| `umbral_latencia_audit` | **≤ 5 s por audit** | el actual mide 2,42 s; 5 s deja margen para la lectura ligera sin aceptar el camino de ~149 s (60×) |
| `ventana_deprecacion` | **una versión** (la siguiente a la que introduce el puerto) | la compat deprecada de `_control_ap40/42/43` es lo que mantiene el cruce en el grafo; mientras exista, `off_port_total` no baja (plan B §7, paso 6) |
| `criterio_de_exito` | `off_port_total` 5 → 3 y divergencias 10 → 0 **sin tocar el snapshot ni ampliar la baseline**, con I1–I5 acreditadas y E2E desde wheel | es el resultado que el plan ya define (§9) |
| `rollback` | por commit (plan B §8): revertir al commit previo al consumo del puerto | el puerto es aditivo; el audit sigue funcionando por el camino viejo |

### 12.4 Plantilla de firma (lo que debe nombrar el acto)

```yaml
decision_DEC-02:
  alternativa: B
  enmienda_I2: "I2-a | I2-b | I2-c"        # una, con motivo
  enmienda_coste: "COST-a | COST-b | COST-c"  # una, con motivo
  umbral_latencia_audit: "<s>"
  ventana_deprecacion: "<versiones>"
  fecha: ""
  ratificado_por: ""
  referencia: ""
```

Con la fila firmada, la implementación sigue el §7 del plan (commits
pequeños reversibles) + las pruebas §6.1 (I1-I5) + §6.2 (equivalencia,
negativa de la negativa, grafo, reconciliador, suite, E2E desde wheel,
efectos laterales) y cierra con re-certificación integral y CI del SHA
resultante. Rollback: §8 (cada commit reversible; el snapshot no se toca).

**Sin esa firma, el ejecutor no implementa nada**: este documento es el
expediente, no un permiso.

## 10. La decisión que se pide

Al propietario, con la evidencia de `QA-RC-03-CRUZES.md` y este plan:

- **A** — composición desde el meta-toolkit: **descartada por dirección**
  (crea el cruce que hay que eliminar).
- **B** — migración compatible por etapas: **recomendada**, con el matiz de que
  el puerto es de **datos y proceso**, no de símbolos, y con la compat de una
  versión con fecha.
- **C** — excepción formal: posible, pero deja la evidencia de gobernanza en
  manos de quien no es el dueño.

Sin ratificación, el ejecutor **no ejecuta nada de este plan** y el estado de
QG-00/QG-01 sigue siendo el de hoy: BLOCKED.

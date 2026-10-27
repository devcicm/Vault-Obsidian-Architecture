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

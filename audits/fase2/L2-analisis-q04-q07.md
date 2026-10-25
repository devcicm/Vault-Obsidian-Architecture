# L2 — Investigación de Q04–Q07 (TD-0003): controles que pueden no ejecutarse y no decirlo

**Alcance:** investigación únicamente. **No se implementa nada** de lo que aquí se propone (asi lo autorizo el propietario y QA).
**Estado de cada afirmación:** `OBSERVADO` (medido o leido con la referencia exacta) · `INFERIDO` (razonamiento sobre lo observado) · `PENDIENTE` (falta medir).

## 1. Hecho observado: el defecto, con su demostracion

`scripts/vault_norms_engine.py` mete tres controles del estandar dentro de `_checks_estandar(flag)` (lineas 136-197). Cada bloque tiene esta forma:

```python
try:
    import vault_mcp_catalog as _cat          # AP-40   (linea 142)
    ... flag("AP-40", ...)
except (ImportError, OSError, ValueError):
    pass                                     # linea 151
```

y sus equivalentes en AP-42 (lineas 159-180) y AP-43 (lineas 186-197).

`_checks_estandar` **no devuelve nada**: el unico canal de salida es `flag(norm, where, detail)`, que anade una violacion a la lista del envelope. Si el bloque se salta por la excepcion, no anade nada: **no deja marca de que no se ejecuto**.

**Demostracion reproducible** (`audits/fase2/demostrar_control_degradado.py`, log `audits/fase2/logs/L2-control-degradado.json`): con la dependencia sana y un verificador que SI encuentra algo, el control aparece en `by_norm`; con la dependencia rota (`sys.modules[<modulo>] = None`), el control **desaparece** y el envelope **no declara** que no se pudo ejecutar. Medido en las tres familias:

| Control | Dependencia | Con dependencia sana | Con dependencia rota | El envelope avisa |
|---|---|---|---|---|
| AP-40 | `vault_mcp_catalog` | aparece en `by_norm` | no aparece | **no** |
| AP-42 | `vault_smoke` | aparece en `by_norm` | no aparece | **no** |
| AP-43 | `vault_voice` | aparece en `by_norm` | no aparece | **no** |

## 2. Causa raiz

`OBSERVADO`: el envelope de `vault/gobernanza/auditoria_runtime.py` (el dueño) tiene esta forma de retorno:

```python
return {"ok": True, "tool": "vault_runtime_audit", "vault_root": ..., "notes_scanned": ...,
        "total_violations": len(violations), "by_norm": by_norm, "violations": violations}
```

`OBSERVADO`: `ok` esta **hardcodeado a True** (el audit corrio bien) y **no hay ningun campo que declare que controles se ejecutaron**.
`OBSERVADO`: el motor (`vault_norms_engine`) es quien aporta los tres controles del estandar, y lo hace como una **fachada historica** (`auditar_runtime(root, insertar_checks_estandar=_checks_estandar)`): el runtime no importa `vault_norms`, `vault_smoke` ni `vault_voice` (lo dice el docstring del dueno, linea 52-53).

`INFERIDO` (causa): **el contrato de salida no tiene estados de ejecucion**. Un control se comunica con el mundo por sus hallazgos, y no por su estado; por eso "no se pudo mirar" y "no se encontro nada" son la misma senal. La causa no es el `except`: es que el `except` no tiene donde dejar constancia, porque el contrato no lo contempla.

## 3. Analisis de consumidores (que se rompe y como)

| Consumidor | Que lee | Que pasa si el control no se ejecuta |
|---|---|---|
| `scripts/vault_norms.py:588-594` (CLI `--audit --strict`) | `result.get("total_violations")` | **LECTURA DE CODIGO**: el veredicto depende SOLO del numero de violaciones. Si el control que habria encontrado la unica violacion no se ejecuta, `total_violations` baja a 0 y la CLI sale con **exit 0**: una puerta que pasa sobre una auditoria que no miro. No se pudo aislar este exit code en un vault sintetico (el montaje arrastraba violaciones propias y el CLI no emitio envelope): queda como lectura, no como medicion. |
| `scripts/vault_norms_coherence.py:652` (puerta de coherencia) | `antes.get("by_norm", {})` frente a `despues.get("by_norm", {})` | Compara el antes y el despues de un sanador. Si un control no se ejecuta en ninguno de los dos pases, su norma falta en ambos: el gate ve "sin cambios" y no puede distinguir "arreglado" de "nunca mirado". |
| `scripts/vault_arch.py:347` | puerto publicado `auditar_normas: vault_norms:vault_norms_audit` | La superficie que otros contextos usan para auditar inherits el defecto: quien la llama recibe el mismo envelope sin estados. |
| `tests/test_vault_norms_audit.py`, `tests/test_norms_coherence.py`, `tests/test_smoke.py`, `tests/test_voice.py` | envelopes y conteos | Los tests actuales comprueban hallazgos; ninguno comprueba que un control se haya ejecutado. |

`PENDIENTE`: el alcance exacto de los consumidores que **deciden** con `total_violations` (la puerta de CI `vault_norms.py --audit --root vault-sandbox --strict` lo usa; falta el inventario completo de quien mas lo hace).

## 4. Lo que el registro ya decidio (y que acota la alternativa)

`OBSERVADO`: en `vault_arch.PRESUPUESTO_DE_CRUCES`, los dos cruces que sostienen estos accesos estan declarados **`objetivo: a_eliminar`**, con `fecha_limite: 2027-06-30`:

- `gobernanza → meta_toolkit`: «`vault_norms_engine` importa `vault_smoke` y `vault_mcp_catalog` en diferido para auditar el catalogo. Va al reves: el m...»
- `gobernanza → autoria`: «`vault_norms_engine` -> `vault_voice`: presentacion colgada del motor, se conserva solo en la fachada estandar para eje...»

`INFERIDO`: la intencion del repo **no es formalizar estos cruces como puertos, sino eliminarlos**. Publicar `check_params` o `coverage` como puertos contradiria la ficha vigente.

## 5. Alternativa arquitectonica (tres vias, con su coste)

**Via A — INVERSION (la que pide el registro).** Que el motor **no importe** los verificadores: quien los tiene los ejecuta y le pasa el resultado. El motor recibe, por puerto ya publicado (`auditar_normas`), una lista de controles con su estado. Ventaja: el cruce `gobernanza → meta_toolkit/autoria` desaparece de verdad y con el se pierde la clase de defecto (un motor no puede callar lo que no ve, porque no lo ve). Coste: hay que mover la ejecucion de los tres controles a sus duenos y dar a la fachada una forma de recogerlos. Es la via que exige trabajo y la que el registro ya pidio.

**Via B — INVERSION PARCIAL: que el dueno pase el estado.** Aunque el motor no importe los verificadores, necesita saber si los controles corrieron: el estado lo declara quien los ejecuta. El envelope gana una seccion `checks` con el estado por control. Es el contrato del punto 6 y es compatible con la via A (de hecho la via A la necesita).

**Via C — FORMALIZAR COMO PUERTOS (contradice la ficha vigente).** Publicar `check_params`, `load_baseline`/`SIN_SMOKE`/`invocation` y `coverage` como puertos de Meta-toolkit y Autoria, y que el motor los pida por ahi. Ventaja: el minimo trabajo. Coste: **formaliza justo lo que el registro declara eliminable antes de 2027-06-30**, y deja el defecto vivo (el puerto se puede degradar igual). `PENDIENTE` de decision: solo si el propietario decide que el plazo del registro se mueve.

**Recomendacion: Via A + Via B** (eliminar el cruce y declarar el estado), que es lo que la ficha dice y lo que cierra el defecto en su raiz.

## 6. Propuesta de contrato (la que haria falta para que un control pueda decir que no corrio)

En el envelope de la auditoria, anadir una seccion que hoy no existe:

```yaml
checks:
  - control: "AP-40"
    estado: "ejecutado"      # ejecutado | degradado | fallido | no_ejecutado
    detalle: null            # por que, cuando no esta ejecutado
    hallazgos: 1
```

Y semantica explicita de `ok`: hoy `ok: True` significa "el audit corrio" (asi lo dice el codigo de la CLI). La propuesta es **no cambiar `ok`** (compatibilidad: hay lectores que lo interpretan) y anadir un campo hermano, por ejemplo `completo: false` cuando algun control quedo sin ejecutar, de modo que quien use el envelope como puerta pueda distinguir "no hay hallazgos" de "no se pudo mirar".

Regla de la propuesta, en una frase: **ningun control puede_reportar cero hallazgos sin declarar su estado de ejecucion**.

## 7. Pruebas propuestas (NO implementadas: son el diseno que se llevaria al dictamen)

| Caso | Que se mide | Como se hace |
|---|---|---|
| **Positiva** | El control sano aparece con su hallazgo y con estado `ejecutado` | Inyectar un verificador que devuelve un problema y comprobar `by_norm` + `checks[AP-40].estado == "ejecutado"` |
| **Negativa (contrato incompleto)** | Un envelope sin `checks` NO puede pasar por conforme | El verificador de la puerta (o el consumidor) tiene que rechazar un envelope sin estados: `evaluar()`-style, como el de la paridad (H-L3-02) |
| **Dependencia fallida** | Con la dependencia rota: el control se declara `no_ejecutado`/`degradado` con motivo, y la auditoria NO se presenta como limpia | Inyectar `ImportError`/`OSError`/`ValueError` en el `import` (mismo mecanismo que usa la demostracion) y comprobar que el envelope lo dice y que `completo` es `false` |
| **Regresion de consumidores** | La CLI y la puerta de coherencia siguen leyendo las claves de siempre | Suite existente (`test_vault_norms_audit.py`, `test_norms_coherence.py`) mas un caso nuevo: la CLI con un control degradado tiene que salir con codigo distinto de cero (hoy sale 0) |
| **Equivalencia** | Un control sano produce EXACTAMENTE el envelope de antes (mismos campos, mismos conteos) mas `checks` | Comparar el envelope antes/despues del cambio, campo a campo |

## 8. Lo que NO se ha hecho y por que

- **No se ha implementado ninguna correccion**: la autorizacion es de investigacion, y el dictamen de QA es el que decide.
- **No se ha medido el exit code de la CLI** en un vault sintetico: el montaje arrastraba violaciones propias y el CLI no emitio envelope. La afirmacion sobre la CLI queda como **LECTURA DE CODIGO** (lineas 584-594), no como medicion, y asi se declara.
- **No se ha inventariado el consumo completo** de `total_violations` (quien decide con el) — es `PENDIENTE` y es trabajo de L4 o de un lote de cierre de QG-02.

## 9. Evidencia

- `audits/fase2/logs/L2-control-degradado.json` — la demostracion (seis mediciones: tres controles por dos estados).
- `audits/fase2/demostrar_control_degradado.py` — el instrumento, reejecutable.
- `audits/fase2/inventario-deuda.yaml` — TD-0003 (P1, vigente) con la causa, la evidencia y el alcance.
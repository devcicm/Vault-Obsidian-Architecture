# Trazabilidad de los Quality Gates (QG-00 … QG-07)

**Generado por:** `audits/architecture/generar_informe.py`

Cada puerta se documenta con su contrato y su subcheck ejecutable.
La distinción que se conserva es la que importa:

```text
RESULTADO DEL VERIFICADOR  ≠  RESULTADO DEL SUBCHECK
                          ≠  RESULTADO DEL QUALITY GATE
                          ≠  APROBACIÓN DE QA
                          ≠  AUTORIZACIÓN DEL PROPIETARIO
```

Un subcheck puede estar ejecutado y su puerta seguir bloqueada por un
prerrequisito: es exactamente lo que ocurre con QG-03…QG-06.

## QG-00 — Identidad, aislamiento y trazabilidad

- **Propósito:** Demostrar que el codigo verificado es el que se declara: rama, SHA, arbol limpio, alcance autorizado, evidencias pertenecientes a ese SHA y ausencia de modificaciones no autorizadas.
- **Propietario:** agente ejecutor
- **Autoridad de aceptación:** QA arquitectonico
- **Alcance:** ['toda la rama de trabajo', 'las evidencias publicadas']
- **Criterio de PASS:** ['los cinco checks anteriores sin desviacion']
- **Criterio de FAIL:** ['arbol sucio sin justificar, evidencias de otro SHA, o una fuga de saneamiento']
- **Política de bloqueo:** bloquea cualquier otro QG
- **Excepciones permitidas:** no permitida: la identidad no se exime
- **Estado en el candidato:** **n/d**

| Subcheck | Verificador | Tipo | Comando / derivación |
|---|---|---|---|
| `identidad_git` | identidad_git | interno | función interna del colector |
| `arbol_limpio` | arbol_limpio | interno | función interna del colector |
| `saneamiento` | saneamiento | comando | `` |
| `reconciliador_archify` | reconciliador_archify | comando | `` |

## QG-01 — Arquitectura, puertos y contratos

- **Propósito:** Fronteras, dependencias y propiedad, con los cinco cruces D-H gestionados como deuda explicita y con el snapshot de Archify reconciliado.
- **Propietario:** meta_toolkit - vault_arch
- **Autoridad de aceptación:** QA arquitectonico
- **Alcance:** ['los diez contextos', 'la baseline de cruces', 'el snapshot de Archify']
- **Criterio de PASS:** ['exit 0 y los tres invariantes']
- **Criterio de FAIL:** ['cualquier cruce nuevo, baseline ampliada, o un invariante roto']
- **Política de bloqueo:** bloquea QG-03 y QG-07
- **Excepciones permitidas:** solo con decision del propietario y fecha de vencimiento (nunca para seguridad)
- **Estado en el candidato:** **n/d**

| Subcheck | Verificador | Tipo | Comando / derivación |
|---|---|---|---|
| `vault_arch` | vault_arch | comando | `` |
| `reconciliador_archify` | reconciliador_archify | comando | `` |

## QG-02 — Gobernanza y normas

- **Propósito:** Que los controles realmente se ejecuten y detecten lo que prometen, con el estado del sandbox documentado y reproducible.
- **Propietario:** gobernanza - vault_norms
- **Autoridad de aceptación:** QA arquitectonico
- **Alcance:** ['las 26 puertas', 'el estado de ejecucion de AP-40/AP-42/AP-43']
- **Criterio de PASS:** ['26/26 puertas Y todos los controles obligatorios en estado ejecutado SIN degradados (completo: true)']
- **Criterio de FAIL:** ['una puerta tecnica fallida, o un control degradado, o un control no ejecutado, o la ausencia de estados de ejecucion en el envelope (BLOCKED con CONTROL_OBLIGATORIO_NO_VERIFICADO)']
- **Política de bloqueo:** bloquea QG-07
- **Excepciones permitidas:** no permitida
- **Estado en el candidato:** **n/d**

| Subcheck | Verificador | Tipo | Comando / derivación |
|---|---|---|---|
| `puertas_26` | vault_gate | comando | `` |
| `auditoria_completa` | vault_norms_audit | comando | `` |
| `sin_violaciones` | sin_violaciones | derivado | derivado de `auditoria_completa` |

## QG-03 — Integridad funcional y regresiones

- **Propósito:** Comportamiento observable del runtime: suite integral, idempotencia, recuperacion, escrituras atomicas, preservacion de datos y pruebas negativas.
- **Propietario:** agente ejecutor
- **Autoridad de aceptación:** QA arquitectonico
- **Alcance:** ['la suite pytest', 'los gates de producto', 'el recorrido MVP']
- **Criterio de PASS:** ['0 failed; los skipped con causa documentada']
- **Criterio de FAIL:** ['cualquier failed, o una perdida de datos en el recorrido']
- **Política de bloqueo:** bloquea QG-07
- **Excepciones permitidas:** no permitida
- **Estado en el candidato:** **n/d**

| Subcheck | Verificador | Tipo | Comando / derivación |
|---|---|---|---|
| `suite_junit` | pytest_junit | externo | evidencia externa (suite/E2E) |
| `recorrido_e2e` | recorrido_e2e | externo | evidencia externa (suite/E2E) |

## QG-04 — Seguridad

- **Propósito:** Impedir riesgos no aceptados en el producto distribuible: secretos, contencion de rutas, superficie de entrada, dependencias y operaciones destructivas.
- **Propietario:** agente ejecutor
- **Autoridad de aceptación:** QA arquitectonico + propietario
- **Alcance:** ['secretos', 'contencion', 'superficie MCP y CLI', 'dependencias', 'operaciones destructivas']
- **Criterio de PASS:** ['sin vulnerabilidad confirmada y explotable; los controles criticos ejecutados']
- **Criterio de FAIL:** ['una fuga de secretos, un escape de contencion, o un control critico no ejecutado']
- **Política de bloqueo:** bloquea QG-07
- **Excepciones permitidas:** solo con propietario, causa, mitigacion y vencimiento; nunca para integridad de datos
- **Estado en el candidato:** **n/d**

| Subcheck | Verificador | Tipo | Comando / derivación |
|---|---|---|---|
| `saneamiento` | saneamiento | comando | `` |
| `pip_audit` | pip_audit | comando | `` |
| `contencion` | contencion | comando | `` |
| `operaciones_destructivas` | operaciones_destructivas | comando | `` |

## QG-05 — Paridad CLI <-> MCP

- **Propósito:** Que los dos adaptadores cumplan el mismo contrato de negocio: misma operacion, mismos argumentos, mismo efecto y mismo significado de error, medido sobre resultados normalizados y sobre los EFECTOS reales del runtime.
- **Propietario:** agente ejecutor
- **Autoridad de aceptación:** QA arquitectonico
- **Alcance:** ['las operaciones con identidad propia', 'el verificador AP-40', 'los efectos sobre el runtime']
- **Criterio de PASS:** ['evaluar() conforme y AP-40 exit 0']
- **Criterio de FAIL:** ['cualquier problema del verificador']
- **Política de bloqueo:** bloquea QG-07
- **Excepciones permitidas:** solo con la divergencia documentada y aceptada por QA
- **Estado en el candidato:** **n/d**

| Subcheck | Verificador | Tipo | Comando / derivación |
|---|---|---|---|
| `paridad_cli_mcp` | paridad_cli_mcp | comando | `` |
| `ap40_contrato` | ap40_contrato | comando | `` |

## QG-06 — Instalacion y distribucion

- **Propósito:** El producto desde la perspectiva de un tercero: construir, instalar en venv nuevo fuera del checkout, runtime externo, entry points, MCP empaquetado, sin rutas al checkout y sin artefactos ajenos.
- **Propietario:** agente ejecutor
- **Autoridad de aceptación:** QA arquitectonico
- **Alcance:** ['la wheel', 'el venv del consumidor', 'el runtime externo', 'el contenido del artefacto']
- **Criterio de PASS:** ['el gate clean_install en PASS y el contenido del artefacto conforme']
- **Criterio de FAIL:** ['instalacion rota, dependencia ausente, acoplamiento al checkout, o artefacto ajeno dentro']
- **Política de bloqueo:** bloquea QG-07
- **Excepciones permitidas:** no permitida
- **Estado en el candidato:** **n/d**

| Subcheck | Verificador | Tipo | Comando / derivación |
|---|---|---|---|
| `construccion` | construccion | comando | `` |
| `wheel_contenido` | wheel_contenido | interno | función interna del colector |
| `instalacion_limpia` | recorrido_e2e | externo | evidencia externa (suite/E2E) |

## QG-07 — Aprobacion del producto

- **Propósito:** Decidir si una version puede entregarse a terceros. Es una DECISION, no una suma de pruebas.
- **Propietario:** propietario del producto
- **Autoridad de aceptación:** QA arquitectonico (verifica) + propietario (autoriza)
- **Alcance:** ['el SHA del release candidate']
- **Criterio de PASS:** ['todas las condiciones anteriores']
- **Criterio de FAIL:** ['CI sin conclusion, un P0/P1 sin mitigacion, o una evidencia faltante']
- **Política de bloqueo:** es la ultima puerta: su fallo impide el release
- **Excepciones permitidas:** una condicion pendiente (como CI) deja la puerta BLOCKED, nunca PASS
- **Estado en el candidato:** **n/d**

| Subcheck | Verificador | Tipo | Comando / derivación |
|---|---|---|---|


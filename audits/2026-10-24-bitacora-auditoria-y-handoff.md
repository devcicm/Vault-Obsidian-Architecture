# Bitácora de auditoría y transferencia entre agentes — 2026-10-24

> **Estado:** trabajo en curso. Documento de coordinación, no certificación de calidad ni autorización de merge. Actualizar este archivo al concluir cada intervención con evidencia, commit y resultado de pruebas.

## 1. Alcance, aislamiento y reglas de colaboración

- **Repositorio:** `devcicm/Vault-Obsidian-Architecture`.
- **Rama de trabajo:** `audit/archify-governance-20261024`.
- **Objetivo:** auditar arquitectura, puertos, contratos y gobernanza; corregir defectos verificados sin encubrir deuda arquitectónica.
- **Otro agente:** trabaja independientemente sobre problemas de gobernanza; su rama y commits no están verificados aquí.
- **Integración:** no fusionar ni publicar a `main` sin comparación de diffs, pruebas y decisión explícita. Si ambos agentes modifican la misma lógica, reconciliar semánticamente; no elegir cambios por fecha.

## 2. Registro de avances verificables

| Paso | Estado | Evidencia | Validación pendiente |
| --- | --- | --- | --- |
| 1. Rama aislada | Completo | `audit/archify-governance-20261024` | Comparar con el trabajo del otro agente antes de integrar |
| 2. Estabilidad de generación de Gobierno | Cambio aplicado | `scripts/vault_servicio.py` commit `477e412470a6f34e7cd235a49321d3d4e1572326`; `docs/GOBIERNO.md` commit `d7b1b4e38b04b00e361361fc27e6a766b28767c0` | Ejecutar regeneración y check, verificar diff limpio y suite |
| 3. Inspección del paquete Archify | Inspección preliminar | ZIP entregado en conversación: tres diagramas de contextos, cruces y onboarding; HTML, JSON, capturas y reportes | Trazar los datos extraídos a módulos e imports del checkout actual |
| 4. Dependencia Kernel → Autoría | Hallazgo documentado | `audits/2026-10-24-kernel-autoria.md`, commit `4091f49d4270b558221fdfa59850aadf62175df1` | Evaluar interfaz, consumidores, regresión y decisión de refactor |
| 5. Puertos y contratos | Pendiente | Ocho accesos fuera de puerto **declarados en el paquete Archify**, no ocho defectos ya comprobados en código actual | Verificar uno a uno, corregir y probar |
| 6. Validación integral | Pendiente | Ninguna ejecución de suite confirmada | Gates, pruebas de regresión y revisión de artefactos derivados |

## 3. Evidencia de los cambios ya aplicados

### G-01 — Fecha variable en documento derivado

**Antes:** el generador añadía la fecha de ejecución a `docs/GOBIERNO.md`, creando diferencias en regeneraciones realizadas en distintos días.

**Después:** `scripts/vault_servicio.py` emite `_Derivado de los registros canónicos. ` sin `date.today()`. El encabezado derivado en `docs/GOBIERNO.md` fue sincronizado. Ambos archivos se recuperaron nuevamente de la rama y se comprobó el encabezado nuevo.

**Límite:** aún no se ha ejecutado `--check` ni la batería de tests. Esta modificación puede solaparse con la corrección del otro agente.

### A-01 — Kernel → Autoría

- `scripts/vault_arch.py` registra explícitamente `_cruce("kernel", "autoria", "permanente", "kernel", ...)`.
- `scripts/vault_errors.py` importa `from vault.autoria.voz import speak as _speak_estable`.
- `vault/autoria/voz.py` implementa el servicio, con imports diferidos hacia normas, vocabulario y raíz.
- **Interpretación:** cruce autorizado por presupuesto; no puede declararse violación sin estudiar la semántica del puerto. Existe acoplamiento directo con el módulo concreto, que merece revisión.
- **Estado:** solo auditoría documentada; no se cambió el comportamiento.

## 4. Paquete Archify recibido

Archivo de entrada: `mapa-contextos.visual-check.2048x1320.light.zip` (adjunto a la conversación; **no** incorporado al repositorio).

Contenido inspeccionado: `mapa-contextos.html`, `mapa-cruces.html`, `mapa-onboarding.html`, `candidata-contextos.json`, `candidata-cruces.json`, `candidata-onboarding.json`, capturas claro/oscuro y reportes de comprobación.

Datos **reportados por Archify**: 37 cruces y 8 accesos fuera de puerto. Son métricas del paquete, no un recálculo sobre la rama actual. Los focos identificados en la revisión preliminar son:

| Dirección | Cantidad reportada | Área |
| --- | ---: | --- |
| Autoría → Índices | 2 | Etiquetas |
| Ciclo de vida → Índices | 1 | Indexación |
| Gobernanza → Meta-toolkit | 4 | Cobertura, catálogo y smoke |
| Gobernanza → Autoría | 1 | Voz |
| **Total** | **8** | Requiere rastreo por símbolo |

Funciones citadas en el análisis preliminar: `check_params`, `notas_indexables`, `apply_vocabulary`, `record_new_tags`. La atribución exacta de cada función a cada cruce debe contrastarse con el JSON y con el código; **no se presenta como comprobada**.

**Precaución temporal:** contextos y cruces citan la revisión `f5f6921`, onboarding `6e460b8`. No asumir que representan el mismo estado de código.

## 5. Trabajo abierto y criterios de cierre

1. Recuperar la lista de los ocho cruces desde `candidata-cruces.json` / `extraccion-registro.json`; anotar archivo, línea, símbolo y propietario.
2. Para cada acceso, decidir entre puerto explícito, inversión de dependencia, traslado de responsabilidad o corrección de clasificación. Registrar la justificación y el impacto.
3. Definir o revisar contratos: parámetros de entrada, tipos y esquema de salida, errores, efectos secundarios, idempotencia y compatibilidad.
4. Implementar cambios mínimos por commit y agregar pruebas de contrato y regresión, incluidos fallos del servicio de voz.
5. Ejecutar los controles del repositorio en checkout completo; capturar comandos, resultados, versión de Python y SHA evaluado.
6. Regenerar documentos **solo desde fuentes canónicas**. No editar derivados manualmente ni ampliar baselines para ocultar cruces.
7. Comparar con el otro agente: cambios coincidentes en `vault_servicio.py` y gobernanza, conflictos de diseño y pruebas; resolver antes de cualquier PR/merge.

## 6. Formato obligatorio para siguientes actualizaciones

| Fecha | Paso | Cambio | Archivo(s) | Commit | Pruebas (comando + resultado) | Riesgos / siguiente acción |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-10-24 | 1–4 | Estado inicial de transferencia | Ver secciones 2–4 | `477e412`, `d7b1b4`, `4091f49` | **No ejecutadas** | Analizar puertos y contratos; validar suite |

**Regla:** no marcar «completado» sin distinguir implementación, comprobación estática y pruebas ejecutadas. El tiempo transcurrido no constituye evidencia de progreso.

## 7. Requisito diferido: Quality Gates de producto

**Decisión del propietario (2026-10-24):** completar primero la auditoría y correcciones de puertos, contratos y dependencias; evaluar al cierre la incorporación de puertas de calidad inspiradas en inspección industrial. No implementar gates nuevos durante la refactorización inicial.

**Investigación pendiente:** inventariar los controles existentes de gobernanza, sanidad, arquitectura, contratos, integridad y regresión; identificar responsables, entradas, salidas, criterios de aceptación, evidencia reproducible y política de bloqueo. Evitar controles duplicados y métricas que puedan aprobar sin verificar el comportamiento.

**Criterio de entrada a esta fase:** cambios arquitectónicos justificados, pruebas de regresión ejecutadas y discrepancias documentadas. **Estado:** diferido, no implementado.

## 8. Investigación de primera frontera — Autoría → Índices (2026-10-24)

**Fuente:** `candidata-cruces.json` del ZIP Archify, revisión declarada `f5f6921`. Se contrastaron símbolos con la rama aislada mediante lectura de GitHub. **No se ha corregido aún el acceso ni ejecutado pruebas.**

| Consumidor | Línea examinada | Proveedor | Contrato observado | Riesgo |
| --- | --- | --- | --- | --- |
| `scripts/vault_write.py` | 43, 1046 | `vault_tags.apply_vocabulary(tags)` | Devuelve `(tags_resueltos, terminos_nuevos)`; operación sin escritura | Acoplamiento directo entre contextos |
| `scripts/vault_write.py` | 1394 | `vault_tags.record_new_tags(new_terms)` | Devuelve número de registros; captura `OSError` y registra `-1` | Side effect append-only, posterior a escritura confirmada |

**Evidencia del proveedor:** `scripts/vault_tags.py` líneas 272–304 y 307–333. `record_new_tags` usa bloqueo y escritura atómica del ledger; `apply_vocabulary` resuelve vocabulario sin mutar archivos. **Invariante crítico:** nunca registrar tags antes de confirmar escritura; fallo de ledger no debe invalidar nota persistida.

**Decisión provisional:** no sustituir imports por una fachada cosmética ni mover funciones sin identificar el puerto canónico, propietarios y consumidores. Próximo paso: contrastar `CONTEXTS` y `PRESUPUESTO_DE_CRUCES` con la ubicación real de la interfaz; crear pruebas de contrato y regresión de escritura exitosa/fallida antes de refactorizar.

**Validación:** lectura estática confirmada; ejecución de suite, pruebas y nuevo contrato: pendientes.

## 9. Pruebas de contrato AP-39 incorporadas (2026-10-24)

- Commit `0748b1ce9340272743fa5ff7f50f23696d9230fe`: `tests/test_ap39_contrato.py` (tres casos: resolución sin efectos secundarios, registro vacío sin escritura, deduplicación del ledger).
- Ejecución prevista: `python -m unittest discover -s tests -p 'test_ap39_contrato.py'`.
- **Estado:** archivo confirmado en GitHub; pruebas **no ejecutadas**. El sandbox no pudo clonar GitHub por error DNS (`Could not resolve host: github.com`). No se afirma aprobación ni corrección del acceso AP-49. Mantener el refactor bloqueado hasta validar las pruebas y revisar propiedad/puerto canónico.

## 10. Protocolo de auditoría asesorada y justificación causal (2026-10-24)

**Decisión del propietario:** mientras no haya ejecución local del repositorio, continuar mediante inspección de código y razonamiento causal trazable, sin equiparar inferencia a prueba ejecutada. Toda recomendación debe explicar **qué**, **por qué**, **cómo** y **qué evidencia la respalda**.

**Plantilla obligatoria para cada hallazgo/cambio:**
1. **Observación:** archivo, símbolo, línea/revisión y evidencia reproducible; distinguir hecho observado de hipótesis.
2. **Causa y riesgo:** mecanismo que produce el defecto, condiciones de activación e impacto; no denominar vulnerabilidad a una sospecha sin demostrar vector y efecto.
3. **Contrato previo e invariantes:** precondiciones, efectos, errores, orden de operaciones, compatibilidad y propietarios.
4. **Intervención propuesta o aplicada:** diff/commit y por qué se elige frente a alternativas; riesgos de regresión.
5. **Modelo causal:** si A (precondición) y B (implementación/garantía) entonces se espera C (resultado), indicando explícitamente supuestos y contraejemplos.
6. **Evidencia y confianza:** inspección estática / simulación conceptual / test unitario ejecutado / integración ejecutada; nunca marcar una inferencia como PASÓ.
7. **Verificación pendiente:** comandos, resultados esperados, criterios de aceptación y responsable de ejecutarlos.

**Aplicación a AP-39 (observación confirmada):** `vault_write.py` llama `apply_vocabulary` antes de persistir y `record_new_tags` después. Si la primera operación no escribe y la segunda solo se ejecuta tras confirmar persistencia, entonces un fallo previo de escritura no debería dejar etiquetas nuevas en el ledger **por esta ruta**. Este resultado depende de que no existan efectos secundarios ocultos ni otros escritores; requiere pruebas de fallo de escritura y de ledger. Un error del ledger se captura como `OSError` en la ruta examinada, pero no se ha demostrado la cobertura de otras excepciones. **Conclusión:** inferencia causal limitada, no validación funcional.

**Estado:** protocolo registrado, inspección estática; pruebas de ejecución bloqueadas por conectividad directa del sandbox. La fase de Quality Gates continúa diferida hasta terminar la auditoría de puertos y contratos.

## 11. Inventario A–H de accesos fuera de puerto (fuente Archify contrastada)

**Extracción exitosa:** se leyó el adjunto `mapa-contextos.visual-check.2048x1320.light.zip`, archivo `extraccion-registro.json`, clave `_off_port`. Se obtuvieron los ocho símbolos exactos, no solo los agregados. El registro Archify corresponde a `f5f6921`; no es una medición actual. Lectura del repositorio de la rama aislada confirma usos en `vault_write.py` y `vault_norms_engine.py`. **No hay pruebas ejecutadas ni corrección de comportamiento.**

| ID | Dependencia reportada por Archify | Evidencia y porqué revisar | Verificación externa propuesta |
|---|---|---|---|
| A | `vault_write → vault_tags.apply_vocabulary` | `vault_write.py:1046`: normaliza tags antes de persistir; la operación no figura entre los puertos publicados de Índices. | Comprobar contrato sin efectos secundarios y normalización estable. |
| B | `vault_write → vault_tags.record_new_tags` | `vault_write.py:1394`: escribe ledger tras persistencia; fuera de puerto publicado. | Inyectar error de escritura de nota y de ledger; verificar orden y que no haya memoria falsa. |
| C | `vault_sanacion → vault_reindex.notas_indexables` | Archify registra la llamada; `vault_sanacion.py` en la revisión actual es breve y no contiene ese símbolo: **posible desactualización o ruta indirecta**. | Rastrear import real y contrastar SHA antes de atribuir defecto vigente. |
| D | `vault_norms_engine → vault_mcp_catalog.check_params` | `vault_norms_engine.py:142` importa catálogo dinámicamente; el puerto publicado en Meta-toolkit es `check_contracts`, no `check_params`. | Inspeccionar llamada, semántica de contrato y efecto del fallo del catálogo. |
| E | `vault_norms_engine → vault_smoke.SIN_SMOKE` | `vault_norms_engine.py:160` importa smoke; símbolo no figura en puertos de Meta-toolkit. | Comprobar propiedad y manejo de ausencia de baseline. |
| F | `vault_norms_engine → vault_smoke.invocation` | Misma dependencia; verificar si se invoca una implementación interna o interfaz estable. | Probar invocación y fallo controlado del smoke. |
| G | `vault_norms_engine → vault_smoke.load_baseline` | Misma dependencia; potencial acoplamiento a formato interno de baseline. | Verificar lectura, esquema y comportamiento ante baseline corrupta. |
| H | `vault_norms_engine → vault_voice.coverage` | `vault_norms_engine.py:187` importa voz; puerto `coverage` no está publicado en Autoría. | Verificar si cobertura es función de consulta pura y qué ocurre si no existe. |

**Razonamiento causal:** A/B: normalización pura + registro posterior a persistencia confirmada ⇒ el ledger no refleja notas fallidas **por esa ruta**, sujeto a excepciones no observadas. D–H: un import hacia una función no publicada ⇒ dependencia de interfaz no garantizada; no implica automáticamente un defecto funcional. C: divergencia entre snapshot y fuente actual ⇒ no se puede tratar el cruce como vigente sin reconstruir su trazabilidad.

**Prioridad:** confirmar C y semántica D–H; proponer puertos explícitos donde corresponda, sin ampliar baseline para ocultar cruces. **Evidencia:** extracción del ZIP + lectura estática de GitHub; **tests:** a ejecutar fuera de este sandbox.

## 12. Revalidación secuencial de hallazgos (2026-10-24)

**C — confirmado en propietario real, corrige interpretación previa:** `scripts/vault_sanacion.py` es alias de compatibilidad (ADR-0002), no implementación. En `vault/ciclo_de_vida/sanacion.py:190–193` se importa `vault_reindex` y se llama `notas_indexables(root=root)`. Por tanto el cruce no desapareció; Archify atribuyó el consumidor al nombre público, mientras el sitio efectivo reside en el dueño migrado. En `scripts/vault_arch.py:420` se publica `index_coherence`, pero `notas_indexables` no figura en la sección de puertos de Índices inspeccionada. **Hipótesis:** falta puerto público para enumeración; verificar si hay interfaz equivalente antes de publicarlo.

**D–H — semántica de fallos observada:** `scripts/vault_norms_engine.py:136–197` ejecuta tres comprobaciones del estándar. En AP-40 usa `check_params`; en AP-42 usa `load_baseline`, `TOOLS_CATALOG`, `SIN_SMOKE`, `invocation`; en AP-43 usa `coverage`. Cada bloque captura `ImportError`, `OSError` y `ValueError` y ejecuta `pass`. **Riesgo causal:** si el chequeo auxiliar falla con esas excepciones, el audit puede omitir la comprobación sin registrar degradación; la ausencia de hallazgo no implica ejecución del control. No se declara vulnerabilidad demostrada. Contrato propuesto: estado explícito `executed / degraded / failed` por control y política de severidad definida, preservando compatibilidad del envelope. No implementar antes de inspeccionar consumidores y pruebas.

**Orden de continuación:** (1) inventario de contratos A/B; (2) C y ubicación de enumeración; (3) D–H y manejo de fallos; (4) propuestas de cambios y pruebas externas; (5) Quality Gates al final. **Evidencia:** lectura directa GitHub en rama aislada. **Tests:** no ejecutados.

## 13. Decisión de diseño A/B/C — no publicar un puerto incorrecto (2026-10-24)

**A/B:** `scripts/vault_arch.py:405–420` ya publica `registrar_tags: vault_tags:registrar_tags_de_nota`. En `scripts/vault_tags.py:336–372`, ese puerto combina `apply_vocabulary` y `record_new_tags` **después** de escribir y devuelve `{tags, vocabulary_introduced, recorded}`. En cambio, `vault_write.py:1046` necesita etiquetas canonizadas **antes** de persistir para construir el contenido, y en `:1394` registra novedades **después**. **Conclusión:** reemplazar ambas llamadas por `registrar_tags_de_nota` antes de persistir introduciría un efecto secundario prematuro; reemplazarlas solo después no garantiza que el frontmatter use los tags canónicos. La frontera correcta exige separar formalmente una operación de consulta pura (`resolver_vocabulario`) de una operación de registro pospersistencia (`registrar_novedades`), o justificar la exposición de las funciones existentes como puertos sin cambiar semántica. La segunda opción es cambio mínimo de contrato, **pendiente de comprobar si los controles de arquitectura reconocen esos nombres y de evaluar compatibilidad**. No se implementa refactor por mera eliminación de aviso.

**C:** `vault/ciclo_de_vida/sanacion.py:160–167` usa `index_coherence(root=root)`, que **sí** es puerto publicado en `vault_arch.py:420`; `:188–203` usa `notas_indexables(root=root)`, que **no** aparece entre puertos publicados. Esta diferencia prueba que el problema es de superficie del contrato de enumeración, no de cualquier import a `vault_reindex`. **Opciones:** publicar enumeración indexable con semántica de raíz, filtros y orden estable; o consumir un puerto ya existente de enumeración si es equivalente. Verificar alcance de notas excluidas y manejo de errores antes de elegir.

**Resultado:** análisis estático completado, propuesta de contrato documentada. **Código productivo:** sin cambios. **Pruebas externas requeridas:** (1) resolución pura, (2) escritura fallida sin ledger, (3) escritura exitosa con registro único, (4) error de ledger sin invalidar nota, (5) equivalencia de conjunto de notas indexables para raíz alternativa. **Quality Gates:** diferidos.

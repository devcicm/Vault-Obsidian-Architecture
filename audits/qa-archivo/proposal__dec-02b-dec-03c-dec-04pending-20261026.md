# Archivo: `proposal/dec-02b-dec-03c-dec-04pending-20261026`

- Commit(s) sobre la rama de trabajo:
  - `cc05eab1e1baf36f75a9bd02fd24d14bc08443dc` 2026-10-26 — docs(proposal): registrar preferencias DEC-02 B, DEC-03 C y DEC-04 pendiente sin ratificar
- Base: `e0fc775551217ee0a778ca3dece0da3f0a63ba38`
- Tag de conservación: `archivo/proposal/dec-02b-dec-03c-dec-04pending-20261026`

## Texto añadido a `audits/handoff/DECISIONES-PROPIETARIO.md`



---

# Anexo consultivo — propuestas DEC-02=B, DEC-03=C y DEC-04=PENDING

**Registrado como propuesta del propietario:** 2026-10-26 (fecha local de la consulta).  
**Origen documental:** rama `work/release-cli-mcp-20261025`, SHA `e0fc775551217ee0a778ca3dece0da3f0a63ba38`.  
**Tipo de registro:** `OWNER_PREFERENCE_PROPOSED`. **No constituye ratificación, waiver, autorización de implementación ni decisión de release.**  
**Estado de las casillas oficiales DEC-02/03/04:** **SIN FIRMAR**, preservadas arriba.  
**Alcance de este anexo:** registra opciones preferidas y sus condiciones de elegibilidad para un acto formal posterior. No sustituye las fichas, la Constitución DRAFT, las pruebas, la política QG ni las evidencias.

| Ficha | Opción propuesta por el propietario | Estado jurídico/técnico en este registro | Gate y efecto |
|---|---|---|---|
| **DEC-02** | **B** — migración compatible por etapas para eliminar los cruces `gobernanza → meta_toolkit` y `gobernanza → autoria` | **PREFERENCIA PROPUESTA, CONDICIONADA**. No se autorizó ejecutar el plan ni aceptar DIV-01..10. | QG-00/QG-01 siguen `BLOCKED`; elegir B no elimina dependencias ni reconcilia por sí solo el snapshot. |
| **DEC-03** | **C** — certificación compuesta: runtime limpio y sandbox canónico medidos por separado; detectar efectos externos nuevos y registrar el residuo histórico | **PREFERENCIA PROPUESTA, CONDICIONADA**. No se autorizó modificar `catalogo-qg.yaml`, `politica_qg.py` ni aceptar AP-36. | QG-02 sigue `BLOCKED`; runtime limpio `PASS` no sustituye al audit del sandbox. |
| **DEC-04** | **pending** — no se elige todavía conservar, trasladar, archivar o purgar `vault-backups` | **SIN DECISIÓN**. No hay permiso para tocar datos ni para aceptar riesgos. | AP-36 y el estado de certificación asociado permanecen abiertos; QG-02 no se desbloquea por este registro. |

## Condiciones exactas de DEC-02=B antes de cualquier implementación reservada

1. **Arquitectura real, no cosmética.** El destino es eliminar los dos pares de dependencia indebida sin reintroducirlos mediante subprocess, registro dinámico ni imports opacos. Conservar `objetivo: a_eliminar` y la fecha límite vigente **2027-06-30**; no ampliar baselines, cambiar `ratificado: false`, modificar el snapshot histórico ni aceptar DIV-01..10 mediante waiver implícito.
2. **I1–I5 obligatorios** según `audits/architecture/PLAN-B-MIGRACION-CRUZES.md` §6.1: independencia semántica, operación desde la wheel instalada, retorno observable, efectos laterales declarados y fallo seguro si un verificador no existe. Verificar equivalencia funcional CLI/MCP, estados TD-0003, seguridad, reconciliador y regresión integral.
3. **Enmienda I2 por decidir expresamente.** El puerto de §3 tal cual no funciona en la wheel: `vault_mcp_catalog`, `vault_smoke` y `vault_voice` son herramientas de mantenimiento no publicadas como superficie instalada. El propietario debe elegir **(I2-a)** publicar entry points compatibles en la wheel, **(I2-b)** restringir explícitamente el puerto a una distribución de mantenimiento sin atribuirle compatibilidad con terceros, o **(I2-c)** explorar registro en proceso con arista declarada y sus límites. No elegir por inferencia; preferir demostrar I2-a si se desea acreditar el producto distribuido.
4. **Enmienda de costo por decidir expresamente.** Medición R14: subprocesos ingenuos **≈149,4 s** frente a audit actual **2,42 s** (~60×), principalmente AP-42 `vault_smoke --check`. Antes de implementar B, seleccionar **(COST-a)** interfaz ligera de baseline publicada por el dueño o **(COST-b)** ejecución diferida con nuevo contrato de estados, o analizar otra arquitectura bajo los mismos criterios; fijar umbral de latencia aceptable y registrar benchmark antes/después. No ejecutar el camino ~60× por defecto ni falsear `ejecutado` cuando solo se pospone.
5. **Orden y rollback.** Concretar interfaces, impacto y plan por commits reversibles; mantener compatibilidad de las superficies públicas y una ventana de deprecación acotada. Acreditar I1–I5, 26 puertas, suite, wheel E2E y matriz CI del SHA resultante. Hasta lograrlo, la expectativa `off_port_total: 5 → 3` y divergencias `10 → 0` es **objetivo**, no resultado.
6. **Autoridad reservada.** Requiere acto expreso del propietario identificando **B, subopción I2, subopción de costo, criterios de aceptación, límites de compatibilidad, fecha y referencia de ratificación**. Después, el ejecutor podrá implementar bajo ese alcance y QA revisará la evidencia sin sustituir al propietario.

## Condiciones exactas de DEC-03=C antes de modificar la política QG-02

1. **Dos sujetos, resultados separados.** Auditar el runtime instalado nuevo y el sandbox canónico del repo con el mismo estándar, guardar run/SHA, salidas y evidencia de cada uno. El primero acredita al consumidor; el segundo acredita ambiente, fixtures y efectos externos. No sustituir uno por el otro.
2. **Detección no degradada.** Un escape AP-36 NUEVO, una violación del runtime o un control AP-40/AP-42/AP-43 omitido o degradado impiden `PASS`. Los 13 defectos de semillas corregidos no son waivers. `NOT_RUN`/`BLOCKED` nunca equivalen a `PASS`.
3. **Residuo histórico separado, no perdonado.** `vault-backups` externo conserva su evidencia y severidad AP-36; se distingue de las emisiones nuevas sin borrar el hallazgo ni declarar que la auditoría original pasó. El dossier advierte que, **mientras DEC-04 siga sin resolver, QG-02 continúa BLOCKED** bajo la política actual y la propuesta estricta.
4. **Cambio reservado de contrato.** Preparar, sin aplicar, el diff propuesto de `POLITICA-CERTIFICACION-PRODUCTO.md`, `catalogo-qg.yaml`, `politica_qg.py`, colector y tests. Incluir negativas sobre escape nuevo, archivo histórico sin procedencia y control no ejecutado. La aprobación exige acto formal del propietario sobre el alcance y revisión QA; no alterar el catálogo para forzar verde.

## DEC-04=PENDING: reglas de preservación y decisión futura

- No borrar, mover, renombrar, comprimir, purgar ni modificar el directorio externo `vault-backups` o su manifiesto. No activar procedimientos de mantenimiento que lo alteren.
- La evidencia existente describe **66 archivos y 854.108 bytes** de un snapshot histórico de junio de 2026, con hashes en el expediente. Esa medición es **histórica**: antes de cualquier futuro movimiento hay que revalidar inventario, SHA-256, titularidad y destino mediante acceso solo lectura.
- Opciones futuras (a/b/c/d) siguen disponibles. Si se considera **c** (archivar y después purgar), el acto requiere autorización escrita del dueño de datos, destino explícito, comparación hash del archivo conservado, plan de recuperación y una autorización **separada** para la purga. Este anexo NO concede ninguna de esas autorizaciones.
- Mantener AP-36 documentado y QG-02 bloqueado o conforme a su evaluador vigente, sin transformar el riesgo en exención.

## Prerrequisitos y siguientes pasos permitidos

1. **Permitido ahora, sin acto reservado:** inspección de solo lectura, comparativas AS-IS/TO-BE, diseño de alternativas I2/costo, benchmarks en sandboxes descartables, propuestas de pruebas y borradores de cambios normativos **no aplicados**.
2. **Prohibido por este anexo:** editar `ratificado`, aplicar waivers, refactorizar el puerto con consecuencias reservadas, cambiar la política QG-02, modificar `vault-backups`, fusionar PR, tocar `main`, modificar historia o publicar release.
3. **Decisiones adicionales no inferidas:** DEC-01 (Constitución), DEC-05 (historia pública) y DEC-06 (autorización de distribución) permanecen exactamente como estaban, sin aprobación.
4. **Siguiente intervención del propietario:** elegir los detalles I2 y costo de DEC-02; delimitar y firmar el contrato C de DEC-03; decidir por separado qué hacer con DEC-04 y, posteriormente, el resto de autoridades de release. Registrar fecha/firmante/referencia sobre la ficha formal cuando exista acto inequívoco.

**Estado formal resultante:** `DEC-02=PROPOSED_B_CONDITIONAL`; `DEC-03=PROPOSED_C_CONDITIONAL`; `DEC-04=PENDING`; `OWNER_RATIFICATION=NOT_GIVEN`; `WAIVERS_RATIFIED=0`; `RELEASE_AUTHORIZED=false`. No modifica los estados de QG existentes ni la matriz de release.


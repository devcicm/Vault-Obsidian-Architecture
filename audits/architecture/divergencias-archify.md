# Las diez divergencias Archify ↔ registro vivo — fichas individuales

**SHA:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9` · **Fuente:** `audits/fase2/reconciliar_archify.py --check`

Causa común: la composición de los controles AP-40/42/43 se movió de
`vault_norms_engine` a la fachada `vault_norms` (commit `667a6a5`), y la
ficha de la deuda se actualizó (`59d0465`). El snapshot de Archify
documenta la revisión anterior, así que las diez divergencias comparten
esa causa. **Actualizar el inventario no elimina el adeudado**: la deuda
sigue declarada como `a_eliminar` con plazo y decisión pendiente.

| ID | Clave | Naturaleza | Ratificada |
|---|---|---|---|
| DIV-01 | `ficha divergente: ['gobernanza', 'autoria']` | ficha desactualizada: el adeudado NO cambio | NO |
| DIV-02 | `ficha divergente: ['gobernanza', 'meta_toolkit']` | ficha desactualizada: el adeudado NO cambio | NO |
| DIV-03 | `acceso no conciliado: vault_norms_engine -> vault_mcp_catalog.check_params` | movimiento | NO |
| DIV-04 | `acceso no conciliado: vault_norms_engine -> vault_smoke.SIN_SMOKE` | movimiento | NO |
| DIV-05 | `acceso no conciliado: vault_norms_engine -> vault_smoke.invocation` | movimiento | NO |
| DIV-06 | `acceso no conciliado: vault_norms_engine -> vault_smoke.load_baseline` | movimiento | NO |
| DIV-07 | `acceso no conciliado: vault_norms_engine -> vault_voice.coverage` | movimiento | NO |
| DIV-08 | `dependencia NO CONCILIABLE: vault_norms_engine -> vault_mcp_catalog` | movimiento | NO |
| DIV-09 | `dependencia NO CONCILIABLE: vault_norms_engine -> vault_smoke` | movimiento | NO |
| DIV-10 | `dependencia NO CONCILIABLE: vault_norms_engine -> vault_voice` | movimiento | NO |

## DIV-01

- **Clave del reconciliador:** `ficha divergente: ['gobernanza', 'autoria']`
- **Tipo:** ficha de par de contextos
- **Elemento original (snapshot):** ficha del par en el snapshot de Archify (revision anterior)
- **Elemento vigente (código):** ficha vigente del par en scripts/vault_arch.py
- **SHA snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA código actual:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **Cambio responsable:** 59d0465 (ficha actualizada al mover el cruce) + 667a6a5 (sitio)
- **Naturaleza:** ficha desactualizada: el adeudado NO cambio
- **¿Movimiento legítimo?** no
- **¿Deuda viva?** no
- **¿Regresión?** no
- **Riesgo de actualizar el inventario:** bajo: la ficha describe el mismo adeudado con el sitio vigente
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit · B: migrarlo a un owner con puerto declarado · C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** ratificar el texto de la ficha conservando la clase a_eliminar y su fecha limite, o re-tomar el snapshot
- **Acción que requiere ratificación:** ratificacion del propietario

## DIV-02

- **Clave del reconciliador:** `ficha divergente: ['gobernanza', 'meta_toolkit']`
- **Tipo:** ficha de par de contextos
- **Elemento original (snapshot):** ficha del par en el snapshot de Archify (revision anterior)
- **Elemento vigente (código):** ficha vigente del par en scripts/vault_arch.py
- **SHA snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA código actual:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **Cambio responsable:** 59d0465 (ficha actualizada al mover el cruce) + 667a6a5 (sitio)
- **Naturaleza:** ficha desactualizada: el adeudado NO cambio
- **¿Movimiento legítimo?** no
- **¿Deuda viva?** no
- **¿Regresión?** no
- **Riesgo de actualizar el inventario:** bajo: la ficha describe el mismo adeudado con el sitio vigente
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit · B: migrarlo a un owner con puerto declarado · C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** ratificar el texto de la ficha conservando la clase a_eliminar y su fecha limite, o re-tomar el snapshot
- **Acción que requiere ratificación:** ratificacion del propietario

## DIV-03

- **Clave del reconciliador:** `acceso no conciliado: vault_norms_engine -> vault_mcp_catalog.check_params`
- **Tipo:** acceso a fichero
- **Elemento original (snapshot):** acceso declarado en el snapshot: vault_norms_engine -> vault_mcp_catalog.check_params
- **Elemento vigente (código):** acceso vigente en la fachada de mantenimiento (mismo par de contextos)
- **SHA snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA código actual:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **¿Movimiento legítimo?** sí
- **¿Deuda viva?** no
- **¿Regresión?** no
- **Riesgo de actualizar el inventario:** bajo: el par de contextos sigue cruzando; solo cambio el modulo
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit · B: migrarlo a un owner con puerto declarado · C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot de Archify o ratificar la aceptacion con la ficha correspondiente
- **Acción que requiere ratificación:** ratificacion del propietario

## DIV-04

- **Clave del reconciliador:** `acceso no conciliado: vault_norms_engine -> vault_smoke.SIN_SMOKE`
- **Tipo:** acceso a fichero
- **Elemento original (snapshot):** acceso declarado en el snapshot: vault_norms_engine -> vault_smoke.SIN_SMOKE
- **Elemento vigente (código):** acceso vigente en la fachada de mantenimiento (mismo par de contextos)
- **SHA snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA código actual:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **¿Movimiento legítimo?** sí
- **¿Deuda viva?** no
- **¿Regresión?** no
- **Riesgo de actualizar el inventario:** bajo: el par de contextos sigue cruzando; solo cambio el modulo
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit · B: migrarlo a un owner con puerto declarado · C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot de Archify o ratificar la aceptacion con la ficha correspondiente
- **Acción que requiere ratificación:** ratificacion del propietario

## DIV-05

- **Clave del reconciliador:** `acceso no conciliado: vault_norms_engine -> vault_smoke.invocation`
- **Tipo:** acceso a fichero
- **Elemento original (snapshot):** acceso declarado en el snapshot: vault_norms_engine -> vault_smoke.invocation
- **Elemento vigente (código):** acceso vigente en la fachada de mantenimiento (mismo par de contextos)
- **SHA snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA código actual:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **¿Movimiento legítimo?** sí
- **¿Deuda viva?** no
- **¿Regresión?** no
- **Riesgo de actualizar el inventario:** bajo: el par de contextos sigue cruzando; solo cambio el modulo
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit · B: migrarlo a un owner con puerto declarado · C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot de Archify o ratificar la aceptacion con la ficha correspondiente
- **Acción que requiere ratificación:** ratificacion del propietario

## DIV-06

- **Clave del reconciliador:** `acceso no conciliado: vault_norms_engine -> vault_smoke.load_baseline`
- **Tipo:** acceso a fichero
- **Elemento original (snapshot):** acceso declarado en el snapshot: vault_norms_engine -> vault_smoke.load_baseline
- **Elemento vigente (código):** acceso vigente en la fachada de mantenimiento (mismo par de contextos)
- **SHA snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA código actual:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **¿Movimiento legítimo?** sí
- **¿Deuda viva?** no
- **¿Regresión?** no
- **Riesgo de actualizar el inventario:** bajo: el par de contextos sigue cruzando; solo cambio el modulo
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit · B: migrarlo a un owner con puerto declarado · C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot de Archify o ratificar la aceptacion con la ficha correspondiente
- **Acción que requiere ratificación:** ratificacion del propietario

## DIV-07

- **Clave del reconciliador:** `acceso no conciliado: vault_norms_engine -> vault_voice.coverage`
- **Tipo:** acceso a fichero
- **Elemento original (snapshot):** acceso declarado en el snapshot: vault_norms_engine -> vault_voice.coverage
- **Elemento vigente (código):** acceso vigente en la fachada de mantenimiento (mismo par de contextos)
- **SHA snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA código actual:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **¿Movimiento legítimo?** sí
- **¿Deuda viva?** no
- **¿Regresión?** no
- **Riesgo de actualizar el inventario:** bajo: el par de contextos sigue cruzando; solo cambio el modulo
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit · B: migrarlo a un owner con puerto declarado · C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot de Archify o ratificar la aceptacion con la ficha correspondiente
- **Acción que requiere ratificación:** ratificacion del propietario

## DIV-08

- **Clave del reconciliador:** `dependencia NO CONCILIABLE: vault_norms_engine -> vault_mcp_catalog`
- **Tipo:** dependencia a granularidad de fichero
- **Elemento original (snapshot):** dependencia en el snapshot: vault_norms_engine -> vault_mcp_catalog
- **Elemento vigente (código):** dependencia vigente en el par de contextos (mismo adeudado)
- **SHA snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA código actual:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **¿Movimiento legítimo?** sí
- **¿Deuda viva?** no
- **¿Regresión?** no
- **Riesgo de actualizar el inventario:** medio: la granularidad del snapshot (fichero) no coincide con la del registro (par de contextos); el adorno de la divergencia lo dice
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit · B: migrarlo a un owner con puerto declarado · C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot o ratificar la aceptacion
- **Acción que requiere ratificación:** ratificacion del propietario

## DIV-09

- **Clave del reconciliador:** `dependencia NO CONCILIABLE: vault_norms_engine -> vault_smoke`
- **Tipo:** dependencia a granularidad de fichero
- **Elemento original (snapshot):** dependencia en el snapshot: vault_norms_engine -> vault_smoke
- **Elemento vigente (código):** dependencia vigente en el par de contextos (mismo adeudado)
- **SHA snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA código actual:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **¿Movimiento legítimo?** sí
- **¿Deuda viva?** no
- **¿Regresión?** no
- **Riesgo de actualizar el inventario:** medio: la granularidad del snapshot (fichero) no coincide con la del registro (par de contextos); el adorno de la divergencia lo dice
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit · B: migrarlo a un owner con puerto declarado · C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot o ratificar la aceptacion
- **Acción que requiere ratificación:** ratificacion del propietario

## DIV-10

- **Clave del reconciliador:** `dependencia NO CONCILIABLE: vault_norms_engine -> vault_voice`
- **Tipo:** dependencia a granularidad de fichero
- **Elemento original (snapshot):** dependencia en el snapshot: vault_norms_engine -> vault_voice
- **Elemento vigente (código):** dependencia vigente en el par de contextos (mismo adeudado)
- **SHA snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA código actual:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **¿Movimiento legítimo?** sí
- **¿Deuda viva?** no
- **¿Regresión?** no
- **Riesgo de actualizar el inventario:** medio: la granularidad del snapshot (fichero) no coincide con la del registro (par de contextos); el adorno de la divergencia lo dice
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit · B: migrarlo a un owner con puerto declarado · C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot o ratificar la aceptacion
- **Acción que requiere ratificación:** ratificacion del propietario

## Procedimiento de reconciliación

1. El snapshot **no se sustituye**: es evidencia de otra revisión.
2. `divergencias-aceptadas.yaml` es la lista DECLARADA de aceptaciones;
   sin `ratificado: true` y evidencia, el reconciliador las lista igual.
3. Alternativa preferida: **re-tomar el snapshot** de Archify sobre el
   SHA vigente → cero divergencias sin tocar la deuda.
4. La decisión es del **propietario**; el ejecutor no ratifica.


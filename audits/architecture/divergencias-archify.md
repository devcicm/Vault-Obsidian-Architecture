# Divergencias del reconciliador Archify ↔ registro vivo

**Generado por:** `audits/architecture/generar_informe.py` (fuente: `audits/fase2/reconciliar_archify.py --check`)
**SHA del codigo:** `ab31bf3b095effb81625464d19f2cf80ab72e35c`

Cada divergencia tiene ficha. Una divergencia **no** es un error del
codigo por definición: puede ser un inventario obsoleto, un movimiento
legitimo o una regresion. Aqui se clasifica una por una.

| ID | Clave | Tipo | Naturaleza | Riesgo | Ratificada |
|---|---|---|---|---|---|
| DIV-01 | `ficha divergente: ['gobernanza', 'autoria']` | ficha de par de contextos | ficha desactualizada: el adeudado NO cambio | bajo: la ficha describe el mismo adeudado con el sitio vigen | NO |
| DIV-02 | `ficha divergente: ['gobernanza', 'meta_toolkit']` | ficha de par de contextos | ficha desactualizada: el adeudado NO cambio | bajo: la ficha describe el mismo adeudado con el sitio vigen | NO |
| DIV-03 | `acceso no conciliado: vault_norms_engine -> vault_mcp_catalog.check_params` | acceso a fichero | movimiento legítimo | bajo: el par de contextos sigue cruzando; solo cambio el mod | NO |
| DIV-04 | `acceso no conciliado: vault_norms_engine -> vault_smoke.SIN_SMOKE` | acceso a fichero | movimiento legítimo | bajo: el par de contextos sigue cruzando; solo cambio el mod | NO |
| DIV-05 | `acceso no conciliado: vault_norms_engine -> vault_smoke.invocation` | acceso a fichero | movimiento legítimo | bajo: el par de contextos sigue cruzando; solo cambio el mod | NO |
| DIV-06 | `acceso no conciliado: vault_norms_engine -> vault_smoke.load_baseline` | acceso a fichero | movimiento legítimo | bajo: el par de contextos sigue cruzando; solo cambio el mod | NO |
| DIV-07 | `acceso no conciliado: vault_norms_engine -> vault_voice.coverage` | acceso a fichero | movimiento legítimo | bajo: el par de contextos sigue cruzando; solo cambio el mod | NO |
| DIV-08 | `dependencia NO CONCILIABLE: vault_norms_engine -> vault_mcp_catalog` | dependencia a granularidad de fichero | movimiento legítimo | medio: la granularidad del snapshot (fichero) no coincide co | NO |
| DIV-09 | `dependencia NO CONCILIABLE: vault_norms_engine -> vault_smoke` | dependencia a granularidad de fichero | movimiento legítimo | medio: la granularidad del snapshot (fichero) no coincide co | NO |
| DIV-10 | `dependencia NO CONCILIABLE: vault_norms_engine -> vault_voice` | dependencia a granularidad de fichero | movimiento legítimo | medio: la granularidad del snapshot (fichero) no coincide co | NO |

## Fichas

### DIV-01 — ficha de par de contextos

- **Clave:** `ficha divergente: ['gobernanza', 'autoria']`
- **Elemento original (snapshot):** ficha del par en el snapshot de Archify (revision anterior)
- **Elemento vigente (código):** ficha vigente del par en scripts/vault_arch.py
- **SHA de referencia del snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA del código actual:** `ab31bf3b095effb81625464d19f2cf80ab72e35c`
- **Cambio responsable:** 59d0465 (ficha actualizada al mover el cruce) + 667a6a5 (sitio)
- **Naturaleza:** ficha desactualizada: el adeudado NO cambio
- **Riesgo de actualizar el inventario:** bajo: la ficha describe el mismo adeudado con el sitio vigente
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit; B: migrarlo a un owner con puerto declarado; C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** ratificar el texto de la ficha conservando la clase a_eliminar y su fecha limite, o re-tomar el snapshot
- **Acción requerida:** ratificacion del propietario

### DIV-02 — ficha de par de contextos

- **Clave:** `ficha divergente: ['gobernanza', 'meta_toolkit']`
- **Elemento original (snapshot):** ficha del par en el snapshot de Archify (revision anterior)
- **Elemento vigente (código):** ficha vigente del par en scripts/vault_arch.py
- **SHA de referencia del snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA del código actual:** `ab31bf3b095effb81625464d19f2cf80ab72e35c`
- **Cambio responsable:** 59d0465 (ficha actualizada al mover el cruce) + 667a6a5 (sitio)
- **Naturaleza:** ficha desactualizada: el adeudado NO cambio
- **Riesgo de actualizar el inventario:** bajo: la ficha describe el mismo adeudado con el sitio vigente
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit; B: migrarlo a un owner con puerto declarado; C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** ratificar el texto de la ficha conservando la clase a_eliminar y su fecha limite, o re-tomar el snapshot
- **Acción requerida:** ratificacion del propietario

### DIV-03 — acceso a fichero

- **Clave:** `acceso no conciliado: vault_norms_engine -> vault_mcp_catalog.check_params`
- **Elemento original (snapshot):** acceso declarado en el snapshot: vault_norms_engine -> vault_mcp_catalog.check_params
- **Elemento vigente (código):** acceso vigente en la fachada de mantenimiento (mismo par de contextos)
- **SHA de referencia del snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA del código actual:** `ab31bf3b095effb81625464d19f2cf80ab72e35c`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **Riesgo de actualizar el inventario:** bajo: el par de contextos sigue cruzando; solo cambio el modulo
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit; B: migrarlo a un owner con puerto declarado; C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot de Archify o ratificar la aceptacion con la ficha correspondiente
- **Acción requerida:** ratificacion del propietario

### DIV-04 — acceso a fichero

- **Clave:** `acceso no conciliado: vault_norms_engine -> vault_smoke.SIN_SMOKE`
- **Elemento original (snapshot):** acceso declarado en el snapshot: vault_norms_engine -> vault_smoke.SIN_SMOKE
- **Elemento vigente (código):** acceso vigente en la fachada de mantenimiento (mismo par de contextos)
- **SHA de referencia del snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA del código actual:** `ab31bf3b095effb81625464d19f2cf80ab72e35c`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **Riesgo de actualizar el inventario:** bajo: el par de contextos sigue cruzando; solo cambio el modulo
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit; B: migrarlo a un owner con puerto declarado; C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot de Archify o ratificar la aceptacion con la ficha correspondiente
- **Acción requerida:** ratificacion del propietario

### DIV-05 — acceso a fichero

- **Clave:** `acceso no conciliado: vault_norms_engine -> vault_smoke.invocation`
- **Elemento original (snapshot):** acceso declarado en el snapshot: vault_norms_engine -> vault_smoke.invocation
- **Elemento vigente (código):** acceso vigente en la fachada de mantenimiento (mismo par de contextos)
- **SHA de referencia del snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA del código actual:** `ab31bf3b095effb81625464d19f2cf80ab72e35c`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **Riesgo de actualizar el inventario:** bajo: el par de contextos sigue cruzando; solo cambio el modulo
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit; B: migrarlo a un owner con puerto declarado; C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot de Archify o ratificar la aceptacion con la ficha correspondiente
- **Acción requerida:** ratificacion del propietario

### DIV-06 — acceso a fichero

- **Clave:** `acceso no conciliado: vault_norms_engine -> vault_smoke.load_baseline`
- **Elemento original (snapshot):** acceso declarado en el snapshot: vault_norms_engine -> vault_smoke.load_baseline
- **Elemento vigente (código):** acceso vigente en la fachada de mantenimiento (mismo par de contextos)
- **SHA de referencia del snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA del código actual:** `ab31bf3b095effb81625464d19f2cf80ab72e35c`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **Riesgo de actualizar el inventario:** bajo: el par de contextos sigue cruzando; solo cambio el modulo
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit; B: migrarlo a un owner con puerto declarado; C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot de Archify o ratificar la aceptacion con la ficha correspondiente
- **Acción requerida:** ratificacion del propietario

### DIV-07 — acceso a fichero

- **Clave:** `acceso no conciliado: vault_norms_engine -> vault_voice.coverage`
- **Elemento original (snapshot):** acceso declarado en el snapshot: vault_norms_engine -> vault_voice.coverage
- **Elemento vigente (código):** acceso vigente en la fachada de mantenimiento (mismo par de contextos)
- **SHA de referencia del snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA del código actual:** `ab31bf3b095effb81625464d19f2cf80ab72e35c`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **Riesgo de actualizar el inventario:** bajo: el par de contextos sigue cruzando; solo cambio el modulo
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit; B: migrarlo a un owner con puerto declarado; C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot de Archify o ratificar la aceptacion con la ficha correspondiente
- **Acción requerida:** ratificacion del propietario

### DIV-08 — dependencia a granularidad de fichero

- **Clave:** `dependencia NO CONCILIABLE: vault_norms_engine -> vault_mcp_catalog`
- **Elemento original (snapshot):** dependencia en el snapshot: vault_norms_engine -> vault_mcp_catalog
- **Elemento vigente (código):** dependencia vigente en el par de contextos (mismo adeudado)
- **SHA de referencia del snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA del código actual:** `ab31bf3b095effb81625464d19f2cf80ab72e35c`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **Riesgo de actualizar el inventario:** medio: la granularidad del snapshot (fichero) no coincide con la del registro (par de contextos); el adorno de la divergencia lo dice
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit; B: migrarlo a un owner con puerto declarado; C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot o ratificar la aceptacion
- **Acción requerida:** ratificacion del propietario

### DIV-09 — dependencia a granularidad de fichero

- **Clave:** `dependencia NO CONCILIABLE: vault_norms_engine -> vault_smoke`
- **Elemento original (snapshot):** dependencia en el snapshot: vault_norms_engine -> vault_smoke
- **Elemento vigente (código):** dependencia vigente en el par de contextos (mismo adeudado)
- **SHA de referencia del snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA del código actual:** `ab31bf3b095effb81625464d19f2cf80ab72e35c`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **Riesgo de actualizar el inventario:** medio: la granularidad del snapshot (fichero) no coincide con la del registro (par de contextos); el adorno de la divergencia lo dice
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit; B: migrarlo a un owner con puerto declarado; C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot o ratificar la aceptacion
- **Acción requerida:** ratificacion del propietario

### DIV-10 — dependencia a granularidad de fichero

- **Clave:** `dependencia NO CONCILIABLE: vault_norms_engine -> vault_voice`
- **Elemento original (snapshot):** dependencia en el snapshot: vault_norms_engine -> vault_voice
- **Elemento vigente (código):** dependencia vigente en el par de contextos (mismo adeudado)
- **SHA de referencia del snapshot:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`
- **SHA del código actual:** `ab31bf3b095effb81625464d19f2cf80ab72e35c`
- **Cambio responsable:** 667a6a5 (la composicion paso de vault_norms_engine a vault_norms)
- **Naturaleza:** movimiento
- **Riesgo de actualizar el inventario:** medio: la granularidad del snapshot (fichero) no coincide con la del registro (par de contextos); el adorno de la divergencia lo dice
- **Alternativas:** A: eliminar el cruce componiendo desde el meta-toolkit; B: migrarlo a un owner con puerto declarado; C: excepcion formal con plazo, riesgo y dueno (ratificacion)
- **Recomendación:** re-tomar el snapshot o ratificar la aceptacion
- **Acción requerida:** ratificacion del propietario

## Procedimiento verificable para reconciliarlas

1. El snapshot (`.archify/`) **no se sustituye**: es evidencia de otra
   revisión y su valor es histórico.
2. `audits/architecture/divergencias-aceptadas.yaml` es la lista
   DECLARADA de aceptaciones. Una entrada solo silencia su divergencia
   si tiene `ratificado: true` **y** evidencia; sin eso, el reconciliador
   se comporta igual que antes (exit ≠ 0 y las diez listadas).
3. Para aceptar cada una: el propietario ratifica la entrada y su
   evidencia, y el reconciliador pasa a informar `ACEPTADA (ratificada)`.
4. La alternativa preferida a aceptar es **re-tomar el snapshot** de
   Archify sobre el SHA vigente, que devuelve el estado a cero
   divergencias sin tocar la deuda.


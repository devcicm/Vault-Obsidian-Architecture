# QA-RC-03 — los cinco cruces fuera de puerto: análisis y decisión

**Estado: PENDIENTE DE RATIFICACIÓN DEL PROPIETARIO.**
El ejecutor no ratifica deuda ni la declara aceptada. Aquí están el análisis,
las alternativas con sus consecuencias y la recomendación técnica.

## 1. Qué cambió, exactamente

| Momento | Sitio del cruce | Consecuencia |
|---|---|---|
| Antes de `667a6a5` | `vault_norms_engine` importaba `vault_mcp_catalog`, `vault_smoke` y `vault_voice` (dentro de `try`, para que un fallo de dependencia no tumbara la auditoría) | El motor **empaquetado** dependía de módulos **no empaquetados**: en la wheel instalada, `vault_norms.audit` no podía ejecutar los controles estándar. El guard `vault_servicio` lo detecta como `shipped_imports_of_excluded` |
| Después de `667a6a5` | La composición pasó a `vault_norms` (fachada de **mantenimiento**, que no viaja en la wheel) y el motor recibe los checks por callback | La wheel deja de importar módulos excluidos (`shipped_imports_of_excluded: []`), y el motor queda limpio |

**El adeudado no cambió:** sigue siendo que *gobernanza* compone controles del
estándar que pertenecen a *meta_toolkit* y *autoría*. Cambió el módulo que
pide, no la dependencia.

## 2. Responsabilidad original y vigente

| Control | Verificador | Dueño legítimo (según el registro) | Composición actual |
|---|---|---|---|
| AP-40 (contrato publicado vs CLI) | `vault_mcp_catalog.check_params` | meta_toolkit | `vault_norms._control_ap40` |
| AP-42 (deuda de ejecución declarada) | `vault_smoke` | meta_toolkit | `vault_norms._control_ap42` |
| AP-43 (norma que ninguna tool pronuncia) | `vault_voice.coverage` | autoría | `vault_norms._control_ap43` |

El registro de contextos ya declara `meta_toolkit` y `autoría` como dueños de
esos verificadores. El problema es de **dirección**: quien *pide* la
verificación es gobernanza, no el dueño.

## 3. Contrato real entre contextos

Hoy no hay contrato: `vault_norms` importa los símbolos de los otros contextos
directamente (un acceso fuera de puerto). Eso es exactamente lo que el
registro marca y lo que el reconciliador no puede conciliar con el snapshot.

## 4. Riesgos

**Mantener los cruces (situación actual):**
- Riesgo de distribución: mitigado (la wheel no los importa).
- Riesgo de gobierno: **alto** — el dueño de un control no puede cambiar su
  verificador sin que la fachada de gobernanza se entere; y la evidencia
  (`checks[]`) la produce quien compone, no quien verifica.
- Riesgo de certificación: el reconciliador declara el inventario no conforme
  (10 divergencias) → QG-00 y QG-01 no acreditan.

**Eliminarlos de golpe:**
- Riesgo de contrato: AP-40/42/43 son controles públicos con fixtures y
  pruebas; moverlos rompe consumidores (CLI `--audit --strict`, puerta de
  coherencia, fachada `vault_norms`).
- Riesgo de alcance: tocar el motor, la fachada, el catálogo QG, el colector y
  las puertas en una sola ronda.

## 5. Alternativas

### A. Composición desde el meta-toolkit (eliminación real)

- **Qué:** el meta-toolkit expone un punto de composición propio (por ejemplo
  un `controles_estandar()` en su contexto) y gobernanza **consume ese puerto**
  en vez de importar los símbolos de cada verificador.
- **Beneficio:** el cruce desaparece del grafo; el dueño publica el contrato;
  la evidencia la produce el dueño.
- **Costo:** mover 3 verificadores a un punto de composición público, actualizar
  el motor, la fachada, el catálogo QG y el colector; revisar fixtures.
- **Riesgos:** ruptura de consumidores de `vault_norms.audit`; divergencia con
  el snapshot (que se reconciliaría re-tomándolo).
- **Pruebas:** las de estados (15), las del colector (30), las de paridad (23)
  y la reconciliación.
- **Compatibilidad CLI/MCP:** intacta (no cambia superficie pública).

### B. Migración compatible por etapas

- **Qué:** introducir el puerto en el meta-toolkit manteniendo la firma actual
  de `vault_norms_audit` durante una versión; el motor deja de importar
  definitivamente; la fachada consume el puerto.
- **Beneficio:** misma eliminación, con ventana de compatibilidad.
- **Costo:** dos versiones manteniendo dos caminos; deuda temporal explícita.
- **Riesgos:** duplicación temporal; el baseline no puede crecer, así que la
  ventana debe cerrarse en la misma versión o con fecha.
- **Pruebas:** las de A + una prueba de equivalencia de ambos caminos.

### C. Excepción formal (lo que el ejecutor NO ratifica)

- **Qué:** declarar los cruces como excepción con dueño, plazo y riesgo
  asumido, aceptarlos en `divergencias-aceptadas.yaml` y re-tomar el snapshot
  para que el reconciliador vuelva a estar conforme.
- **Beneficio:** QG-00/QG-01 acreditan sin rehacer la arquitectura.
- **Costo:** el adeudado sigue vivo; la evidencia de gobernanza la sigue
  produciendo quien no es el dueño.
- **Riesgos:** es la opción que menos mejora el producto y la que más
  legitima el paso atrás; **no se recomienda sin que el propietario la motive
  explícitamente**.

## 6. Recomendación técnica

**Alternativa B (migración compatible), con A como destino.** Motivos:

1. La eliminación real es posible sin romper contratos públicos: el problema
   es de *dirección* de la dependencia, no de diseño de los controles.
2. La wheel ya está limpia; lo que falta es que el dueño publique el contrato
   y que gobernanza lo consuma.
3. B deja el cierre verificable: el reconciliador vuelve a estar conforme sin
   tocar el snapshot, y las divergencias se resuelven **eliminando**, no
   aceptando.

**Lo que este ejecutor hará tras la ratificación:** implementar B, con la
secuencia de commits `refactor(puerto de controles) → test(equivalencia) →
refactor(el motor consume el puerto) → reconciliación`, y re-tomar el snapshot
de Archify sobre el SHA resultante.

## 7. Qué se ha corregido ya (sin ratificación)

- El **motor empaquetado** ya no importa módulos que no viajan en la wheel
  (`shipped_imports_of_excluded: []`), y el guard `vault_servicio` lo verifica.
- La **clase de la deuda** se ha restituido a `a_eliminar` con su fecha límite
  original (el cambio a `permanente` que hice sin autorización quedó revertido
  en esta ronda), y la ficha describe el movimiento sin cancelar el adeudado.
- La **ficha** de cada par nombra el movimiento, el commit responsable y la
  decisión pendiente.

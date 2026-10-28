# Archivo: `qa/review-authority-r20-e0d0c75-20261027`

- Commit(s) sobre la rama de trabajo:
  - `e5220ffc62ab6835e0d41bba8c877be1a698c5b9` 2026-10-27 — docs(qa): revisión independiente R20, fallo AP-37 en CI y alcance de delegación AUTH-12
- Base: `e0d0c754aa0897f23779aa67d6f0f36960fe3126`
- Tag de conservación: `archivo/qa/review-authority-r20-e0d0c75-20261027`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`


---

# QA R20 — autoridad, custodia y CI (2026-10-27)

**Revisión independiente del SHA de HEAD:** `e0d0c754aa0897f23779aa67d6f0f36960fe3126` (delta documental sobre `efae50272e2e309335c65ef44d681512fba59684`).
**Producto inmutable referido:** `015b7765b80cac21c6dcf859ae075d036cd01def`, árbol `d190fd24...`.
**Rama QA:** `qa/review-authority-r20-e0d0c75-20261027`.
**Método:** inspección de código, tests fuente, manifiestos, expediente de decisiones y respuestas de GitHub Actions, **sin ejecutar tests locales ni ratificar actos**.

## Veredicto

**QA_REQUIRES_CHANGES / GOAL_ABIERTO; RELEASE_BLOCKED.** Se reconoce implementación real de controles AUTH-05..11 en código y fixtures de prueba, pero su aprobación global queda condicionada por un hueco adicional de alcance de delegación y un fallo CI reproducido dos veces. El producto congelado `015b776` tiene una corrida propia `40442954197` en `completed/success` 25/25: no reutilizarla para certificar los cambios de gobernanza R20. El registro de autoridades permanece `PROPUESTA`, `custodios: []`; el motor real sigue `fail-closed`. **No existe acto firmado por el propietario, QA no otorga ratificación y no autoriza release.**

## QA-R20-CI-01 — P1: AP-37 `vault_graph` sin motivo cuando no escribe en Linux

- Run `40499964653` SHA `efae502`: `completed/failure`, 24/25. El único job rojo es `Validate Vault Spec (ubuntu-latest, 3.12)`, step `Puertas del estándar`, `vault_gate` 25/26; gate `noop` de AP-37. En el artefacto de la salida del job: `vault_noop_audit`, `modo=ejecutado`, `sin_escritura_sin_motivo=["vault_graph"]`, ejemplo `argv=[]` con `tool_ok=true`, sin modificación medida.
- Run `40506345684` SHA `e0d0c75`: **el mismo fallo en el mismo job**, `completed/failure` 24/25; NO es correcto describirlo como un simple run pendiente. La conclusión aparece en Actions y en los logs. El ejecutor local dice no reproducirlo, pero dos CI separadas lo reproducen.
- `scripts/vault_noop_audit.py::ejecutado` construye vault a partir del sandbox, llama `vault_smoke.run_one` por línea y marca `sin_motivo` cuando no hay escritura sin registro en `SIN_ESCRITURA_DECLARADA`; `vault_graph` no está en ese registro. Esta lógica es deliberadamente fail-closed y **no debe deshabilitarse**.
- **Acción obligatoria:** extraer el JSON íntegro del gate, reconstruir el sandbox Linux con estado documentado, ejecutar DOS pasadas sucesivas del ejemplo de `vault_graph` registrando status, checksum de `graph.json`, inventario antes/después, exit, envelope/indicadores, y comparación de contenido. Contrastar Windows/macOS. Determinar si la diferencia es idempotencia genuina (grafo ya actualizado), fixture distinta, orden, timestamps, condición de carrera o anomalía de medición; solo después elegir entre garantizar escritura determinista cuando corresponde o declarar un no-op idempotente comprobado con motivo. Probar ambos: primera ejecución escribe si hay cambio; segunda no escribe y queda acreditada; una tool que no hace trabajo sin justificación sigue fallando.
- **Verificación:** tests focalizados de AP-37, repetición en Linux 3.12 y 26 gates, luego CI completa del nuevo SHA. No ejecutar de forma repetida las ~6.400 pruebas para diagnosticar un gate; conservar suite final del SHA congelado.

## QA-R20-AUTH-12 — P1 latente: delegación con alcance afirmado, no cotejado

`audits/fase2/verificador_actos.py::_delega_verificada(custodio, datos)` valida formato/existencia de SHA y `ACTO: DELEGACION`, `ACCION: DELEGAR`, `DELEGANTE`, `DELEGADO` y presencia de algún `ALCANCE`, pero **no coteja el alcance declarado del acta contra el residuo concreto ni con `datos["delega"]["alcance"]`**, y tampoco verifica que el commit de delegación sea alcanzable desde un canal autorizado del delegante ni su identidad/autorización. `verificar_custodia` invoca ese método sin el `hallazgo` que debe delimitar alcance. El único test focalizado `test_una_delegacion_exige_acto_verificable_con_alcance` prueba un SHA inexistente, no casos de acta existente para otro residuo o canal ajeno.

**Impacto:** con registro ratificado y delegado configurado, un acto de delegación existente que mencione cualquier alcance puede llegar a acreditarse en otro contexto. Hoy no está explotable en producción porque el registro sigue PROPUESTA y no hay custodios designados. **Antes de ratificar DEC-03/04:** exigir acto de delegación auténtico, alcance específico (identidad de residuo/norma/ruta/huella o contrato equivalente), autoridad del delegante, identidad y canal, correspondencia con la configuración, vigencia/revocación si aplica, y negativos en repositorios Git temporales. No autorizar cambios amplios de política ni delegación implícita.

## Estado de AUTH-05..11 (inspección estática)

Implementados y razonables en su alcance:
- AUTH-05: `custodios: []` no admite custodia automática por autoridad.
- AUTH-06: exige identidad y canal del custodio del acto (el subcaso de delegación tiene la brecha QA-R20-AUTH-12).
- AUTH-07: el acta de ratificación del registro exige campos completos.
- AUTH-08: alias resueltos contra el registro y contradicciones rechazadas.
- AUTH-09: fechas ISO, ventana temporal.
- AUTH-10: campos obligatorios duplicados rechazados.
- AUTH-11: revocación consultada en el canal declarado, e invalida acto.

**No se ha realizado una ejecución independiente de los 34+33 tests; el hecho de que el código exista y los jobs unitarios pasen no sustituye QA de sus casos adversariales omitidos.** Revisar confianza operativa: identidad Git y permiso de push compartidos no demuestran voluntad del propietario. La propia documentación lo reconoce. Recomendable canal protegido, roles separados y commits firmados verificables como prerequisito de activación real del registro.

## Estado de la liberación y decisiones reservadas

- `main=1c34754258441550139ce895e182ab219c93f9bb` inalterada y PR #3 en DRAFT sin merge.
- `015b776`: CI 25/25, wheeled E2E 27/27 según manifiesto del candidato y fuentes del ejecutor; QA no repitió localmente E2E.
- QG-00/01 BLOCKED por diez divergencias; QG-02 BLOCKED por residuo externo AP-36 y contrato sin ratificar; QG-03..06 PASS en recibos propios del candidato pero dependencia QG-00 impide release; QG-07 BLOCKED.
- DEC-01 (Constitución), DEC-02 (migración B con I2-a + COST-a, ≤5s, una versión, I1..I5), DEC-03 (política C y autoridades/canales), DEC-04 (custodia; **archivo** separado de traslado/purga), DEC-05 (historia) y DEC-06 (publicación) **siguen sin ratificación**.
- El agente **NO** debe completar campos del propietario, crear actos atribuidos a él, ejecutar purga de backups ni fusionar ramas.

## Recomendación de siguiente bloque

1. Aislar y corregir `vault_graph` en AP-37 reproduciendo Ubuntu 3.12; preservar los negativos.
2. Reparar delegación de AUTH-06 con pruebas de identidad/canal/alcance específico y caso positivo legítimo.
3. Completar pruebas focalizadas, run Linux y CI; capturar resultados por SHA.
4. Mantener `015b776` como producto congelado si el árbol empaquetado no cambia; si se modifica código de paquete o su comportamiento, crear **nuevo candidato** y repetir suite, wheel/sdist, E2E, CI y recibos.
5. Dar al propietario decisiones A/B/C con riesgos, sin ratificarlas por él. Tras acto real, ejecutar únicamente los cambios autorizados y QA independiente.

**Dictamen:** `QA_R20=REQUIRES_CHANGES`; `AUTH05..11=IMPLEMENTADO_SIN_APROBACION_GLOBAL`; `AUTH12=OPEN`; `AP37_LINUX=FAIL`; `RELEASE=BLOCKED`. No merge, no tag, no release, no tocar main.


# Archivo: `qa/review-authority-r21-4bf4092-20261027`

- Commit(s) sobre la rama de trabajo:
  - `2d00db418e1764f8ea99834da30efc0af18050b7` 2026-10-27 — docs(qa): dictamen R21 AP-37, AUTH-12, CI 25/25 y decisiones de release
- Base: `4bf40922ab96bd46167f50fe91e99b691389a2f2`
- Tag de conservación: `archivo/qa/review-authority-r21-4bf4092-20261027`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# QA R21 — AP-37 idempotencia, AUTH-12 delegación y CI 25/25 (2026-10-27)

**Revisado independientemente:** `cd98ff09e771e5dc8570be7c09cd09f78c1d12b2` (corrección validada por CI) y delta documental `4bf40922ab96bd46167f50fe91e99b691389a2f2`.  
**Producto congelado:** `015b7765b80cac21c6dcf859ae075d036cd01def` (`product_tree_sha=d190fd243567556e824795154b6fd44bd76309d5`).  
**Rama QA aislada:** `qa/review-authority-r21-4bf4092-20261027`.  
**Dictamen antecedente:** `e5220ffc62ab6835e0d41bba8c877be1a698c5b9` (R20).  
**Método:** lectura estática del código y pruebas en GitHub, diff entre producto/código R21, lectura de manifiesto de empaquetado, verificación por API de runs y sus 25 jobs. **QA no ejecutó localmente pytest, el banco Linux del ejecutor, ni descargó/comparó los bytes de la wheel.**

## Dictamen

**QA-R20-CI-01 (AP-37 Linux): ACEPTADO_EN_ALCANCE.** Se comprobó en `scripts/vault_noop_audit.py` que `IDEMPOTENTES_DECLARADAS` exige a `vault_graph` `written=0` y `unchanged>=1` del envelope verdadero para considerar un no-op sin escritura; la ausencia del indicador permanece roja, y escritura con declaración falsa de `written=0` queda en `ofensores`. `vault_smoke.run_one` transporta el objeto `datos`, no solo el nombre de campos. `tests/test_noop_audit.py` contiene casos negativos de indicador ausente, no-op falso y herramienta no declarada. El experimento de tres pasadas de Linux 3.12 (hash y brokenLinks) está **reportado por el ejecutor**, no reproducido por QA; CI del SHA reparado pasa las 25 columnas, incluida ubuntu-3.12.

**QA-R20-AUTH-12 (delegación): ACEPTADO_EN_ALCANCE_ESTÁTICO.** `_delega_verificada` valida RESIDUO, NORMA, HUELLA y ALCANCE contra el hallazgo/registro, delegante registrado con canal, delegado exacto, procedencia, identidad Git si está declarada, fechas y revocación cuando aplican. Hay nueve tests de caso válido y negativos con repos Git descartables en `tests/test_delegacion_actos.py`. **LÍMITE: la ausencia de `VIGENCIA` está permitida como contrato actual; cuando se declara sí se valida.** La identidad Git y permiso de push compartidos siguen siendo control administrativo y NO firma ni autorización independiente del propietario. Ningún custodio está habilitado porque `autoridades-de-decision.yaml` permanece `PROPUESTA`, `custodios: []`.

**CI R21: VERIFICADO.** GitHub Actions run `40575556783` SHA `ab95c1c`: `completed/failure`, regresiones de `Any` ausente y ruta local absoluta; el commit `cd98ff0` corrige ambos. Run `40580542007` SHA `cd98ff09e771e5dc8570be7c09cd09f78c1d12b2`: **`completed/success`, 25/25 jobs `completed/success`**, incluyendo validate ×12, product ×12 y lint. Run del HEAD documental `4bf4092`, `40586948925`, seguía **in_progress**, 12/25 jobs exitosos y 13 sin conclusión al consultar: no acreditarlo todavía como 25/25. Su delta desde `cd98ff0` es exclusivamente `audits/handoff/RESPUESTA-DEL-EJECUTOR.md`. Evidencia CI de `cd98ff0` no se atribuye falsamente a HEAD.

**Producto congelado: sin cambios empaquetados observables en el diff.** La comparación desde `015b776` hasta `4bf4092` contiene modificaciones en `scripts/vault_noop_audit.py` y `scripts/vault_smoke.py`, pero ambos aparecen en `empaquetado/fuera-de-la-wheel.json`, aplicado por `empaquetado/construir.BuildPy`; `vault_graph` no se modifica en el diff. El manifiesto del producto declara wheel `8cda5ef45626dd244199528eb3f8b5403788f6f1e4b3e2e75ac98f5f737f3cfd`, y run propio `40442954197` para `015b776` confirmado hoy `completed/success` con 25/25. **QA no comprobó personalmente el digest del archivo de wheel**, por lo que se acepta consistencia de código/manifiesto, no una nueva validación binaria.

## Decisión de release

**`RELEASE_BLOCKED / BLOCKED_OWNER_DECISION` permanece CORRECTO.** No es un fallo actual de CI: los dos runs exigidos, producto y corrección R21, están en success. Sin embargo `QG-00` y `QG-01` siguen bloqueados por las 10 divergencias y los cruces sin resolver; `QG-02` sigue bloqueado por sujeto de certificación y residuo AP-36 externo. Los recibos QG-03..06 `PASS` no autorizan liberar por los prerrequisitos. `QG-07` está bloqueado hasta que los anteriores sean efectivos y se emita autorización tras QA. `catalogo-qg.yaml` y `politica_qg.py` no fueron cambiados en R21.

**Qué debe decidir el propietario (sin autoatribución):**

- **DEC-01:** enmendar/revisar y ratificar Constitución DRAFT o aceptar limitación declarada.
- **DEC-02:** alternativa **B + I2-a + COST-a**, sugerida, con invariantes I1–I5, objetivo 5→3 cruces y DIV-01..10 10→0, audit ≤5 s y compatibilidad una versión. **Es una autorización de implementación, NO una aprobación de release ni permiso para mutar el producto `015b776`.** Al implementarla se crea SHA candidato NUEVO y se exige suite, 26 puertas, E2E de wheel, CI, QG y QA del nuevo SHA.
- **DEC-03:** política compuesta **C**, con sujeto runtime limpio + sandbox, fail-closed ante efectos nuevos y registro formal de residuo/autoridad en vigor. El ejecutor no puede poner `RATIFICADO` sin acto auténtico. El cambio de política requiere diff y tests negativos/QA.
- **DEC-04:** designar custodio legítimo con identidad y canal, conservar 66 archivos/hashes; **custodia NO autoriza archivo, traslado ni purga**. Archivo no destructivo, movimiento y purga requieren actos separados y deliberados. No eliminar `vault-backups` automáticamente.
- **DEC-05:** decidir conservar historia con riesgo documentado o reescritura formal (alto costo e invalidación de SHAs); QA recomienda NO reescribir sin necesidad nueva acreditada.
- **DEC-06:** autorización de publicación **solo después** de QG-00..07 efectivos, nuevo dictamen QA y alcance/artefacto certificados.

**Precaución de autoridad:** el mecanismo actual usa ramas e identidad Git compartidas. Un commit con texto `RATIFICADO` hecho por el ejecutor no demuestra voluntad del propietario. Si el proceso requiere independencia fuerte, usar canal protegido, permisos/identidades separados y firma verificable; documentar el nivel efectivo de garantía y no presentarlo como criptográfico hoy.

## Siguiente instrucción recomendada

No solicitar otra optimización general ni repetir 6400 tests sin cambios relevantes. Registrar los cierres AP-37/AUTH-12 y un índice de evidencia CI por SHA; verificar el run del HEAD documental cuando concluya. Preparar **dos rutas** sin ejecutarlas hasta autorización: (a) **ruta B** de migración arquitectónica con nuevo candidato y recertificación total, y (b) **ruta C** de política QG-02, con ratificación legítima y custodia de `vault-backups`. Presentar al propietario fichas claras de decisión, con alcance y exclusiones; no firmar en su nombre. Cuando el propietario elija, aplicar SOLO la autorización real, manteniendo `main` y los PR sin tocar hasta la aprobación final.

**Estado:** `AP37_LINUX=ACCEPTED_SCOPED`; `AUTH12=ACCEPTED_SCOPED_STATIC`; `CI_CD98=VERIFIED_25_OF_25`; `PRODUCT_CI=VERIFIED_25_OF_25`; `RELEASE=BLOCKED_OWNER_DECISION`; `GOAL=OPEN`. **NO MERGE / NO TAG / NO RELEASE / NO FALSE PASS.**


# Manifiesto de recibos — recibos del SHA e198ffb (ronda R13)

Fuente: directorio de recibos fuera del árbol versionado (AP-36).
Cada recibo acredita la ejecución LOCAL de ese verificador con su exit
code y el SHA-256 de su artefacto. No es firma frente a un actor con
escritura: para eso están la CI externa (QG-07) y el dictamen de QA.
Rutas saneadas: solo nombres base de fichero.

## QG-00

- status: **FAIL** · exit_code: 1
- run_id: `local-QG-00-e198ffb` · inicio: 2026-10-27T02:02:47Z · fin: 2026-10-27T02:02:57Z
- artefacto agregado: `QG-00.subchecks.json` · sha256 `566c540075020cb11cd48d41d3f48775686d5a7cbb11a425cf9a8a282265eb4e`
- checks: {"identidad_git": "ejecutado", "arbol_limpio": "ejecutado", "saneamiento": "ejecutado", "reconciliador_archify": "fallido"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| identidad_git | ejecutado | — | — | `QG-00.identidad_git.json` | `736462b96d43aa8f…` |
| arbol_limpio | ejecutado | — | — | `QG-00.arbol_limpio.json` | `99cda91a1c023100…` |
| saneamiento | ejecutado | — | 0 | `QG-00.saneamiento.salida.txt` | `2a088c40366977da…` |
| reconciliador_archify | fallido | exit=1 | 1 | `QG-00.reconciliador_archify.salida.txt` | `559b31413082b74b…` |

## QG-01

- status: **FAIL** · exit_code: 1
- run_id: `local-QG-01-e198ffb` · inicio: 2026-10-27T02:02:57Z · fin: 2026-10-27T02:03:23Z
- artefacto agregado: `QG-01.subchecks.json` · sha256 `3e9b855ae9f3619c37b2338206a4f53435313638aa3d56542e2c1b4550b3bb63`
- checks: {"vault_arch": "ejecutado", "reconciliador_archify": "fallido"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| vault_arch | ejecutado | — | 0 | `QG-01.vault_arch.salida.txt` | `0e9b3aa4499ed5f5…` |
| reconciliador_archify | fallido | exit=1 | 1 | `QG-01.reconciliador_archify.salida.txt` | `559b31413082b74b…` |

## QG-02

- status: **FAIL** · exit_code: 1
- run_id: `local-QG-02-e198ffb` · inicio: 2026-10-27T02:03:23Z · fin: 2026-10-27T02:18:25Z
- artefacto agregado: `QG-02.subchecks.json` · sha256 `b354f2a1937669a59a89f08c4ae792fda483cdad11187196f36d670d584527a1`
- checks: {"puertas_26": "ejecutado", "auditoria_completa": "ejecutado", "sin_violaciones": "fallido"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| puertas_26 | ejecutado | — | 0 | `QG-02.puertas_26.salida.txt` | `fa2c50b339979848…` |
| auditoria_completa | ejecutado | — | 0 | `QG-02.auditoria_completa.salida.txt` | `14e1de2c7789c069…` |
| sin_violaciones | fallido | total_violations=1 | — | `QG-02.auditoria_completa.salida.txt` | `14e1de2c7789c069…` |

## QG-03

- status: **PASS** · exit_code: 0
- run_id: `local-QG-03-e198ffb` · inicio: 2026-10-27T02:18:25Z · fin: 2026-10-27T02:18:25Z
- artefacto agregado: `QG-03.subchecks.json` · sha256 `8688cfbc49f0e0077463a6c36b312e9c7222dc406758a90f2228b15feb2bca57`
- checks: {"suite_junit": "ejecutado", "recorrido_e2e": "ejecutado"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| suite_junit | ejecutado | — | — | `r13b-junit.xml` | `7045816f123e3847…` |
| recorrido_e2e | ejecutado | — | — | `e2e.json` | `3ed06ca067964063…` |

## QG-04

- status: **PASS** · exit_code: 0
- run_id: `local-QG-04-e198ffb` · inicio: 2026-10-27T02:18:25Z · fin: 2026-10-27T02:18:51Z
- artefacto agregado: `QG-04.subchecks.json` · sha256 `e1477bde5eb96aa4c61351d9bc3784a5fdff3c15d9937fc63522ae7678e5ea0a`
- checks: {"saneamiento": "ejecutado", "pip_audit": "ejecutado", "contencion": "ejecutado", "operaciones_destructivas": "ejecutado"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| saneamiento | ejecutado | — | 0 | `QG-04.saneamiento.salida.txt` | `2a088c40366977da…` |
| pip_audit | ejecutado | — | 0 | `QG-04.pip_audit.salida.txt` | `fd3fddf842808e36…` |
| contencion | ejecutado | — | 0 | `QG-04.contencion.salida.txt` | `4b950891a4a75b17…` |
| operaciones_destructivas | ejecutado | — | 0 | `QG-04.operaciones_destructivas.salida.txt` | `098283e4e53edd3e…` |

## QG-05

- status: **PASS** · exit_code: 0
- run_id: `local-QG-05-e198ffb` · inicio: 2026-10-27T02:18:51Z · fin: 2026-10-27T02:19:14Z
- artefacto agregado: `QG-05.subchecks.json` · sha256 `348065224260fe8e03fc3eee3bc4ed9cb70559f64cc11e3acb551efc9d0e968f`
- checks: {"paridad_cli_mcp": "ejecutado", "ap40_contrato": "ejecutado"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| paridad_cli_mcp | ejecutado | — | 0 | `QG-05.paridad_cli_mcp.salida.txt` | `b3d35c9179997bd1…` |
| ap40_contrato | ejecutado | — | 0 | `QG-05.ap40_contrato.salida.txt` | `d8d4cb5955dbae32…` |

## QG-06

- status: **PASS** · exit_code: 0
- run_id: `local-QG-06-e198ffb` · inicio: 2026-10-27T02:19:14Z · fin: 2026-10-27T02:19:31Z
- artefacto agregado: `QG-06.subchecks.json` · sha256 `9814d3c461dbb1661eb0e6d5ea71815ba1e177fdff71fa84298cd90b591eca73`
- checks: {"construccion": "ejecutado", "wheel_contenido": "ejecutado", "instalacion_limpia": "ejecutado"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| construccion | ejecutado | — | 0 | `QG-06.construccion.salida.txt` | `9bba5f4d505918d0…` |
| wheel_contenido | ejecutado | — | — | `QG-06.wheel_contenido.json` | `13389bcdfda041db…` |
| instalacion_limpia | ejecutado | — | — | `e2e.json` | `3ed06ca067964063…` |


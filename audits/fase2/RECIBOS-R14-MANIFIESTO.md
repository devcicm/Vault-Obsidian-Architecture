# Manifiesto de recibos — recibos del SHA 015b776 (ronda R14)

Fuente: directorio de recibos fuera del árbol versionado (AP-36).
Cada recibo acredita la ejecución LOCAL de ese verificador con su exit
code y el SHA-256 de su artefacto. No es firma frente a un actor con
escritura: para eso están la CI externa (QG-07) y el dictamen de QA.
Rutas saneadas: solo nombres base de fichero.

## QG-00

- status: **FAIL** · exit_code: 1
- run_id: `local-QG-00-015b776` · inicio: 2026-10-27T04:51:29Z · fin: 2026-10-27T04:51:39Z
- artefacto agregado: `QG-00.subchecks.json` · sha256 `829a123fe75d11a73a9a895fddd1c079780615bd94414cb5329820b0d7dca324`
- checks: {"identidad_git": "ejecutado", "arbol_limpio": "ejecutado", "saneamiento": "ejecutado", "reconciliador_archify": "fallido"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| identidad_git | ejecutado | — | — | `QG-00.identidad_git.json` | `082a96c015fdaad5…` |
| arbol_limpio | ejecutado | — | — | `QG-00.arbol_limpio.json` | `99cda91a1c023100…` |
| saneamiento | ejecutado | — | 0 | `QG-00.saneamiento.salida.txt` | `2a088c40366977da…` |
| reconciliador_archify | fallido | exit=1 | 1 | `QG-00.reconciliador_archify.salida.txt` | `559b31413082b74b…` |

## QG-01

- status: **FAIL** · exit_code: 1
- run_id: `local-QG-01-015b776` · inicio: 2026-10-27T04:51:39Z · fin: 2026-10-27T04:52:02Z
- artefacto agregado: `QG-01.subchecks.json` · sha256 `b4149eec1784c560329af7521ab47bc67af1e2ec3f960d3e844733d3daaa855b`
- checks: {"vault_arch": "ejecutado", "reconciliador_archify": "fallido"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| vault_arch | ejecutado | — | 0 | `QG-01.vault_arch.salida.txt` | `0e9b3aa4499ed5f5…` |
| reconciliador_archify | fallido | exit=1 | 1 | `QG-01.reconciliador_archify.salida.txt` | `559b31413082b74b…` |

## QG-02

- status: **FAIL** · exit_code: 1
- run_id: `local-QG-02-015b776` · inicio: 2026-10-27T04:52:02Z · fin: 2026-10-27T05:05:20Z
- artefacto agregado: `QG-02.subchecks.json` · sha256 `149f35259588ecf4ee6de8d619c95205e5ec568c172773258113aefcf5f1bc76`
- checks: {"puertas_26": "ejecutado", "auditoria_completa": "ejecutado", "sin_violaciones": "fallido"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| puertas_26 | ejecutado | — | 0 | `QG-02.puertas_26.salida.txt` | `dcb05295e1593939…` |
| auditoria_completa | ejecutado | — | 0 | `QG-02.auditoria_completa.salida.txt` | `7fb87970c7dc2b52…` |
| sin_violaciones | fallido | total_violations=1 | — | `QG-02.auditoria_completa.salida.txt` | `7fb87970c7dc2b52…` |

## QG-03

- status: **PASS** · exit_code: 0
- run_id: `local-QG-03-015b776` · inicio: 2026-10-27T05:05:20Z · fin: 2026-10-27T05:05:20Z
- artefacto agregado: `QG-03.subchecks.json` · sha256 `d8e1584918a1a6c0ea71c9ac3db7b02ac6bdfa8ca5314096bdb7da1c124af68a`
- checks: {"suite_junit": "ejecutado", "recorrido_e2e": "ejecutado"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| suite_junit | ejecutado | — | — | `r14-junit.xml` | `fa321a023d97e8b7…` |
| recorrido_e2e | ejecutado | — | — | `e2e.json` | `9d6a3c3fd2f70422…` |

## QG-04

- status: **PASS** · exit_code: 0
- run_id: `local-QG-04-015b776` · inicio: 2026-10-27T05:05:20Z · fin: 2026-10-27T05:05:27Z
- artefacto agregado: `QG-04.subchecks.json` · sha256 `067d27b3a7cad15f912387985714d8cd822a292f9607880bfcc642adf4f5dbea`
- checks: {"saneamiento": "ejecutado", "pip_audit": "ejecutado", "contencion": "ejecutado", "operaciones_destructivas": "ejecutado"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| saneamiento | ejecutado | — | 0 | `QG-04.saneamiento.salida.txt` | `2a088c40366977da…` |
| pip_audit | ejecutado | — | 0 | `QG-04.pip_audit.salida.txt` | `6b98438f524efb73…` |
| contencion | ejecutado | — | 0 | `QG-04.contencion.salida.txt` | `4b950891a4a75b17…` |
| operaciones_destructivas | ejecutado | — | 0 | `QG-04.operaciones_destructivas.salida.txt` | `5b19f56301af23c4…` |

## QG-05

- status: **PASS** · exit_code: 0
- run_id: `local-QG-05-015b776` · inicio: 2026-10-27T05:05:27Z · fin: 2026-10-27T05:05:52Z
- artefacto agregado: `QG-05.subchecks.json` · sha256 `cf99922ff071ce675ec3d91c2804dfa1b28be8f74c06b7bb877812636fed3166`
- checks: {"paridad_cli_mcp": "ejecutado", "ap40_contrato": "ejecutado"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| paridad_cli_mcp | ejecutado | — | 0 | `QG-05.paridad_cli_mcp.salida.txt` | `84b31ee34ed4069f…` |
| ap40_contrato | ejecutado | — | 0 | `QG-05.ap40_contrato.salida.txt` | `d8d4cb5955dbae32…` |

## QG-06

- status: **PASS** · exit_code: 0
- run_id: `local-QG-06-015b776` · inicio: 2026-10-27T05:05:52Z · fin: 2026-10-27T05:06:06Z
- artefacto agregado: `QG-06.subchecks.json` · sha256 `14137f5c185a1e9c97b8ac35da13b08935476623c0c629eb7c7ce963be829c15`
- checks: {"construccion": "ejecutado", "wheel_contenido": "ejecutado", "instalacion_limpia": "ejecutado"}

| subcheck | estado | detalle | exit | artefacto | sha256 |
|---|---|---|---|---|---|
| construccion | ejecutado | — | 0 | `QG-06.construccion.salida.txt` | `b2ab581865d6ccb1…` |
| wheel_contenido | ejecutado | — | — | `QG-06.wheel_contenido.json` | `0ad4c04e1cebceaa…` |
| instalacion_limpia | ejecutado | — | — | `e2e.json` | `9d6a3c3fd2f70422…` |


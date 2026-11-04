# Recibos de la CI: el job `qg-receipts` del workflow Release (R27, v41.26)

Estos son los recibos que produjo **la máquina**, en la CI, sobre el worktree
del `product_sha` (`9ac330a`), en la corrida del tag `v41.26` (run 41744360675).
Los de la corrida local están en `../recibos-R27-9ac330a/`; los de la CI se
versionan aparte porque son la prueba de que **el job funciona** —la deuda
`colector_qg_sin_primera_corrida` decía exactamente eso: «solo una corrida real
de la CI dice que el job funciona, y la CI corre al subir un tag `v*`»—.

**Resultado: QG-00..QG-07 PASS, `liberable: true`.**

Lo que esta corrida midió de verdad:

- **La suite, en Linux y Python 3.12** (la local fue en Windows y 3.14):
  6789 tests, 0 failed, 0 errores, 19 skipped. Su recibo de procedencia
  (`suite.xml.procedencia.json`) dice, textualmente, «corrida de la CI
  (qg-receipts) sobre el worktree del product_sha»: es la firma que la deuda
  pedía.
- **El E2E desde la wheel** construida en la propia CI.
- **La paridad CLI/MCP sobre un runtime recién creado** con `vault init`, como
  en R26.
- **QG-07**: la CI del candidato (run 41718868947) en `completed/success`, 27/27
  jobs, consultada con `gh` desde el job.

## Lo que esta corrida encontró

La **primera** corrida real del job (tag `v41.26` sobre `86d4885`) tuvo QG-00..06
en PASS y **QG-07 BLOCKED**: el job no tenía `GH_TOKEN`, y el colector consulta
la CI con `gh`, que en un workflow sin token responde «set the GH_TOKEN
environment variable». El arreglo (`GH_TOKEN` y `permissions: actions: read`)
está en `dba11cd`, con un test que lo fija
(`tests/test_release_qg_receipts.py::test_el_colector_puede_consultar_la_ci_del_candidato`),
y el tag se movió a ese commit. El candidato y sus QG-00..07 no cambian.

## Límites declarados

- Las rutas del runner se normalizan (`<repo>`, `<runner>`, `<toolcache>`,
  `<python>`). El sha256 de cada fichero es el del ORIGINAL:
  `sha256-original.json` los recoge.
- El `pip-audit` de esta corrida audita el intérprete del job (el entorno de la
  ronda), no un venv con lo que el producto declara: es lo que hace el workflow.
- macOS no se promete; el alcance son Linux y Windows con Python 3.9–3.12.

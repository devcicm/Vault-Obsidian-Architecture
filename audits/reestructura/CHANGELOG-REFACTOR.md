# Changelog del refactor — rama `reestructura/teseo`

Una fila por tablón ejecutado. «Paridad» es la salida de `paridad.py --comparar` en ese
commit. «Custodia» es el hash del commit verificable.

| Paso | Criterio | Qué cambió | Mapeo antes → después | Paridad | Custodia |
|---|---|---|---|---|---|
| — | — | Golden master capturado sobre `44a60de`: 301 módulos, 128 `--help`, 126 tools / 233 líneas (12 con volátiles declarados) y la suite 6726 passed / 16 skipped. Todavía no se ha ejecutado ningún tablón. | — | autocomprobación `estatico,superficie,ayuda` en verde | `bad1750` |
| — | instrumento | `paridad.py`: cada repetición de la captura construye su propio vault de origen. Se recapturó `envelopes` porque el detector no veía los hashes sobre la hora del alta de `mi-api`. No es un tablón y no hay código del producto tocado. | 12 → 14 corridas con volátiles (`vault_backup#0/#1 merkle_root`, `vault_graph_fix#0 source_sha`, `vault_toolkit_audit#0 segundos`); plan y resto de corridas idénticos al golden anterior | comparación completa sobre `bad1750`: estatico, superficie y ayuda en verde; envelopes en rojo solo por esas tres rutas | `a0b0bc4` |
| A-1 | H-01 | Nada. Al deconstruirlo, las dos copias de `tools-catalog.json` resultaron proyecciones de un único conocimiento (`TOOLS_CATALOG`), con un lector cada una en un paquete distinto de la wheel. `check_sync` ya exige que sean iguales. Se reclasifica NOT_APPLICABLE en `AUDITORIA.md`. | — | no aplica: no hay código tocado | `625a982` |
| A-2 | H-08 · CN-05 | `vault/uninstall.py` importa `_run` de `vault/install.py` en vez de repetir el cuerpo. `clones-baseline` pasa de 1 sitio a 0 y el motivo se queda como historia. | `uninstall::_run` (cuerpo propio) → `from vault.install import _run` | `estatico,superficie,ayuda` en verde; `_run` es el mismo objeto, con el mismo eco, comando y código de retorno; carril dev 1201 passed; puertas `rapida` en verde | `428c895` |

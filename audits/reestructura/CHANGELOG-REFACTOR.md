# Changelog del refactor — rama `reestructura/teseo`

Una fila por tablón ejecutado. «Paridad» es la salida de `paridad.py --comparar` en ese
commit. «Custodia» es el hash del commit verificable.

| Paso | Criterio | Qué cambió | Mapeo antes → después | Paridad | Custodia |
|---|---|---|---|---|---|
| — | — | Golden master capturado sobre `44a60de`: 301 módulos, 128 `--help`, 126 tools / 233 líneas (12 con volátiles declarados) y la suite 6726 passed / 16 skipped. Todavía no se ha ejecutado ningún tablón. | — | autocomprobación `estatico,superficie,ayuda` en verde | `bad1750` |
| — | instrumento | `paridad.py`: cada repetición de la captura construye su propio vault de origen. Se recapturó `envelopes` porque el detector no veía los hashes sobre la hora del alta de `mi-api`. No es un tablón y no hay código del producto tocado. | 12 → 14 corridas con volátiles (`vault_backup#0/#1 merkle_root`, `vault_graph_fix#0 source_sha`, `vault_toolkit_audit#0 segundos`); plan y resto de corridas idénticos al golden anterior | comparación completa sobre `bad1750`: estatico, superficie y ayuda en verde; envelopes en rojo solo por esas tres rutas | (este commit) |

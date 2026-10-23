# Métricas de desarrollo y de producto

> **Derivado** de `scripts/vault_metricas.py` (`METRICAS`) y de
> `scripts/metricas-observaciones.json`. Se regenera con
> `python scripts/vault_metricas.py --doc`; lo escrito a mano se pierde.
> El estado de cada métrica (cumple, en plazo, vencido) depende del día y
> no se publica aquí: lo da `python scripts/vault_metricas.py --check`.

## Desarrollo

| Métrica | Qué mide | Origen | Mejora si | Objetivo | Fuente |
|---|---|---|---|---|---|
| `deuda_pendiente` | Deudas declaradas en el plano que siguen `pendiente`. | calculada | baja | ≤ 2 entradas para 2027-01-14 · cada 30 d · meta_toolkit — vault_metricas | vault_blueprint.DEUDA_DECLARADA |
| `normas_vencidas` | Normas cuya revisión venció: `revisado_en` más su cadencia ya pasó (R4). | calculada | baja | ≤ 0 normas para 2027-01-14 · cada 30 d · meta_toolkit — vault_metricas | vault_norms_catalog.gestion_de_normas |
| `baselines_vencidas` | Baselines cuyo objetivo pasó de fecha sin cumplirse. | calculada | baja | ≤ 0 baselines para 2027-01-14 · cada 30 d · meta_toolkit — vault_metricas | vault_baseline.estado_objetivo sobre vault_blueprint._BASELINES |
| `baselines_por_encima_de_objetivo` | Baselines con objetivo que todavía no han encogido hasta él (en plazo o vencidas). | calculada | baja | ≤ 7 baselines para 2027-01-14 · cada 30 d · meta_toolkit — vault_metricas | vault_baseline.estado_objetivo sobre vault_blueprint._BASELINES |
| `commits_ultima_version` | Commits entre el hash de la penúltima versión del changelog y el de la última. | calculada | baja | — *sin objetivo*: mide el tamaño del lote, no su calidad: un objetivo empujaría a partir o juntar commits para cumplirlo | vault_changelog_check.entradas + git rev-list |
| `dias_entre_versiones` | Días entre la fecha de la penúltima versión del changelog y la de la última. | calculada | baja | — *sin objetivo*: la versión sube con permiso del usuario, no por calendario: fecharla sería medir cuándo se pide el permiso | vault_changelog_check.entradas |
| `suite_fallos` | Tests en rojo en una ronda completa de la suite (failed + errors). | observada | baja | ≤ 0 tests para 2027-01-14 · cada 30 d · meta_toolkit — vault_metricas | resumen final de `python -m pytest tests/` (--registrar-suite) |
| `suite_duracion_s` | Duración de una ronda completa de la suite, según pytest. | observada | baja | ≤ 4339 s para 2027-01-14 · cada 30 d · meta_toolkit — vault_metricas | resumen final de `python -m pytest tests/` (--registrar-suite) |
| `suite_tests` | Tests ejecutados en una ronda completa de la suite. | observada | sube | — *sin objetivo*: crece por diseño —toda norma con guard lleva test— y un objetivo premiaría escribir tests por la cifra | resumen final de `python -m pytest tests/` (--registrar-suite) |
| `puertas_duracion_s` | Suma de lo que tardan las puertas en verde, según vault_gate. La paga cada commit, no cada ronda: crecer aquí es AP-66 en el proceso del repo. | observada | baja | ≤ 87 s para 2027-01-14 · cada 30 d · meta_toolkit — vault_metricas | `seconds` de `python scripts/vault_gate.py --strict` (--registrar-puertas) |
| `colisiones_de_sanadores` | Normas ajenas que un sanador de SANADORES hace subir al reparar las suyas (AP-55, C8), sobre una copia temporal del vault medido. | observada | baja | ≤ 0 colisiones para 2027-01-14 · cada 30 d · meta_toolkit — vault_metricas | `collisions_total` de `python scripts/vault_norms_coherence.py --colisiones` |

## Producto

| Métrica | Qué mide | Origen | Mejora si | Objetivo | Fuente |
|---|---|---|---|---|---|
| `contexto_agente_s` | Coste de la cadena de consulta de contexto que paga el agente: vault_query_parse + vault_context_pack sobre un vault real. | observada | baja | ≤ 12 s para 2026-12-31 · cada 30 d · meta_toolkit — vault_metricas | `vault_metricas --registrar-contexto` (mide la ronda; no acepta un número a mano: una métrica de producto que se rellena a mano no mide el producto) |
| `skip_path_escritura_s` | Coste de una corrida de onboarding que no escribe nada: el caso que se paga por convención en cada reintento. | observada | baja | ≤ 2 s para 2026-12-31 · cada 30 d · meta_toolkit — vault_metricas | `vault_metricas --registrar-skip` (doble pasada real sobre un proyecto demo) |
| `promesas_descubiertas` | Promesas a quien instala (versión, dependencia, plataforma, red) sin ejecutor. | calculada | baja | ≤ 0 promesas para 2027-01-14 · cada 30 d · meta_toolkit — vault_metricas | vault_produccion.check()['descubiertas'] |
| `smoke_fallos` | Tools del catálogo que fallan el smoke. | observada | baja | ≤ 0 tools para 2027-01-14 · cada 30 d · meta_toolkit — vault_metricas | `failing` de `python scripts/vault_smoke.py` (--registrar-smoke) |
| `banco_tareas_fallidas` | Tareas del banco del agente (orientar, escribir, recuperarse…) que no salen ok. | observada | baja | ≤ 0 tareas para 2027-01-14 · cada 30 d · meta_toolkit — vault_metricas | informe JSON de `tests/banco_agente.py` (--registrar-banco) |
| `recall_pack_ajeno` | Recall del paquete de contexto sobre la copia de un vault ajeno (regla 7). | observada | sube | ≥ 1.0 fracción para 2027-01-14 · cada 30 d · meta_toolkit — vault_metricas | `recuerdo_preexistente.recall_pack` de `banco_agente.py --copiar-de` (--registrar-banco) |

## Histórico de observaciones

| Fecha | Commit | Métrica | Valor | Fuente |
|---|---|---|---|---|
| 2026-10-14 | `32d2561` | `suite_fallos` | 0 | ronda r35 (suite completa en serie) |
| 2026-10-14 | `32d2561` | `suite_tests` | 5516 | ronda r35 (suite completa en serie) |
| 2026-10-14 | `32d2561` | `suite_duracion_s` | 4119.01 | ronda r35 (suite completa en serie) |
| 2026-10-14 | `55df632` | `suite_fallos` | 0 | ronda r37 (suite completa en serie) |
| 2026-10-14 | `55df632` | `suite_tests` | 5528 | ronda r37 (suite completa en serie) |
| 2026-10-14 | `55df632` | `suite_duracion_s` | 4044.93 | ronda r37 (suite completa en serie) |
| 2026-10-14 | `7b21643` | `suite_fallos` | 0 | ronda r38 (suite completa en serie) |
| 2026-10-14 | `7b21643` | `suite_tests` | 5530 | ronda r38 (suite completa en serie) |
| 2026-10-14 | `7b21643` | `suite_duracion_s` | 4338.98 | ronda r38 (suite completa en serie) |
| 2026-10-14 | `df0ff4d` | `smoke_fallos` | 0 | vault_smoke 123/123 sobre df0ff4d |
| 2026-10-14 | `df0ff4d` | `banco_tareas_fallidas` | 0 | banco_agente --copiar-de /vcloud (copia; original intacto por hash), muestra 25 |
| 2026-10-14 | `df0ff4d` | `recall_pack_ajeno` | 1.0 | banco_agente --copiar-de /vcloud (copia; original intacto por hash), muestra 25 |
| 2026-10-14 | `efc8093` | `colisiones_de_sanadores` | 0 | C8 --colisiones sobre copia de /vcloud (original intacto por hash); 6 sanadores, 4 ociosos |
| 2026-10-14 | `efc8093` | `colisiones_de_sanadores` | 0 | C8 --colisiones sobre copia de /ans (original intacto por hash); 4 desenmascarados en ADR-004, completar y graph_fix fallidos |
| 2026-10-14 | `42a6fa8` | `suite_fallos` | 0 | pytest sobre suite.txt |
| 2026-10-14 | `42a6fa8` | `suite_tests` | 5600 | pytest sobre suite.txt |
| 2026-10-14 | `42a6fa8` | `suite_duracion_s` | 4874.47 | pytest sobre suite.txt |
| 2026-10-14 | `42a6fa8` | `smoke_fallos` | 0 | vault_smoke sobre 124 tools |
| 2026-10-15 | `ae3c5df` | `suite_fallos` | 0 | pytest sobre suite.txt |
| 2026-10-15 | `ae3c5df` | `suite_tests` | 5604 | pytest sobre suite.txt |
| 2026-10-15 | `ae3c5df` | `suite_duracion_s` | 3951.77 | pytest sobre suite.txt |
| 2026-10-15 | `ae3c5df` | `smoke_fallos` | 0 | vault_smoke sobre 124 tools |
| 2026-10-15 | `abd5cc2` | `suite_fallos` | 1 | pytest sobre suite.txt |
| 2026-10-15 | `abd5cc2` | `suite_tests` | 5624 | pytest sobre suite.txt |
| 2026-10-15 | `abd5cc2` | `suite_duracion_s` | 3997.04 | pytest sobre suite.txt |
| 2026-10-15 | `abd5cc2` | `smoke_fallos` | 0 | vault_smoke sobre 124 tools |
| 2026-10-15 | `26c2b04` | `suite_fallos` | 0 | pytest sobre suite.txt |
| 2026-10-15 | `26c2b04` | `suite_tests` | 5624 | pytest sobre suite.txt |
| 2026-10-15 | `26c2b04` | `suite_duracion_s` | 3436.61 | pytest sobre suite.txt |
| 2026-10-15 | `26c2b04` | `smoke_fallos` | 0 | vault_smoke sobre 124 tools |
| 2026-10-16 | `2fb0465` | `puertas_duracion_s` | 87.21 | vault_gate sobre 24 puertas |
| 2026-10-16 | `6940d1c` | `suite_fallos` | 1 | ronda r44 (suite completa en serie) |
| 2026-10-16 | `6940d1c` | `suite_tests` | 5736 | ronda r44 (suite completa en serie) |
| 2026-10-16 | `6940d1c` | `suite_duracion_s` | 4492.65 | ronda r44 (suite completa en serie) |
| 2026-10-16 | `0a5549d` | `suite_fallos` | 0 | ronda r45 (suite completa en serie) |
| 2026-10-16 | `0a5549d` | `suite_tests` | 5737 | ronda r45 (suite completa en serie) |
| 2026-10-16 | `0a5549d` | `suite_duracion_s` | 4567.03 | ronda r45 (suite completa en serie) |
| 2026-10-16 | `cc1aaa9` | `suite_fallos` | 1 | ronda r47 (suite completa en serie) |
| 2026-10-16 | `cc1aaa9` | `suite_tests` | 5758 | ronda r47 (suite completa en serie) |
| 2026-10-16 | `cc1aaa9` | `suite_duracion_s` | 4391.35 | ronda r47 (suite completa en serie) |
| 2026-10-16 | `d492db0` | `suite_fallos` | 1 | ronda r48 (suite completa en serie) |
| 2026-10-16 | `d492db0` | `suite_tests` | 5758 | ronda r48 (suite completa en serie) |
| 2026-10-16 | `d492db0` | `suite_duracion_s` | 4288.41 | ronda r48 (suite completa en serie) |
| 2026-10-16 | `c52f3e1` | `suite_fallos` | 0 | ronda r49 (suite completa en serie) |
| 2026-10-16 | `c52f3e1` | `suite_tests` | 5761 | ronda r49 (suite completa en serie) |
| 2026-10-16 | `c52f3e1` | `suite_duracion_s` | 4374.15 | ronda r49 (suite completa en serie) |
| 2026-10-16 | `9b897bb` | `suite_fallos` | 0 | ronda r50 (suite completa en serie) |
| 2026-10-16 | `9b897bb` | `suite_tests` | 5772 | ronda r50 (suite completa en serie) |
| 2026-10-16 | `9b897bb` | `suite_duracion_s` | 4288.26 | ronda r50 (suite completa en serie) |
| 2026-10-17 | `9c85e2f` | `suite_fallos` | 0 | ronda r51 (suite completa en serie) |
| 2026-10-17 | `9c85e2f` | `suite_tests` | 5804 | ronda r51 (suite completa en serie) |
| 2026-10-17 | `9c85e2f` | `suite_duracion_s` | 3474.25 | ronda r51 (suite completa en serie) |
| 2026-10-17 | `59f86d1` | `suite_fallos` | 0 | ronda r52 (suite completa en serie) |
| 2026-10-17 | `59f86d1` | `suite_tests` | 5844 | ronda r52 (suite completa en serie) |
| 2026-10-17 | `59f86d1` | `suite_duracion_s` | 2967.96 | ronda r52 (suite completa en serie) |
| 2026-10-17 | `f1e5ac6` | `suite_fallos` | 2 | ronda r53 (suite completa en serie) |
| 2026-10-17 | `f1e5ac6` | `suite_tests` | 5852 | ronda r53 (suite completa en serie) |
| 2026-10-17 | `f1e5ac6` | `suite_duracion_s` | 3187.43 | ronda r53 (suite completa en serie) |
| 2026-10-17 | `744d635` | `suite_fallos` | 0 | ronda r54 (suite completa en serie) |
| 2026-10-17 | `744d635` | `suite_tests` | 5852 | ronda r54 (suite completa en serie) |
| 2026-10-17 | `744d635` | `suite_duracion_s` | 2555.56 | ronda r54 (suite completa en serie) |
| 2026-10-17 | `9bf32f3` | `suite_fallos` | 0 | ronda r55 (suite completa en serie) |
| 2026-10-17 | `9bf32f3` | `suite_tests` | 5858 | ronda r55 (suite completa en serie) |
| 2026-10-17 | `9bf32f3` | `suite_duracion_s` | 3275.55 | ronda r55 (suite completa en serie) |
| 2026-10-17 | `e8500f7` | `suite_fallos` | 0 | ronda r56 (suite completa en serie) |
| 2026-10-17 | `e8500f7` | `suite_tests` | 5858 | ronda r56 (suite completa en serie) |
| 2026-10-17 | `e8500f7` | `suite_duracion_s` | 3269.91 | ronda r56 (suite completa en serie) |
| 2026-10-18 | `8c59a48` | `suite_fallos` | 1 | ronda r57 (suite completa en serie) |
| 2026-10-18 | `8c59a48` | `suite_tests` | 5863 | ronda r57 (suite completa en serie) |
| 2026-10-18 | `8c59a48` | `suite_duracion_s` | 3403.67 | ronda r57 (suite completa en serie) |
| 2026-10-18 | `6e4b926` | `suite_fallos` | 0 | ronda r58 (suite completa en serie) |
| 2026-10-18 | `6e4b926` | `suite_tests` | 5863 | ronda r58 (suite completa en serie) |
| 2026-10-18 | `6e4b926` | `suite_duracion_s` | 3620.26 | ronda r58 (suite completa en serie) |
| 2026-10-18 | `9e2ea6c` | `suite_fallos` | 0 | ronda r59 (suite completa en serie) |
| 2026-10-18 | `9e2ea6c` | `suite_tests` | 5863 | ronda r59 (suite completa en serie) |
| 2026-10-18 | `9e2ea6c` | `suite_duracion_s` | 3516.01 | ronda r59 (suite completa en serie) |
| 2026-10-23 | `0b6c042` | `contexto_agente_s` | 0.452 | medición real: parse 0.185s + pack 0.267s sobre vault temporal |
| 2026-10-23 | `0b6c042` | `skip_path_escritura_s` | 4.569 | medición real: onboarding doble pasada sobre proyecto demo con git (2.ª pasada = 5 skipped, 0 escrituras) |
| 2026-10-23 | `0b6c042` | `contexto_agente_s` | 0.587 | medición real: parse 0.27s + pack 0.317s sobre vault temporal |
| 2026-10-23 | `0b6c042` | `contexto_agente_s` | 0.461 | medición real: parse 0.186s + pack 0.275s sobre vault temporal |
| 2026-10-23 | `0b6c042` | `contexto_agente_s` | 0.454 | medición real: parse 0.177s + pack 0.277s sobre vault temporal |
| 2026-10-23 | `0b6c042` | `contexto_agente_s` | 0.484 | medición real: parse 0.215s + pack 0.269s sobre vault temporal |
| 2026-10-23 | `0b6c042` | `contexto_agente_s` | 0.739 | medición real: parse 0.283s + pack 0.456s sobre vault temporal |
| 2026-10-23 | `0b6c042` | `skip_path_escritura_s` | 4.438 | medición real: onboarding doble pasada sobre proyecto demo con git (2.ª pasada = 5 skipped, 0 escrituras) |
| 2026-10-23 | `0b6c042` | `contexto_agente_s` | 0.454 | medición real: parse 0.185s + pack 0.269s sobre vault temporal |
| 2026-10-23 | `0b6c042` | `contexto_agente_s` | 0.709 | medición real: parse 0.297s + pack 0.412s sobre vault temporal |
| 2026-10-23 | `35ba058` | `skip_path_escritura_s` | 1.051 | medición real: onboarding doble pasada sobre proyecto demo con git (2.ª pasada = 5 skipped, 0 escrituras) |
| 2026-10-23 | `35ba058` | `skip_path_escritura_s` | 1.105 | medición real: onboarding doble pasada sobre proyecto demo con git (2.ª pasada = 5 skipped, 0 escrituras) |

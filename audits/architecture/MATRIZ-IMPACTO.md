# Matriz de impacto y cambio (CHG-XXXX)

Cada corrección de esta ronda, con los recursos y contratos que alcanza. El
"antes/después" se contrasta con el grafo: si el cambio introduce o elimina
relaciones, se declaran.

| change_id | Razón | Recursos afectados | Contratos afectados | Dependientes | QG afectadas | Pruebas | Documentos | Riesgos | Rollback | Verificación |
|---|---|---|---|---|---|---|---|---|---|---|
| **CHG-01** | QA-RC-02g: la puerta no puede pasar con subchecks no ejecutados | `audits/fase2/colector_qg.py` (contrato de subchecks),Quality Gates QG-00..QG-06 | contrato de acreditación de puertas | `politica_qg.py`, `catalogo-qg.yaml` | QG-02, QG-03, QG-04, QG-05, QG-06 | `tests/test_colector_qg.py` (30) | `audits/architecture/trazabilidad-qg.md` | Un subcheck sin verificador propio queda `no_ejecutado` y bloquea: más estricto, no más laxo | `git revert` del commit | recibos externos con artefacto por subcheck |
| **CHG-02** | QA-RC-02h: la CLI del colector era incompatible con su propia función | `colector_qg.py` (`main`, `colectar`) | CLI de mantenimiento | — | QG-00..QG-07 | `tests/test_colector_qg.py` (CLI como proceso) | `RESPUESTA-DEL-EJECUTOR.md` | Un error de argumentos debe fallar explícito (exit 2), nunca PASS | `git revert` | `python audits/fase2/colector_qg.py --help` y flujo completo |
| **CHG-03** | QA-RC-02i: la CI aceptaba jobs sin identidad verificable | `colector_qg.py` (`estado_ci`, `jobs_de_run`) | acreditación de CI | GitHub Actions (API) | QG-07 | `tests/test_colector_qg.py` (jobs de otro run, duplicados, null, paginación) | `audits/architecture/CI-EVIDENCIA.md` | Sin jobs legibles la CI queda BLOCKED: correcto, pero bloquea | `git revert` | QG-07 sigue BLOCKED mientras la CI no conclude |
| **CHG-04** | QA-RC-05: el recorrido no aislaba ni verificaba | `audits/fase2/recorrido_terceros_r07.py` | recorrido de terceros | wheel/sdist, CLI, MCP | QG-03, QG-05, QG-06 | el propio recorrido (27/27) | `audits/fase2/MVP-terceros.md` | — | `git revert` | 27/27 pasos |
| **CHG-05** | Reversión de una decisión no ratificada: las fichas de deuda habían pasado de `a_eliminar` a `permanente` sin autorización | `scripts/vault_arch.py` (fichas de los pares gobernanza→meta_toolkit y →autoria) | registro de cruces | `scripts/arch-baseline.json` (5 entradas, sin cambio), `reconciliar_archify.py` | QG-01 | `vault_arch --check --strict` | `QA-RC-03-CRUZES.md`, `divergencias-archify.yaml` | Volver a `a_eliminar` **reabre** el adeudado con su fecha límite: es el estado correcto | `git revert` | `vault_arch --check --strict` ok |
| **CHG-06** | Mecanismo verificable para reconciliar divergencias | `audits/fase2/reconciliar_archify.py` (nuevo `_divergencias_aceptadas`), `audits/architecture/divergencias-aceptadas.yaml` | contrato del reconciliador | `divergencias-archify.yaml` | QG-00, QG-01 | `tests/test_arquitectura_trazabilidad.py` | `divergencias-archify.md` | Riesgo de usarlo como apagafuegos: solo silencia con `ratificado: true` **y** evidencia | `git revert` (el mecanismo es aditivo) | lista vacía ⇒ las 10 divergencias se siguen listando |
| **CHG-07** | Capa de trazabilidad (constitución, inventario, grafo, fichas, informes) | `audits/architecture/**`, `docs/architecture/CONSTITUCION-ARQUITECTONICA.md` | ninguno (aditivo) | fuentes vivas del repositorio | ninguna | `tests/test_arquitectura_trazabilidad.py` (10) | toda la capa | Que la capa se desincronice: lo vigila su propio test (reproducibilidad) | `git revert` | generación determinista + test de reproducibilidad |
| **CHG-08** | Corrección del defecto de AP-39 en runtime limpio | *(no implementado en esta ronda: DIF-03)* | — | — | QG-02 | — | `hallazgos-qg02.md` (INC-0015) | — | — | pendiente |

## Antes/después en el grafo

| Métrica | Antes (capa inexistente) | Después |
|---|---|---|
| Recursos inventariados | 0 | 699 |
| Verificados / no verificados | — | 686 / 13 |
| Relaciones con fundamento | 0 | 703 |
| Documentos con reconciliación de estado | 0 | 24 (RECONCILIACION-HISTORICA.md) |
| Fichas de divergencia con clasificación | 0 | 10 |
| Fichas de hallazgo con escenario | 0 | 15 |
| Veredictos QA con ficha | 0 | 56 |

**Relaciones nuevas:** ninguna en el grafo de producto (la capa es aditiva).
**Relaciones eliminadas:** ninguna.
**Derivados afectados:** `audits/architecture/{inventario-maestro.yaml,
grafo-trazabilidad.json, divergencias-archify.yaml, hallazgos-qg02.yaml,
registro-veredictos.yaml, *.md}` — todos se regeneran con
`generar_inventario.py` / `generar_fichas.py` / `generar_informe.py`.

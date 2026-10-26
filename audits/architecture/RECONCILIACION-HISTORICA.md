# RECONCILIACIÓN HISTÓRICA — qué sigue vigente y qué no

**SHA de referencia:** el del árbol en que se redacta (ver
`audits/architecture/mediciones.json`).
**Clasificación:** `VIGENTE` · `SUPERADO` · `CORREGIDO` · `CONTRADICHO` ·
`HISTÓRICO` · `NO_VERIFICADO` · `PENDIENTE_DECISIÓN`.

Los originales **se conservan**. Este documento no reescribe la historia: dice
qué documento manda hoy y qué queda como evidencia de una revisión anterior.

## A. Registros canónicos (mandan; la capa nueva solo los enlaza)

| Documento | Qué afirmaba / qué afirma | Vigencia | Nota |
|---|---|---|---|
| `vault-obsidian-architecture.md` | El manifiesto del estándar | **VIGENTE** | Fuente normativa; la constitución lo enlaza, no lo sustituye |
| `scripts/vault_arch.py` (`CONTEXTS`, `PRESUPUESTO_DE_CRUCES`) | Contextos, puertos y cruces | **VIGENTE** | **Es la verdad de la arquitectura.** El reconciliador lo llama "la verdad" y el snapshot "evidencia auxiliar" |
| `scripts/arch-baseline.json` | Baseline de cruces fuera de puerto | **VIGENTE** | 5 entradas; reubicadas de `vault_norms_engine` a `vault_norms` (commit 59d0465); no crece |
| `audits/fase2/catalogo-qg.yaml` | Contrato de los Quality Gates | **VIGENTE** | Catálogo; la política ejecutable vive en `politica_qg.py` y los subchecks en `colector_qg.py` |
| `audits/fase2/inventario-deuda.yaml` | Deuda registrada (12 TD) | **VIGENTE** | Fuente de la deuda; `deuda-inconsistencias.md` señala sus desalineaciones |
| `normas/<código>/` (82 paquetes) | Normas con guard y sanador | **VIGENTE** | Fuente de las invariantes INV-03/INV-05 |
| `docs/product/prd-cli.md`, `prd-mcp.md`, `runtime-contract.md` | PRD CLI/MCP y contrato de runtime | **NO_VERIFICADO** | Declarados como contrato del producto; esta ronda **no** ha contrastado su texto con el comportamiento medido. Pendiente de reconciliación |
| `docs/adr/0001-*`, `0002-*` | Decisiones de distribución (toolkit híbrido) y del puente de scripts | **VIGENTE** | ADR aceptados; son la referencia de la frontera de producto de §A de la constitución |

## B. Documentos de diseño superados por implementación

| Documento | Qué afirmaba | Vigencia | Por qué |
|---|---|---|---|
| `audits/fase2/L2-diseno-final.md` | Diseño de TD-0003: inversión, `checks[]`, `completo` | **SUPERADO** | Implementado (51b5cd1, 667a6a5, 532f19e). Se conserva como diseño de referencia |
| `audits/fase2/R04-diseno-td0008.md` | Diseño de la cuarentena de `--clean` | **SUPERADO** | Implementado (cc85491) y endurecido (2a98dfd, 532f19e). Conserva el diseño de la máquina de estados |
| `audits/fase2/L2-analisis-q04-q07.md` | Análisis de los cruces Q04–Q07 | **HISTÓRICO** | El análisis sigue siendo válido como diagnóstico; la conclusión (cruces eliminados) **no** se sostiene: ver `QA-RC-03-CRUZES.md` |
| `audits/fase2/L4-auditoria.md`, `L4-documental.txt` | Auditoría documental de L4 | **HISTÓRICO** | Cuadra de una ronda concreta; no describe el estado actual |
| `audits/fase2/backlog.md` | Pendientes de fase 2 | **PENDIENTE_DECISIÓN** | Varias entradas ya tienen implementación; su estado real está en `deuda-inconsistencias.md` |

## C. Evidencias (se conservan; cada una atada a su ejecución)

| Documento | Qué afirmaba | Vigencia |
|---|---|---|
| `audits/fase2/logs/*.txt|json` | Salidas de verificación de rondas anteriores | **HISTÓRICO** — evidencia de su SHA, no del candidato actual |
| `audits/handoff/logs/*` | Evidencia de la ronda 1B | **HISTÓRICO** |
| `audits/fase2/mediciones.json` y `diagnostico-escenario-*.json` | Hechos medidos de esta ronda | **VIGENTE** (se regeneran) |
| `%TEMP%\opencode\qg-recibos-final` (externos al árbol) | Recibos por subcheck del candidato | **VIGENTE mientras el SHA no cambie**; fuera del árbol por diseño (circularidad) |

## D. Dictámenes QA (autoridad independiente; ramas propias)

| Rama / commit | Qué afirmaba | Vigencia |
|---|---|---|
| `origin/qa/review-release-cli-mcp-29c1a15-20261025` (a9e0143) | R09: subchecks, CLI, CI, recorrido | **VIGENTE como restricción**: QA-RC-02g/h/i y QA-RC-05 están implementados; QA-RC-03 sigue pendiente |
| `origin/qa/review-release-cli-mcp-5836474-20261025` (628df53) | R08: recibos, CI, recorrido | **SUPERADO** por el dictamen de 29c1a15 |
| `origin/qa/review-release-cli-mcp-4595aea-20261025` (fabe442) | R07 | **SUPERADO** |
| `origin/qa/review-release-cli-mcp-4c66fc2-20261025` (a9e0143 → 628df53) | R07 | **SUPERADO** |
| Ramas anteriores (4396273, bfca45a, 0580b7e) | R05–R06 | **HISTÓRICO**: sus restricciones se hanpowdered o superado; ver `registro-veredictos.yaml` |
| `audits/handoff/RESPUESTA-QA.md` (rama de trabajo) | Copia local del buzón de QA | **DERIVADO**: el canónico es la rama QA |

## E. Snapshot de Archify (evidencia de otra revisión)

| Documento | Qué afirmaba | Vigencia |
|---|---|---|
| `.archify/candidata-*.json`, `.archify/mapa-contextos.*.json` | Mapa de contextos de **otra revisión** | **HISTÓRICO por diseño**: es la evidencia externa contra la que el reconciliador comprueba el registro vivo. **No se sustituye**: se acepta divergencia o se re-toma el snapshot (ver `divergencias-archify.md`) |
| `.archify/extraccion-registro.json` | Extracción del registro | **HISTÓRICO** (misma revisión que el snapshot) |

## F. Documentos de esta capa (aditivos)

| Documento | Estado |
|---|---|
| `docs/architecture/CONSTITUCION-ARQUITECTONICA.md` | **DRAFT — PENDIENTE DE RATIFICACIÓN** |
| `audits/architecture/inventario-maestro.yaml` | Derivado de las fuentes vivas |
| `audits/architecture/grafo-trazabilidad.json` | Derivado; relaciones con fundamento declarado |
| `audits/architecture/{divergencias-archify,hallazgos-qg02,registro-veredictos}.yaml` | Derivados de la medición y de las ramas QA |
| `audits/architecture/{trazabilidad-qg,deuda-inconsistencias,estado-y-trazabilidad}.md` | Derivados; se regeneran con `generar_informe.py` |

## G. Conflictos abiertos que este documento NO resuelve

1. **PRD CLI/MCP y contrato de runtime** no verificados contra el
   comportamiento medido: puede haber contradicción entre el texto y el
   producto. **NO_VERIFICADO** — requiere una ronda de contraste.
2. **`audits/fase2/backlog.md`** puede contener entradas ya implementadas.
3. **Las diez divergencias** del reconciliador: pendientes de decisión del
   propietario (fichas DIV-01…DIV-10).
4. **El sandbox canónico** tiene 14 hallazgos reales de contenido: el
   vault de evidencia no está limpio (INC-0001…INC-0014).
5. **El producto deja 1 violación** (AP-39) en un runtime recién creado
   (INC-0015): contradice la invariante INV-10.

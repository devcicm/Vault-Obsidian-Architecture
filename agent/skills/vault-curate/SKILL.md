---
name: vault-curate
description: Ejecuta el circuito de curación por lotes de la Fábrica de Conocimiento (SPEC-04, SP-05) cruzando banderas de ejecutores (.flags.jsonl), cola de propagación y fuentes /raw mediante vault_propagate --curate-plan y --curate-apply.
---

# Skill: `vault-curate` — Curador Batch de la Fábrica de Conocimiento (`SP-05`)

## Cuándo activar
- Al cerrar una jornada o lote de ejecuciones de agentes con perfil `ejecutor` (`VAULT_MCP_ROL=ejecutor` o `VAULT_MCP_TOKENS=ejecutor:...`).
- Cuando existan banderas abiertas en `00_System/.flags.jsonl` (`vault_ronda --flags --status open`) o elementos pendientes en `00_System/propagation-queue.json`.
- Cuando una ingesta (`vault_ingest`) reporte `conflict_candidates` que requieran contraste `PAT-7` en lugar de *last-write-wins*.

## Flujo obligatorio (perfil `operador`)

1. **Inspección sin efectos secundarios (`dry-run`):**
   ```bash
   python scripts/vault_propagate.py --curate-plan
   ```
   Revisa `groups`, `unassigned_flags` y `conflict_warnings`.
2. **Triaje de banderas sin destino o ruido:**
   ```bash
   python scripts/vault_propagate.py --resolve-flag FLAG-001 --flag-status dismissed --resolution-note "Duplicada"
   ```
3. **Resolución de conflictos sin sobrescribir (`PAT-7`):**
   ```bash
   python scripts/vault_propagate.py --mark-contradicts 07_Knowledge/a.md --other-note 07_Knowledge/b.md --reason "Posturas divergentes"
   ```
4. **Aplicación gobernada en lote:**
   ```bash
   python scripts/vault_propagate.py --curate-apply --agent curator
   ```
   Aplica únicamente cambios que superan el pre-vuelo `scan_poison`, estampa `source_flags`/`trace_ref`, transiciona cada bandera a `applied`, anota fila `curated` en `00_System/.change-log.jsonl` (`AP-74`) y deja acta en `19_Audits/curation/`.

## Reglas invariantes
- Nunca otorgar perfil `operador` al agente ejecutor; el ejecutor solo levanta banderas con `vault_ronda --flag`.
- Cero dependencias externas, cero bases de datos y cero embeddings: todo vive en Markdown + JSONL + Git.

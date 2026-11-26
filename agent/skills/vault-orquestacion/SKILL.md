---
name: vault-orquestacion
description: "Trigger: lifecycle orchestration, durable execution, DAG workflow, ACID transactions, Saga compensation, Dispose RAII pattern, graceful shutdown, resource leaks. Guides diagnosing, designing, implementing, and documenting the 5-pillar execution lifecycle (DAG, execution, durability/ACID, resilience/Saga, Dispose/RAII) in any project using existing vault tools."
allowed-tools: Bash(vault *) Bash(python *) Read Glob Grep
argument-hint: "[--project SLUG] [--path REPO_PATH] [--profile ligero|servicio|distribuido]"
entry-point: none
version: "1.0"
---

# vault-orquestacion

Orchestrates the 5-pillar modern execution lifecycle across any target project
(CLI/toolkit, API/service, or distributed workflow) and records its architecture,
flows, patterns, requirements, tests, and recovery runbooks in the governed vault
with zero new tools and zero third-party dependencies.

Reference framework: `docs/MODO-AGENTICO-ORQUESTACION.md`.

## Hard rules

- **Profile first, never over-engineer.** Classify the target project as **Perfil A (Ligero/CLI)**, **Perfil B (Servicio/API)**, or **Perfil C (Distribuido/Durable)** before proposing infrastructure.
- **No-database promise for VOA vaults.** When applying this framework inside Vault-Obsidian-Architecture itself, apply it strictly to toolkit execution processes (Perfil A: atomic writes, locks, JSONL checkpoints, Git pre-SHA compensation, stdlib `TopologicalSorter`, `ExitStack`, graceful shutdown) — never introduce databases, embeddings, or third-party brokers into the vault storage model.
- **Evidence before notes (AP-45).** Scan the real codebase with `vault_pattern_list --scan-path` before saving patterns or flows; never invent patterns not backed by code or an approved design requirement.
- **Enforce `Dispose` / RAII and ACID explicitly.** Every implementation plan must audit resource lifetimes (files, locks, sockets, timers, subprocesses) for deterministic idempotent disposal and protect multi-step mutations against partial corruption (ACID or Saga compensation).
- **Never point tools at the spec repo root.** Always target `VAULT_ROOT` (a real project vault or `vault-sandbox/` during testing).

## Prerequisites

- `VAULT_ROOT` set to an initialized vault (or `vault-sandbox/` inside the spec repo) and `VAULT_AGENT` identifying the active agent.
- Target project slug registered in the vault and source path accessible for read-only scanning.
- Read `docs/MODO-AGENTICO-ORQUESTACION.md` to select the exact invariants for the chosen profile.

## When not to use it

- To heal a pre-existing broken vault without losing notes: use `vault-sanacion`.
- To perform initial greenfield/brownfield repository onboarding from scratch: use `vault-onboard`.
- To consolidate executor `FLAG-NNN` curation batches (`SP-05`): use `vault-curate`.

## Steps

```bash
# 1. Load existing architectural and resilience context from the vault
vault run vault_context_pack --query "arquitectura flujos patrones resiliencia dispose acid"

# 2. Scan the target repository for existing patterns across all 5 categories (PAT-10)
vault run vault_pattern_list --scan-path /ruta/al/proyecto

# 3. Record the requirement for durable lifecycle, ACID integrity, and Dispose/RAII
vault run vault_requirement_save --project mi-proyecto --title "Ciclo de vida durable ACID y Dispose" --type functional --priority high --description "Aplicar 5 pilares de ejecucion, transacciones ACID, compensacion Saga y liberacion determinista Dispose/RAII" --acceptance_criteria "Idempotencia probada, cero estados parciales corruptos y cero fugas de recursos"

# 4. Record the DAG workflow and its triggers/steps
vault run vault_flow_save --project mi-proyecto --name "Orquestacion principal" --type workflow --description "Flujo modelado como DAG con checkpoints y compensacion" --triggers "cli,webhook" --steps "validar,adquirir_recurso,ejecutar_acid,checkpoint,dispose"

# 5. Persist detected concurrency, resilience, and architecture patterns with code evidence
vault run vault_pattern_save --project mi-proyecto --scan-path /ruta/al/proyecto --category concurrencia_resiliencia

# 6. Document execution infrastructure (workers, sandboxes, queues, shutdown)
vault run vault_infra_save --project mi-proyecto --name "Runtime y aislamiento de ejecucion" --type runtime --description "Perfil operativo, limites de timeout, aislamiento de procesos y graceful shutdown"

# 7. Register the recovery and replay runbook
vault run vault_runbook_save --project mi-proyecto --title "Recuperacion tras fallo y replay" --category incident --trigger "Fallo parcial de lote, timeout o caida de worker" --steps "1. Verificar ultimo checkpoint 2. Ejecutar compensacion Saga o rollback 3. Reanudar con replay idempotente"

# 8. Register verification tests for idempotency, rollback, and zero resource leaks
vault run vault_test_save --project mi-proyecto --title "Pruebas de idempotencia ACID y Dispose" --test_type integration --description "Valida doble ejecucion segura, rollback ante fallo y liberacion LIFO de recursos" --steps "1. Inyectar fallo a mitad de lote 2. Verificar compensacion 3. Reejecutar y comprobar cero fugas" --expected_result "Estado consistente, sin duplicados ni handles abiertos"

# 9. Review code changes against vault rules and close with health audit
vault run vault_code_review --path /ruta/al/proyecto --project mi-proyecto
vault run vault_audit
```

## Decision gates

| Situation | Action |
|---|---|
| Target is a CLI/toolkit or local script (Perfil A) | Use stdlib DAG (`TopologicalSorter`), atomic write-temp-rename, file locks, JSONL checkpoints, Git pre-SHA rollback, and `with`/`ExitStack`; reject brokers or external DBs |
| Target is a multi-step distributed write without single ACID DB | Design an explicit Saga with idempotent steps and compensating actions plus Transactional Outbox |
| Code acquires files, locks, sockets, timers, or subprocesses outside scope guards | Block sign-off until wrapped in deterministic RAII / `Dispose` (`with`, `ExitStack`, `using`, `defer`) with idempotent `dispose()` and `SIGTERM`/`SIGINT` draining |
| `vault_pattern_list --scan-path` finds zero resilience/dispose patterns | Document the gap as an explicit requirement (`vault_requirement_save`) before writing implementation code |
| `vault_audit` reports broken links or schema errors after saving notes | Fix the generated notes before closing the session |

## Output contract

Report: this skill and version (`v1.0`); the selected profile (`Perfil A`, `Perfil B`, or `Perfil C`);
the patterns detected vs. gaps identified across the 5 pillars (including `ACID` and `Dispose` / RAII);
the exact paths of created or updated vault notes (requirement, flow, patterns, infra, runbook, test);
and the closing `vault_code_review` and `vault_audit` results.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Orchestration plan and vault documentation completed cleanly |
| 1 | Validation, scan, or vault write error |
| 2 | Argument error in one of the invoked tools |

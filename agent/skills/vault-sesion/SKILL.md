---
name: vault-sesion
description: "Trigger: start or close a work session, orient in a vault, before and after working. Runs the session protocol: health at the start, what to load, how to write and delete, and the closing checks."
allowed-tools: Bash(vault *) Read Glob Grep
argument-hint: "[--project SLUG]"
entry-point: none
version: "1.0"
---

# vault-sesion

The daily session protocol of the standard, step by step. Its source is
`vault.kernel.protocolo_de_sesion.PROTOCOLO_DE_SESION`; when that registry and this
skill disagree, the registry wins and this skill is corrected.

## Hard rules

- Every write goes through a tool (`vault_write`, `vault_delete`, the `*_save`): never
  edit a note's file by hand; the tool keeps the guards, the history and the log.
- Delete only with `vault_delete --reason`: the change log keeps who deleted what and why.
- Compare the closing health with the starting one; a session must not leave it lower
  without saying why.

## Prerequisites

- `VAULT_ROOT` points at the vault and `VAULT_AGENT` names who signs.
- For the drift steps: the project is registered and linked (`vault run vault_project --list`).

## Steps

```bash
# Start: version, index, structure, starting health, the user's stable context
vault run vault_standard_upgrade --check
vault run vault_reindex --check
vault run vault_validate --check structure
vault run vault_audit
vault run vault_preferences --context
vault run vault_drift_detect --project <slug> --mode snapshot   # only with a linked project

# Remember before writing (see the vault-recordar skill)
vault run vault_context_pack --query "<question>"

# Before a bulk operation: a baseline to measure its impact
vault run vault_delta --snapshot

# Close: what changed in the code without notes, index and graph, final health
vault run vault_drift_detect --project <slug> --mode report      # only with a linked project
vault run vault_reindex --graph
vault run vault_audit
```

## Decision gates

| Situation | Action |
|---|---|
| `vault_standard_upgrade --check` reports an older standard | Upgrade before writing; do not write against an old contract |
| `vault_reindex --check` is not `index_ok` | Run `vault run vault_reindex` before searching |
| An error envelope carries `recovery.tool` | Follow it (`vault run vault_section --list` for `INVALID_FOLDER`, `vault run vault_project --list` for `PROJECT_NOT_FOUND`) |
| The closing audit is lower than the starting one | Report which issues appeared and leave them in `nextActions`, never silently |
| The drift report lists changed files | Update their existing notes first (a module note declares `source_file:`); create only what has no note |

## Output contract

Report: the starting and closing `healthScore`, the notes written or deleted (paths),
the drift report summary when a project is linked, and anything left pending with its
next action.

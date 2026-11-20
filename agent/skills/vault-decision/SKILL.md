---
name: vault-decision
description: "Trigger: we changed our mind, replace a decision, supersede, undo a note. Records the new decision, declares that it supersedes the old one without deleting it, and shows how to undo."
allowed-tools: Bash(vault *) Read Glob Grep
argument-hint: "--path OLD_NOTE --by NEW_NOTE [--apply]"
entry-point: vault_supersede
version: "1.0"
---

# vault-decision

A decision that changes is not rewritten: the new one is written, the old one declares
`superseded_by:` and stays on disk. Readers get the current one; the history is kept.

## Hard rules

- Never edit or delete the old decision to "update" it: write the new note and supersede.
- `vault_supersede` measures by default; it writes only with `--apply`.
- A closed decision that must change is superseded, not reopened (AP-07, AP-75).

## Steps

```bash
# 1. Write the new decision (an ADR in 03_Decisions, or a note where the old one lives)
vault run vault_write --folder 07_Knowledge --title "Cola de eventos con NATS" \
  --tags eventos arquitectura --content "$(printf '%s\n' \
    'Los servicios publican sus eventos en NATS JetStream desde marzo.' \
    'Cada consumidor durable confirma lo procesado y se puede reprocesar.' \
    'Reemplaza a Redis Streams porque necesitabamos retencion por tiempo.')"

# 2. Measure, then declare that it supersedes the old one
vault run vault_supersede --path 07_Knowledge/cola-de-eventos-con-redis.md --by cola-de-eventos-con-nats
vault run vault_supersede --path 07_Knowledge/cola-de-eventos-con-redis.md --by cola-de-eventos-con-nats --apply

# 3. The trace: the substitution is in the change log and the previous version is kept
vault run vault_change_log --query
vault run vault_undo --list 07_Knowledge/cola-de-eventos-con-redis.md
```

## Decision gates

| Situation | Action |
|---|---|
| The old note already declares a different `superseded_by:` | Stop: it is a decision already taken; repeat with `--replace` only if the owner confirms |
| `IMMUTABLE_NOTE` | Follow its hint: the section's immutability mode decides whether substitution is allowed |
| The substitution was a mistake | `vault run vault_undo --restore <old note>` restores the version saved before it |

## Arguments

| Argument | Description |
|---|---|
| `--path` | The superseded note, path relative to the vault |
| `--by` | The note that rules, as a wikilink target: file name, alias or path |
| `--apply` | Write (by default it only measures) |
| `--replace` | Replace a different `superseded_by:` already written |

## Output contract

Report: the new note's path, the superseded note and its `superseded_by:`, the
`version_saved` and `change_log` of the substitution, and how to undo it.

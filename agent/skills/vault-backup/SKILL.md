---
name: vault-backup
description: Creates a vault backup and proves it restores — rehearsal in an isolated destination, comparison and an explicit recovery report. Use before trusting any backup, before destructive maintenance, or when the owner asks whether the backups work.
allowed-tools: Bash(python *) Bash(vault *) Read Glob Grep
argument-hint: "[--label LABEL] [--verify]"
version: "1.0"
---

# vault-backup

A backup is not evidence until it restores. This skill creates one, rehearses
the recovery **somewhere that is not the vault**, and reports what the
rehearsal proved and what it did not.

## Usage

```bash
# Create a backup with a recognisable label
vault run vault_backup --label pre-mantenimiento

# Create it and verify the manifest (the tool's own check)
vault run vault_backup --verify

# Inspect what exists before choosing one
vault run vault_backup_list --limit 10

# Rehearse the recovery in an ISOLATED destination (never the vault itself)
vault run vault_restore --confirm <destino-aislado>
```

`vault run vault_backup …` is the installed CLI (the wheel); the restore tool
has its own arguments in `scripts/README.md`. From a checkout of the
standard, `python scripts/vault_backup.py …` takes the same arguments as the
CLI.

## Arguments

| Argument | Description |
|---|---|
| `--label` | A label for the backup, so the next reader knows why it exists |
| `--verify` | Verify the backup manifest as part of the run |

## Procedure

1. **Backup** with a label that says why: `pre-mantenimiento`,
   `antes-de-mover`, `antes-de-release`. A date alone ages without meaning.
2. **List** the backups and pick one — never the newest by faith: check its
   label and date.
3. **Rehearse** the recovery into a **disposable destination**, never the
   vault in use. The restore mutates what it is pointed at.
4. **Compare**: the rehearsal destination has the same notes and the same
   content for the files you check. A note count is a start, not a proof —
   compare content, and say which files you compared.
5. **Report the limits**: what the rehearsal proved, what it did not (other
   volumes, the running MCP server, the git history of the vault), and where
   the backup lives.

## Execution evidence

In the result to the user, report: this skill and version, the backup label
and path, the rehearsal destination, what was compared and the outcome. **Do
not claim a backup works until the rehearsal ran.** If the rehearsal could not
run (no space, no isolated destination, permissions), say so — an untested
backup is a stated risk, not a success.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Backup created — and, if rehearsed, the recovery compared |
| 1 | Backup or rehearsal failed; the report says which step and why |

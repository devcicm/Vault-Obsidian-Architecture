---
name: vault-backup
description: "Trigger: backup, respaldo, does the backup work, before destructive maintenance. Creates a vault backup, verifies its manifest and rehearses the restore on a disposable copy of the vault."
allowed-tools: Bash(python *) Bash(vault *) Read Glob Grep
argument-hint: "[--label LABEL] [--verify BACKUP_NAME]"
version: "1.1"
---

# vault-backup

A backup is not evidence until it restores. Create one, verify its manifest,
rehearse the restore **on a copy of the vault**, compare, and report what the
rehearsal proved and what it did not.

Version 1.1. The previous definition remains next to this one as `SKILL-v1.0.md`.

## Hard rules

- **Never run `vault_restore` against the vault in use.** It always restores
  into the vault `VAULT_ROOT` resolves to and replaces its content; it has no
  destination flag. Rehearse only with `VAULT_ROOT` pointing at a copy.
- `--verify` takes the **name** of an existing backup; it does not create one.
- Do not claim a backup works until the rehearsal ran and the comparison
  passed. An untested backup is a stated risk, not a success.

## Prerequisites

- An initialized vault (`VAULT_ROOT` set) and the product installed (`vault --version`).
- Free disk space for one more copy of the vault (the rehearsal copy).

## When not to use it

- To recover a single note: use `vault run vault_undo --list <path>`, then
  `vault run vault_undo --restore <path>`.
- To undo the last operations of the vault's git history: `vault run vault_undo --commits`.

## Steps

```bash
# 1. Create the backup with a label that says why (a date alone ages without meaning)
vault run vault_backup --label pre-mantenimiento

# 2. List the backups and take the exact name of the one just created
vault run vault_backup_list --limit 10

# 3. Verify that backup's manifest (integrity of the copy, not yet a restore)
vault run vault_backup --verify <BACKUP_NAME>

# 4. Rehearse on a disposable COPY: backups live in <vault>/vault-backups/,
#    so copying the vault folder carries them along
ENSAYO="$(mktemp -d)/vault-ensayo"
cp -r "$VAULT_ROOT" "$ENSAYO"
VAULT_ROOT="$ENSAYO" vault run vault_restore --backup_name <BACKUP_NAME> --confirm true

# 5. Compare the restored copy with the vault: notes only, not system state
#    (dot files such as .tool-trace.json record the restore itself)
diff -r --exclude=vault-backups --exclude='.*' "$VAULT_ROOT" "$ENSAYO"
```

## Decision gates

| Situation | Action |
|---|---|
| `--verify` reports a broken manifest | Stop: the backup is not usable; create a new one and say so |
| No space or no writable temp dir for the copy | Do not rehearse on the vault itself; report the backup as untested |
| `diff` shows differences in notes | Report each differing file; the backup does not restore those as they were |
| `diff` shows only derived files (indexes, graph) | Expected after a restore; say they are regenerated with `vault run vault_reindex` |

## Arguments

| Argument | Description |
|---|---|
| `--label` | A label for the backup, so the next reader knows why it exists |
| `--verify` | Name of an existing backup whose manifest to verify (it does not create a backup) |

## Output contract

Report: this skill and version; the backup name and its path under
`vault-backups/`; the `--verify` result; the rehearsal copy path; what was
compared (files or the `diff` scope) and the outcome; and the limits — what the
rehearsal did not prove (other volumes, the running MCP server, the vault's git
history).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Backup created, manifest verified and, if rehearsed, the restore compared |
| 1 | A step failed; the report says which one and why |
| 2 | Argument error (argparse) |

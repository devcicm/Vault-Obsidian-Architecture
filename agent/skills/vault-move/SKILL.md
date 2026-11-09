---
name: vault-move
description: Moves a note or a whole folder inside the vault with an impact preflight, a dry run and verification. Use when a note is in the wrong section, when a folder must move, or before any relocation that other notes link to — it reports every inbound link and updates them.
allowed-tools: Bash(python *) Bash(vault *) Read Glob Grep
argument-hint: "--from NOTE --to NOTE | --folder FROM --to-folder TO [--dry-run] [--impact] [--type TYPE] [--json]"
version: "1.0"
---

# vault-move

Move a note or a folder **inside** the vault, and leave no link behind.

This is the note/folder relocation. Moving the **vault root** —the directory
itself— is a different, multi-consumer decision (active configuration,
clients, history): that one is *not* this command, and it needs the owner's
approval; see the proposal `vault-root-rename-path-impact-and-migration-
proposal` before attempting it.

## Usage

```bash
# Impact analysis before moving anything
vault run vault_move --from 07_Knowledge/nota.md --to 05_Patterns/nota.md --impact

# Dry run: what would move and which links would be rewritten
vault run vault_move --from 07_Knowledge/nota.md --to 05_Patterns/nota.md --dry-run

# Move the note (rewrites inbound links)
vault run vault_move --from 07_Knowledge/nota.md --to 05_Patterns/nota.md

# Move a whole folder
vault run vault_move --folder 07_Knowledge/conceptos --to-folder 05_Patterns/conceptos
```

`vault run vault_move …` is the installed CLI (the wheel). From a checkout of
the standard, `python scripts/vault_move.py …` takes the same arguments.

## Arguments

| Argument | Description |
|---|---|
| `--from` | Note origin, relative to the vault root |
| `--to` | Note destination |
| `--folder` | Folder origin (moves the whole folder) |
| `--to-folder` | Folder destination |
| `--dry-run` | Show what would happen without touching anything |
| `--type` | New `type` for the note (validated against the section map) |
| `--impact` | Find every inbound link and other consequences, without moving |
| `--json` | Machine-readable output |

## Procedure

1. **Read the impact first**: run with `--impact` and check every inbound
   link. A note that other notes cite moves with them rewritten; a note whose
   citations you did not see is a note whose context you did not move.
2. **Dry run** for the exact list of operations.
3. **Move**, then **verify**: the destination exists, the origin does not, and
   the inbound links resolve — the envelope reports `links_updated`.
4. If a section has a declared policy (`00_System/inmutable.json`), a move
   out of an immutable section is a **content change**: it needs the owner's
   approval, not a flag.

## Execution evidence

In the result to the user, report: this skill and version, the origin and
destination, the inbound links found and updated, and whether the run was a
dry run. Do not claim a move happened unless the run or a readback confirms
it. If the destination already existed, say what happened to it — the tool
refuses to overwrite, and a refusal is not a move.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Moved and verified — or, with `--dry-run`/`--impact`, the plan is complete |
| 1 | Refused: destination exists, invalid path, or immutable policy |

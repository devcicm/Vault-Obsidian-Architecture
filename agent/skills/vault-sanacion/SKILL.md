---
name: vault-sanacion
description: Diagnoses a pre-existing vault and returns the 12-phase healing plan with a per-phase verdict and the evidence behind it. Read-only — it never writes. Use when taking over a vault written without the standard, when the user asks to "heal", "sanar", "clean up" or "audit" an existing vault, or before deciding which corrective tools to run and in what order.
allowed-tools: Bash(python *) Bash(vault *) Read Glob Grep
argument-hint: "[--phase N] [--strict]"
version: "2.0"
---

# vault-sanacion

Measure a pre-existing vault against the 12 phases of
`docs/MODO-AGENTICO-SANACION.md`, then decide.

Version 2.0. The previous definition is kept next to this one as
`SKILL-v1.0.md`.

## Usage

```bash
# Full plan for the auto-detected vault
vault run vault_sanacion

# Point it at a foreign vault — this is where it earns its keep
VAULT_ROOT=/path/to/other/vault vault run vault_sanacion

# One phase in detail
vault run vault_sanacion --phase 8

# CI gate: exit 1 if any phase applies or could not be measured
vault run vault_sanacion --strict
```

`vault run vault_sanacion …` is the installed CLI (the wheel). From a checkout
of the standard, `python scripts/vault_sanacion.py …` takes the same arguments.

## Arguments

| Argument | Description |
|---|---|
| `--phase` | Detail for a single phase (1..12); out of range is `INVALID_VALUE` |
| `--strict` | Exit 1 if any phase applies or is `unknown` |

## Target vault

Resolved by `vault_io` auto-detection, or forced with the `VAULT_ROOT`
environment variable. There is no root flag. The tools that accept one are a
short, closed list with a reason each — the ones that write to the vault they
are pointed at, and the ones that exist to measure a foreign vault read-only —
and a diagnostic that only reads its session's vault is neither. The list
lives in rule 1 of `AGENTS.md`, not here: a count copied into a skill is the
figure that ages first.

Export `VAULT_STRICT_ROOT=1` so an unsafe detection fails instead of falling
back to the repo root. The envelope reports `vault_root` and
`vault_root_origin`; read them before trusting the verdicts.

## Output

An envelope with all 12 phases. Each carries a `verdict` — `applies`, `clean`
or `unknown` — the `evidence` behind it, a `measured` count, the standard tool
that does the writing, and `decision_not_automatable` where the phase hinges on
a judgement no tool can make.

`unknown` is not `clean`. It means the measurement failed, and a phase that
could not be measured is a phase you still owe.

## It does not write

Ever. Rule 2 of the agentic mode — the subagent proposes, it does not write —
applied to the tool that proposes. Every phase names the standard tool that
performs the write, with its guard and its `.change-log.json` entry. A
diagnostic tool holding write permission is a second author with no norm
governing it.

## Why the order matters

The phase order is the contract, not a presentation choice. Relocating notes
(7) after fixing links (8) re-breaks every link you just repaired. Knowing
which phases you may skip is what makes the order safe to follow.

## Reference

`docs/MODO-AGENTICO-SANACION.md` — the phases, the rules, and the decisions no
tool takes. `docs/SKILLS.md` — the skill layer itself.

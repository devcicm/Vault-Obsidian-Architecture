---
name: vault-sdd-init
description: Spec-Driven Development (SDD) documentation initializer. Generates the SDD specification suite for a project under docs/sdd/. Use when starting a new project, adding SDD documentation to an existing project, or when the user asks to "initialize SDD" or "create SDD docs".
allowed-tools: Bash(python *) Bash(vault *) Read Write Glob Grep
argument-hint: "[--bilingual] [--check] [--dry-run] [--force] [--vault-root PATH]"
version: "2.0"
---

# vault-sdd-init

Initialize Spec-Driven Development documentation for a project.

Version 2.0. The previous definition is kept next to this one as
`SKILL-v1.0.md`.

Generates the SDD specification suite under `docs/sdd/`: README.md,
00-principles.md, 01-state-machines.md, 02-implementation.md, 03-usage.md,
04-antipatterns.md, 05-reference-matrix.md, 06-documentation-methodology.md,
07-process-antipatterns.md, 08-roadmap.md, 09-metrics.md, 10-appendices.md,
integrity-report.json and gaps.md. The list is owned by `EXPECTED_OUTPUTS` in
`vault_sdd_init.py`; `--dry-run` prints it.

## Usage

```bash
# Basic (bilingual Spanish/English)
vault run vault_sdd_init --bilingual

# Dry-run (preview without writing)
vault run vault_sdd_init --bilingual --dry-run

# Staleness gate: exit 1 if docs/sdd/ lags behind the norm registry
vault run vault_sdd_init --check

# Force regeneration of what is derived (never gaps.md)
vault run vault_sdd_init --bilingual --force

# Custom vault root
vault run vault_sdd_init --vault-root /path/to/vault --bilingual
```

`vault run vault_sdd_init …` is the installed CLI (the wheel). From a checkout
of the standard, `python scripts/vault_sdd_init.py …` takes the same arguments.

## Arguments

| Argument | Description |
|---|---|
| `--bilingual` | Generate docs in Spanish and English |
| `--check` | Compare the range on disk against `NORM_CATALOG`; exit 1 if stale (AP-47) |
| `--dry-run` | Preview changes without writing |
| `--force` | Regenerate every derived document — never overwrites `gaps.md` |
| `--vault-root` | Custom vault root path (default: auto-detect) |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | All files generated successfully — or, with `--check`, the disk matches the registry |
| 1 | Validation error, missing dependencies — or, with `--check`, a stale derived artifact |

## Staleness gate (AP-47)

The range in `04-antipatterns.md` is derived from `NORM_CATALOG` on every run,
so a freshly written file never lies. What ages is the file from the *previous*
run: it gets committed and then sits still while the registry grows underneath
it. `--check` is the only thing that looks. Measured before it existed:
`AP-01..AP-35` in the body, `AP-01..AP-25` in the index, `AP-01..AP-47` in the
registry — one month and three releases of drift, with every other gate green.

`gaps.md` is the one file declared *manual fill*, and `--force` does not touch
it. `--force` lifts idempotency over what is generated, not the ban on
overwriting what a person wrote.

## Output

All files are written to `<vault-root>/docs/sdd/`. The `integrity-report.json`
contains validation results. Run with `--dry-run` first to preview.

## Containment (AP-36)

Every write happens under `<vault-root>/docs/sdd/`. The skill is **read-only**
over the rest of the vault: it never modifies existing notes and never creates
notes outside `docs/sdd/`. Without `--vault-root`, the target is resolved by
`vault_io` auto-detection, which in this repo yields `vault-sandbox/`.

## Norm coverage

`04-antipatterns.md` is generated from `vault_norms.NORM_CATALOG` — the range
is derived, never hardcoded. `--dry-run` reports `missing_norms`, computed by
contiguity: if `AP-36` exists, every lower code must exist too. A non-empty
list means the registry has a hole, not that the skill failed.

## Reference

Full documentation, installation and lifecycle: `docs/SKILLS.md`.

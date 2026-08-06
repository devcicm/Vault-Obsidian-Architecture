---
name: vault-sdd-init
description: Spec-Driven Development (SDD) documentation initializer. Generates the 14-document SDD specification suite for a project. Use when starting a new project, adding SDD documentation to an existing project, or when the user asks to "initialize SDD" or "create SDD docs".
allowed-tools: Bash(python *) Read Write Glob Grep
argument-hint: [--bilingual] [--check] [--dry-run] [--force]
---

# vault-sdd-init

Initialize Spec-Driven Development documentation for a project.

Generates the complete 14-file SDD specification suite under `docs/sdd/`:
00-principles.md, 01-state-machines.md, 02-implementation.md, 03-usage.md,
04-antipatterns.md, 05-reference-matrix.md, 06-documentation-methodology.md,
07-process-antipatterns.md, 08-roadmap.md, 09-metrics.md, 10-appendices.md,
README.md, integrity-report.json, gaps.md.

## Usage

```bash
# Basic (bilingual Spanish/English)
python scripts/vault_sdd_init.py --bilingual

# Dry-run (preview without writing)
python scripts/vault_sdd_init.py --bilingual --dry-run

# Force overwrite existing files
python scripts/vault_sdd_init.py --bilingual --force

# Custom vault root
python scripts/vault_sdd_init.py --vault-root /path/to/vault --bilingual
```

## Arguments

| Argument | Description |
|---|---|
| `--bilingual` | Generate docs in Spanish and English |
| `--check` | Compare the range on disk against `NORM_CATALOG`; exit 1 if stale (AP-47) |
| `--dry-run` | Preview changes without writing |
| `--force` | Regenerate the 13 derived documents — never overwrites `gaps.md` |
| `--vault-root` | Custom vault root path |

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

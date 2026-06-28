---
name: vault-sdd-init
description: Spec-Driven Development (SDD) documentation initializer. Generates the 14-document SDD specification suite for a project. Use when starting a new project, adding SDD documentation to an existing project, or when the user asks to "initialize SDD" or "create SDD docs".
allowed-tools: Bash(python *) Read Write Glob Grep
argument-hint: [--bilingual] [--dry-run] [--force]
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
| `--dry-run` | Preview changes without writing |
| `--force` | Overwrite existing SDD files |
| `--vault-root` | Custom vault root path |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | All files generated successfully |
| 1 | Validation error or missing dependencies |

## Output

All files are written to `docs/sdd/`. The `integrity-report.json` contains
validation results. Run with `--dry-run` first to preview.

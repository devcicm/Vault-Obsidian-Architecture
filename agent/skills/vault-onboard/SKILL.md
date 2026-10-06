---
name: vault-onboard
description: Populates a vault from a code project that has none — git archaeology, module map, retroactive ADRs, environment and infrastructure notes. Use when a project has code but no vault, when the user asks to "onboard", "bootstrap a vault", "poblar el vault" or "document this repo", or right after vault_init on an empty vault.
allowed-tools: Bash(python *) Bash(vault *) Read Glob Grep
argument-hint: "--project NAME --path REPO [--dry-run] [--depth N] [--max-commits N] [--skip NN ...]"
version: "2.0"
---

# vault-onboard

Take a code project with no vault and populate one, respecting the norms from
the first note.

Version 2.0. The previous definition is kept next to this one as
`SKILL-v1.0.md`; it taught a `--skip` value the script accepted and silently
ignored.

## Usage

```bash
# Always start here — writes nothing, shows what it would create
vault run vault_onboard --project mi-api --path /ruta/al/repo --dry-run

# For real, into the vault VAULT_ROOT points at
VAULT_ROOT=/ruta/al/vault-nuevo vault run vault_onboard \
    --project mi-api --path /ruta/al/repo

# Bound the git window explicitly; the cap is reported, never silent
vault run vault_onboard --project mi-api --path /repo --max-commits 2000

# Skip sections you will write by hand — two-digit codes, not folder names
vault run vault_onboard --project mi-api --path /repo --skip 07 13
```

`vault run vault_onboard …` is the installed CLI (the wheel). From a checkout of
the standard, `python scripts/vault_onboard.py …` takes the same arguments.

## Arguments

`--project` and `--path` are required; the rest have defaults, and the
tool's own help owns them. This table must list exactly the flags of
the argparse — `tests/test_skills_versionadas.py` fails otherwise.

| Argument | Description |
|---|---|
| `--project` | Project name — becomes the slug under each section |
| `--path` | Path to the code repository. **Read-only**: the tool never writes there |
| `--dry-run` | Show the plan without writing |
| `--no-git` | Skip git archaeology entirely |
| `--git-phases` | Maximum number of development phases reconstructed from the commit history |
| `--depth` | How deep to walk the source tree for the module map |
| `--max-commits` | Cap on commits read; hitting the cap lands in `warnings` |
| `--max-modules` | Cap on modules mapped |
| `--skip` | Two-digit section codes to leave alone (`07`, `13`, …). Any other value is rejected with exit 2, and the tool's help lists the accepted ones |
| `--lang` | The project's programming language. When given it replaces detection from the manifest and file extensions |
| `--agent` | Agent name recorded in the frontmatter |

## Read the envelope, not just `ok`

Three fields carry the honesty of the run, and an agent that ignores them will
report a vault richer than the one that exists:

- **`degraded[]`** — detection steps that could not complete. A project file
  that could not be read is written to the vault as "the project does not have
  this", which is an absence asserted without checking. Each entry names the
  step and the error.
- **`skipped_no_evidence[]`** — notes deliberately not written because there was
  no real content behind them. A note whose body is `_Pendiente_` raises coverage
  and lowers reliability (AP-45).
- **`sections_left_empty_by_design[]`** — `18_Bugs`, `19_Audits` and
  `20_Quarantine` stay empty. They are event-driven; populating them at bootstrap
  would be exactly AP-45. That is also why `--skip` does not accept them.

## Order

If the project already has loose documentation, run `vault_migrate_docs` **first**
— staging, classification, distribution — so the onboard does not duplicate what
someone already wrote.

The resulting vault should need no healing. If `vault_audit` reports metadata
debt over it, the generator is broken, not the vault. Check with
`vault_sanacion` and `vault_audit`.

## Nothing is invented

Healing preserves; onboarding does not invent. There is no prior content to
protect here — what applies instead is that a note is only written when there is
something real behind it. A commit is not an ADR unless it changed an
architectural decision. A `TODO` in the code is a `TODO`, not an observability
note. A module does not deserve a note for existing; the threshold is that
something else references it. Reconstructed notes are born `stub` or `draft`,
never `implemented` — that would assert a review nobody performed.

## Reference

`docs/MODO-AGENTICO-ONBOARDING.md` — the 7 phases and the decisions no tool
takes. `docs/SKILLS.md` — the skill layer itself.

---
name: vault-onboard
description: Populates a vault from a code project that has none — git archaeology, module map, retroactive ADRs, environment and infrastructure notes. Use when a project has code but no vault, when the user asks to "onboard", "bootstrap a vault", "poblar el vault" or "document this repo", or right after vault_init on an empty vault.
allowed-tools: Bash(python *) Read Glob Grep
argument-hint: [--project NAME] [--path REPO] [--dry-run] [--depth N] [--max-commits N] [--skip SECTION]
---

# vault-onboard

Take a code project with no vault and populate one, respecting the norms from
the first note.

## Usage

```bash
# Always start here — writes nothing, shows what it would create
python scripts/vault_onboard.py --project mi-api --path /ruta/al/repo --dry-run

# For real, into the vault VAULT_ROOT points at
VAULT_ROOT=/ruta/al/vault-nuevo python scripts/vault_onboard.py \
    --project mi-api --path /ruta/al/repo

# Bound the git window explicitly; the cap is reported, never silent
python scripts/vault_onboard.py --project mi-api --path /repo --max-commits 2000

# Skip a section you will write by hand
python scripts/vault_onboard.py --project mi-api --path /repo --skip 07_Knowledge
```

## Arguments

| Argument | Description |
|---|---|
| `--project` | Project name — becomes the slug under each section |
| `--path` | Path to the code repository. **Read-only**: the tool never writes there |
| `--dry-run` | Show the plan without writing |
| `--no-git` | Skip git archaeology entirely |
| `--git-phases` | Reconstruct development phases from commit history |
| `--depth` | How deep to walk the source tree for the module map |
| `--max-commits` | Cap on commits read; hitting the cap lands in `warnings` |
| `--max-modules` | Cap on modules mapped |
| `--skip` | Section to leave alone |
| `--lang` | Language of the generated prose |
| `--agent` | Agent name recorded in the frontmatter |

## Read the envelope, not just `ok`

Three fields carry the honesty of the run, and an agent that ignores them will
report a vault richer than the one that exists:

- **`degraded[]`** — detection steps that could not complete. A project file
  that could not be read is written to the vault as "the project does not have
  this", which is an absence asserted without checking. Eleven steps report here.
- **`skipped_no_evidence[]`** — notes deliberately not written because there was
  no real content behind them. A note whose body is `_Pendiente_` raises coverage
  and lowers reliability (AP-45).
- **`sections_left_empty_by_design[]`** — `18_Bugs`, `19_Audits` and
  `20_Quarantine` stay empty. They are event-driven; populating them at bootstrap
  would be exactly AP-45.

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

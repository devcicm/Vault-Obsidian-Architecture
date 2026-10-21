---
name: vault-toolkit-audit
description: Audits every tool of the toolkit against its declared function — it runs each tool's documented example for real, checks its envelope against the contract, and measures whether a second run rewrites the vault. Use when auditing the toolkit, when a tool's behaviour has to be measured instead of declared, or before declaring a change closed.
allowed-tools: Bash(python *) Bash(vault *) Read Glob Grep
argument-hint: "[--todo] [--grupo N] [--tools a,b] [--check] [--freeze] [--doc]"
version: "1.0"
---

# vault-toolkit-audit

Measure every tool against what it declares, and record the measurement.

A tool's `example` is its contract: the command a consumer can copy. The
audit **runs** it (in a disposable copy of the sandbox, prepared like the
AP-37 bank prepares it) and asks six questions per tool:

| Control | Question |
|---|---|
| C0 | Does the tool exist and does the example parse into runnable lines? |
| C1 | Does the example exercise the work the tool declares (`side_effects`), or only look? |
| C2 | Does the envelope cover the contract (`declared_returns`), and does the example run without the tool rejecting it? |
| C3 | If the tool promises idempotence (`unchanged`), does the **second** run leave the vault byte-identical? |
| C4 | Do the CLI and the MCP dispatch of the same owner agree? |
| C5 | Does the tool degrade with a reason when an optional dependency is missing? |

## Usage

```bash
# Full sweep — the catalog, every tool (this is the slow one: it copies the
# sandbox once per example line)
vault run vault_toolkit_audit --todo

# One group, or a suspect tool
vault run vault_toolkit_audit --grupo 15
vault run vault_toolkit_audit --tools vault_write,vault_read

# Gate: exit 1 if the last sweep found debt that is not frozen
vault run vault_toolkit_audit --check

# Re-freeze the baseline with this sweep's verdicts
vault run vault_toolkit_audit --todo --freeze

# Regenerate the published report from the last sweep
vault run vault_toolkit_audit --doc
```

`vault run vault_toolkit_audit …` is the installed CLI (the wheel). From a
checkout of the standard, `python scripts/vault_toolkit_audit.py …` takes the
same arguments.

## Arguments

| Argument | Description |
|---|---|
| `--todo` | Full sweep of the catalog |
| `--tools` | List separated by commas |
| `--grupo` | Number(s) of group according to the numbering in scripts/README.md |
| `--check` | Exit 1 with new debt not frozen |
| `--strict` | Together with --check: frozen debt still in red also fails |
| `--freeze` | Re-freezes the baseline with the verdict of this run |
| `--admitir-nuevos` | Together with --freeze: explicit (and visible) permission to open new debt |
| `--doc` | Regenerates docs/auditorias/auditoria-toolkit.md from the last-run |
| `--parcial` | Together with --doc: allows publishing the report even when the last-run does not cover the whole catalog |

## The baseline only shrinks

`scripts/toolkit-audit-baseline.json` holds the tools whose defect is
**known and accepted**, each with a reason and an owner. It is the same
rule the other guards follow: a debt that is not written down is not a debt,
it is a surprise.

Freezing writes what this sweep found; growing it needs
`--freeze --admitir-nuevos`, which lists the newcomers in the envelope. A
frozen defect is a promise to fix it — so freeze only after the tool was
repaired or its example corrected, and write the reason where the freeze
happens.

## What the verdicts mean

- **OK** — the example runs, the envelope covers the contract, and the
  promise (idempotence, if any) holds on the second run.
- **DEFECTO** — a promise is broken. Only these enter the baseline.
- **MEJORA** — the example does less than the tool declares. Not debt.
- **NO-VERIFICABLE** — the tool cannot be exercised from the CLI (a
  node-native tool is exercised by the MCP server). The reason is written
  down; a silent exemption is the failure this instrument exists to avoid.

## Reading the result

The report is derived (`docs/auditorias/auditoria-toolkit.md`, regenerated
with `--doc`): never edited by hand. It declares its own scope — a sweep of
one group says so, and a report generated from a partial sweep says so too
(`--parcial`).

The scope lives in the last-run (`scripts/toolkit-audit-last.json`), which
records the tools it covered. A report that does not cover the catalog is
not the state of the catalog, and the tool refuses to publish it as such.

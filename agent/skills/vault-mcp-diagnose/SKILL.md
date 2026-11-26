---
name: vault-mcp-diagnose
description: "Trigger: MCP server failed, tools not showing in client, concurrency timeout, handshake error, diagnose MCP. Verifies MCP catalog sync, contracts, concurrency config, vault root resolution, and server startup health."
allowed-tools: Bash(vault *) Bash(python *) Bash(node *) Read Glob Grep
argument-hint: "[--root PATH]"
entry-point: none
version: "1.0"
---

# vault-mcp-diagnose

Diagnoses MCP server integration issues end-to-end without mutating any vault notes:
catalog parity, tool contracts, CQRS read/write concurrency (`VAULT_MCP_MAX_READS`),
root resolution (`VAULT_ROOT`), and environment variable hygiene.

## Hard rules

- **Read-only diagnosis.** Never rewrite notes or mutate the vault while diagnosing MCP.
- Always verify `VAULT_ROOT` points to a real vault (or `vault-sandbox/` inside the spec repo), never to the spec repository root.
- Report concrete tool outputs and exit codes; never guess why a client failed to connect without checking the handshake and catalog first.

## Prerequisites

- Python >= 3.9 and Node.js >= 18 available on `PATH`.
- `VAULT_ROOT` set to the target vault (or `--root` passed to `vault mcp-path`).
- Steps 1–3 (`vault_entorno.py` and `vault_mcp_catalog.py`) are standard-repo maintenance checks and require a checkout of `Vault-Obsidian-Architecture`; steps 4–5 run in any installed environment.

## When not to use it

- To fix corrupted notes or broken wikilinks inside a vault: use `vault-sanacion`.
- To install the product from scratch: follow `docs/INSTALACION-LIMPIA.md`.

## Steps

```bash
# 1. Inspect the active environment and MCP limits (spec repo checkout)
python scripts/vault_entorno.py --limites

# 2. Verify catalog parity: Python TOOLS_CATALOG vs mcp/nodejs/tools-catalog.json (spec repo checkout)
python scripts/vault_mcp_catalog.py --check

# 3. Verify tool contracts: tool-spec.json coverage and AP-48 single backend (spec repo checkout)
python scripts/vault_mcp_catalog.py --check-contracts

# 4. Verify vault health and root resolution (installed CLI)
vault run vault_validate --check structure

# 5. Print the exact server path and client config snippet for the target vault
vault mcp-path --root "$VAULT_ROOT"
```

## Decision gates

| Situation | Action |
|---|---|
| `vault_mcp_catalog --check` fails | Run `python scripts/vault_mcp_catalog.py --sync` in the spec repo checkout before re-testing |
| `vault_mcp_catalog --check-contracts` fails | Fix missing `tool-spec.json` entry or AP-48 dual-backend conflict before exposing the tool |
| `VAULT_ROOT` resolves to the spec repo root | Stop: export `VAULT_ROOT` to a real vault or `vault-sandbox/` |
| Client times out on parallel reads | Check `VAULT_MCP_MAX_READS` (default 4) and verify Node >= 18 is the binary configured in `.mcp.json` |

## Output contract

Report: this skill and version (`v1.0`); the resolved `VAULT_ROOT` and `VAULT_MCP_MAX_READS`;
the pass/fail status of catalog parity, contracts, and vault structure validation; and
the exact remediation command for any failing check.

---
name: vault-recordar
description: "Trigger: what do we know about, recall, find context, before deciding or writing. Builds a context pack for a question, checks that notes exist and reads them whole."
allowed-tools: Bash(vault *) Read Glob Grep
argument-hint: "--query QUESTION [--budget TOKENS] [--incluir-historico]"
entry-point: vault_context_pack
version: "1.0"
---

# vault-recordar

Turn a question into the context the vault already holds, within a token budget,
before deciding or writing anything new.

## Hard rules

- Ask the vault before answering from memory: a decision taken in an earlier session
  lives in a note, not in the conversation.
- Answers are current truth: history (superseded ADRs, archived, deprecated, obsolete
  or revoked notes, archived sources, quarantine) is left out and counted in
  `history_excluded`. Ask for it with `--incluir-historico` only when the question is
  about history.
- Link a note only after a search confirmed it exists (SP-02).

## Steps

```bash
# 1. The context pack for the question, within the budget
vault run vault_context_pack --query "how do services publish events" --budget 4000

# 2. Check that a note exists before linking it
vault run vault_search --query "cola de eventos"

# 3. Read whole the notes the pack or the search point to
vault run vault_read --path 07_Knowledge/cola-de-eventos-con-nats.md

# 4. Only for questions about what was decided before and replaced
vault run vault_context_pack --query "event queue decisions" --incluir-historico
```

## Decision gates

| Situation | Action |
|---|---|
| The pack is empty or `warnings` say the index is stale | Run `vault run vault_reindex`, then ask again |
| `history_excluded` lists a superseded note | The current one is its successor; read it, not the old one |
| The answer synthesizes several notes and will be worth it next session | Save it as a draft with `vault run vault_ingest` citing the notes it came from |

## Arguments

| Argument | Description |
|---|---|
| `--query` | The question, in plain words |
| `--intento` | What the answer is for (explorar, documentar, cambiar, depurar, revisar): weighs the candidates |
| `--budget` | Token budget of the pack |
| `--top-k` | Maximum candidate notes |
| `--excerpt-tokens` | Tokens per excerpt |
| `--min-score` | Drop candidates below this score |
| `--no-preferences` | Do not inject the user's `must` preferences |
| `--format` | `json` or `markdown` |
| `--explain` | Include the rerank signals per note |
| `--incluir-historico` | Also return history, penalized, instead of current truth only |
| `--max-sensitivity` | Exclude notes whose `cia_sensitivity` exceeds `public`, `internal`, or `restricted` |

## Output contract

Report: the question, the notes included with their path, what was left out as history
(`history_excluded`), and the warnings of the pack.

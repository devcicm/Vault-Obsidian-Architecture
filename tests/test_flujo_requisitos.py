"""QA-FL-05 -- a requirement walks `STATUS_TRANSITIONS` or is rejected untouched (AP-41).

The flow QA reproduced it on a fresh vault: REQ-001 created as `draft` accepted
`--status approved`, then `implemented`, then `draft` again, and a new
requirement could be born `verified`. None of those moves exist in
`vault_norms_catalog.STATUS_TRANSITIONS`, and nothing went to `.history/`, so
the audit's AP-41 replay could not see them either. The note and its change-log
row were also signed `agent: system` whatever `VAULT_AGENT` said.

Every test drives the published CLI on a copy of an initialised vault. A
rejected transition must leave the requirement ledger, its projection, the note
and the vault's own git history exactly as they were.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict

import pytest

from apoyo import correr_tool, entorno, git_en
from vault_base import copiar_vault
from vault_lib import parse_frontmatter_with_body
from vault_norms_catalog import STATUS_TRANSITIONS

TOOL = "vault_requirement_save"
AGENT = "qa-flujo"
BASE = ("--project", "demo", "--title", "Login seguro", "--type", "functional",
        "--priority", "must-have", "--description", "Descripcion suficiente del requisito.")


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return copiar_vault(tmp_path / "vault", "demo")


def _save(vault: Path, *extra: str):
    return correr_tool(TOOL, *BASE, *extra, env=entorno(vault, VAULT_AGENT=AGENT))


def _ledger_state(vault: Path) -> Dict[str, str]:
    """Hash of every file the requirement flow owns, plus the vault's git HEAD.

    Tool traces and the voice counter are written by `wrap_main` on every call,
    successful or not; they are not requirement state and are left out.
    """
    owned = [vault / "00_System" / ".change-log.json", vault / "00_System" / "change-log.md"]
    owned += sorted(p for p in (vault / "14_Requirements").rglob("*") if p.is_file())
    state = {p.relative_to(vault).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in owned if p.is_file()}
    state["git:HEAD"] = git_en(vault, "rev-parse", "HEAD")
    return state


def _transition_rows(vault: Path):
    rows = json.loads((vault / "00_System" / ".change-log.json").read_text(encoding="utf-8"))
    return [row for row in rows if isinstance(row.get("requirement"), dict)]


def _walk_to(vault: Path, *states: str) -> None:
    for state in states:
        run = _save(vault, "--status", state)
        assert run.codigo == 0 and run.envelope["ok"], run.envelope


@pytest.mark.parametrize("path, target", [
    (("draft",), "approved"),
    (("draft",), "implemented"),
    (("draft", "reviewed", "approved", "implemented"), "draft"),
])
def test_illegal_transition_is_rejected_and_writes_nothing(vault, path, target):
    _walk_to(vault, *path)
    before = _ledger_state(vault)
    events_before = _transition_rows(vault)

    run = _save(vault, "--req-id", "REQ-001", "--status", target)

    env = run.envelope
    assert run.codigo == 1
    assert env["ok"] is False
    assert env["error_code"] == "illegal_status_transition"
    assert env["error"] == "illegal_status_transition"
    assert env["norm_code"] == "AP-41"
    assert env["from_status"] == path[-1]
    assert env["to_status"] == target
    assert env["allowed"] == sorted(STATUS_TRANSITIONS[path[-1]])
    assert env["recovery"]["action"] == "fix_input"
    assert _ledger_state(vault) == before
    assert _transition_rows(vault) == events_before


def test_new_requirement_cannot_be_born_in_a_closed_state(vault):
    before = _ledger_state(vault)

    run = _save(vault, "--status", "verified")

    env = run.envelope
    assert run.codigo == 1
    assert env["error_code"] == "illegal_status_transition"
    assert env["from_status"] is None
    assert env["to_status"] == "verified"
    assert env["allowed"] == ["draft", "reviewed"]
    assert _ledger_state(vault) == before
    assert not list((vault / "14_Requirements").rglob("req-*.md"))
    # The rejected call reserved no identifier: the next requirement is REQ-001.
    created = _save(vault)
    assert created.codigo == 0 and created.envelope["req_id"] == "REQ-001"


def test_legal_walk_is_recorded_signed_by_the_real_agent_and_replays(vault):
    _walk_to(vault, "draft", "reviewed", "approved", "implemented", "verified")

    rows = _transition_rows(vault)
    assert [(r["requirement"]["from"], r["requirement"]["to"]) for r in rows] == [
        (None, "draft"), ("draft", "reviewed"), ("reviewed", "approved"),
        ("approved", "implemented"), ("implemented", "verified")]
    assert {r["agent"] for r in rows} == {AGENT}
    index = json.loads((vault / "14_Requirements" / ".requirements-index.json")
                       .read_text(encoding="utf-8"))
    entry = index["requirements"][0]
    assert entry["status"] == "verified"
    assert [e["id"] for e in entry["events"]] == [r["id"] for r in rows]
    assert {e["agent"] for e in entry["events"]} == {AGENT}
    fm, _ = parse_frontmatter_with_body((vault / entry["relPath"]).read_text(encoding="utf-8"))
    assert fm["agent"] == AGENT and fm["status"] == "verified"

    replay = correr_tool("vault_reindex", "--check-indices", vault=vault)
    assert replay.codigo == 0, replay.envelope
    assert replay.envelope["ok"] is True


def test_same_state_update_is_still_accepted_without_a_transition(vault):
    """Previous behaviour: an edit that keeps the state writes no transition."""
    _walk_to(vault, "draft")
    rows_before = _transition_rows(vault)

    run = correr_tool(TOOL, "--project", "demo", "--req-id", "REQ-001", "--title",
                      "Login seguro v2", "--type", "functional", "--priority", "must-have",
                      "--description", "Otra descripcion suficiente.", "--status", "draft",
                      env=entorno(vault, VAULT_AGENT=AGENT))

    assert run.codigo == 0
    assert run.envelope["action"] == "updated"
    assert run.envelope["transition_logged"] is False
    assert _transition_rows(vault) == rows_before

#!/usr/bin/env python3
"""vault_session — Agent session lifecycle manager.

Tracks AI agent work sessions: start/end timestamps, agent identity, project
focus, planned tasks, completed tasks, knowledge acquired, decisions made.
Provides session observability and traceability.

Uses 04_Sessions/ as the canonical folder.

Usage:
    # Start a session
    python vault_session.py --start --agent claude --project ans \\
        --goal "Refactor error layer"

    # Append a task
    python vault_session.py --task "Split vault_errors.py" --status done

    # Append a knowledge item
    python vault_session.py --knowledge "D2: split god modules by responsibility"

    # Record a decision
    python vault_session.py --decision "Use Anthropic format for SKILL.md"

    # End the session
    python vault_session.py --end --summary "Refactor complete, tests passing"

    # Query active session
    python vault_session.py --active

    # List past sessions
    python vault_session.py --list --last 10

ARCHIVADA (politica de no-derogacion; ver scripts/_archived/README.md).
superseded_by: vault_delta.py
reason: La sesion se deriva del cambio real registrado, no de un log a mano.
"""

from __future__ import annotations


import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from vault_io import atomic_write_json, atomic_write_text, VAULT_ROOT
from vault_lib import utcnow
from vault_errors import wrap_main

SESSIONS_DIR = VAULT_ROOT / "04_Sessions"
ACTIVE_FILE = VAULT_ROOT / "00_System" / ".active-session.json"


def _read_active() -> dict | None:
    if not ACTIVE_FILE.exists():
        return None
    try:
        return json.loads(ACTIVE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_active(session: dict) -> None:
    ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(ACTIVE_FILE, session)


def _clear_active() -> None:
    if ACTIVE_FILE.exists():
        ACTIVE_FILE.unlink()


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.md"


def _md_frontmatter(session: dict) -> str:
    fm = ["---"]
    fm.append(f"id: {session['id']}")
    fm.append(f"title: Session {session['id'][:8]} — {session.get('goal', 'no goal')}")
    fm.append(f"agent: {session.get('agent', 'unknown')}")
    fm.append(f"project: {session.get('project', '')}")
    fm.append(f"createdAt: {session['started_at']}")
    fm.append(f"updatedAt: {session.get('ended_at', session['started_at'])}")
    fm.append(f"tags: {json.dumps(['session', session.get('project', ''), session.get('agent', '')])}")
    fm.append("type: session")
    fm.append("cia_integrity: high")
    fm.append("cia_availability: medium")
    fm.append("cia_sensitivity: internal")
    fm.append("status: active")
    fm.append(f"startedAt: {session['started_at']}")
    if session.get("ended_at"):
        fm.append(f"endedAt: {session['ended_at']}")
    fm.append("---")
    return "\n".join(fm) + "\n"


def _md_body(session: dict) -> str:
    lines = [
        f"# Session {session['id'][:8]}",
        "",
        f"**Agent:** {session.get('agent', 'unknown')}  ",
        f"**Project:** {session.get('project', '')}  ",
        f"**Started:** {session['started_at']}  ",
    ]
    if session.get("ended_at"):
        lines.append(f"**Ended:** {session['ended_at']}  ")
    if session.get("goal"):
        lines += ["", f"## Goal", "", session["goal"]]
    if session.get("summary"):
        lines += ["", f"## Summary", "", session["summary"]]
    if session.get("tasks"):
        lines += ["", "## Tasks"]
        for t in session["tasks"]:
            mark = "[x]" if t.get("status") == "done" else "[ ]"
            lines.append(f"- {mark} {t.get('description', '')}")
    if session.get("knowledge"):
        lines += ["", "## Knowledge Acquired"]
        for k in session["knowledge"]:
            lines.append(f"- {k}")
    if session.get("decisions"):
        lines += ["", "## Decisions Made"]
        for d in session["decisions"]:
            lines.append(f"- {d}")
    return "\n".join(lines) + "\n"


def vault_session_start(agent: str, project: str, goal: str) -> dict:
    if _read_active():
        return {"ok": False, "error": "A session is already active. End it first."}
    session_id = str(uuid.uuid4())
    started = utcnow()
    session = {
        "id": session_id,
        "agent": agent,
        "project": project,
        "goal": goal,
        "started_at": started,
        "ended_at": None,
        "summary": "",
        "tasks": [],
        "knowledge": [],
        "decisions": [],
    }
    _write_active(session)
    return {
        "ok": True,
        "session_id": session_id,
        "started_at": started,
        "path": str(_session_path(session_id).relative_to(VAULT_ROOT)).replace(
            "\\", "/"
        ),
    }


def vault_session_end(summary: str) -> dict:
    session = _read_active()
    if not session:
        return {"ok": False, "error": "No active session."}
    session["ended_at"] = utcnow()
    session["summary"] = summary
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    content = _md_frontmatter(session) + "\n" + _md_body(session)
    atomic_write_text(_session_path(session["id"]), content)
    _clear_active()
    return {
        "ok": True,
        "session_id": session["id"],
        "ended_at": session["ended_at"],
        "path": str(_session_path(session["id"]).relative_to(VAULT_ROOT)).replace(
            "\\", "/"
        ),
        "tasks_count": len(session.get("tasks", [])),
        "knowledge_count": len(session.get("knowledge", [])),
        "decisions_count": len(session.get("decisions", [])),
    }


def vault_session_task(description: str, status: str = "pending") -> dict:
    session = _read_active()
    if not session:
        return {"ok": False, "error": "No active session."}
    session["tasks"].append({"description": description, "status": status})
    _write_active(session)
    return {
        "ok": True,
        "task_added": description,
        "status": status,
        "tasks_count": len(session["tasks"]),
    }


def vault_session_knowledge(item: str) -> dict:
    session = _read_active()
    if not session:
        return {"ok": False, "error": "No active session."}
    session["knowledge"].append(item)
    _write_active(session)
    return {
        "ok": True,
        "knowledge_added": item,
        "knowledge_count": len(session["knowledge"]),
    }


def vault_session_decision(decision: str) -> dict:
    session = _read_active()
    if not session:
        return {"ok": False, "error": "No active session."}
    session["decisions"].append(decision)
    _write_active(session)
    return {
        "ok": True,
        "decision_added": decision,
        "decisions_count": len(session["decisions"]),
    }


def vault_session_active() -> dict:
    session = _read_active()
    if not session:
        return {"ok": True, "active": False, "message": "No active session."}
    return {
        "ok": True,
        "active": True,
        "session_id": session["id"],
        "agent": session.get("agent"),
        "project": session.get("project"),
        "goal": session.get("goal"),
        "started_at": session.get("started_at"),
        "tasks": session.get("tasks", []),
        "knowledge": session.get("knowledge", []),
        "decisions": session.get("decisions", []),
    }


def vault_session_list(last: int = 10) -> dict:
    if not SESSIONS_DIR.exists():
        return {"ok": True, "count": 0, "sessions": []}
    files = sorted(SESSIONS_DIR.glob("*.md"), reverse=True)
    sessions = []
    for f in files[:last]:
        try:
            text = f.read_text(encoding="utf-8")
            started = ""
            agent = ""
            project = ""
            for line in text.splitlines():
                if line.startswith("startedAt:"):
                    started = line.replace("startedAt:", "").strip()
                elif line.startswith("agent:"):
                    agent = line.replace("agent:", "").strip()
                elif line.startswith("project:"):
                    project = line.replace("project:", "").strip()
            sessions.append(
                {
                    "id": f.stem,
                    "started_at": started,
                    "agent": agent,
                    "project": project,
                    "path": str(f.relative_to(VAULT_ROOT)).replace("\\", "/"),
                }
            )
        except Exception:
            continue
    return {"ok": True, "count": len(sessions), "sessions": sessions}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Session — agent session lifecycle manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--start", action="store_true", help="Start a new session")
    parser.add_argument("--end", action="store_true", help="End the active session")
    parser.add_argument("--active", action="store_true", help="Show the active session")
    parser.add_argument("--list", action="store_true", help="List past sessions")
    parser.add_argument(
        "--task", metavar="DESC", help="Append a task to active session"
    )
    parser.add_argument(
        "--task-status", default="pending", choices=["pending", "done", "cancelled"]
    )
    parser.add_argument("--knowledge", metavar="ITEM", help="Append a knowledge item")
    parser.add_argument("--decision", metavar="TEXT", help="Record a decision")
    parser.add_argument(
        "--agent", default="claude", help="Agent name (default: claude)"
    )
    parser.add_argument("--project", help="Project focus")
    parser.add_argument("--goal", help="Goal description (for --start)")
    parser.add_argument("--summary", help="Summary (for --end)")
    parser.add_argument(
        "--last", type=int, default=10, help="Last N sessions (for --list)"
    )
    args = parser.parse_args()

    result: dict
    if args.start:
        if not args.project:
            print("--project is required with --start", file=sys.stderr)
            return 1
        if not args.goal:
            print("--goal is required with --start", file=sys.stderr)
            return 1
        result = vault_session_start(
            agent=args.agent, project=args.project, goal=args.goal
        )
    elif args.end:
        result = vault_session_end(summary=args.summary or "")
    elif args.task:
        result = vault_session_task(args.task, args.task_status)
    elif args.knowledge:
        result = vault_session_knowledge(args.knowledge)
    elif args.decision:
        result = vault_session_decision(args.decision)
    elif args.active:
        result = vault_session_active()
    elif args.list:
        result = vault_session_list(args.last)
    else:
        result = vault_session_active()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_session"))

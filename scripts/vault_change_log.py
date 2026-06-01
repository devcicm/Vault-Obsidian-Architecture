#!/usr/bin/env python3
"""
Vault Change Log Tool -- Record note lifecycle events in the vault.

Tracks: created, updated, deleted, moved actions on vault notes.
Writes to two targets:
  - 00_System/change-log.md  (Markdown table, readable in Obsidian)
  - 00_System/.change-log.json  (JSON array, queryable by agents)

GOVERNANCE RULE: before deleting any vault note, the agent MUST call:
  vault_change_log --action deleted --path <note> --reason <why>

Usage:
    python vault_change_log.py --action created --path "01_Projects/ans/status.md" --reason "New sprint" --agent claude
    python vault_change_log.py --action updated --path "03_Decisions/adr-001.md" --reason "Added context"
    python vault_change_log.py --action deleted --path "07_Knowledge/old.md" --reason "Duplicate of glossary/jwt.md"
    python vault_change_log.py --action moved --path "10_Migrated/old.md" --new_path "07_Knowledge/jwt.md" --reason "Promoted"
    python vault_change_log.py --query --last 20
    python vault_change_log.py --query --project "ans" --last 10
    python vault_change_log.py --query --action deleted
"""

import argparse
import json
import subprocess
import sys
from vault_errors import wrap_main
from vault_io import atomic_write_textVAULT_ROOT
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


SYSTEM_DIR = VAULT_ROOT / "00_System"
LOG_MD = SYSTEM_DIR / "change-log.md"
LOG_JSON = SYSTEM_DIR / ".change-log.json"

VALID_ACTIONS = ["created", "updated", "deleted", "moved"]
VALID_PROPAGATE_STRATEGIES = ["conservative", "transitive", "critical-path"]

SCRIPTS_DIR = Path(__file__).parent


def _read_json_log() -> List[Dict[str, Any]]:
    if not LOG_JSON.exists():
        return []
    try:
        return json.loads(LOG_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []


def _write_json_log(entries: List[Dict[str, Any]]) -> None:
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_text(LOG_JSON, json.dumps(entries, indent=2, ensure_ascii=False))


def _append_md_log(entry: Dict[str, Any]) -> None:
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)

    HEADER = (
        "# Change Log\n\n"
        "Registro automatico de cambios en el vault.\n\n"
        "| Timestamp | Action | Path | New Path | Reason | Agent |\n"
        "|---|---|---|---|---|---|\n"
    )

    existing = ""
    if LOG_MD.exists():
        try:
            existing = LOG_MD.read_text(encoding="utf-8")
        except OSError:
            pass
    if "| Timestamp |" not in existing:
        existing = HEADER

    ts = entry.get("timestamp", "")[:19]
    action = entry.get("action", "")
    path = entry.get("path", "")
    new_path = entry.get("new_path") or ""
    reason = entry.get("reason", "").replace("|", "\\|")
    agent = entry.get("agent", "")

    row = f"| {ts} | `{action}` | `{path}` | `{new_path}` | {reason} | {agent} |\n"
    atomic_write_text(LOG_MD, existing + row)


def _run_propagation(path: str, strategy: str) -> Dict[str, Any]:
    """Fire vault_propagate in background — does not block the changelog response."""
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "vault_propagate.py"),
        "--changed", path,
        "--strategy", strategy,
        "--action", "notify,queue",
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True, "strategy": strategy, "queued_async": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def vault_change_log_add(
    action: str,
    path: str,
    reason: str,
    agent: str = "claude",
    new_path: Optional[str] = None,
    propagate: Optional[str] = None,
) -> Dict[str, Any]:
    action = action.lower()
    if action not in VALID_ACTIONS:
        return {"ok": False, "error": f"Invalid action '{action}'. Valid: {VALID_ACTIONS}"}

    if not reason or not reason.strip():
        return {"ok": False, "error": "reason is required and cannot be empty"}

    if action == "moved" and not new_path:
        return {"ok": False, "error": "new_path is required for action 'moved'"}

    if propagate and propagate not in VALID_PROPAGATE_STRATEGIES:
        return {"ok": False, "error": f"Invalid propagate strategy '{propagate}'. Valid: {VALID_PROPAGATE_STRATEGIES}"}

    entry: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "action": action,
        "path": path,
        "new_path": new_path,
        "reason": reason.strip(),
        "agent": agent,
        "timestamp": _utcnow(),
    }

    entries = _read_json_log()
    entries.append(entry)
    _write_json_log(entries)
    _append_md_log(entry)

    response: Dict[str, Any] = {
        "ok": True,
        "id": entry["id"],
        "action": action,
        "path": path,
        "log_md": str(LOG_MD.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "log_json": str(LOG_JSON.relative_to(VAULT_ROOT)).replace("\\", "/"),
    }

    if propagate:
        prop_result = _run_propagation(path, propagate)
        response["propagation_triggered"] = prop_result.get("ok", False)
        response["propagation_strategy"] = propagate
        response["impacted_count"] = prop_result.get("impacted_count", 0)
        if not prop_result.get("ok"):
            response["propagation_error"] = prop_result.get("error")

    return response


def vault_change_log_query(
    project: Optional[str] = None,
    action_filter: Optional[str] = None,
    last: int = 20,
) -> Dict[str, Any]:
    entries = _read_json_log()

    if action_filter:
        entries = [e for e in entries if e.get("action") == action_filter.lower()]

    if project:
        entries = [e for e in entries if project.lower() in e.get("path", "").lower()]

    entries_sorted = sorted(entries, key=lambda e: e.get("timestamp", ""), reverse=True)
    page = entries_sorted[:last]

    return {
        "ok": True,
        "total": len(entries),
        "returned": len(page),
        "entries": page,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Change Log -- record and query note lifecycle events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
REGLA DE GOBERNANZA: antes de eliminar cualquier nota del vault, llamar:
  vault_change_log --action deleted --path <ruta> --reason <motivo>

Ejemplos:
  # Registrar creacion
  python vault_change_log.py --action created --path "01_Projects/ans/status.md" --reason "New sprint tracking" --agent claude

  # Registrar actualizacion
  python vault_change_log.py --action updated --path "03_Decisions/adr-001.md" --reason "Updated rationale section"

  # Registrar eliminacion (REQUERIDO antes de borrar)
  python vault_change_log.py --action deleted --path "07_Knowledge/old-note.md" --reason "Duplicate of glossary/jwt.md"

  # Registrar movimiento
  python vault_change_log.py --action moved --path "10_Migrated/draft.md" --new_path "07_Knowledge/jwt.md" --reason "Promoted from migrated"

  # Consultar ultimas 20 entradas
  python vault_change_log.py --query --last 20

  # Consultar por proyecto
  python vault_change_log.py --query --project "ans" --last 10

  # Consultar solo eliminaciones
  python vault_change_log.py --query --action deleted

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Guarda en 00_System/change-log.md y 00_System/.change-log.json
  - --query retorna JSON ordenado por timestamp desc
""",
    )

    parser.add_argument("--action", help=f"Action to record: {VALID_ACTIONS}")
    parser.add_argument("--path", help="Vault-relative path of the affected note")
    parser.add_argument("--new_path", help="New path (required for action 'moved')")
    parser.add_argument("--reason", help="Why this change was made (required)")
    parser.add_argument("--summary", help="Alias for --reason (accepted for compatibility)")
    parser.add_argument("--agent", default="claude", help="Agent name (default: claude)")
    parser.add_argument("--propagate", choices=VALID_PROPAGATE_STRATEGIES, metavar="STRATEGY",
                        help="After recording, trigger propagation: conservative|transitive|critical-path")
    parser.add_argument("--query", action="store_true", help="Query mode: return recent log entries")
    parser.add_argument("--project", help="Filter query by project name (substring match on path)")
    parser.add_argument("--last", type=int, default=20, help="Number of entries to return in query (default: 20)")

    args = parser.parse_args()

    # --summary is a documented alias for --reason
    reason = args.reason or args.summary

    if args.query:
        result = vault_change_log_query(
            project=args.project,
            action_filter=args.action,
            last=args.last,
        )
    else:
        if not args.action:
            parser.error("--action is required (or use --query mode)")
        if not args.path:
            parser.error("--path is required")
        if not reason:
            parser.error("--reason (or --summary) is required")

        result = vault_change_log_add(
            action=args.action,
            path=args.path,
            reason=reason,
            agent=args.agent,
            new_path=args.new_path,
            propagate=args.propagate,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_change_log"))

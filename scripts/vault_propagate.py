#!/usr/bin/env python3
"""
vault_propagate.py — Propagation strategies for graph-aware change management.

Applies one of three strategies over the impact graph returned by vault_impact,
then executes one or more actions on the affected notes.

Strategies:
  conservative   — only dist=1 (direct neighbors)
  transitive     — full BFS up to --max-hops (default 5)
  critical-path  — any distance, only cia_integrity high|critical

Actions (comma-separated, combinable):
  notify    — write propagation_pending timestamp to frontmatter
  queue     — append to 00_System/propagation-queue.json
  reindex   — call vault_section_index per affected folder

Usage:
    python vault_propagate.py --changed "overview.md" --strategy transitive --action notify
    python vault_propagate.py --changed "api.md" --strategy critical-path --action queue,reindex
    python vault_propagate.py --queue-report          # list pending notes, most urgent first
    python vault_propagate.py --clear "01_Projects/api/overview.md"  # mark as reviewed
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from vault_errors import wrap_main
from vault_impact import vault_impact
from vault_io import atomic_write_json, file_lock, VAULT_ROOT

SYSTEM_DIR = VAULT_ROOT / "00_System"
SCRIPTS_DIR = Path(__file__).parent
PROPAGATION_QUEUE = SYSTEM_DIR / "propagation-queue.json"

RISK_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}

VALID_STRATEGIES = ("conservative", "transitive", "critical-path")
VALID_ACTIONS = ("notify", "queue", "reindex")


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _read_propagation_queue() -> Dict[str, Any]:
    if not PROPAGATION_QUEUE.exists():
        return {"updated_at": _utcnow(), "pending": []}
    try:
        data = json.loads(PROPAGATION_QUEUE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"updated_at": _utcnow(), "pending": []}
    except Exception:
        return {"updated_at": _utcnow(), "pending": []}


def _write_propagation_queue(data: Dict[str, Any]) -> None:
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _utcnow()
    with file_lock(PROPAGATION_QUEUE, timeout=30.0):
        atomic_write_json(PROPAGATION_QUEUE, data)


def _action_notify(note_path: str, timestamp: str) -> bool:
    """Write propagation_pending field to frontmatter of a note."""
    full_path = VAULT_ROOT / note_path
    if not full_path.exists():
        return False
    try:
        content = full_path.read_text(encoding="utf-8", errors="ignore")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm_block = parts[1]
                # Remove existing propagation_pending if present
                fm_block = re.sub(r"\npropagation_pending:.*", "", fm_block)
                fm_block = fm_block.rstrip() + f"\npropagation_pending: \"{timestamp}\"\n"
                new_content = "---" + fm_block + "---" + parts[2]
                full_path.write_text(new_content, encoding="utf-8")
                return True
    except Exception:
        pass
    return False


def _action_queue(
    note_path: str,
    triggered_by: List[str],
    distance: int,
    stale_risk: str,
) -> None:
    """Append a note to propagation-queue.json."""
    queue = _read_propagation_queue()
    pending = queue.get("pending", [])

    # Dedup: update existing entry if already queued
    existing = next((e for e in pending if e["path"] == note_path), None)
    if existing:
        existing["queued_at"] = _utcnow()
        existing["triggered_by"] = list(set(existing.get("triggered_by", []) + triggered_by))
        existing["distance"] = min(existing.get("distance", distance), distance)
        existing["priority"] = stale_risk
    else:
        pending.append({
            "path": note_path,
            "queued_at": _utcnow(),
            "triggered_by": triggered_by,
            "distance": distance,
            "priority": stale_risk,
            "action_required": "review_content",
        })

    queue["pending"] = pending
    _write_propagation_queue(queue)


def _action_reindex(folders: Set[str]) -> List[str]:
    """Call vault_section_index for each affected top-level folder."""
    reindexed = []
    for folder in sorted(folders):
        cmd = [sys.executable, str(SCRIPTS_DIR / "vault_section_index.py"), "--folder", folder]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                reindexed.append(folder)
        except Exception:
            pass
    return reindexed


def vault_propagate(
    changed_notes: List[str],
    strategy: str = "conservative",
    actions: List[str] = None,
    max_hops: int = 5,
    since: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply a propagation strategy and execute actions on affected notes.

    Args:
        changed_notes: Vault-relative paths of changed notes.
        strategy:      'conservative' | 'transitive' | 'critical-path'
        actions:       List of actions: ['notify', 'queue', 'reindex']
        max_hops:      Max BFS depth (only for 'transitive')
        since:         If provided, augment changed_notes from change log.

    Returns:
        {ok, strategy, actions, impacted_count, notified, queued, reindexed, timestamp}
    """
    if actions is None:
        actions = ["notify", "queue"]

    strategy = strategy.lower()
    if strategy not in VALID_STRATEGIES:
        return {"ok": False, "error": f"Invalid strategy '{strategy}'. Must be one of: {VALID_STRATEGIES}"}

    invalid_actions = [a for a in actions if a not in VALID_ACTIONS]
    if invalid_actions:
        return {"ok": False, "error": f"Invalid actions: {invalid_actions}. Must be in: {VALID_ACTIONS}"}

    # Get impact
    hops = 1 if strategy == "conservative" else max_hops
    impact = vault_impact(list(changed_notes), max_hops=hops, since=since)

    if not impact.get("ok"):
        return {"ok": False, "error": f"vault_impact failed: {impact.get('error')}"}

    impacted = impact.get("impacted", [])

    # Apply strategy filter
    if strategy == "conservative":
        impacted = [n for n in impacted if n["distance"] == 1]
    elif strategy == "critical-path":
        impacted = [n for n in impacted if n["cia_integrity"] in ("critical", "high")]

    if not impacted:
        return {
            "ok": True,
            "strategy": strategy,
            "actions": actions,
            "impacted_count": 0,
            "notified": [],
            "queued": [],
            "reindexed": [],
            "timestamp": _utcnow(),
            "message": "No notes require propagation with this strategy",
        }

    timestamp = _utcnow()
    notified: List[str] = []
    queued: List[str] = []
    affected_folders: Set[str] = set()

    for node in impacted:
        note_path = node["path"]
        affected_folders.add(note_path.split("/")[0])

        if "notify" in actions:
            if _action_notify(note_path, timestamp):
                notified.append(note_path)

        if "queue" in actions:
            _action_queue(
                note_path=note_path,
                triggered_by=list(changed_notes),
                distance=node["distance"],
                stale_risk=node["stale_risk"],
            )
            queued.append(note_path)

    reindexed: List[str] = []
    if "reindex" in actions:
        reindexed = _action_reindex(affected_folders)

    return {
        "ok": True,
        "strategy": strategy,
        "actions": actions,
        "impacted_count": len(impacted),
        "notified": notified,
        "queued": queued,
        "reindexed": reindexed,
        "timestamp": timestamp,
    }


def vault_propagate_queue_report(min_priority: Optional[str] = None) -> Dict[str, Any]:
    """List pending propagation items, sorted by priority then queued_at."""
    queue = _read_propagation_queue()
    pending = queue.get("pending", [])

    if min_priority:
        min_level = RISK_ORDER.get(min_priority.lower(), 1)
        pending = [e for e in pending if RISK_ORDER.get(e.get("priority", "low"), 1) >= min_level]

    pending.sort(key=lambda e: (-RISK_ORDER.get(e.get("priority", "low"), 1), e.get("queued_at", "")))

    return {
        "ok": True,
        "total_pending": len(pending),
        "updated_at": queue.get("updated_at", ""),
        "pending": pending,
    }


def vault_propagate_clear(note_path: str) -> Dict[str, Any]:
    """Mark a note as reviewed: remove propagation_pending from frontmatter and queue."""
    cleared_fm = False
    full_path = VAULT_ROOT / note_path
    if full_path.exists():
        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
            if "propagation_pending" in content:
                new_content = re.sub(r"\npropagation_pending:.*", "", content)
                full_path.write_text(new_content, encoding="utf-8")
                cleared_fm = True
        except Exception:
            pass

    cleared_queue = False
    queue = _read_propagation_queue()
    pending = queue.get("pending", [])
    new_pending = [e for e in pending if e["path"] != note_path]
    if len(new_pending) < len(pending):
        queue["pending"] = new_pending
        _write_propagation_queue(queue)
        cleared_queue = True

    return {
        "ok": True,
        "path": note_path,
        "cleared_frontmatter": cleared_fm,
        "cleared_queue": cleared_queue,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_propagate — propagation strategies for graph-aware change management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Notificar vecinos directos
  python vault_propagate.py --changed "overview.md" --strategy conservative --action notify

  # Propagar completamente con queue y reindex
  python vault_propagate.py --changed "api.md" --strategy transitive --action queue,reindex

  # Solo notas criticas/high, cualquier distancia
  python vault_propagate.py --changed "core.md" --strategy critical-path --action notify,queue

  # Ver cola de propagacion pendiente
  python vault_propagate.py --queue-report

  # Ver solo items high/critical
  python vault_propagate.py --queue-report --min-priority high

  # Marcar nota como revisada
  python vault_propagate.py --clear "01_Projects/api/overview.md"

  # Propagar con --since (auto-detecta que cambio)
  python vault_propagate.py --since "2026-05-09" --strategy conservative --action queue
""",
    )
    parser.add_argument("--changed", nargs="+", metavar="PATH", default=[], help="Vault-relative paths of changed notes")
    parser.add_argument("--strategy", default="conservative", choices=list(VALID_STRATEGIES), help="Propagation strategy (default: conservative)")
    parser.add_argument("--action", default="notify,queue", metavar="ACTIONS", help="Comma-separated actions: notify,queue,reindex (default: notify,queue)")
    parser.add_argument("--max-hops", type=int, default=5, metavar="N", help="Max BFS depth for transitive strategy (default: 5)")
    parser.add_argument("--since", metavar="DATE", help="Augment --changed from change log since this date (YYYY-MM-DD)")
    parser.add_argument("--queue-report", action="store_true", help="List pending propagation items")
    parser.add_argument("--min-priority", choices=["critical", "high", "medium", "low"], help="Filter queue-report by minimum priority")
    parser.add_argument("--clear", metavar="PATH", help="Mark a note as reviewed (remove propagation_pending)")

    args = parser.parse_args()

    if args.queue_report:
        result = vault_propagate_queue_report(min_priority=args.min_priority)
    elif args.clear:
        result = vault_propagate_clear(args.clear)
    else:
        if not args.changed and not args.since:
            parser.error("Provide --changed PATH [PATH ...] or --since DATE (or use --queue-report / --clear)")

        actions = [a.strip() for a in args.action.split(",") if a.strip()]
        result = vault_propagate(
            changed_notes=list(args.changed),
            strategy=args.strategy,
            actions=actions,
            max_hops=args.max_hops,
            since=args.since,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_propagate"))

#!/usr/bin/env python3
"""
vault_tokens.py -- Token usage analytics for vault tools.

Reads 00_System/.tool-tokens.json (populated when VAULT_COUNT_TOKENS=1)
and provides summary, per-tool breakdown, and top-N ranking.

Usage:
    VAULT_COUNT_TOKENS=1 python vault_write.py ...  # records tokens
    python vault_tokens.py --summary
    python vault_tokens.py --top 10
    python vault_tokens.py --query vault_audit
    python vault_tokens.py --since 2026-05-01
    python vault_tokens.py --reset
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import wrap_main, emit_error

from vault_io import VAULT_ROOT
TOKENS_FILE = VAULT_ROOT / "00_System" / ".tool-tokens.json"


def _load_entries(since: Optional[str] = None) -> List[Dict[str, Any]]:
    if not TOKENS_FILE.exists():
        return []
    try:
        entries = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            return []
    except Exception:
        return []

    if since:
        try:
            cutoff = datetime.fromisoformat(since)
            entries = [
                e for e in entries
                if datetime.fromisoformat(e.get("timestamp", "")[:19]) >= cutoff
            ]
        except Exception:
            pass

    return entries


def _aggregate(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_tool: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"calls": 0, "input": 0, "output": 0, "total": 0})
    grand_in = grand_out = grand_total = 0

    for e in entries:
        t = e.get("tool", "unknown")
        i = e.get("input_tokens", 0)
        o = e.get("output_tokens", 0)
        tot = e.get("total_tokens", i + o)
        by_tool[t]["calls"] += 1
        by_tool[t]["input"] += i
        by_tool[t]["output"] += o
        by_tool[t]["total"] += tot
        grand_in += i
        grand_out += o
        grand_total += tot

    return {
        "grand": {"calls": len(entries), "input_tokens": grand_in, "output_tokens": grand_out, "total_tokens": grand_total},
        "by_tool": dict(by_tool),
    }


def vault_tokens(
    summary: bool = False,
    query_tool: Optional[str] = None,
    top: Optional[int] = None,
    since: Optional[str] = None,
    reset: bool = False,
) -> Dict[str, Any]:
    if reset:
        if TOKENS_FILE.exists():
            TOKENS_FILE.unlink()
        return {"ok": True, "action": "reset", "message": "Token log cleared."}

    entries = _load_entries(since)

    if not entries:
        return {
            "ok": True,
            "action": "empty",
            "message": "No token data found. Set VAULT_COUNT_TOKENS=1 and run any vault tool.",
            "hint": "Example: VAULT_COUNT_TOKENS=1 python vault_audit.py",
        }

    agg = _aggregate(entries)

    if query_tool:
        tool_entries = [e for e in entries if e.get("tool") == query_tool]
        tool_agg = agg["by_tool"].get(query_tool, {})
        return {
            "ok": True,
            "action": "query",
            "tool": query_tool,
            "calls": tool_agg.get("calls", 0),
            "input_tokens": tool_agg.get("input", 0),
            "output_tokens": tool_agg.get("output", 0),
            "total_tokens": tool_agg.get("total", 0),
            "entries": tool_entries[-50:],
        }

    if top is not None:
        ranked = sorted(
            [{"tool": t, **v} for t, v in agg["by_tool"].items()],
            key=lambda x: x["total"],
            reverse=True,
        )[:top]
        return {
            "ok": True,
            "action": "top",
            "top": top,
            "grand": agg["grand"],
            "ranking": ranked,
        }

    # Default: summary
    tools_ranked = sorted(
        [{"tool": t, **v} for t, v in agg["by_tool"].items()],
        key=lambda x: x["total"],
        reverse=True,
    )
    providers = defaultdict(int)
    for e in entries:
        providers[e.get("provider", "heuristic")] += 1

    return {
        "ok": True,
        "action": "summary",
        "grand": agg["grand"],
        "providers": dict(providers),
        "tools": tools_ranked,
        "period": {
            "from": entries[0].get("timestamp") if entries else None,
            "to": entries[-1].get("timestamp") if entries else None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_tokens -- Token usage analytics for vault tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Activar conteo:
  $env:VAULT_COUNT_TOKENS=1  # PowerShell
  export VAULT_COUNT_TOKENS=1  # bash

Consultas:
  python vault_tokens.py --summary
  python vault_tokens.py --top 10
  python vault_tokens.py --query vault_audit
  python vault_tokens.py --since 2026-05-01
  python vault_tokens.py --top 5 --since 2026-05-10
  python vault_tokens.py --reset
""",
    )
    parser.add_argument("--summary", action="store_true", help="Resumen global de uso de tokens")
    parser.add_argument("--top", type=int, metavar="N", help="Top N tools por tokens consumidos")
    parser.add_argument("--query", metavar="TOOL", help="Detalle de una tool especifica")
    parser.add_argument("--since", metavar="DATE", help="Filtrar desde fecha (YYYY-MM-DD o ISO)")
    parser.add_argument("--reset", action="store_true", help="Borrar el log de tokens")

    args = parser.parse_args()

    if not any([args.summary, args.top, args.query, args.reset]):
        args.summary = True  # default action

    result = vault_tokens(
        summary=args.summary,
        query_tool=args.query,
        top=args.top,
        since=args.since,
        reset=args.reset,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_tokens"))

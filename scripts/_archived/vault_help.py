#!/usr/bin/env python3
"""vault_help — Tool discovery and documentation for vault tools.

Queries vault_mcp_catalog for tool definitions, groups, and metadata.
Returns JSON for agent consumption.

Usage:
    python vault_help.py                         # list all tools by group
    python vault_help.py --tool vault_write      # show tool details
    python vault_help.py --group Core            # list tools in group
    python vault_help.py --search "backup"       # search tools by keyword
    python vault_help.py --groups                # list groups only
    python vault_help.py --count                 # count tools
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from vault_mcp_catalog import TOOLS_CATALOG
from vault_errors import wrap_main


def list_groups() -> None:
    groups: dict[str, list[str]] = {}
    for name, info in TOOLS_CATALOG.items():
        g = info.get("group", "Other")
        groups.setdefault(g, []).append(name)
    result = {}
    for g in sorted(groups, key=lambda x: sorted(groups[x])[0] if groups[x] else ""):
        result[g] = sorted(groups[g])
    print(json.dumps(result, indent=2, ensure_ascii=False))


def show_tool(name: str) -> None:
    info = TOOLS_CATALOG.get(name)
    if not info:
        print(json.dumps({"ok": False, "error": f"Tool not found: {name}"}))
        sys.exit(1)
    print(json.dumps(info, indent=2, ensure_ascii=False))


def list_group(group: str) -> None:
    group_lower = group.lower()
    tools = {
        name: info
        for name, info in TOOLS_CATALOG.items()
        if info.get("group", "").lower() == group_lower
    }
    if not tools:
        print(json.dumps({"ok": False, "error": f"Group not found: {group}"}))
        sys.exit(1)
    print(json.dumps(tools, indent=2, ensure_ascii=False))


def search_tools(query: str) -> None:
    q = query.lower()
    results = {}
    for name, info in TOOLS_CATALOG.items():
        searchable = json.dumps(info).lower()
        if q in searchable or q in name.lower():
            results[name] = {
                "group": info.get("group"),
                "purpose": info.get("purpose", "")[:120],
                "script": info.get("script"),
            }
    print(json.dumps(results, indent=2, ensure_ascii=False))


def count_tools() -> None:
    print(json.dumps({"ok": True, "total": len(TOOLS_CATALOG)}))


def list_tools_summary() -> None:
    result = {}
    for name in sorted(TOOLS_CATALOG):
        info = TOOLS_CATALOG[name]
        result[name] = {
            "group": info.get("group"),
            "purpose": info.get("purpose", "")[:120],
            "script": info.get("script"),
        }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Vault tool discovery")
    parser.add_argument("--tool", help="Show tool details")
    parser.add_argument("--group", help="List tools in group")
    parser.add_argument("--search", help="Search tools by keyword")
    parser.add_argument("--groups", action="store_true", help="List groups only")
    parser.add_argument("--count", action="store_true", help="Count tools")
    args = parser.parse_args()

    if args.tool:
        show_tool(args.tool)
    elif args.group:
        list_group(args.group)
    elif args.search:
        search_tools(args.search)
    elif args.groups:
        list_groups()
    elif args.count:
        count_tools()
    else:
        list_tools_summary()
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_help"))

#!/usr/bin/env python3
"""vault — Unified CLI dispatcher for vault tools.

Replaces `python scripts/vault_<tool>.py [args]` with `vault <tool> [args]`.
Discovers all vault_*.py scripts in the scripts/ directory and forwards
arguments to the selected script as a subprocess.

Usage:
    vault                     # list all available tools
    vault <tool> [args]       # run selected tool with args
    vault <tool> --help       # show tool-specific help
    vault --version           # vault dispatcher version
    vault --catalog [query]   # query tool catalog (uses vault_mcp_catalog)

Setup:
    Add scripts/ to PATH, or symlink vault to ~/bin/vault.

Examples:
    vault write --folder 01_Projects/foo --title "Demo" --content "# Demo"
    vault audit --project my-api
    vault search --query "jwt"
    vault help write         # show catalog info for vault_write
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
__version__ = "1.0"


def discover_tools() -> dict[str, str]:
    """Return {tool_name: script_path} for all vault_*.py in scripts/."""
    tools: dict[str, str] = {}
    for p in sorted(SCRIPTS_DIR.glob("vault_*.py")):
        if p.stem == "vault_help" and p.stem.startswith("_"):
            continue
        name = (
            p.stem.replace("vault_", "", 1) if p.stem.startswith("vault_") else p.stem
        )
        if name:
            tools[name] = str(p)
    return tools


def list_tools(tools: dict[str, str]) -> None:
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        from vault_mcp_catalog import TOOLS_CATALOG

        grouped: dict[str, list[str]] = {}
        for tool_name in sorted(TOOLS_CATALOG):
            info = TOOLS_CATALOG[tool_name]
            g = info.get("group", "Other")
            grouped.setdefault(g, []).append(tool_name)
        for g in sorted(grouped):
            print(f"\n[{g}]")
            for t in grouped[g]:
                purpose = TOOLS_CATALOG[t].get("purpose", "")[:90]
                print(f"  {t:<28} {purpose}")
    except ImportError:
        for t in sorted(tools):
            print(f"  vault {t}")


def dispatch(tool: str, args: list[str], tools: dict[str, str]) -> int:
    """Run scripts/<tool>.py with the given args. Returns exit code."""
    script = tools.get(tool) or SCRIPTS_DIR / f"vault_{tool}.py"
    if not Path(script).exists():
        print(f"Unknown tool: vault_{tool}", file=sys.stderr)
        print(f"Run `vault` to see available tools.", file=sys.stderr)
        return 2
    cmd = [sys.executable, str(script), *args]
    return subprocess.call(cmd)


def show_help_for_tool(tool: str, tools: dict[str, str]) -> int:
    """Show --help for the given tool without running it."""
    script = tools.get(tool) or SCRIPTS_DIR / f"vault_{tool}.py"
    if not Path(script).exists():
        print(f"Unknown tool: vault_{tool}", file=sys.stderr)
        return 2
    return subprocess.call([sys.executable, str(script), "--help"])


def query_catalog(query: str) -> None:
    """Use vault_mcp_catalog to answer a query."""
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        from vault_help import search_tools, show_tool, list_group

        if not query:
            list_tools(discover_tools())
            return
        parts = query.split(maxsplit=1)
        first = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        if first in ("tool", "info", "show", "--tool") and rest:
            show_tool(f"vault_{rest.lstrip('-')}")
            return
        if first in ("group", "--group") and rest:
            list_group(rest)
            return
        search_tools(query)
    except ImportError as exc:
        print(f"Catalog unavailable: {exc}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="vault",
        description="Unified CLI dispatcher for vault tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  vault write --folder 01_Projects/foo --title "Demo" --content "# Demo"\n'
            "  vault audit --project my-api\n"
            "  vault search --query jwt\n"
            "  vault --catalog jwt\n"
            "  vault --help-tool write"
        ),
    )
    parser.add_argument(
        "tool",
        nargs="?",
        help="Tool name without 'vault_' prefix (e.g. 'write' for vault_write.py)",
    )
    parser.add_argument(
        "args", nargs=argparse.REMAINDER, help="Arguments forwarded to the tool"
    )
    parser.add_argument("--version", action="version", version=f"vault {__version__}")
    parser.add_argument(
        "--catalog",
        metavar="QUERY",
        nargs="?",
        const="",
        help="Search tool catalog (uses vault_mcp_catalog + vault_help)",
    )
    parser.add_argument(
        "--help-tool",
        metavar="TOOL",
        help="Show --help for a specific tool without running it",
    )
    args = parser.parse_args()

    tools = discover_tools()

    if args.catalog is not None:
        query_catalog(args.catalog)
        return 0
    if args.help_tool:
        return show_help_for_tool(args.help_tool, tools)
    if not args.tool:
        list_tools(tools)
        return 0
    return dispatch(args.tool, args.args, tools)


if __name__ == "__main__":
    sys.exit(main())

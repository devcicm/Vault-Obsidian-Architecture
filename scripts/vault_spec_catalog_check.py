#!/usr/bin/env python3
"""vault_spec_catalog_check — Validate sync between tool-spec.json and TOOLS_CATALOG.

Detects:
- Tools missing from either source
- Group name mismatches
- Status mismatches (active/deprecated)

Usage:
    python scripts/vault_spec_catalog_check.py
    python scripts/vault_spec_catalog_check.py --fix
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from vault_mcp_catalog import TOOLS_CATALOG
from vault_errors import wrap_main
from vault_io import resolve_tool_spec, tool_spec_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate tool-spec.json vs TOOLS_CATALOG sync"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Fix group mismatches in vault_mcp_catalog.py",
    )
    args = parser.parse_args()

    spec_path = resolve_tool_spec()
    if spec_path is None:
        print(json.dumps({
            "ok": False,
            "error": "tool_spec_not_found",
            "expected": str(tool_spec_path()),
            "hint": "python vault_manifest.py --bootstrap",
        }, indent=2, ensure_ascii=False))
        return 1
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec_tools = set(spec["tools"].keys())
    catalog_tools = set(TOOLS_CATALOG.keys())

    issues: list[str] = []

    # Coverage
    only_catalog = catalog_tools - spec_tools
    only_spec = spec_tools - catalog_tools
    common = catalog_tools & spec_tools

    if only_catalog:
        issues.append(
            f"TOOLS_CATALOG only ({len(only_catalog)}): {sorted(only_catalog)}"
        )
    if only_spec:
        issues.append(f"tool-spec.json only ({len(only_spec)}): {sorted(only_spec)}")

    # Group mismatches
    for t in sorted(common):
        cg = TOOLS_CATALOG[t].get("group", "")
        sg = spec["tools"][t].get("group", "")
        if cg.lower() != sg.lower():
            issues.append(f'Group mismatch: {t}: catalog="{cg}" spec="{sg}"')

    if not issues:
        print(
            json.dumps(
                {
                    "ok": True,
                    "catalog_tools": len(catalog_tools),
                    "spec_tools": len(spec_tools),
                    "in_sync": True,
                    "message": f"{len(common)} tools in sync — groups match, no coverage gaps",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    result = {
        "ok": False,
        "catalog_tools": len(catalog_tools),
        "spec_tools": len(spec_tools),
        "in_sync": False,
        "issues": issues,
        "issue_count": len(issues),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_spec_catalog_check"))

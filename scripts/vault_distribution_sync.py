#!/usr/bin/env python3
"""Genera adaptadores de operaciones desde los registros canónicos."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vault_mcp_catalog import TOOLS_CATALOG
from vault_servicio import NATURALEZAS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.meta_toolkit.distribucion import clasificar_tools

ROOT = Path(__file__).resolve().parent.parent
OPERATIONS = ROOT / "vault_toolkit" / "operations"

_TEMPLATE = '''"""Adaptador generado para la operación canónica ``{name}``."""

from vault_toolkit.loading import import_toolkit_module, legacy_scripts_for

_impl = import_toolkit_module(
    "{implementation}",
    legacy_scripts=legacy_scripts_for(__file__),
)
main = _impl.main


def __getattr__(name):
    return getattr(_impl, name)


if __name__ == "__main__":
    import sys

    wrap_main = import_toolkit_module(
        "vault_errors",
        legacy_scripts=legacy_scripts_for(__file__),
    ).wrap_main
    sys.exit(wrap_main(main, "{name}"))
'''


def render() -> dict[str, str]:
    distribucion = clasificar_tools(TOOLS_CATALOG, NATURALEZAS)
    return {
        d.execution_module.rsplit(".", 1)[-1] + ".py": _TEMPLATE.format(
            name=d.nombre,
            implementation=Path(TOOLS_CATALOG[d.nombre].get("script") or f"{d.nombre}.py").stem,
        )
        for d in distribucion.values()
        if d.distributable and d.execution_module
    }


def sync(*, check: bool = False) -> int:
    expected = render()
    actual = {
        p.name: p.read_text(encoding="utf-8")
        for p in OPERATIONS.glob("vault_*.py")
    }
    if check:
        return 0 if actual == expected else 1
    OPERATIONS.mkdir(parents=True, exist_ok=True)
    for stale in set(actual) - set(expected):
        (OPERATIONS / stale).unlink()
    for name, content in expected.items():
        (OPERATIONS / name).write_text(content, encoding="utf-8", newline="\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return sync(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())

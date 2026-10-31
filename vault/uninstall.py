"""Desinstalador del toolkit Vault-Obsidian-Architecture.

Uso:
    python -m vault.uninstall       # desinstalar CLI
    python -m vault.uninstall --mcp # desinstalar CLI + MCP symlink
    python -m vault.uninstall --all # desinstalar todo
"""

from __future__ import annotations

import argparse
import subprocess  # noqa: F401 — nombre público del módulo desde antes de compartir `_run`
import sys
from pathlib import Path

# El lanzador es el del instalador: el mismo programa en las dos direcciones.
# La dependencia va de uninstall a install y nunca al revés, porque el
# instalador corre antes de que exista nada más del paquete (CN-05).
from vault.install import _run


REPO_ROOT = Path(__file__).resolve().parent.parent


def _pip_uninstall() -> int:
    pkg = "vault-obsidian-architecture"
    print(f"[uninstall] pip uninstall {pkg}")
    return _run([sys.executable, "-m", "pip", "uninstall", "-y", pkg])


def _uninstall_mcp() -> int:
    dest = Path("/usr/local/bin/vault-mcp")
    print(f"[uninstall] MCP symlink: {dest}")
    if dest.is_symlink() or dest.exists():
        dest.unlink()
        print(f"  Eliminado: {dest}")
    else:
        print("  No existía")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vault.uninstall", allow_abbrev=False)
    parser.add_argument("--mcp", action="store_true", help="También eliminar MCP symlink")
    parser.add_argument("--all", action="store_true", help="Desinstalar todo (CLI + MCP)")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué haría")
    args = parser.parse_args(argv)

    if args.dry_run:
        print("[dry-run] Acciones que se ejecutarían:")
        print("  pip uninstall vault-obsidian-architecture")
        if args.mcp or args.all:
            print("  rm /usr/local/bin/vault-mcp")
        return 0

    print(f"=== Vault-Obsidian-Architecture uninstall ===")
    print()

    uninstall_mcp = args.mcp or args.all

    if uninstall_mcp:
        _uninstall_mcp()
        print()

    rc = _pip_uninstall()
    if rc != 0:
        print(f"[ERROR] pip uninstall returned {rc}")
        print()
        print(f"=== Desinstalación INCOMPLETA (exit {rc}) ===")
        return rc

    print()
    print("=== Desinstalación completa ===")
    print("  El directorio del repo queda intacto.")
    print("  Para eliminar definitivamente: rm -rf /ruta/al/Vault-Obsidian-Architecture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

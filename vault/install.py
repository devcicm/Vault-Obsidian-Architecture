"""Instalador del toolkit Vault-Obsidian-Architecture.

Uso:
    python -m vault.install          # instalar CLI + entry points
    python -m vault.install --mcp   # instalar CLI + MCP server
    python -m vault.install --all   # instalar todo (CLI + MCP + skills)

Desinstalar:
    python -m vault.uninstall
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALLER_ROOT = REPO_ROOT


def _run(cmd: list[str], **kwargs) -> int:
    print(f"  {' '.join(cmd)}")
    r = subprocess.run(cmd, **kwargs)
    return r.returncode


def _pip_install(extra: str = "") -> int:
    cmd = [sys.executable, "-m", "pip", "install", "-e", str(REPO_ROOT)]
    if extra:
        cmd.extend(extra.split())
    return _run(cmd)


def _install_cli() -> int:
    print("[install] CLI + entry points (pip install -e .)")
    rc = _pip_install()
    if rc != 0:
        return rc
    print("[install] Verificando entry points...")
    try:
        from vault.product_cli import main as cli_main
        from vault.gobernanza.tool import main as gobernanza_main
        print("  vault.product_cli: OK")
        print("  vault.gobernanza.tool: OK")
    except ImportError as e:
        print(f"  [WARN] import failed: {e}")
    return 0


def _install_mcp() -> int:
    print("[install] MCP server symlink...")
    mcp_script = REPO_ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs"
    dest = Path("/usr/local/bin/vault-mcp")
    if not dest.parent.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        dest.unlink()
    try:
        dest.symlink_to(mcp_script.resolve())
        print(f"  Symlink: {dest} -> {mcp_script}")
    except OSError as e:
        print(f"  [WARN] Could not create symlink: {e}")
        print(f"  Copia alternativa: cp {mcp_script} {dest}")
        return 1
    return 0


def _install_skills() -> int:
    print("[install] Skills (agent/skills/)...")
    skills_dir = REPO_ROOT / "agent" / "skills"
    if not skills_dir.exists():
        print("  agent/skills/ no encontrado, omitido")
        return 0
    print(f"  Skills disponibles en: {skills_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vault.install", allow_abbrev=False)
    parser.add_argument("--mcp", action="store_true", help="Instalar MCP server")
    parser.add_argument("--all", action="store_true", help="Instalar CLI + MCP + skills")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué haría")
    args = parser.parse_args(argv)

    install_mcp = args.mcp or args.all
    install_skills = args.all

    if args.dry_run:
        print("[dry-run] Acciones que se ejecutarían:")
        print("  pip install -e .")
        if install_mcp:
            print("  ln -sf .../vault-mcp-server.mjs /usr/local/bin/vault-mcp")
        if install_skills:
            print("  (skills descubribles por convención de path)")
        return 0

    print(f"=== Vault-Obsidian-Architecture install ===")
    print(f"Repo root: {REPO_ROOT}")
    print()

    rc = _install_cli()
    if rc != 0:
        print(f"[ERROR] CLI install failed (exit {rc})")
        return rc

    if install_mcp:
        print()
        rc = _install_mcp()
        if rc != 0:
            print(f"[WARN] MCP install failed (exit {rc})")

    if install_skills:
        print()
        rc = _install_skills()

    print()
    print("=== Instalación completa ===")
    print()
    print("CLAVE: exporta VAULT_ROOT al directorio de tu vault:")
    print(f"  export VAULT_ROOT=/ruta/al/tu-vault")
    print()
    print("Verificar instalación:")
    print("  vault --version")
    print("  vault tools list")
    print("  python -m vault.gobernanza.tool --help")
    print()
    print("MCP server:")
    print("  vault-mcp --help")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

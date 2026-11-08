"""Desinstalador del toolkit Vault-Obsidian-Architecture.

Uso:
    python -m vault.uninstall       # desinstalar CLI
    python -m vault.uninstall --mcp # desinstalar CLI + el lanzador MCP
    python -m vault.uninstall --all # desinstalar todo

El lanzador MCP solo se borra si lo puso este instalador: el manifiesto de
propiedad que acompaña al lanzador lo dice. Sin manifiesto, el desinstalador
**no borra nada** y lo explica (antes borraba lo que hubiera en el destino,
fuese de quien fuese). El código de salida se deriva de los pasos: un `pip
uninstall` fallido deja el código de ese paso.
"""

from __future__ import annotations

import argparse
import json
import subprocess  # noqa: F401 — nombre público del módulo desde antes de compartir `_run`
import sys
from pathlib import Path

# El lanzador es el del instalador: el mismo programa en las dos direcciones.
# La dependencia va de uninstall a install y nunca al revés, porque el
# instalador corre antes de que exista nada más del paquete (CN-05).
from vault.install import _destino_mcp, _manifiesto_de, _run


REPO_ROOT = Path(__file__).resolve().parent.parent


def _pip_uninstall() -> int:
    pkg = "vault-obsidian-architecture"
    print(f"[uninstall] pip uninstall {pkg}")
    return _run([sys.executable, "-m", "pip", "uninstall", "-y", pkg])


def _uninstall_mcp() -> int:
    """Quita el lanzador MCP **si es nuestro**.

    El manifiesto de propiedad (`owner.json` junto al lanzador) es la prueba.
    Si no está, el destino no lo puso este instalador y no se toca: borrar un
    fichero ajeno es una decisión de la persona.
    """
    dest = _destino_mcp()
    manifiesto = _manifiesto_de(dest)
    print(f"[uninstall] MCP launcher: {dest}")
    if not manifiesto.is_file():
        if dest.exists() or dest.is_symlink():
            print(f"  No lo instalo este instalador (sin manifiesto de "
                  f"propiedad): {dest} NO se borra")
            print("  Borralo a mano si quieres quitarlo.")
        else:
            print("  No existia")
        return 0
    try:
        datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = {}
    if dest.exists() or dest.is_symlink():
        try:
            dest.unlink()
            print(f"  Eliminado: {dest}")
        except OSError as e:
            print(f"  [ERROR] no se pudo eliminar {dest}: {e}")
            return 1
    try:
        manifiesto.unlink(missing_ok=True)
    except OSError:
        pass
    if datos.get("script"):
        print(f"  (era el lanzador de {datos['script']})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vault.uninstall", allow_abbrev=False)
    parser.add_argument("--mcp", action="store_true", help="También eliminar el lanzador MCP")
    parser.add_argument("--all", action="store_true", help="Desinstalar todo (CLI + MCP)")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué haría")
    args = parser.parse_args(argv)

    if args.dry_run:
        print("[dry-run] Acciones que se ejecutarían:")
        print("  pip uninstall vault-obsidian-architecture")
        if args.mcp or args.all:
            print(f"  borrar {_destino_mcp()} (solo si tiene manifiesto de propiedad)")
        return 0

    print(f"=== Vault-Obsidian-Architecture uninstall ===")
    print()

    uninstall_mcp = args.mcp or args.all
    fallo = 0

    if uninstall_mcp:
        rc = _uninstall_mcp()
        if rc != 0:
            print(f"[ERROR] MCP uninstall failed (exit {rc})")
            fallo = fallo or rc
        print()

    rc = _pip_uninstall()
    if rc != 0:
        print(f"[ERROR] pip uninstall returned {rc}")
        print()
        print(f"=== Desinstalación INCOMPLETA (exit {rc}) ===")
        return rc or fallo or 1

    if fallo:
        print()
        print(f"=== Desinstalación INCOMPLETA (exit {fallo}) ===")
        return fallo

    print()
    print("=== Desinstalación completa ===")
    print("  El directorio del repo queda intacto.")
    print("  Para eliminar definitivamente: rm -rf /ruta/al/Vault-Obsidian-Architecture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

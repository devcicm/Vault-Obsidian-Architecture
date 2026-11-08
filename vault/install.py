"""Instalador del toolkit Vault-Obsidian-Architecture.

Uso:
    python -m vault.install          # instalar CLI + entry points
    python -m vault.install --mcp   # instalar CLI + MCP server
    python -m vault.install --all   # instalar todo (CLI + MCP + skills)

Desinstalar:
    python -m vault.uninstall

Cuatro reglas que este instalador cumple y antes no cumplía (medido el
2026-10-30, nota de causa raíz «Installer and uninstaller report success
after a required step fails»):

1. **El código de salida se deriva de los pasos.** Un paso fallido deja el
   código de ese paso; `main()` acumula y devuelve el primero. El mensaje
   «Instalación completa» solo se imprime sin fallos.
2. **El destino tiene dueño.** Antes se borraba el fichero que hubiera en el
   destino sin comprobar de quién era. Ahora el instalador escribe un
   manifiesto de propiedad junto al lanzador; si el destino existe y no hay
   manifiesto —o el manifiesto no es de este repo— el instalador **no toca
   nada** y falla.
3. **El destino se deriva de la plataforma.** `/usr/local/bin` es Unix; en
   Windows el lanzador es un `.cmd` en el directorio local de la aplicación,
   y nunca se crea `/usr/local` en un sistema que no lo tiene.
4. **Descubrir no es instalar.** Las skills se anuncian como lo que son: el
   instalador dice dónde están y el agente las usa por convención de ruta.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import sysconfig
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALLER_ROOT = REPO_ROOT

#: Nombre del manifiesto de propiedad que acompaña al lanzador instalado.
NOMBRE_MANIFIESTO = "owner.json"


def _run(cmd: list[str], **kwargs) -> int:
    print(f"  {' '.join(cmd)}")
    r = subprocess.run(cmd, **kwargs)
    return r.returncode


def _pip_install(extra: str = "") -> int:
    cmd = [sys.executable, "-m", "pip", "install", "-e", str(REPO_ROOT)]
    if extra:
        cmd.extend(extra.split())
    return _run(cmd)


# ── El destino y su dueño ────────────────────────────────────────────────────


def _destino_mcp() -> Path:
    """Dónde vive el lanzador del servidor MCP, según la plataforma.

    En Unix, `/usr/local/bin/vault-mcp` es el sitio de siempre. En Windows no
    hay symlinks sin privilegios de desarrollador y `/usr/local` no existe: el
    lanzador es un `.cmd` **junto al launcher de la CLI** —el directorio que
    `sysconfig` declara para los scripts—, que es donde `pip` deja `vault`.

    El destino no se lee de ninguna variable de entorno: el registro de
    variables del estándar no declara las del sistema (AP-49), y una ruta que
    depende de `LOCALAPPDATA` sería además distinta en cada instalación.
    """
    if os.name == "nt":
        return Path(sysconfig.get_path("scripts")) / "vault-mcp.cmd"
    return Path("/usr/local/bin/vault-mcp")


def _manifiesto_de(destino: Path) -> Path:
    """El manifiesto de propiedad: dice quién puso ese lanzador ahí."""
    return destino.with_name(destino.name + "." + NOMBRE_MANIFIESTO)


def _es_nuestro(destino: Path, manifiesto: Path, script: Path) -> bool:
    """¿Este lanzador lo puso este instalador?

    Dos pruebas: el manifiesto (que escribe el instalador) o, en Unix, que el
    symlink apunte al script de este repo. Sin las dos, el destino es de
    alguien y no se toca.
    """
    if manifiesto.is_file():
        try:
            datos = json.loads(manifiesto.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return datos.get("script") == str(script)
    if destino.is_symlink():
        try:
            return destino.resolve() == script.resolve()
        except OSError:
            return False
    return False


def _escribir_manifiesto(destino: Path, script: Path) -> None:
    """El manifiesto de propiedad: qué lanzador es y quién lo puso.

    Sin huella del script: el lanzador **apunta** al script del repo, así que
    su contenido cambia con el repo y una huella se quedaría vieja al
    instante. Lo que prueba la propiedad es la ruta y el destino.
    """
    datos = {
        "destino": str(destino),
        "script": str(script),
        "instalado": datetime.now(timezone.utc).isoformat(),
        "repo": str(REPO_ROOT),
    }
    manifiesto = _manifiesto_de(destino)
    manifiesto.parent.mkdir(parents=True, exist_ok=True)
    manifiesto.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                          encoding="utf-8")


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
        # Antes: `[WARN]` y `return 0` — la instalación «completa» de una
        # CLI que no importa. Ahora el paso fallido es el paso fallido.
        print(f"  [ERROR] import failed: {e}")
        return 1
    return 0


def _install_mcp() -> int:
    print("[install] MCP server launcher...")
    mcp_script = REPO_ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs"
    if not mcp_script.is_file():
        print(f"  [ERROR] no existe el servidor MCP: {mcp_script}")
        return 1
    dest = _destino_mcp()
    manifiesto = _manifiesto_de(dest)

    if dest.exists() or dest.is_symlink():
        if not _es_nuestro(dest, manifiesto, mcp_script):
            # Lo de otro no se borra: decidir qué hacer con un fichero ajeno
            # es de la persona, no del instalador.
            print(f"  [ERROR] {dest} ya existe y no lo instaló este instalador:")
            print("          no se toca. Borralo a mano si quieres que lo "
                  "sustituya.")
            return 1
        dest.unlink(missing_ok=True)

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        if os.name == "nt":
            node = shutil.which("node") or "node"
            temporal = dest.with_name(dest.name + ".tmp")
            temporal.write_text(
                f'@echo off\r\n"{node}" "{mcp_script.resolve()}" %*\r\n',
                encoding="utf-8")
            os.replace(temporal, dest)
            print(f"  Lanzador: {dest} -> {mcp_script}")
        else:
            dest.symlink_to(mcp_script.resolve())
            print(f"  Symlink: {dest} -> {mcp_script}")
    except OSError as e:
        print(f"  [ERROR] no se pudo escribir el lanzador: {e}")
        return 1

    _escribir_manifiesto(dest, mcp_script.resolve())
    return 0


def _install_skills() -> int:
    """Las skills se **descubren**: el instalador dice dónde están.

    No las copia a ningún sitio: el agente las usa por convención de ruta
    (`agent/skills/`). Antes el instalador anunciaba «Skills instaladas» sin
    instalar nada; ahora el texto dice lo que pasa, y `--all` no cuenta este
    paso como una instalación.
    """
    print("[install] Skills (descubrimiento, no instalación)...")
    skills_dir = REPO_ROOT / "agent" / "skills"
    if not skills_dir.exists():
        print("  agent/skills/ no encontrado, omitido")
        return 0
    print(f"  Skills disponibles en: {skills_dir}")
    print("  (el agente las usa por convencion de ruta; no se copia nada)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vault.install", allow_abbrev=False)
    parser.add_argument("--mcp", action="store_true", help="Instalar MCP server")
    parser.add_argument("--all", action="store_true", help="Instalar CLI + MCP + skills")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué haría")
    args = parser.parse_args(argv)

    install_mcp = args.mcp or args.all
    install_skills = args.all
    fallo = 0

    if args.dry_run:
        print("[dry-run] Acciones que se ejecutarían:")
        print("  pip install -e .")
        if install_mcp:
            print(f"  escribir el lanzador MCP en {_destino_mcp()}")
        if install_skills:
            print("  (skills descubribles por convencion de path)")
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
            print(f"[ERROR] MCP install failed (exit {rc})")
            fallo = fallo or rc

    if install_skills:
        print()
        rc = _install_skills()
        if rc != 0:
            print(f"[ERROR] Skills install failed (exit {rc})")
            fallo = fallo or rc

    print()
    if fallo:
        print(f"=== Instalación INCOMPLETA (exit {fallo}) ===")
        return fallo
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
    if install_mcp:
        print("MCP server:")
        print(f"  {_destino_mcp()} --help")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

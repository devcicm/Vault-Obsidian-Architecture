#!/usr/bin/env python3
"""
vault_init.py — Bootstrap de un vault fresco en un solo comando.

Hace lo que el README quickstart describe como 3-4 pasos, en uno solo:
  1. Crea las 17 carpetas estándar (00_System → 99_Index)
  2. Escribe 00_System/standard-version.json
  3. Aplica las migraciones pendientes (v20 → current)
  4. Auto-genera el índice de cada sección
  5. Crea 00_System/vault-hub.md y vault-commands.md si no existen
  6. Ejecuta vault_audit y reporta el health score inicial

Diseñado para que un consumer repo pueda ejecutar:

    mkdir vault-mi-proyecto
    cp -r Vault-Obsidian-Architecture/scripts ./
    python scripts/vault_init.py

Y termine con un vault navegable de inmediato, sin tener que recordar
la secuencia exacta de comandos del README.

Usage:
    python vault_init.py                  # versión por defecto (current)
    python vault_init.py --target v32     # migrar hasta v32 explícitamente
    python vault_init.py --no-audit       # omitir vault_audit final
    python vault_init.py --clean          # peligroso: borra el contenido actual
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from vault_errors import wrap_main
from vault_io import VAULT_ROOT
from vault_registry import standard_folders


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def vault_init(target_version: str = "v32", run_audit: bool = True, clean: bool = False) -> dict:
    """Inicializa un vault fresco en VAULT_ROOT.

    Returns a structured result suitable for both CLI JSON output and tests.
    """
    result = {
        "ok": True,
        "vault_root": str(VAULT_ROOT).replace("\\", "/"),
        "target_version": target_version,
        "steps": [],
    }

    # Safety: refuse to run if VAULT_ROOT looks wrong (sandbox not detected)
    if not VAULT_ROOT.exists() or not VAULT_ROOT.is_dir():
        result["ok"] = False
        result["error"] = f"VAULT_ROOT does not exist or is not a directory: {VAULT_ROOT}"
        return result

    # Step 0: --clean wipes existing content (only if explicitly asked)
    if clean and VAULT_ROOT.exists():
        wiped = []
        for entry in VAULT_ROOT.iterdir():
            if entry.name == ".locks":
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            wiped.append(entry.name)
        result["steps"].append({"step": "clean", "wiped": wiped})

    # Step 1: create all 17 standard folders
    folders_created = []
    for folder in standard_folders():
        folder_path = VAULT_ROOT / folder
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
            folders_created.append(folder)
        # always ensure .gitkeep
        gitkeep = folder_path / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
    result["steps"].append({"step": "folders", "created": folders_created, "total": len(standard_folders())})

    # Step 2: run vault_standard_upgrade --init <target>
    # We invoke the script as a subprocess to reuse its full logic
    import subprocess
    scripts_dir = Path(__file__).parent
    upgrade_script = scripts_dir / "vault_standard_upgrade.py"
    if upgrade_script.exists():
        proc = subprocess.run(
            [sys.executable, str(upgrade_script), "--init", target_version, "--agent", "vault_init"],
            capture_output=True,
            text=True,
        )
        try:
            upgrade_data = json.loads(proc.stdout)
            result["steps"].append({"step": "init", "output": upgrade_data})
        except json.JSONDecodeError:
            result["steps"].append({"step": "init", "raw_stdout": proc.stdout, "raw_stderr": proc.stderr})

    # Step 3: run vault_master_index which also indexes all sections
    master_script = scripts_dir / "vault_master_index.py"
    if master_script.exists():
        proc = subprocess.run(
            [sys.executable, str(master_script)],
            capture_output=True,
            text=True,
        )
        try:
            master_data = json.loads(proc.stdout)
            result["steps"].append({"step": "master_index", "output": master_data})
        except json.JSONDecodeError:
            result["steps"].append({"step": "master_index", "raw_stdout": proc.stdout, "raw_stderr": proc.stderr})

    # Step 4: run vault_reindex --graph to populate graph.json + search-index.json + hash-index.json
    reindex_script = scripts_dir / "vault_reindex.py"
    if reindex_script.exists():
        proc = subprocess.run(
            [sys.executable, str(reindex_script), "--graph"],
            capture_output=True,
            text=True,
        )
        try:
            reindex_data = json.loads(proc.stdout)
            result["steps"].append({"step": "reindex", "output": reindex_data})
        except json.JSONDecodeError:
            result["steps"].append({"step": "reindex", "raw_stdout": proc.stdout, "raw_stderr": proc.stderr})

    # Step 5: optional vault_audit
    if run_audit:
        audit_script = scripts_dir / "vault_audit.py"
        if audit_script.exists():
            proc = subprocess.run(
                [sys.executable, str(audit_script)],
                capture_output=True,
                text=True,
            )
            try:
                audit_data = json.loads(proc.stdout)
                result["steps"].append({"step": "audit", "output": audit_data})
                result["healthScore"] = audit_data.get("healthScore")
                result["noteCount"] = audit_data.get("stats", {}).get("total", 0)
            except json.JSONDecodeError:
                result["steps"].append({"step": "audit", "raw_stdout": proc.stdout, "raw_stderr": proc.stderr})

    # Step 6: report on hub notes
    hub_note = VAULT_ROOT / "00_System" / "vault-hub.md"
    commands_note = VAULT_ROOT / "00_System" / "vault-commands.md"
    result["hub_notes"] = {
        "hub": str(hub_note.relative_to(VAULT_ROOT)).replace("\\", "/") if hub_note.exists() else None,
        "commands": str(commands_note.relative_to(VAULT_ROOT)).replace("\\", "/") if commands_note.exists() else None,
    }

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Init — bootstrap a fresh vault in one command",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Bootstrap con versión por defecto (v32)
  python vault_init.py

  # Migrar a una versión específica
  python vault_init.py --target v32

  # Bootstrap sin ejecutar vault_audit al final
  python vault_init.py --no-audit

  # Bootstrap desde cero (BORRA el contenido actual — usar con cuidado)
  python vault_init.py --clean

Notas:
  - VAULT_ROOT se detecta automáticamente
  - Crea las 17 carpetas estándar, aplica migraciones, indexa todo,
    genera hub/commands notes y reporta el health score.
  - --clean borra TODO el contenido del vault actual excepto .locks
        """,
    )
    parser.add_argument("--target", default="v32", help="Target vault version (default: v32)")
    parser.add_argument("--no-audit", action="store_true", help="Skip final vault_audit run")
    parser.add_argument("--clean", action="store_true",
                        help="Wipe existing vault content before init (DANGEROUS)")
    args = parser.parse_args()

    result = vault_init(
        target_version=args.target,
        run_audit=not args.no_audit,
        clean=args.clean,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_init"))

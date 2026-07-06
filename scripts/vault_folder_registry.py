#!/usr/bin/env python3

"""
Vault Folder Registry — Auto-detección y registro de carpetas personalizadas.

Detecta carpetas no estándar dentro de las secciones del vault, las registra
automáticamente y las incluye en índices y búsquedas.

Usage:
    python vault_folder_registry.py
    python vault_folder_registry.py --scan
    python vault_folder_registry.py --list
    python vault_folder_registry.py --add "11_Code/tests"
    python vault_folder_registry.py --remove "11_Code/tests"
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import wrap_main
from vault_io import VAULT_ROOT


SYSTEM_DIR = VAULT_ROOT / "00_System"
REGISTRY_FILE = SYSTEM_DIR / "custom-folders.json"


STANDARD_SECTIONS = {
    "00_System",
    "01_Projects",
    "02_Observability",
    "03_Decisions",
    "04_Sessions",
    "05_Patterns",
    "06_Diagrams",
    "07_Knowledge",
    "08_Runbooks",
    "09_Infrastructure",
    "10_Migrated",
    "11_Code",
    "99_Index",
}


def get_registry() -> Dict[str, Any]:
    """Carga el registro de carpetas."""
    if REGISTRY_FILE.exists():
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    return {
        "detected_at": None,
        "updated_at": None,
        "folders": [],
    }


def save_registry(registry: Dict[str, Any]) -> None:
    """Guarda el registro de carpetas."""
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    registry["updated_at"] = datetime.now(timezone.utc).isoformat()
    REGISTRY_FILE.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def detect_custom_folders() -> List[Dict[str, Any]]:
    """Detecta carpetas personalizadas dentro de las secciones estándar."""
    detected = []

    for section in STANDARD_SECTIONS:
        section_path = VAULT_ROOT / section
        if not section_path.exists():
            continue

        for item in section_path.iterdir():
            if not item.is_dir():
                continue
            if item.name.startswith("."):
                continue
            if item.name.startswith("_"):
                continue

            relative_path = str(item.relative_to(VAULT_ROOT))

            detected.append(
                {
                    "path": relative_path,
                    "name": item.name,
                    "section": section,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "type": "subfolder",
                    "created_by": "unknown",
                }
            )

            for subitem in item.iterdir():
                if subitem.is_dir():
                    sub_relative = str(subitem.relative_to(VAULT_ROOT))
                    detected.append(
                        {
                            "path": sub_relative,
                            "name": subitem.name,
                            "section": section,
                            "parent": relative_path,
                            "detected_at": datetime.now(timezone.utc).isoformat(),
                            "type": "subfolder",
                            "created_by": "unknown",
                        }
                    )

    return detected


def scan_and_update() -> Dict[str, Any]:
    """Escanea y actualiza el registro de carpetas."""
    registry = get_registry()
    detected = detect_custom_folders()

    existing_paths = {f["path"] for f in registry.get("folders", [])}
    new_folders = [f for f in detected if f["path"] not in existing_paths]

    if new_folders:
        registry["folders"].extend(new_folders)

    registry["detected_at"] = datetime.now(timezone.utc).isoformat()
    save_registry(registry)

    return {
        "ok": True,
        "total_folders": len(registry["folders"]),
        "new_folders": len(new_folders),
        "new_paths": [f["path"] for f in new_folders],
    }


def list_folders() -> List[Dict[str, Any]]:
    """Lista carpetas registradas."""
    registry = get_registry()
    return registry.get("folders", [])


def add_folder(path: str, created_by: str = "manual") -> Dict[str, Any]:
    """Agrega una carpeta manualmente."""
    registry = get_registry()

    for folder in registry.get("folders", []):
        if folder["path"] == path:
            return {"ok": False, "error": "Carpeta ya registrada"}

    section = path.split("/")[0] if "/" in path else ""

    folder_entry = {
        "path": path,
        "name": Path(path).name,
        "section": section,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "type": "subfolder",
        "created_by": created_by,
    }

    registry["folders"].append(folder_entry)
    save_registry(registry)

    return {"ok": True, "folder": folder_entry}


def remove_folder(path: str) -> Dict[str, Any]:
    """Elimina una carpeta del registro."""
    registry = get_registry()

    original_count = len(registry.get("folders", []))
    registry["folders"] = [f for f in registry.get("folders", []) if f["path"] != path]

    if len(registry["folders"]) == original_count:
        return {"ok": False, "error": "Carpeta no encontrada en el registro"}

    save_registry(registry)
    return {"ok": True, "removed": path}


def check_orphan_folders() -> List[str]:
    """Detecta carpetas registradas que ya no existen."""
    registry = get_registry()
    orphans = []

    for folder in registry.get("folders", []):
        folder_path = VAULT_ROOT / folder["path"]
        if not folder_path.exists():
            orphans.append(folder["path"])

    return orphans


def cleanup_orphans() -> Dict[str, Any]:
    """Limpia carpetas huérfanas del registro."""
    registry = get_registry()
    orphans = check_orphan_folders()

    if not orphans:
        return {"ok": True, "removed": 0}

    registry["folders"] = [
        f for f in registry.get("folders", []) if f["path"] not in orphans
    ]
    save_registry(registry)

    return {
        "ok": True,
        "removed": len(orphans),
        "orphans": orphans,
    }


def get_folders_for_indexing() -> List[str]:
    """Retorna lista de carpetas para indexación."""
    registry = get_registry()
    folders = [f["path"] for f in registry.get("folders", [])]

    all_folders = list(STANDARD_SECTIONS)
    all_folders.extend(folders)

    return all_folders


def main():
    parser = argparse.ArgumentParser(
        description="Vault Folder Registry - Gestión de carpetas personalizadas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_folder_registry.py
  python vault_folder_registry.py --scan
  python vault_folder_registry.py --list
  python vault_folder_registry.py --add "11_Code/tests"
  python vault_folder_registry.py --remove "11_Code/tests"
  python vault_folder_registry.py --cleanup
        """,
    )

    parser.add_argument(
        "--scan", action="store_true", help="Escanear y detectar carpetas nuevas"
    )
    parser.add_argument(
        "--list", action="store_true", help="Listar carpetas registradas"
    )
    parser.add_argument("--add", type=str, help="Agregar carpeta manualmente")
    parser.add_argument("--remove", type=str, help="Eliminar carpeta del registro")
    parser.add_argument(
        "--cleanup", action="store_true", help="Limpiar carpetas huérfanas"
    )
    parser.add_argument("--json", action="store_true", help="Salida JSON")

    args = parser.parse_args()

    if args.scan:
        result = scan_and_update()
    elif args.add:
        result = add_folder(args.add, created_by="manual")
    elif args.remove:
        result = remove_folder(args.remove)
    elif args.cleanup:
        result = cleanup_orphans()
    else:
        folders = list_folders()
        result = {
            "ok": True,
            "total": len(folders),
            "folders": folders,
            "orphan_folders": check_orphan_folders(),
        }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("ok", True):
            if "total" in result:
                print(f"Carpetas registradas: {result['total']}")
                for folder in result.get("folders", []):
                    print(
                        f"  - {folder['path']} ({folder.get('created_by', 'unknown')})"
                    )
                if result.get("orphan_folders"):
                    print(f"\nCarpetas huérfanas (no existen):")
                    for o in result["orphan_folders"]:
                        print(f"  - {o}")
            elif "new_folders" in result:
                print(f"Nuevas carpetas detectadas: {result['new_folders']}")
                for p in result.get("new_paths", []):
                    print(f"  + {p}")
            elif "removed" in result:
                print(f"Eliminadas: {result['removed']}")
                for o in result.get("orphans", []):
                    print(f"  - {o}")
            else:
                print("Carpeta agregada correctamente")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
            return 1

    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_folder_registry"))

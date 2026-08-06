#!/usr/bin/env python3

"""
Vault Folder Registry — adaptador de transporte del contexto Índices.

Detecta carpetas no estándar dentro de las secciones del vault, las registra
automáticamente y las incluye en índices y búsquedas. Desde v40.0 este fichero
no decide nada: las reglas viven en `vault/indices/carpetas.py`, con la raíz
inyectada en vez de derivada al importar (AP-49).

La ruta y el nombre no cambian: `scripts/vault_folder_registry.py` es lo que
resuelven el tool-spec, `cli/registry.py`, el runner del MCP y `vault_smoke`.

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
from pathlib import Path
from typing import Any, Dict, List

from vault_errors import wrap_main
from vault_registry import ORDERED_SECTIONS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.indices.carpetas import ServicioCarpetas  # noqa: E402
from vault.indices.repositorio import RepositorioIndices  # noqa: E402
from vault.kernel import construir  # noqa: E402

#: Se conserva el nombre publicado (no-derogación): quien importe
#: `STANDARD_SECTIONS` sigue teniendo el mismo contrato. Deriva del registro,
#: nunca de una lista copiada — la copia se quedó en 13 secciones mientras el
#: estándar ya tenía 22.
STANDARD_SECTIONS = frozenset(ORDERED_SECTIONS)


def _servicio(root=None) -> ServicioCarpetas:
    return ServicioCarpetas(RepositorioIndices(construir(root)))


def get_registry(root=None) -> Dict[str, Any]:
    """Carga el registro de carpetas."""
    return _servicio(root).registro()


def save_registry(registry: Dict[str, Any], root=None) -> None:
    """Guarda el registro de carpetas."""
    _servicio(root).guardar(registry)


def detect_custom_folders(root=None) -> List[Dict[str, Any]]:
    """Detecta carpetas personalizadas dentro de las secciones estándar."""
    return _servicio(root).detectar()


def scan_and_update(root=None) -> Dict[str, Any]:
    """Escanea y actualiza el registro de carpetas."""
    return _servicio(root).escanear()


def list_folders(root=None) -> List[Dict[str, Any]]:
    """Lista carpetas registradas."""
    return _servicio(root).listar()


def add_folder(path: str, created_by: str = "manual", root=None) -> Dict[str, Any]:
    """Agrega una carpeta manualmente."""
    return _servicio(root).anadir(path, created_by)


def remove_folder(path: str, root=None) -> Dict[str, Any]:
    """Elimina una carpeta del registro."""
    return _servicio(root).eliminar(path)


def check_orphan_folders(root=None) -> List[str]:
    """Detecta carpetas registradas que ya no existen."""
    return _servicio(root).huerfanas()


def cleanup_orphans(root=None) -> Dict[str, Any]:
    """Limpia carpetas huérfanas del registro."""
    return _servicio(root).limpiar_huerfanas()


def get_folders_for_indexing(root=None) -> List[str]:
    """Retorna lista de carpetas para indexación."""
    return _servicio(root).carpetas_indexables()


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
    servicio = _servicio()

    if args.scan:
        result = servicio.escanear()
    elif args.add:
        result = servicio.anadir(args.add, created_by="manual")
    elif args.remove:
        result = servicio.eliminar(args.remove)
    elif args.cleanup:
        result = servicio.limpiar_huerfanas()
    else:
        folders = servicio.listar()
        result = {
            "ok": True,
            "total": len(folders),
            "folders": folders,
            "orphan_folders": servicio.huerfanas(),
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
                    print("\nCarpetas huérfanas (no existen):")
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

#!/usr/bin/env python3

"""

Vault Migrate Rollback — Surgical undo of vault_migrate_docs



Reads _report-{project}-{date}.md as a reversal map and removes ONLY

the notes and stubs created by that migration. The rest of the vault is

untouched. Source files in source_path are never modified.



Usage:

    python vault_migrate_rollback.py --report_path "10_Migrated/_report-ans-2026-05-06.md" --confirm false

    python vault_migrate_rollback.py --report_path "10_Migrated/_report-ans-2026-05-06.md" --confirm true

"""


import argparse

import json

import re

import sys

from vault_errors import wrap_main

from pathlib import Path

from typing import Any, Dict, List, Tuple


from vault_io import atomic_write_json


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.ciclo_de_vida.repositorio import RepositorioCicloDeVida  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioCicloDeVida:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioCicloDeVida(construir(root))


def _index_file() -> Path:
    return _repo().indice_busqueda


def parse_report(report_path: Path) -> Tuple[List[str], List[str]]:

    """Parse migration report and return (distributed_paths, stub_paths)."""

    content = report_path.read_text(encoding="utf-8", errors="ignore")


    # Parse "## Archivos Distribuidos" table: | `name` | [[destPath]] | relevance |

    distributed = [

        m.strip()

        for m in re.findall(r"\|\s*`[^`]+`\s*\|\s*\[\[([^\]|]+)(?:\|[^\]]+)?\]\]\s*\|", content)

    ]


    # Parse "## Stubs Creados": - `name` → [[stubPath]]

    stubs = [

        m.strip()

        for m in re.findall(r"→\s*\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)

    ]


    return distributed, stubs


def remove_from_index(paths_to_remove: List[str]) -> int:

    """Remove entries from search-index.json. Returns count removed."""

    try:

        with open(_index_file(), "r", encoding="utf-8") as f:

            index = json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):

        return 0


    paths_set = set(paths_to_remove)

    original_count = len(index.get("notes", []))

    index["notes"] = [n for n in index.get("notes", []) if n.get("path") not in paths_set]

    removed = original_count - len(index["notes"])


    # atomic_write_* y no `open(..., "w")`: el escaneo de secretos, el
    # saneado de encoding y el temp+replace viven ahí. Escribir en crudo los
    # esquivaba los tres (AP-36) y dejaba la nota a medias si el proceso moría.
    atomic_write_json(_index_file(), index)


    return removed


def vault_migrate_rollback(report_path_str: str, confirm: bool = False) -> Dict[str, Any]:

    """

    Undo a vault_migrate_docs migration using its report as a reversal map.



    Args:

        report_path_str: Relative path to the migration report (e.g. '10_Migrated/_report-ans-2026-05-06.md')

        confirm: If False, returns a preview without deleting. If True, executes the rollback.



    Returns:

        Dict with rollback result or preview.

    """

    report_path = _raiz() / report_path_str


    if not report_path.exists():

        return {"ok": False, "error": f"Report not found: {report_path_str}"}


    distributed_paths, stub_paths = parse_report(report_path)

    all_paths = distributed_paths + stub_paths


    if not all_paths:

        return {

            "ok": False,

            "error": "No files found in report — report may be empty or malformed.",

            "hint": "Check that the report has '## Archivos Distribuidos' and '## Stubs Creados' sections.",

        }


    existing_files = [_raiz() / p for p in all_paths if (_raiz() / p).exists()]

    not_found = [p for p in all_paths if not (_raiz() / p).exists()]


    if not confirm:

        return {

            "ok": True,

            "preview": True,

            "reportPath": report_path_str,

            "toDelete": [str(f.relative_to(_raiz())) for f in existing_files],

            "notFound": not_found,

            "totalInReport": len(all_paths),

            "existingFiles": len(existing_files),

            "message": (

                f"Preview: {len(existing_files)} files would be deleted "

                f"({len(not_found)} already missing). "

                f"Run with confirm=true to execute."

            ),

        }


    # Execute rollback

    deleted = []

    errors = []


    for f in existing_files:

        try:

            f.unlink()

            deleted.append(str(f.relative_to(_raiz())))

        except Exception as e:

            errors.append({"path": str(f.relative_to(_raiz())), "error": str(e)})


    # Remove entries from search index

    index_removed = remove_from_index(all_paths)


    # Delete the report itself

    report_deleted = False

    try:

        report_path.unlink()

        report_deleted = True

    except Exception:

        pass


    return {

        "ok": True,

        "preview": False,

        "deleted": deleted,

        "deletedCount": len(deleted),

        "notFound": not_found,

        "errors": errors,

        "indexEntriesRemoved": index_removed,

        "reportDeleted": report_deleted,

        "message": (

            f"Rollback complete: {len(deleted)} files removed, "

            f"{index_removed} index entries removed."

        ),

    }


def main():

    parser = argparse.ArgumentParser(

        description="Vault Migrate Rollback -- Surgical undo of vault_migrate_docs",

        formatter_class=argparse.RawDescriptionHelpFormatter,

        epilog="""

Ejemplos:

  python vault_migrate_rollback.py --report_path "10_Migrated/_report-ans-2026-05-06.md" --confirm false

  python vault_migrate_rollback.py --report_path "10_Migrated/_report-ans-2026-05-06.md" --confirm true

  python vault_migrate_rollback.py --report_path "10_Migrated/_report-mi-api-2026-04-01.md" --confirm true



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - --confirm false (default) muestra preview sin borrar nada

  - --confirm true ejecuta el rollback: borra notas, stubs y actualiza el indice

  - Solo elimina archivos creados por esa migracion especifica

""",

    )

    parser.add_argument(

        "--report_path",

        required=True,

        help="Relative path to migration report (e.g. '10_Migrated/_report-ans-2026-05-06.md')",

    )

    parser.add_argument(

        "--confirm",

        type=lambda x: x.lower() == "true",

        default=False,

        help="If false (default), shows preview only. If true, executes the rollback.",

    )


    args = parser.parse_args()

    result = vault_migrate_rollback(args.report_path, args.confirm)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":

    sys.exit(wrap_main(main, "vault_migrate_rollback"))


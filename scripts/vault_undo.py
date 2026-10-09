#!/usr/bin/env python3
"""
Vault Undo Tool — Recover a note from .history/.

Lists available versions in .history/ and restores one to the vault.
Does NOT overwrite the current version — restores to a new file unless --force is used.

SP-01 applies if the restored note replaces an existing one: a change_log entry
with action=updated is written before the restore.

Usage:
    python vault_undo.py --list "01_Projects/ans/status.md"
    python vault_undo.py --restore "01_Projects/ans/status.md"
    python vault_undo.py --restore "01_Projects/ans/status.md" --version "01_Projects__ans__status-2026-07-15T09-00-00.md"
    python vault_undo.py --restore "01_Projects/ans/status.md" --force   # overwrite current
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import emit_error, emit_fallo, wrap_main
from vault_io import assert_within_vault, atomic_write_text, tomar_lock
from vault_lib import utcnow

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel import historia  # noqa: E402


def _raiz() -> Path:
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    return RepositorioAutoria(construir(root))


def _history_dir() -> Path:
    return _repo().dir_historial


def _ruta_fuera_del_vault(path: str) -> Optional[Dict[str, Any]]:
    """AP-36: el envelope INVALID_PATH si *path* sale del vault; None si no.

    Sin esto una ruta absoluta acababa en UNEXPECTED_ERROR critical, y una con
    `../` se buscaba en .history/ como si fuera una nota del vault.
    """
    try:
        assert_within_vault(_raiz() / path, _raiz())
    except ValueError as exc:
        return emit_error("vault_undo", "INVALID_PATH", str(exc))
    return None


def get_history_versions(note_path: str) -> List[Dict[str, Any]]:
    """Return sorted list of version metadata for a note (newest first).

    Delega en `vault.kernel.historia` (v41.3): el prefijo `carpeta__stem-` que
    filtraba aquí también casaba con las versiones de `stem-otra.md`, y el orden
    por mtime lo deshace cualquier copia del vault.
    """
    note_path_obj = _raiz() / note_path
    if not note_path_obj.exists():
        return []
    rel = note_path_obj.relative_to(_raiz()).as_posix()
    versions: List[Dict[str, Any]] = []
    for v in historia.versiones(_history_dir(), rel):
        try:
            st = v["path"].stat()
        except OSError:
            continue
        versions.append({
            "filename": v["filename"],
            "size_bytes": st.st_size,
            "modified": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            "timestamp": v["timestamp"].isoformat(),
        })
    return versions


#: Espera máxima por el lock de la nota; la misma que vault_write y vault_append.
_LOCK_TIMEOUT = 10.0


def _guardar_version_actual(note_path: Path) -> str:
    """Copia la versión actual a .history/ antes de taparla (CIA-A).

    Mismo nombre que leen `get_history_versions` y escribe `vault_write`, así
    que la versión tapada pasa a ser la más reciente y otro `--force` la
    devuelve. Devuelve el nombre del fichero guardado.
    """
    # Dos versiones en el mismo segundo: la segunda no pisa a la primera.
    destino = historia.nombre_libre(_history_dir(),
                                    note_path.relative_to(_raiz()).as_posix())
    _history_dir().mkdir(parents=True, exist_ok=True)
    atomic_write_text(destino, note_path.read_text(encoding="utf-8", errors="replace"))
    return destino.name


def _restore_change_log(note_path: str, version_filename: str, agent: str) -> str:
    """Write SP-01 entry before restoring over an existing note. Returns entry id."""
    from vault_change_log import vault_change_log_add

    result = vault_change_log_add(
        action="updated",
        path=note_path,
        reason=f"Restored from .history/{version_filename}",
        agent=agent,
    )
    if not result.get("ok"):
        raise RuntimeError(f"vault_change_log_add failed: {result}")
    return result["id"]


def vault_undo(
    path: str,
    version: Optional[str] = None,
    force: bool = False,
    dry_run: bool = False,
    agent: str = "claude",
) -> Dict[str, Any]:
    """
    Restore a note from .history/.

    By default restores to a NEW file: <note>-restored-<timestamp>.md
    With --force: overwrites the current note (SP-01 change_log entry is written).

    Args:
        path: vault-relative note path
        version: specific version filename in .history/ (default: most recent)
        force: overwrite current note instead of creating restored copy
        dry_run: don't write anything, just report what would happen
        agent: agent name for change_log
    """
    fuera = _ruta_fuera_del_vault(path)
    if fuera:
        return fuera

    vault_root = _raiz()
    note_path = vault_root / path

    if not note_path.exists():
        return emit_error(
            "vault_undo", "NOTE_NOT_FOUND",
            f"No existe la nota: {path}",
        )

    versions = get_history_versions(path)
    if not versions:
        return emit_error(
            "vault_undo", "HISTORY_NOT_FOUND",
            f"No se encontraron versiones en .history/ para: {path}",
        )

    if version is None:
        target = versions[0]
    else:
        target = next((v for v in versions if v["filename"] == version), None)
        if target is None:
            available = [v["filename"] for v in versions]
            return emit_error(
                "vault_undo", "VERSION_NOT_FOUND",
                f"Version '{version}' no encontrada. Disponibles: {available}",
            )

    history_file = _history_dir() / target["filename"]
    restored_content = history_file.read_text(encoding="utf-8", errors="replace")

    if force:
        previous_saved_as = None
        if not dry_run:
            # Bajo el lock de la nota: un vault_append concurrente no se pierde
            # bajo la versión restaurada (F1). Y la actual se guarda antes de
            # taparla, o un undo equivocado no tendría vuelta (CIA-A).
            lock = tomar_lock(note_path, _LOCK_TIMEOUT)
            if lock is None:
                return {
                    **emit_error(
                        "vault_undo", "NOTE_LOCKED",
                        f"Otro escritor tiene {path}; no se restauró nada.",
                    ),
                    "path": path,
                }
            with lock:
                previous_saved_as = _guardar_version_actual(note_path)
                _restore_change_log(path, target["filename"], agent)
                atomic_write_text(note_path, restored_content)
        return {
            "ok": True,
            "action": "overwritten",
            "note": path,
            "restored_from": target["filename"],
            "previous_saved_as": previous_saved_as,
            "restored_at": utcnow(),
            "versions_restored": 1,
            "dry_run": dry_run,
        }
    else:
        timestamp = datetime.now(timezone.utc).strftime(historia.FORMATO)
        stem = note_path.stem
        restored_name = f"{stem}-restored-{timestamp}.md"
        restored_path = note_path.parent / restored_name

        if not dry_run:
            _restore_change_log(path, target["filename"], agent)
            atomic_write_text(restored_path, restored_content)

        return {
            "ok": True,
            "action": "restored_as_new",
            "note": path,
            "restored_from": target["filename"],
            "restored_to": str(restored_path.relative_to(vault_root)).replace("\\", "/"),
            "restored_at": utcnow(),
            "versions_restored": 1,
            "dry_run": dry_run,
        }


def vault_undo_list(path: str) -> Dict[str, Any]:
    """List available versions in .history/ for a note."""
    fuera = _ruta_fuera_del_vault(path)
    if fuera:
        return fuera
    versions = get_history_versions(path)
    if not versions:
        return emit_error(
            "vault_undo", "HISTORY_NOT_FOUND",
            f"No se encontraron versiones en .history/ para: {path}",
        )
    return {
        "ok": True,
        "note": path,
        "versions": versions,
        "total": len(versions),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Undo — recover notes from .history/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Listar versiones disponibles
  python vault_undo.py --list "01_Projects/ans/status.md"

  # Restaurar la version mas reciente como nuevo archivo
  python vault_undo.py --restore "01_Projects/ans/status.md"

  # Restaurar version especifica como nuevo archivo
  python vault_undo.py --restore "01_Projects/ans/status.md" --version "01_Projects__ans__status-2026-07-15T09-00-00.md"

  # Restaurar sobreescribiendo la nota actual (SP-01: genera change_log)
  python vault_undo.py --restore "01_Projects/ans/status.md" --force

  # Simular sin escribir nada
  python vault_undo.py --restore "01_Projects/ans/status.md" --dry-run

Notas:
  - Sin --force: restaura como <nota>-restored-<timestamp>.md (no sobreescribe)
  - Con --force: sobreescribe la nota actual y escribe entrada en change-log (SP-01)
  - Solo funciona para notas que fueron editadas con vault_write (que crea el .history/)
""",
        allow_abbrev=False,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", dest="list_path", metavar="PATH",
                       help="Listar versiones disponibles en .history/ para esta nota")
    group.add_argument("--restore", dest="restore_path", metavar="PATH",
                       help="Restaurar una version desde .history/")

    parser.add_argument("--version", dest="version",
                        help="Filename exacto en .history/ (default: la mas reciente)")
    parser.add_argument("--force", action="store_true",
                        help="Sobrescribir la nota actual en lugar de crear copia")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo reportar lo que haria, sin escribir nada")
    parser.add_argument("--agent", default="claude",
                        help="Nombre del agente para change-log (default: claude)")

    args = parser.parse_args()

    if args.list_path:
        result = vault_undo_list(args.list_path)
    else:
        result = vault_undo(
            path=args.restore_path,
            version=args.version,
            force=args.force,
            dry_run=args.dry_run,
            agent=args.agent,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_undo"))

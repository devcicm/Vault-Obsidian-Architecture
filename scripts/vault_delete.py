#!/usr/bin/env python3
"""
Vault Delete Tool — Delete a note with SP-01 enforcement.

SP-01 exige que antes de eliminar cualquier nota se registre en change-log.
Esta tool lo hace automatico: si no hay entrada de deleted para esta nota,
la crea ANTES de borrar (SP-01), y luego elimina.

Usage:
    python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Duplicate of glossary/jwt.md"
    python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Outdated" --dry-run
    python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Outdated" --trash-only
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

from vault_errors import emit_error, fuera_de_sesion, wrap_main
from vault_entorno import agente_por_defecto
from vault_io import (
    assert_within_vault, atomic_write_json, atomic_write_text, refrescar_indice_de_seccion,
)
from vault_registry import es_artefacto_derivado
from vault_move import notas_que_enlazan

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel import historia  # noqa: E402


def _raiz() -> Path:
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    return RepositorioAutoria(construir(root))


def _trash_dir() -> Path:
    trash = _raiz() / "20_Quarantine"
    trash.mkdir(parents=True, exist_ok=True)
    return trash


def _already_deleted(path: str) -> bool:
    """Check if a change_log entry with action=deleted already exists for this path."""
    from vault_change_log import vault_change_log_query

    result = vault_change_log_query(action_filter="deleted")
    if not result.get("ok"):
        return False
    entries = result.get("entries", [])
    path_normalized = path.replace("\\", "/")
    return any(
        e.get("path", "").replace("\\", "/") == path_normalized
        for e in entries
    )


def _write_deleted_entry(path: str, reason: str, agent: str) -> str:
    """Write SP-01 change_log entry via vault_change_log_add. Returns entry id."""
    from vault_change_log import vault_change_log_add

    result = vault_change_log_add(
        action="deleted",
        path=path,
        reason=reason,
        agent=agent,
    )
    if not result.get("ok"):
        raise RuntimeError(f"vault_change_log_add failed: {result}")
    return result["id"]


def _quitar_del_indice(rel_path: str) -> Dict[str, Any]:
    """Retira la nota de search-index.json.

    Sin esto `vault_search` seguia devolviendo la nota borrada: una entrada
    que apunta a un fichero que ya no existe. Es la contraparte de
    `vault_move.update_search_index`, que reescribe la ruta en vez de quitarla.
    """
    indice = _repo().indice_busqueda
    if not indice.exists():
        return {"updated": False, "reason": "search-index not found"}
    datos = json.loads(indice.read_text(encoding="utf-8"))
    if not isinstance(datos, dict):
        return {"updated": False, "reason": "search-index con esquema no reconocido"}
    notas = datos.get("notes", [])
    quedan = [n for n in notas if not (isinstance(n, dict) and n.get("path") == rel_path)]
    if len(quedan) == len(notas):
        return {"updated": False, "removed": 0}
    datos["notes"] = quedan
    atomic_write_json(indice, datos)
    return {"updated": True, "removed": len(notas) - len(quedan)}


def _indice_tras_borrar(rel_path: str) -> Dict[str, Any]:
    """El borrado ya ocurrio: un indice ilegible se degrada a aviso, no a ok:false."""
    try:
        return _quitar_del_indice(rel_path)
    except Exception as exc:  # noqa: BLE001 - la nota ya no esta en disco
        return {"updated": False, "error": f"{type(exc).__name__}: {exc}",
                "hint": "ejecutar vault_reindex"}


def _guardar_lo_que_se_borra(note_path: Path, rel_path: str) -> str:
    """CIA-A: la versión que se borra queda en `.history/` antes del `unlink`.

    Hasta 2026-10-10 el borrado era definitivo salvo que una escritura previa
    hubiese dejado versión. Mismo nombre que escribe `vault_write` y lee
    `vault_undo` (`vault.kernel.historia`), así que `vault_undo --restore` la
    encuentra sin saber que vino de un borrado. Devuelve el nombre guardado.
    """
    destino = historia.nombre_libre(_repo().dir_historial, rel_path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(destino, note_path.read_text(encoding="utf-8", errors="replace"))
    return destino.name


def vault_delete(
    path: str,
    reason: str,
    agent: str = "claude",
    trash_only: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Delete a note with SP-01 enforcement.

    SP-01 (Delete protocol): antes de eliminar, debe existir una entrada en
    change-log con action=deleted. Esta tool lo garantiza de forma automatica:
    si no existe la entrada, la crea ANTES de borrar.

    Args:
        path: vault-relative note path
        reason: motivo de eliminacion (requerido)
        agent: agente que realiza la eliminacion
        trash_only: solo mover a 20_Quarantine/ en vez de eliminar
        dry_run: no escribir nada, solo reportar
        force: omitir la verificacion SP-01 (para uso interno)
    """
    if not reason or not reason.strip():
        return emit_error(
            "vault_delete", "MISSING_REQUIRED_ARG",
            "`--reason` es obligatorio y no puede estar vacio",
        )

    vault_root = _raiz()
    note_path = vault_root / path

    # AP-36: `--path "../x"` o una ruta absoluta borraban —o movian a
    # cuarentena— un fichero fuera del vault y devolvian ok: true. La
    # contencion se comprueba antes de mirar si existe, para que la respuesta
    # no revele que hay fuera del vault.
    try:
        assert_within_vault(note_path, vault_root)
    except ValueError as exc:
        return emit_error("vault_delete", "INVALID_PATH", str(exc))

    bloqueo = fuera_de_sesion("vault_delete", note_path)
    if bloqueo:
        return bloqueo

    # SP-01 es el protocolo de borrado de notas: los indices, el change-log y
    # cualquier otro fichero del vault no se borran por esta via.
    if note_path.suffix.lower() != ".md":
        return emit_error(
            "vault_delete", "INVALID_PATH",
            f"'{path}' no es una nota (.md); vault_delete solo elimina notas.",
        )

    # AP-47: el `index.md` de una sección lo rehace su generador; borrarlo con
    # ok:true dejaba la sección sin índice hasta la siguiente escritura
    # (medido como consumidor, 2026-10-10). La ruta se resuelve antes de
    # clasificarla, para que `x/../07_Knowledge/index.md` no esquive el criterio.
    relativa = note_path.resolve().relative_to(vault_root.resolve()).as_posix()
    if es_artefacto_derivado(relativa):
        return emit_error(
            "vault_delete", "INVALID_PATH",
            f"AP-47: '{path}' es un artefacto derivado (lo rehace su generador); "
            "vault_delete solo elimina notas.",
        )

    if not note_path.exists():
        return emit_error(
            "vault_delete", "NOTE_NOT_FOUND",
            f"No existe la nota: {path}",
        )

    if note_path.is_dir():
        return emit_error(
            "vault_delete", "INVALID_PATH",
            f" path '{path}' es una carpeta, no un archivo.",
        )

    # La forma con la que vault_write indexa la nota: relativa y con `/`.
    rel_path = note_path.resolve().relative_to(vault_root.resolve()).as_posix()

    already_logged = _already_deleted(path)
    # AP-14: borrar deja rotos los enlaces que llegaban a la nota. No se
    # reescriben —no hay destino—, pero el sobre los nombra: hasta 2026-10-10
    # el consumidor se enteraba al auditar el grafo, no al borrar.
    entrantes = notas_que_enlazan(rel_path)

    if dry_run:
        if already_logged:
            sp01_note = "SP-01: entrada de change-log ya existente"
        elif force:
            sp01_note = "SP-01: forzado con --force (sin change-log)"
        else:
            sp01_note = "SP-01: WOULD escribir entrada en change-log antes de eliminar"
        return {
            "ok": True,
            "action": "dry_run",
            "note": path,
            "sp01_status": sp01_note,
            "would_delete": not trash_only,
            "would_move_to_quarantine": trash_only,
            # AP-37: los indicadores que `tool-spec.json` declara, en falso.
            "deleted": False,
            "trashed": False,
            "change_logged": False,
            "inbound_links": entrantes,
        }

    change_logged = not already_logged and not force
    if change_logged:
        entry_id = _write_deleted_entry(path, reason, agent)
        sp01_note = (
            "SP-01: entrada de change-log escrita antes de eliminar "
            f"(id: {entry_id[:8]}...)"
        )
    elif already_logged:
        sp01_note = "SP-01: entrada de change-log ya existente para esta nota"
    else:
        sp01_note = "SP-01: forzado con --force (sin change-log)"

    if trash_only:
        trash_dest = _trash_dir() / note_path.name
        counter = 1
        while trash_dest.exists():
            stem = note_path.stem
            trash_dest = _trash_dir() / f"{stem}_{counter}.md"
            counter += 1
        shutil.move(str(note_path), str(trash_dest))
        # AP-47: quitarla de su sección la saca del `index.md`, que solo se
        # rehacía al escribir (medido como consumidor, 2026-10-10).
        seccion = refrescar_indice_de_seccion(note_path)
        return {
            "ok": True,
            "action": "moved_to_quarantine",
            "note": path,
            "quarantined_to": str(trash_dest.relative_to(vault_root)).replace("\\", "/"),
            "deleted": False,
            "trashed": True,
            "change_logged": change_logged,
            "sp01_status": sp01_note,
            "inbound_links": entrantes,
            "section_index": seccion,
            "search_index": _indice_tras_borrar(rel_path),
        }
    else:
        guardada = _guardar_lo_que_se_borra(note_path, rel_path)
        note_path.unlink()
        seccion = refrescar_indice_de_seccion(note_path)
        return {
            "ok": True,
            "action": "deleted",
            "note": path,
            "deleted": True,
            "trashed": False,
            "change_logged": change_logged,
            "sp01_status": sp01_note,
            "recoverable": {
                "history": guardada,
                "restore": f'vault_undo --restore "{rel_path}"',
            },
            "inbound_links": entrantes,
            "section_index": seccion,
            "search_index": _indice_tras_borrar(rel_path),
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Delete — delete a note with SP-01 enforcement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
SP-01 (Delete Protocol): antes de eliminar, debe existir una entrada en
change-log con action=deleted. Esta tool lo garantiza automaticamente.

Si no existe la entrada para esta nota, la CREA ANTES de borrar.

Ejemplos:
  # Eliminacion normal (crea change-log si no existe, luego borra)
  python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Duplicate of glossary/jwt.md"

  # Solo mover a cuarentena (no elimina)
  python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Needs review" --trash-only

  # Simular sin escribir nada
  python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Test" --dry-run

  # Forzar eliminacion sin change-log (uso interno)
  python vault_delete.py --path "07_Knowledge/old-note.md" --reason "Test" --force

Notas:
  - --reason es OBLIGATORIO
  - Si la nota ya fue registrada como deleted en change-log, no escribira entrada duplicada
  - --trash-only mueve a 20_Quarantine/ en vez de eliminar
  - --force omite la creacion de change-log (para recovery de la propia tool)
""",
        allow_abbrev=False,
    )
    parser.add_argument("--path", required=True, help="Ruta relativa al vault de la nota a eliminar")
    parser.add_argument("--reason", required=True, help="Motivo de eliminacion (SP-01)")
    parser.add_argument("--agent", default=agente_por_defecto(), help="Nombre del agente (default: VAULT_AGENT o claude)")
    parser.add_argument("--trash-only", action="store_true",
                        help="Solo mover a 20_Quarantine/ en vez de eliminar")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simular sin escribir nada")
    parser.add_argument("--force", action="store_true",
                        help="Omitir creacion de change-log (uso interno)")

    args = parser.parse_args()
    result = vault_delete(
        path=args.path,
        reason=args.reason,
        agent=args.agent,
        trash_only=args.trash_only,
        dry_run=args.dry_run,
        force=args.force,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_delete"))

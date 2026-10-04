#!/usr/bin/env python3

"""

Vault Merge — Merge an external vault or deduplicate internal notes.



Blueprint: vault-obsidian-architecture.md § vault_merge(source, conflict?, action?)



Actions:

  merge  — import all notes from external vault into this vault

  detect — find internally duplicated notes (same stem, different folders)

  dedup  — merge duplicate internal notes, keeping the most recent (DESTRUCTIVE)



Usage:

    python vault_merge.py --source "/path/to/other-vault" --action merge --conflict skip

    python vault_merge.py --action detect

    python vault_merge.py --action dedup   # run vault_backup first!

"""

import argparse

import json

import sys

from vault_errors import emit_error, wrap_main

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Dict, List, Optional


from vault_io import atomic_write_text, get_vault_root, normalize_stem, tomar_lock, write_report
from vault_undo import _guardar_version_actual

from vault_lib import separar_frontmatter
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402


#: Espera máxima por el lock de la nota; la misma que vault_write y vault_undo.
_LOCK_TIMEOUT = 10.0


def _read_note(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _tag_frontmatter(content: str, source: str) -> str:
    """Inject mergedFrom and mergedAt into existing frontmatter, or prepend one."""

    bloque, cuerpo = separar_frontmatter(content)

    # AP-46: el bloque lo reescribe su dueño. Antes se añadían las dos líneas
    # al final, así que fusionar dos veces en la misma nota dejaba dos
    # `mergedFrom:` —YAML se queda con la última; otros lectores, no—. Ahora
    # la segunda fusión reemplaza a la primera en su sitio.
    fm = (
        Frontmatter.editar(bloque or "")
        .set("mergedFrom", source)
        .set("mergedAt", f"{datetime.now(timezone.utc).isoformat()[:19]}Z")
    )

    if bloque is not None:
        return fm.render() + "\n" + cuerpo

    # No frontmatter — prepend minimal block

    return fm.render() + "\n\n" + content


def _note_updated_at(path: Path) -> str:
    """Extract updatedAt from frontmatter, fallback to mtime."""

    try:
        content = _read_note(path)

        bloque, _ = separar_frontmatter(content)

        if bloque is not None:
            for line in bloque.splitlines():
                if line.startswith("updatedAt:"):
                    return line.split(":", 1)[1].strip().strip("\"'")

    except Exception as exc:
        emit_error("vault_merge", "UPDATED_AT_PARSE_ERROR", str(exc))

    return datetime.fromtimestamp(path.stat().st_mtime).isoformat()


# ── action: merge ────────────────────────────────────────────────────────────


def _action_merge(source_dir: Path, conflict: str) -> Dict[str, Any]:
    notes = [
        n
        for n in source_dir.rglob("*.md")
        if ".history" not in str(n) and not n.name.startswith("_")
    ]

    merged = skipped = conflicts = 0

    locked: List[str] = []

    for src in notes:
        # Preserve relative structure from source root

        try:
            rel = src.relative_to(source_dir)

        except ValueError:
            rel = Path(src.name)

        dest = get_vault_root() / rel

        if dest.exists() and conflict == "rename":
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

            dest = dest.with_stem(f"{dest.stem}-{stamp}")

            conflicts += 1

        dest.parent.mkdir(parents=True, exist_ok=True)

        content = _tag_frontmatter(_read_note(src), str(source_dir))

        # CIA-A / F1: `overwrite` tapaba la nota del vault sin copiarla antes a
        # .history/ y sin lock. Medido en v40.34: `vault_undo` no tenía nada que
        # devolver y una nota con el lock de otro escritor se reescribía igual,
        # con `ok: true`. La existencia se decide dentro del lock: fuera, `skip`
        # era comprobar-y-luego-escribir.
        lock = tomar_lock(dest, _LOCK_TIMEOUT)

        if lock is None:
            locked.append(rel.as_posix())

            continue

        with lock:
            if dest.exists():
                if conflict == "skip":
                    conflicts += 1

                    skipped += 1

                    continue

                if conflict == "overwrite":
                    conflicts += 1

                # overwrite, o un rename cuyo nombre sellado ya creó otro
                # escritor en el mismo segundo: lo tapado queda en el historial.
                _guardar_version_actual(dest)

            atomic_write_text(dest, content)

        merged += 1

    if locked:
        return emit_error(
            "vault_merge", "NOTE_LOCKED",
            f"{len(locked)} nota(s) las tiene otro escritor y no se fusionaron "
            f"({', '.join(locked)}); se fusionaron {merged} y se omitieron {skipped}",
        )

    return {
        "ok": True,
        **write_report(),
        "action": "merge",
        "merged": merged,
        "skipped": skipped,
        "conflicts": conflicts,
    }


# ── action: detect ───────────────────────────────────────────────────────────


def _normalize(stem: str) -> str:
    # Identidad por nombre: la del dueño, no una copia (AP-57, AP-17).
    return normalize_stem(stem)


def _action_detect() -> Dict[str, Any]:
    buckets: Dict[str, List[str]] = {}

    for note in get_vault_root().rglob("*.md"):
        if ".history" in str(note) or note.name.startswith("_"):
            continue

        key = _normalize(note.stem)

        buckets.setdefault(key, []).append(note.relative_to(get_vault_root()).as_posix())

    duplicates = {k: v for k, v in buckets.items() if len(v) > 1}

    return {
        "ok": True,
        **write_report(),
        "action": "detect",
        "duplicateGroups": len(duplicates),
        "duplicates": duplicates,
    }


# ── action: dedup ─────────────────────────────────────────────────────────────


def _action_dedup() -> Dict[str, Any]:
    buckets: Dict[str, List[Path]] = {}

    for note in get_vault_root().rglob("*.md"):
        if ".history" in str(note) or note.name.startswith("_"):
            continue

        key = _normalize(note.stem)

        buckets.setdefault(key, []).append(note)

    merged_count = 0

    for key, paths in buckets.items():
        if len(paths) < 2:
            continue

        # Sort: most recent first (by updatedAt or mtime)

        paths.sort(key=_note_updated_at, reverse=True)

        canonical = paths[0]

        others = paths[1:]

        canonical_content = _read_note(canonical)

        for other in others:
            body = _read_note(other)

            # Strip frontmatter from the non-canonical note

            body = separar_frontmatter(body)[1]

            canonical_content += "\n\n---\n\n" + body.strip()

            other.unlink()

            merged_count += 1

        atomic_write_text(canonical, canonical_content)

    return {
        "ok": True,
        **write_report(),
        "action": "dedup",
        "merged": merged_count,
    }


# ── public API ────────────────────────────────────────────────────────────────


def vault_merge(
    source: Optional[str] = None,
    conflict: str = "skip",
    action: str = "merge",
) -> Dict[str, Any]:
    """

    Merge an external vault or manage internal duplicates.



    Args:

        source:   Path to external vault root (required for action="merge").

        conflict: "skip" | "overwrite" | "rename"  (used by action="merge").

        action:   "merge" | "detect" | "dedup"



    Returns:

        { ok, action, merged, skipped, conflicts }          for action="merge"

        { ok, action, duplicateGroups, duplicates: {...} }  for action="detect"

        { ok, action, merged }                              for action="dedup"

    """

    if action == "merge":
        if not source:
            return emit_error("vault_merge", "MISSING_REQUIRED_ARG", "action='merge' requires --source")

        source_dir = Path(source)

        if not source_dir.exists():
            return emit_error("vault_merge", "FOLDER_NOT_FOUND", f"Source not found: {source}")

        return _action_merge(source_dir, conflict)

    if action == "detect":
        return _action_detect()

    if action == "dedup":
        return _action_dedup()

    return emit_error("vault_merge", "INVALID_VALUE", f"Unknown action: {action}. Use merge | detect | dedup")


def main():
    parser = argparse.ArgumentParser(
        description="Vault Merge -- blueprint: vault-obsidian-architecture.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_merge.py --source "/path/to/other-vault" --action merge --conflict skip

  python vault_merge.py --source "C:/old-vault" --action merge --conflict rename

  python vault_merge.py --action detect

  python vault_merge.py --action dedup



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - action=dedup es DESTRUCTIVO -- ejecutar vault_backup primero

  - conflict=skip (default), overwrite, rename

""",
        allow_abbrev=False,
    )

    parser.add_argument(
        "--source", help="Path to external vault root (required for action=merge)"
    )

    parser.add_argument(
        "--conflict",
        choices=["skip", "overwrite", "rename"],
        default="skip",
        help="Conflict policy when merging external vault (default: skip)",
    )

    parser.add_argument(
        "--action",
        choices=["merge", "detect", "dedup"],
        default="merge",
        help="merge=import external vault | detect=find duplicates | dedup=merge duplicates (default: merge)",
    )

    args = parser.parse_args()

    result = vault_merge(args.source, args.conflict, args.action)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_merge"))

#!/usr/bin/env python3
"""
Vault Section Index — Generate {folder}/index.md for a vault section.

Scans all notes in a section folder and writes a human-readable index.md.
This is a derived artifact — it is auto-regenerated and must never be edited manually.
vault_write calls this automatically after each successful write.

Usage:
    python vault_section_index.py --folder 01_Projects
    python vault_section_index.py --folder 01_Projects --no-subdirs
"""

import argparse
import json
import re
import sys
from vault_errors import wrap_main
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_io import VAULT_ROOT, assert_within_vault, safe_wikilink
from vault_registry import section_description, section_tool_hint


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _parse_frontmatter(content: str) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return meta
    for line in m.group(1).split("\n"):
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip("\"'")
        meta[key] = val
    return meta


def _collect_notes(section_path: Path, include_subdirs: bool) -> List[Dict[str, Any]]:
    """Scan folder and return metadata list for all real notes (excludes index.md)."""
    candidates = list(section_path.rglob("*.md")) if include_subdirs else list(section_path.glob("*.md"))
    notes: List[Dict[str, Any]] = []
    for note_path in sorted(candidates):
        if note_path.name == "index.md":
            continue
        if any(part.startswith(".") for part in note_path.parts):
            continue
        try:
            content = note_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        meta = _parse_frontmatter(content)
        rel = str(note_path.relative_to(section_path)).replace("\\", "/")
        notes.append({
            "title": meta.get("title") or note_path.stem,
            "path": rel,
            "type": meta.get("type") or "",
            "updatedAt": meta.get("updatedAt") or meta.get("createdAt") or "",
        })
    return notes


def _build_index_content(folder: str, notes: List[Dict[str, Any]], now: str) -> str:
    """Render index.md content — always populated even when section is empty."""
    folder_key = folder.replace("\\", "/")

    description = section_description(folder_key)
    hint = section_tool_hint(folder_key)
    tool_hint = hint if hint else f"vault_write --folder {folder_key} --title <titulo>"

    lines = [
        f"# {folder_key} — Índice",
        "",
        f"> **Propósito:** {description}",
        f"> Generado automáticamente · {now} · {len(notes)} nota(s)",
        "",
    ]

    if notes:
        lines += [
            "| Nota | Tipo | Actualizado |",
            "|---|---|---|",
        ]
        for n in notes:
            stem = safe_wikilink(Path(n["path"]).stem)
            title = safe_wikilink(n["title"])
            link = f"[[{stem}|{title}]]"
            lines.append(f"| {link} | {n['type']} | {n['updatedAt']} |")
    else:
        lines += [
            "## Estado",
            "",
            "Sección sin notas. Añade la primera con:",
            "",
            f"```bash",
            f"python scripts/{tool_hint}",
            f"```",
            "",
            "Una vez creada la primera nota, este índice se regenera automáticamente.",
        ]

    lines.append("")
    return "\n".join(lines)


def vault_section_index(folder: str, include_subdirs: bool = True) -> Dict[str, Any]:
    """
    Generate or update {folder}/index.md with a readable index of all notes.
    Always produces populated content — never a bare empty file.
    Also generates index.md for each immediate subdirectory when include_subdirs=True.

    Args:
        folder: Section folder relative to vault root (e.g. "01_Projects")
        include_subdirs: If True, include notes in subdirectories and index their subdirs

    Returns:
        {"ok": True, "path": "01_Projects/index.md", "noteCount": 12, "is_empty": False,
         "subdirIndexes": [...]}
    """
    section_path = VAULT_ROOT / folder
    if not section_path.exists():
        return {"ok": False, "error": "folder_not_found", "folder": folder}

    try:
        assert_within_vault(section_path, VAULT_ROOT)
    except ValueError as e:
        return {"ok": False, "error": "path_traversal", "detail": str(e)}

    now = _utcnow()
    notes = _collect_notes(section_path, include_subdirs)

    # Write main section index
    index_path = section_path / "index.md"
    assert_within_vault(index_path, VAULT_ROOT)
    index_path.write_text(_build_index_content(folder, notes, now), encoding="utf-8")

    # Generate index.md for each immediate subdirectory
    subdir_indexes: List[str] = []
    if include_subdirs:
        for sub in sorted(section_path.iterdir()):
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            sub_folder = str(sub.relative_to(VAULT_ROOT)).replace("\\", "/")
            sub_notes = _collect_notes(sub, include_subdirs=True)
            sub_index = sub / "index.md"
            assert_within_vault(sub_index, VAULT_ROOT)
            sub_index.write_text(_build_index_content(sub_folder, sub_notes, now), encoding="utf-8")
            subdir_indexes.append(str(sub_index.relative_to(VAULT_ROOT)).replace("\\", "/"))

    return {
        "ok": True,
        "path": str(index_path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "noteCount": len(notes),
        "is_empty": len(notes) == 0,
        "subdirIndexes": subdir_indexes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Section Index -- generate {folder}/index.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_section_index.py --folder 01_Projects
  python vault_section_index.py --folder 07_Knowledge
  python vault_section_index.py --folder 01_Projects --no-subdirs
  python vault_section_index.py --folder 08_Runbooks

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Se llama automaticamente por vault_write despues de cada escritura exitosa
  - El index.md generado es un artefacto derivado -- no editar manualmente
""",
    )
    parser.add_argument("--folder", required=True, help="Section folder relative to vault root")
    parser.add_argument("--no-subdirs", action="store_true", help="Exclude notes in subdirectories")
    args = parser.parse_args()

    result = vault_section_index(args.folder, include_subdirs=not args.no_subdirs)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_section_index"))

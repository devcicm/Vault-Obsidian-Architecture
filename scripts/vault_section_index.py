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

from vault_io import VAULT_ROOT

SECTION_DESCRIPTIONS = {
    "00_System": "Identidad, reglas y configuración del agente",
    "01_Projects": "Estado, contexto y progreso de proyectos activos",
    "02_Observability": "Errores, métricas, alertas y observabilidad",
    "03_Decisions": "Decisiones de arquitectura y diseño (ADRs)",
    "04_Sessions": "Diarios de sesión y contexto de trabajo",
    "05_Patterns": "Patrones reutilizables de código y arquitectura",
    "06_Diagrams": "Diagramas y representaciones visuales",
    "07_Knowledge": "Base de conocimiento técnico y conceptual",
    "08_Runbooks": "Procedimientos operativos paso a paso",
    "09_Infrastructure": "Infraestructura, entornos y configuraciones",
    "10_Migrated": "Documentos migrados de otras fuentes",
    "11_Code": "Módulos de código y relaciones entre ellos",
    "99_Index": "Índices de navegación del vault",
}


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


def vault_section_index(folder: str, include_subdirs: bool = True) -> Dict[str, Any]:
    """
    Generate or update {folder}/index.md with a readable index of all notes.

    Args:
        folder: Section folder relative to vault root (e.g. "01_Projects")
        include_subdirs: If True, include notes in subdirectories

    Returns:
        {"ok": True, "path": "01_Projects/index.md", "noteCount": 12}
    """
    section_path = VAULT_ROOT / folder
    if not section_path.exists():
        return {"ok": False, "error": "folder_not_found", "folder": folder}

    index_path = section_path / "index.md"

    # Collect all notes, excluding index.md itself
    if include_subdirs:
        candidates = list(section_path.rglob("*.md"))
    else:
        candidates = list(section_path.glob("*.md"))

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
        title = meta.get("title") or note_path.stem
        updated = meta.get("updatedAt") or meta.get("createdAt") or ""
        note_type = meta.get("type") or ""
        rel = str(note_path.relative_to(section_path)).replace("\\", "/")

        notes.append({
            "title": title,
            "path": rel,
            "type": note_type,
            "updatedAt": updated,
        })

    # Generate index.md content
    description = SECTION_DESCRIPTIONS.get(folder.split("/")[0], folder)
    now = _utcnow()

    lines = [
        f"# {folder} — Índice",
        "",
        f"> {description}",
        f"> Generado automáticamente · {now} · {len(notes)} nota(s)",
        "",
    ]

    if notes:
        lines += [
            "| Nota | Tipo | Actualizado |",
            "|---|---|---|",
        ]
        for n in notes:
            stem = Path(n["path"]).stem
            link = f"[[{stem}|{n['title']}]]"
            lines.append(f"| {link} | {n['type']} | {n['updatedAt']} |")
    else:
        lines.append("_Sin notas en esta sección._")

    lines.append("")
    index_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "ok": True,
        "path": str(index_path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "noteCount": len(notes),
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

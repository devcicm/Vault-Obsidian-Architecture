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


HUB_NOTE = VAULT_ROOT / "00_System" / "vault-hub.md"
COMMANDS_NOTE = VAULT_ROOT / "00_System" / "vault-commands.md"


def _ensure_hub_notes() -> None:
    """Idempotently create 00_System/vault-hub.md and vault-commands.md.

    The hub note is the single authoritative entry point — it links to every
    section index using stems Obsidian can resolve. The commands note is the
    single authoritative reference for execution commands — no command should
    appear inline in any other auto-generated file.

    Both are user-editable: if the file already exists we leave it alone.
    This protects manual edits while still bootstrapping a fresh vault.
    """
    if not HUB_NOTE.exists():
        hub_content = (
            "---\n"
            "title: Vault Hub\n"
            "id: vault-hub\n"
            "createdAt: " + _utcnow() + "\n"
            "updatedAt: " + _utcnow() + "\n"
            "cia_integrity: high\n"
            "cia_availability: high\n"
            "cia_sensitivity: internal\n"
            "agent: system\n"
            "tags: [\"nav\", \"hub\"]\n"
            "norm_refs: [\"CN-01\"]\n"
            "---\n"
            "\n"
            "# Vault Hub — Punto único de navegación\n"
            "\n"
            "> Esta nota es el **único hub** del vault. Todos los índices de sección "
            "y el índice maestro apuntan aquí. Si acabas de llegar al vault, lee primero esto.\n"
            "\n"
            "## Navegación principal\n"
            "\n"
            "- [[vault-commands|Comandos del vault]] — referencia unificada de comandos CLI\n"
            "- `99_Index/index.md` (Índice Maestro) — tabla resumen con conteo de notas por sección\n"
            "\n"
            "## Secciones\n"
            "\n"
            "| Sección | Descripción | Índice |\n"
            "|---|---|---|\n"
        )
        for section in [
            "00_System", "01_Projects", "02_Observability", "03_Decisions",
            "04_Sessions", "05_Patterns", "06_Diagrams", "07_Knowledge",
            "08_Runbooks", "09_Infrastructure", "10_Migrated", "11_Code",
            "12_Bibliography", "13_Flows", "14_Requirements", "15_Tests",
            "16_AI_Governance", "99_Index",
        ]:
            desc = section_description(section)
            hub_content += f"| `{section}` | {desc} | `{section}/index.md` |\n"
        hub_content += (
            "\n"
            "## Protocolo de sesión\n"
            "\n"
            "Inicio:\n"
            "1. `python scripts/vault_standard_upgrade.py --check`\n"
            "2. `python scripts/vault_reindex.py`\n"
            "3. `python scripts/vault_audit.py`\n"
            "\n"
            "Cierre:\n"
            "1. `python scripts/vault_audit.py`\n"
            "2. `python scripts/vault_tags.py`\n"
            "3. `python scripts/vault_reindex.py --graph`\n"
            "\n"
            "Para detalles de cada comando, ver [[vault-commands|vault-commands]].\n"
        )
        HUB_NOTE.write_text(hub_content, encoding="utf-8")

    if not COMMANDS_NOTE.exists():
        commands_content = (
            "---\n"
            "title: Vault Commands\n"
            "id: vault-commands\n"
            "createdAt: " + _utcnow() + "\n"
            "updatedAt: " + _utcnow() + "\n"
            "cia_integrity: high\n"
            "cia_availability: high\n"
            "cia_sensitivity: internal\n"
            "agent: system\n"
            "tags: [\"nav\", \"commands\"]\n"
            "norm_refs: [\"CN-01\"]\n"
            "---\n"
            "\n"
            "# Vault Commands — Referencia unificada de comandos CLI\n"
            "\n"
            "> Esta nota es la **referencia única de comandos** del vault. Ningún "
            "otro archivo (incluyendo índices auto-generados y stubs de sección) "
            "debería embeber un bloque `python scripts/...` inline. Si necesitas un "
            "comando nuevo, agrégalo aquí.\n"
            "\n"
            "Los ejemplos asumen que el CWD es la raíz del repositorio consumidor.\n"
            "\n"
            "## Inicialización\n"
            "\n"
            "```bash\n"
            "# Inicializar un vault nuevo con todas las carpetas y auto-indexar\n"
            "python scripts/vault_standard_upgrade.py --init v32\n"
            "\n"
            "# Aplicar migraciones pendientes (v20 → v32)\n"
            "python scripts/vault_standard_upgrade.py --to v32\n"
            "\n"
            "# Verificar estado de versión y carpetas\n"
            "python scripts/vault_standard_upgrade.py --check\n"
            "```\n"
            "\n"
            "## Bootstrap de un vault fresco (todo en uno)\n"
            "\n"
            "```bash\n"
            "# Equivalente a: init v32 + aplicar migraciones + auto-indexar todas las secciones\n"
            "python scripts/vault_init.py\n"
            "```\n"
            "\n"
            "## Escritura y lectura de notas\n"
            "\n"
            "```bash\n"
            "# Crear o actualizar una nota\n"
            "python scripts/vault_write.py --folder \"01_Projects/mi-api\" --title \"Status\" --content \"# Status\\n\\nActivo\"\n"
            "\n"
            "# Leer una nota por ruta\n"
            "python scripts/vault_read.py --path \"01_Projects/mi-api/status.md\"\n"
            "\n"
            "# Buscar full-text\n"
            "python scripts/vault_search.py --query \"circuit breaker\"\n"
            "\n"
            "# Listar notas de una carpeta\n"
            "python scripts/vault_list.py --folder \"01_Projects\"\n"
            "\n"
            "# Agregar contenido al final (changelogs, session logs)\n"
            "python scripts/vault_append.py --path \"04_Sessions/2026-06-19.md\" --content \"## Tasks\\n\\n- [x] Fix init\"\n"
            "```\n"
            "\n"
            "## Índices\n"
            "\n"
            "```bash\n"
            "# Regenerar índice de una sección\n"
            "python scripts/vault_section_index.py --folder \"01_Projects\"\n"
            "\n"
            "# Regenerar TODOS los índices de sección + el master index\n"
            "python scripts/vault_master_index.py\n"
            "\n"
            "# Regenerar search-index.json + graph.json + hash-index.json\n"
            "python scripts/vault_reindex.py --graph\n"
            "```\n"
            "\n"
            "## Salud y auditoría\n"
            "\n"
            "```bash\n"
            "# Health score + issues (link rotos, orphan notes, etc.)\n"
            "python scripts/vault_audit.py\n"
            "\n"
            "# Validar contratos de las tools\n"
            "python scripts/vault_spec_validate.py\n"
            "\n"
            "# Validar estructura del vault (notas, frontmatter, CIA)\n"
            "python scripts/vault_validate.py\n"
            "```\n"
            "\n"
            "## Comandos por sección\n"
            "\n"
        )
        for section, hint in [
            ("00_System", None),
            ("01_Projects", "vault_project_overview --project <slug>"),
            ("02_Observability", "vault_log_error --project <slug> --error <msg>"),
            ("03_Decisions", "vault_write --folder 03_Decisions --title <adr>"),
            ("04_Sessions", "vault_write --folder 04_Sessions --title YYYY-MM-DD"),
            ("05_Patterns", "vault_pattern_save --name <pattern>"),
            ("06_Diagrams", "vault_diagram_save --project <slug> --type erd"),
            ("07_Knowledge", "vault_knowledge_save --title <concept>"),
            ("08_Runbooks", "vault_runbook_save --title <runbook>"),
            ("09_Infrastructure", "vault_infra_save --project <slug>"),
            ("10_Migrated", "vault_migrate_docs --source <path>"),
            ("11_Code", "vault_code_module --project <slug> --file_path <path>"),
            ("12_Bibliography", "vault_bibliography_save --title <ref> --type web"),
            ("13_Flows", "vault_flow_save --project <slug> --title <flow>"),
            ("14_Requirements", "vault_requirement_save --project <slug> --title <req>"),
            ("15_Tests", "vault_test_save --project <slug> --title <test>"),
            ("16_AI_Governance", "vault_ai_decision --project <slug> --title <decision>"),
        ]:
            if hint:
                commands_content += f"- **{section}** — `{hint}`\n"
        commands_content += (
            "\n"
            "## Backups\n"
            "\n"
            "```bash\n"
            "# Crear snapshot con Merkle tree para verificación de integridad\n"
            "python scripts/vault_backup.py\n"
            "\n"
            "# Listar backups disponibles\n"
            "python scripts/vault_backup_list.py\n"
            "\n"
            "# Restaurar desde un backup\n"
            "python scripts/vault_restore.py --name <backup-name>\n"
            "```\n"
        )
        COMMANDS_NOTE.write_text(commands_content, encoding="utf-8")


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


def _breadcrumb(folder_key: str) -> str:
    """Build navigation breadcrumb for a section or subsection index.

    AP-21 compliance: NEVER use path-anchored wiki-links like [[folder/index]]
    in the breadcrumb — Obsidian resolves by stem only, and `index` is a
    generic stem shared by every section. Use plain-text navigation with a
    single link to the hub note `00_System/vault-hub.md`, which is the only
    authoritative entry point.
    """
    parts = folder_key.split("/")
    if len(parts) == 1:
        return "> **←** [[vault-hub|Hub]]  ·  [[vault-commands|Comandos]]  ·  _99_Index/index.md_"
    else:
        parent = parts[0]
        return (
            f"> **←** [[vault-hub|Hub]]  ·  [[vault-commands|Comandos]]  "
            f"·  _99_Index/index.md_  ·  _{parent}/"
        )


def _build_index_content(
    folder: str,
    notes: List[Dict[str, Any]],
    now: str,
    subdirs: Optional[List[str]] = None,
) -> str:
    """Render index.md with navigation, notes table and subcarpeta listing."""
    folder_key = folder.replace("\\", "/")

    description = section_description(folder_key)
    hint = section_tool_hint(folder_key)
    tool_hint = hint if hint else f"vault_write --folder {folder_key} --title <titulo>"

    lines = [
        f"# {folder_key} — Índice",
        "",
        _breadcrumb(folder_key),
        f"> **Propósito:** {description}",
        f"> Generado automáticamente · {now} · {len(notes)} nota(s)",
        "",
    ]

    # Subcarpetas — listed before notes for discoverability
    # AP-21 compliance: NO path-anchored wiki-links like [[02_Observability/errors/index]].
    # Obsidian resolves by stem only, and `index` is a generic stem.
    # Use plain-text path + a separate row pointing to vault-hub for navigation.
    if subdirs:
        lines += ["## Subcarpetas", ""]
        lines += ["| Carpeta | Propósito |", "|---|---|"]
        for sub in sorted(subdirs):
            sub_key = sub.replace("\\", "/")
            sub_desc = section_description(sub_key)
            sub_name = sub_key.split("/")[-1]
            lines.append(f"| `{sub_key}/` | {sub_desc} |")
        lines.append("")
        lines.append("> Para navegar a una subcarpeta, abre `{folder}/{subcarpeta}/index.md` desde tu editor, o usa el [[vault-hub|Hub]].")
        lines.append("")

    if notes:
        lines += [
            "## Notas" if subdirs else "",
            "",
            "| Nota | Tipo | Actualizado |",
            "|---|---|---|",
        ]
        for n in notes:
            note_path = n["path"].replace("\\", "/")
            # AP-21 compliance: stem-only wiki-link, no folder prefix.
            stem = safe_wikilink(Path(note_path).stem)
            title = safe_wikilink(n["title"])
            link = f"[[{stem}|{title}]]"
            lines.append(f"| {link} | {n['type']} | {n['updatedAt']} |")
    else:
        # Empty section — minimal stub, NO inline bash block. All execution
        # commands live in `00_System/vault-commands.md` (the centralized
        # reference). This keeps the section index clean and avoids
        # duplicating the same command block in 16 places.
        lines += [
            "## Notas",
            "",
            "_Sección sin notas._",
            "",
            f"> **Propósito:** {description}",
            "",
            f"Para poblar esta sección consulta la **referencia unificada de comandos** en [[vault-commands|vault-commands]] "
            f"(entrada _{folder_key}_).",
            "",
            f"> **Comando sugerido:** `{tool_hint}`",
            "",
            "Una vez creada la primera nota, este índice se regenera automáticamente.",
        ]

    lines.append("")
    return "\n".join(lines)


def vault_section_index(folder: str, include_subdirs: bool = True) -> Dict[str, Any]:
    """
    Generate or update {folder}/index.md with navigation, notes table and subdir listing.
    Always produces populated content — never a bare empty file.
    Also generates index.md for each immediate subdirectory when include_subdirs=True.

    Args:
        folder: Section folder relative to vault root (e.g. "01_Projects")
        include_subdirs: If True, include notes in subdirectories and index their subdirs

    Returns:
        {"ok": True, "path": "01_Projects/index.md", "noteCount": 12, "is_empty": False,
         "subdirIndexes": [...]}
    """
    # Ensure the hub notes exist (idempotent — only creates on first call).
    # This makes the vault self-bootstrapping: a single call to vault_section_index
    # for any section creates vault-hub.md and vault-commands.md if missing.
    try:
        _ensure_hub_notes()
    except Exception:
        # hub note creation must never block the indexer
        pass

    section_path = VAULT_ROOT / folder
    if not section_path.exists():
        return {"ok": False, "error": "folder_not_found", "folder": folder}

    try:
        assert_within_vault(section_path, VAULT_ROOT)
    except ValueError as e:
        return {"ok": False, "error": "path_traversal", "detail": str(e)}

    now = _utcnow()
    notes = _collect_notes(section_path, include_subdirs)

    # Discover immediate subdirectories (for subdir listing in index)
    subdir_folders: List[str] = []
    subdir_indexes: List[str] = []
    if include_subdirs:
        for sub in sorted(section_path.iterdir()):
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            sub_folder = str(sub.relative_to(VAULT_ROOT)).replace("\\", "/")
            subdir_folders.append(sub_folder)

            # Generate sub-section index (no nested subdirs to avoid deep recursion)
            sub_notes = _collect_notes(sub, include_subdirs=True)
            sub_index = sub / "index.md"
            assert_within_vault(sub_index, VAULT_ROOT)
            sub_index.write_text(
                _build_index_content(sub_folder, sub_notes, now, subdirs=None),
                encoding="utf-8",
            )
            subdir_indexes.append(str(sub_index.relative_to(VAULT_ROOT)).replace("\\", "/"))

    # Write main section index — includes subdir listing
    index_path = section_path / "index.md"
    assert_within_vault(index_path, VAULT_ROOT)
    index_path.write_text(
        _build_index_content(folder, notes, now, subdirs=subdir_folders or None),
        encoding="utf-8",
    )

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

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
import sys
from vault_errors import wrap_main
from vault_lib import parse_frontmatter, utcnow
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_io import (
    assert_within_vault,
    file_lock,
    get_vault_root,
    record_raw_write,
    safe_wikilink,
    write_report,
)
from vault_registry import (
    MACHINERY_FOLDERS,
    ORDERED_SECTIONS,
    section_description,
    section_tool_hint,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vault.indices.seccion import (  # noqa: E402
    RE_ALIAS_EN_TABLA,
    RenderizadorDeIndice,
    migaja,
    recolectar_notas,
)


# AP-36: paths lazy — respetan set_vault_root() en runtime (--root).
def _hub_note() -> Path:
    return get_vault_root() / "00_System" / "vault-hub.md"


def _commands_note() -> Path:
    return get_vault_root() / "00_System" / "vault-commands.md"


def _ensure_hub_notes() -> None:
    """Idempotently create 00_System/vault-hub.md and vault-commands.md.

    The hub note is the single authoritative entry point — it links to every
    section index using stems Obsidian can resolve. The commands note is the
    single authoritative reference for execution commands — no command should
    appear inline in any other auto-generated file.

    Both are user-editable: if the file already exists we leave it alone.
    This protects manual edits while still bootstrapping a fresh vault.
    """
    if not _hub_note().exists():
        hub_content = (
            "---\n"
            "title: Vault Hub\n"
            "id: vault-hub\n"
            "createdAt: " + utcnow() + "\n"
            "updatedAt: " + utcnow() + "\n"
            "cia_integrity: high\n"
            "cia_availability: high\n"
            "cia_sensitivity: internal\n"
            "agent: system\n"
            'tags: ["nav", "hub"]\n'
            'norm_refs: ["CN-01"]\n'
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
        # La tabla del hub listaba 18 secciones escritas a mano: las cuatro
        # más nuevas existían en disco y no aparecían en el índice principal,
        # que es la única página por la que se navega el vault. Se deriva.
        for section in ORDERED_SECTIONS:
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
        _hub_note().write_text(hub_content, encoding="utf-8")

    if not _commands_note().exists():
        commands_content = (
            "---\n"
            "title: Vault Commands\n"
            "id: vault-commands\n"
            "createdAt: " + utcnow() + "\n"
            "updatedAt: " + utcnow() + "\n"
            "cia_integrity: high\n"
            "cia_availability: high\n"
            "cia_sensitivity: internal\n"
            "agent: system\n"
            'tags: ["nav", "commands"]\n'
            'norm_refs: ["CN-01"]\n'
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
            'python scripts/vault_write.py --folder "01_Projects/mi-api" --title "Status" --content "# Status\\n\\nActivo"\n'
            "\n"
            "# Leer una nota por ruta\n"
            'python scripts/vault_read.py --path "01_Projects/mi-api/status.md"\n'
            "\n"
            "# Buscar full-text\n"
            'python scripts/vault_search.py --query "circuit breaker"\n'
            "\n"
            "# Listar notas de una carpeta\n"
            'python scripts/vault_list.py --folder "01_Projects"\n'
            "\n"
            "# Agregar contenido al final (changelogs, session logs)\n"
            'python scripts/vault_append.py --path "04_Sessions/2026-06-19.md" --content "## Tasks\\n\\n- [x] Fix init"\n'
            "```\n"
            "\n"
            "## Índices\n"
            "\n"
            "```bash\n"
            "# Regenerar índice de una sección\n"
            'python scripts/vault_section_index.py --folder "01_Projects"\n'
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
            (
                "14_Requirements",
                "vault_requirement_save --project <slug> --title <req>",
            ),
            ("15_Tests", "vault_test_save --project <slug> --title <test>"),
            (
                "16_AI_Governance",
                "vault_ai_decision --project <slug> --title <decision>",
            ),
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
        _commands_note().write_text(commands_content, encoding="utf-8")


def _collect_notes(section_path: Path, include_subdirs: bool) -> List[Dict[str, Any]]:
    """Adaptador: el recorrido vive en el dominio de Índices."""
    from vault_registry import SECTIONS as _SECTIONS

    return recolectar_notas(
        get_vault_root(),
        section_path,
        [s["folder"] for s in _SECTIONS],
        include_subdirs,
        parse_frontmatter,
    )


def _breadcrumb(folder_key: str) -> str:
    """Adaptador: la migaja de navegación vive en el dominio de Índices."""
    return migaja(folder_key)


def _renderizador() -> RenderizadorDeIndice:
    """Se construye por llamada: `section_description` lee el registro y
    `safe_wikilink` el kernel, y ninguno de los dos se congela en el import."""
    return RenderizadorDeIndice(
        describir_seccion=section_description,
        pista_de_tool=section_tool_hint,
        enlace_seguro=safe_wikilink,
    )


def _build_index_content(
    folder: str,
    notes: List[Dict[str, Any]],
    now: str,
    subdirs: Optional[List[str]] = None,
) -> str:
    """Adaptador: el formato del índice vive en el dominio de Índices."""
    return _renderizador().render(folder, notes, now, subcarpetas=subdirs)



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
    # Guard CN-02/AP-15: solo secciones canónicas son destinos válidos. Sin esto,
    # folder="" o "." escribe index.md y .locks/ en la RAÍZ del vault.
    folder = (folder or "").strip().replace("\\", "/").strip("/")
    if not folder or folder == ".":
        return {
            "ok": False,
            "error": "invalid_folder",
            "detail": "folder no puede ser la raíz del vault (CN-02/AP-15); usar una sección canónica, ej. 01_Projects",
        }
    from vault_registry import SECTIONS as _SECTIONS

    if folder.split("/")[0] not in {s["folder"] for s in _SECTIONS}:
        return {
            "ok": False,
            "error": "invalid_folder",
            "detail": f"'{folder.split('/')[0]}' no es una sección canónica del registro (CN-02)",
        }

    # Ensure the hub notes exist (idempotent — only creates on first call).
    # This makes the vault self-bootstrapping: a single call to vault_section_index
    # for any section creates vault-hub.md and vault-commands.md if missing.
    try:
        _ensure_hub_notes()
    except Exception:
        # hub note creation must never block the indexer
        pass

    vroot = get_vault_root()
    section_path = vroot / folder
    if not section_path.exists():
        return {"ok": False, "error": "folder_not_found", "folder": folder}

    try:
        assert_within_vault(section_path, vroot)
    except ValueError as e:
        return {"ok": False, "error": "path_traversal", "detail": str(e)}

    now = utcnow()
    notes = _collect_notes(section_path, include_subdirs)

    # Discover immediate subdirectories (for subdir listing in index)
    subdir_folders: List[str] = []
    subdir_indexes: List[str] = []
    if include_subdirs:
        for sub in sorted(section_path.iterdir()):
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            sub_folder = str(sub.relative_to(vroot)).replace("\\", "/")
            # Maquinaria declarada: la carpeta existe porque una norma guarda
            # ahí su estado, no porque haya notas. Indexarla creaba un
            # `index.md` sobre una carpeta vacía que después contaba como nota
            # en disco y desajustaba el índice de búsqueda (AP-47) — un vault
            # recién onboardeado nacía violando una norma del estándar que lo
            # creó, y solo se veía al escribir la bitácora antes del reindex.
            if sub_folder in MACHINERY_FOLDERS:
                continue
            subdir_folders.append(sub_folder)

            # Generate sub-section index (no nested subdirs to avoid deep recursion)
            sub_notes = _collect_notes(sub, include_subdirs=True)
            sub_index = sub / "index.md"
            assert_within_vault(sub_index, vroot)
            # Leaf lock on the index file itself: serializes concurrent regens of
            # this same sub-index (two notes in the section written at once). Safe
            # from deadlock — index.md is in _SKIP_AUTO_INDEX so writing it never
            # re-enters _auto_section_index, and no caller holds this lock.
            with file_lock(sub_index):
                sub_contenido = _build_index_content(
                    sub_folder, sub_notes, now, subdirs=None
                )
                record_raw_write(sub_index, sub_contenido)
                sub_index.write_text(sub_contenido, encoding="utf-8")
            subdir_indexes.append(
                str(sub_index.relative_to(vroot)).replace("\\", "/")
            )

    # Write main section index — includes subdir listing
    index_path = section_path / "index.md"
    assert_within_vault(index_path, vroot)
    # Leaf lock (see sub-index note above): serialize concurrent regens of this
    # section index; deadlock-free because index.md is skipped by _auto_section_index.
    with file_lock(index_path):
        contenido = _build_index_content(
            folder, notes, now, subdirs=subdir_folders or None
        )
        record_raw_write(index_path, contenido)
        index_path.write_text(contenido, encoding="utf-8")

    return {
        "ok": True,
        **write_report(),
        "path": str(index_path.relative_to(vroot)).replace("\\", "/"),
        "noteCount": len(notes),
        "is_empty": len(notes) == 0,
        "subdirIndexes": subdir_indexes,
    }


# Nombre público conservado (lo importan tests y `vault_norms`); la definición
# es una sola y vive en el dominio, para que el guard y el generador no puedan
# discrepar sobre qué formato está prohibido (AP-05).
RE_ALIAS_IN_INDEX_TABLE = RE_ALIAS_EN_TABLA


def heal_indexes(root: Optional[Path] = None) -> Dict[str, Any]:
    """Sanea todos los index.md del vault: regenera los que tengan formato
    legacy ([[stem|alias]] en celdas) o estén ausentes en secciones con notas.

    Idempotente (AP-36): correrlo N veces converge al mismo estado.
    """
    from vault_io import get_vault_root
    from vault_registry import SECTIONS

    vroot = (root or get_vault_root()).resolve()
    healed: List[Dict[str, str]] = []
    skipped = 0
    for s in SECTIONS:
        folder = s["folder"]
        sec_path = vroot / folder
        if not sec_path.is_dir() or folder in ("00_System", "10_Migrated", "99_Index"):
            continue
        for index_path in [sec_path / "index.md", *sec_path.glob("*/index.md")]:
            reason = None
            if not index_path.exists():
                if any(index_path.parent.glob("*.md")):
                    reason = "missing"
            else:
                try:
                    text = index_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    reason = "unreadable"
                else:
                    if RE_ALIAS_IN_INDEX_TABLE.search(text):
                        reason = "legacy_alias_format"
            if reason is None:
                skipped += 1
                continue
            target_folder = str(index_path.parent.relative_to(vroot)).replace("\\", "/")
            # Regenerar la sección top-level cubre también sus sub-índices
            top = target_folder.split("/")[0]
            r = vault_section_index(top)
            healed.append({"index": f"{target_folder}/index.md", "reason": reason, "ok": str(r.get("ok"))})
    return {
        "ok": True,
        "tool": "vault_section_index.heal",
        "vault_root": str(vroot),
        "healed": healed,
        "healed_count": len(healed),
        "clean_count": skipped,
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
    parser.add_argument(
        "--folder", help="Section folder relative to vault root"
    )
    parser.add_argument(
        "--no-subdirs", action="store_true", help="Exclude notes in subdirectories"
    )
    parser.add_argument(
        "--heal",
        action="store_true",
        help="Sanear todos los index.md (formato legacy con alias o ausentes)",
    )
    parser.add_argument("--root", help="Vault root para --heal (default: auto-detect)")
    args = parser.parse_args()

    if args.heal:
        if args.root:
            from vault_io import set_vault_root

            set_vault_root(Path(args.root))  # AP-36: side-effects al vault objetivo
        result = heal_indexes(Path(args.root) if args.root else None)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if not args.folder:
        parser.error("--folder es requerido (o usar --heal)")

    result = vault_section_index(args.folder, include_subdirs=not args.no_subdirs)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_section_index"))

#!/usr/bin/env python3

"""

Vault Master Index — Generate 99_Index/index.md (vault-wide master index).



Calls vault_section_index for each of the 12 standard sections (00_System…11_Code),

then writes 99_Index/index.md with a summary table linking to each section index.



Usage:

    python vault_master_index.py

"""

import json

import sys

from vault_errors import wrap_main
from vault_lib import utcnow
from pathlib import Path

from typing import Any, Dict


from vault_io import VAULT_ROOT, write_report
from vault_registry import ORDERED_SECTIONS, section_name, section_description

INDEX_DIR = VAULT_ROOT / "99_Index"


def vault_master_index() -> Dict[str, Any]:
    """

    Generate 99_Index/index.md as the vault-wide master index.



    Internally calls vault_section_index for each section, then produces

    a summary table in 99_Index/index.md.



    Returns:

        {"ok": True, "path": "99_Index/index.md", "sectionsTotal": 12, "notesTotal": 108}

    """

    # Import here to avoid circular dependency issues when scripts are used standalone

    sys.path.insert(0, str(Path(__file__).parent))

    from vault_section_index import vault_section_index

    section_results = []

    total_notes = 0

    for section in ORDERED_SECTIONS:
        section_path = VAULT_ROOT / section

        if not section_path.exists():
            section_results.append({"section": section, "noteCount": 0, "ok": False})

            continue

        result = vault_section_index(section, include_subdirs=True)

        note_count = result.get("noteCount", 0)

        total_notes += note_count

        section_results.append(
            {
                "section": section,
                "noteCount": note_count,
                "ok": result.get("ok", False),
            }
        )

    # Generate 99_Index/index.md

    now = utcnow()

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    master_path = INDEX_DIR / "index.md"

    lines = [
        "# Vault — Índice Maestro",
        "",
        f"> Generado automáticamente · {now} · {total_notes} nota(s) en {len(ORDERED_SECTIONS)} secciones",
        "",
        "| Sección | Descripción | Notas | Índice |",
        "|---|---|---|---|",
    ]

    for r in section_results:
        section = r["section"]

        desc = section_description(section)

        count = r["noteCount"]

        # AP-21 compliance: NO path-anchored wiki-links. Use the section folder
        # name in backticks + plain text. The reader navigates by opening the
        # section's index.md from the editor.
        if r["ok"]:
            index_link = f"`{section}/index.md`"
        else:
            index_link = "_(vacía)_"

        lines.append(f"| `{section}` | {desc} | {count} | {index_link} |")

    lines += [
        "",
        "---",
        "",
        "> **Navegación:** [[vault-hub|Hub]]  ·  [[vault-commands|Comandos]]",
        "",
        "## Índices técnicos",
        "",
        "| Archivo | Descripción |",
        "|---|---|",
        "| `99_Index/search-index.json` | Índice de búsqueda full-text (auto-generado por vault_write) |",
        "| `99_Index/graph.json` | Grafo de wiki-links, orphans y broken links (vault_graph) |",
        "| `99_Index/hash-index.json` | Hash + size + CIA por nota (auto-generado por vault_reindex) |",
        "",
    ]

    master_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "ok": True,
        **write_report(),
        "path": str(master_path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "sectionsTotal": len(ORDERED_SECTIONS),
        "notesTotal": total_notes,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Vault Master Index -- Generate 99_Index/index.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_master_index.py



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Llama a vault_section_index para cada una de las 12 secciones estandar

  - Genera 99_Index/index.md con tabla resumen de todo el vault

""",
    )

    parser.parse_args()

    result = vault_master_index()

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_master_index"))

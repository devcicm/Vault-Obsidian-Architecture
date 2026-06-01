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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from vault_io import VAULT_ROOT
INDEX_DIR = VAULT_ROOT / "99_Index"

ORDERED_SECTIONS = [
    "00_System",
    "01_Projects",
    "02_Observability",
    "03_Decisions",
    "04_Sessions",
    "05_Patterns",
    "06_Diagrams",
    "07_Knowledge",
    "08_Runbooks",
    "09_Infrastructure",
    "10_Migrated",
    "11_Code",
]

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
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


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
        section_results.append({
            "section": section,
            "noteCount": note_count,
            "ok": result.get("ok", False),
        })

    # Generate 99_Index/index.md
    now = _utcnow()
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
        desc = SECTION_DESCRIPTIONS.get(section, "")
        count = r["noteCount"]
        index_link = f"[[{section}/index]]" if r["ok"] else "_vacía_"
        lines.append(f"| `{section}` | {desc} | {count} | {index_link} |")

    lines += [
        "",
        "---",
        "",
        "## Índices técnicos",
        "",
        "| Archivo | Descripción |",
        "|---|---|",
        "| [[99_Index/search-index|search-index.json]] | Índice de búsqueda full-text (auto-generado por vault_write) |",
        "| [[99_Index/graph|graph.json]] | Grafo de wiki-links, orphans y broken links (vault_graph) |",
        "",
    ]

    master_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "ok": True,
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

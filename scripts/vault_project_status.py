#!/usr/bin/env python3
"""
Vault Project Status Tool — Update project status

Updates project status.md and appends to changelog.md.

States: en_desarrollo | en_revision | bloqueado | completado | archivado | en_produccion

Usage:
    python vault_project_status.py --project ans --status en_produccion --summary "Lanzado v1.0"
"""

import argparse
import json
import re
import sys
from vault_errors import wrap_main
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

# Configuration
from vault_io import VAULT_ROOT

# Valid states
VALID_STATES = ["en_desarrollo", "en_revision", "bloqueado", "completado", "archivado", "en_produccion"]


def vault_project_status(project: str, status: str, summary: str, modified_files: list = None) -> dict:
    """
    Update project status.md and changelog.md.

    Args:
        project: Project slug
        status: New status
        summary: What was done
        modified_files: List of files modified
    """
    if status not in VALID_STATES:
        return {"ok": False, "error": f"Invalid status: {status}. Valid: {VALID_STATES}"}

    project_path = VAULT_ROOT / "01_Projects" / project
    status_file = project_path / "status.md"
    changelog_file = project_path / "changelog.md"

    # Ensure project folder exists
    project_path.mkdir(parents=True, exist_ok=True)

    now = _utcnow()

    # Read existing status.md to preserve id and createdAt
    existing_id = None
    existing_created = None
    if status_file.exists():
        try:
            existing_content = status_file.read_text(encoding="utf-8")
            fm_match = re.match(r"^---\n(.*?)\n---", existing_content, re.DOTALL)
            if fm_match:
                for line in fm_match.group(1).split("\n"):
                    if line.startswith("id:"):
                        existing_id = line.split(":", 1)[1].strip().strip("\"'")
                    elif line.startswith("createdAt:"):
                        existing_created = line.split(":", 1)[1].strip().strip("\"'")
        except Exception:
            pass

    note_id = existing_id or str(uuid.uuid4())
    created_at = existing_created or now

    status_content = f"""---
title: {project} — Status
id: {note_id}
project: {project}
status: {status}
createdAt: {created_at}
updatedAt: {now}
tags: ["status", "{project}"]
---

# {project} — Status

**Última actualización:** {now}
**Estado:** {status.upper()}
**Resumen:** {summary}

---

## Detalles

- **Estado anterior:** _[Registrado en historial]_
- **Fecha del cambio:** {now}
- **Resumen del cambio:** {summary}

---

## Archivos modificados

{chr(10).join(f"- `{f}`" for f in (modified_files or [])) or "_Ninguno_"}
"""

    with open(status_file, "w", encoding="utf-8") as f:
        f.write(status_content)

    # Append to changelog.md
    changelog_entry = f"""

### {now} — {status.upper()}

**{summary}**

{f"- Archivos: {', '.join(modified_files)}" if modified_files else ""}
"""

    if changelog_file.exists():
        with open(changelog_file, "r", encoding="utf-8") as f:
            existing = f.read()
    else:
        existing = f"# Changelog\n\n"

    with open(changelog_file, "w", encoding="utf-8") as f:
        f.write(existing + changelog_entry)

    return {
        "ok": True,
        "project": project,
        "status": status,
        "path": str(status_file.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "changelogPath": str(changelog_file.relative_to(VAULT_ROOT)).replace("\\", "/"),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Project Status Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_project_status.py --project ans --status en_produccion --summary "Lanzado v1.0"
  python vault_project_status.py --project mi-api --status en_desarrollo --summary "Sprint 3 iniciado"
  python vault_project_status.py --project backend --status bloqueado --summary "Esperando acceso a BD" --files "src/db.py"
  python vault_project_status.py --project ans --status completado --summary "Feature X terminada"

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Estados validos: en_desarrollo, en_revision, bloqueado, completado, archivado, en_produccion
  - Actualiza status.md y agrega entrada a changelog.md del proyecto
""",
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--status", required=True, choices=VALID_STATES)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--files", nargs="*", help="Modified files")

    args = parser.parse_args()
    result = vault_project_status(args.project, args.status, args.summary, args.files)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_project_status"))

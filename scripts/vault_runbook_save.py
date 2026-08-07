#!/usr/bin/env python3

"""

Vault Runbook Save Tool — Save operational procedures



Saves step-by-step operational procedures to 08_Runbooks/ subfolders.

Supports categories: deploy, debug, setup, rollback, maintenance, incident.



Usage:

    python vault_runbook_save.py --project "ans" --title "Deploy to Proxmox" --trigger "Manual deploy" --category "deploy" --steps '[{"step":"SSH to server","command":"ssh user@host"},{"step":"Pull latest","command":"git pull"}]'

    python vault_runbook_save.py --project "mi-api" --title "Memory Leak Debug" --trigger "High memory usage" --category "debug" --estimated_time "30 min"

"""

import argparse

import json

import re

import sys

from vault_errors import wrap_main
from vault_lib import utcnow, slugify
from vault_io import atomic_write_text, assert_within_vault, safe_wikilink, write_report
import uuid

from pathlib import Path

from typing import Any, Dict, List, Optional


CATEGORIES = [
    "deploy",
    "debug",
    "setup",
    "rollback",
    "maintenance",
    "pipeline",
    "incident",
]


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _runbooks_dir() -> Path:
    return _repo().seccion("08_Runbooks")


def vault_runbook_save(
    project: str,
    title: str,
    trigger: str,
    category: str,
    steps: List[Dict[str, Any]],
    estimated_time: Optional[str] = None,
    prerequisites: Optional[List[str]] = None,
) -> Dict[str, Any]:
    category = category.lower()

    if category not in CATEGORIES:
        return {
            "ok": False,
            "error": f"Categoría inválida: {category}. Válidas: {CATEGORIES}",
        }

    safe_project = slugify(project)

    safe_title = slugify(title)

    folder = _runbooks_dir() / category

    filename = f"{safe_project}-{safe_title}.md"

    note_path = folder / filename

    timestamp = utcnow()

    note_path_candidate = folder / filename

    try:
        assert_within_vault(note_path_candidate, _raiz())

    except ValueError as exc:
        return {
            "ok": False,
            "error_code": "INVALID_PATH",
            "error": "INVALID_PATH",
            "message": str(exc),
        }

    frontmatter = ["---"]

    frontmatter.append(f"title: {json.dumps(title)}")

    frontmatter.append(f"id: {str(uuid.uuid4())}")

    frontmatter.append(f"project: {project}")

    frontmatter.append(f"category: {category}")

    frontmatter.append(f"trigger: {trigger}")

    frontmatter.append(f"status: active")

    frontmatter.append(f"executions: 0")

    frontmatter.append(f"createdAt: {timestamp}")

    frontmatter.append(f"updatedAt: {timestamp}")

    if estimated_time:
        frontmatter.append(f"estimatedTime: {estimated_time}")

    frontmatter.append(f"cia_integrity: medium")

    frontmatter.append(f"cia_availability: high")

    frontmatter.append(f"cia_sensitivity: internal")

    frontmatter.append(f"agent: system")

    frontmatter.append("---")

    body_sections = []

    body_sections.append(f"## Trigger\n\n>{trigger}")

    if prerequisites:
        body_sections.append(
            "## Prerequisitos\n\n" + "\n".join(f"- [ ] {p}" for p in prerequisites)
        )

    steps_content = ["## Pasos\n"]

    for i, step in enumerate(steps, 1):
        step_text = step.get("step", "")

        command = step.get("command")

        note = step.get("note")

        steps_content.append(f"\n### {i}. {step_text}")

        if command:
            steps_content.append(f"\n```bash\n{command}\n```")

        if note:
            steps_content.append(f"\n> ⚠️ {note}")

    body_sections.append("\n".join(steps_content))

    body_sections.append(
        "## Historial de Ejecuciones\n\n*Sin ejecuciones registradas.*"
    )

    final_content = "\n".join(frontmatter) + "\n\n" + "\n\n".join(body_sections)

    folder.mkdir(parents=True, exist_ok=True)

    atomic_write_text(note_path, final_content)

    return {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(_raiz())),
        "category": category,
        "steps": len(steps),
        "message": f"Runbook '{title}' saved to {category}/",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Runbook Save Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_runbook_save.py --project "ans" --title "Deploy to Proxmox" --trigger "Manual deploy" --category "deploy" --steps '[{"step":"SSH to server","command":"ssh user@host"},{"step":"Pull latest","command":"git pull"}]'

  python vault_runbook_save.py --project "mi-api" --title "Memory Leak Debug" --trigger "High memory usage" --category "debug" --estimated_time "30 min"

  python vault_runbook_save.py --project "backend" --title "DB Migration" --trigger "Schema changes" --category "maintenance" --steps '[{"step":"Backup DB","command":"pg_dump ..."}]'

  python vault_runbook_save.py --project "ans" --title "Rollback Deploy" --trigger "Failed deployment" --category "rollback" --prerequisites "Access to server" "Git installed"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Categorias validas: deploy, debug, setup, rollback, maintenance, pipeline, incident

  - Cada paso puede tener: step (requerido), command (opcional), note (opcional)

""",
    )

    parser.add_argument("--project", required=True, help="Project name")

    parser.add_argument("--title", required=True, help="Runbook title")

    parser.add_argument(
        "--trigger", required=True, help="When this runbook should be triggered"
    )

    parser.add_argument("--category", required=True, help=f"Category: {CATEGORIES}")

    parser.add_argument("--steps", required=True, help="Steps as JSON array")

    parser.add_argument("--estimated_time", help="Estimated time (e.g., '30 min')")

    parser.add_argument("--prerequisites", nargs="*", help="Prerequisites list")

    args = parser.parse_args()

    try:
        steps = json.loads(args.steps)

    except json.JSONDecodeError:
        return {"ok": False, "error": "Invalid JSON in --steps parameter"}

    result = vault_runbook_save(
        args.project,
        args.title,
        args.trigger,
        args.category,
        steps,
        args.estimated_time,
        args.prerequisites,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_runbook_save"))

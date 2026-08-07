#!/usr/bin/env python3

"""

Vault Requirement Save Tool -- Save software requirements (ISO/IEC/IEEE 29148)



Saves requirements to 14_Requirements/{project}/ with traceability to code.

Types: functional, non-functional, constraint, assumption

Priority: must-have, should-have, nice-to-have (MoSCoW)

Status: draft -> reviewed -> approved -> implemented -> verified -> obsolete



Usage:

    python vault_requirement_save.py --project "mi-api" --title "User Authentication" --description "The system must authenticate users via JWT" --type functional --priority must-have

    python vault_requirement_save.py --project "mi-api" --title "Response Time" --description "API must respond in < 200ms at p99" --type non-functional --priority must-have --acceptance_criteria '["p99 latency < 200ms in load tests","No degradation under 1000 concurrent users"]'

    python vault_requirement_save.py --project "mi-api" --title "GDPR Compliance" --description "User data must be deletable on request" --type constraint --priority must-have --related_code "src/user.py,src/gdpr.py"

"""

import argparse

import json

import re

import sys

from vault_errors import wrap_main
from vault_norms import status_frontmatter_lines
from vault_lib import yaml_scalar, slugify_strict, utcnow
from datetime import datetime, timezone
from vault_io import (
    write_report,
    atomic_write_text,
    atomic_write_json,
    assert_within_vault,
)
import uuid

from pathlib import Path


from typing import Any, Dict, List, Optional


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.autoria.frontmatter import Frontmatter  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _req_dir() -> Path:
    return _repo().seccion("14_Requirements")


def _index_file() -> Path:
    return _repo().seccion("14_Requirements") / ".requirements-index.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


REQ_TYPES = ["functional", "non-functional", "constraint", "assumption"]

PRIORITIES = ["must-have", "should-have", "nice-to-have", "wont-have"]

STATUSES = ["draft", "reviewed", "approved", "implemented", "verified", "obsolete"]


def slugify(text: str) -> str:
    # Delega en el slug canónico (`vault_lib.slugify`). La copia que había
    # aquí divergía del resto: unas borraban los acentos, otras los dejaban
    # en el nombre de fichero. Una sola fuente, un solo nombre de nota.
    return slugify_strict(text)


def load_index() -> Dict[str, Any]:
    try:
        with open(_index_file(), "r", encoding="utf-8") as f:
            return json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):
        return {"requirements": []}


def save_index(data: Dict[str, Any]) -> None:
    _req_dir().mkdir(parents=True, exist_ok=True)

    atomic_write_json(_index_file(), data)


def vault_requirement_save(
    project: str,
    title: str,
    description: str,
    req_type: str,
    priority: str,
    acceptance_criteria: Optional[List[str]] = None,
    source: Optional[str] = None,
    status: str = "draft",
    related_code: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if req_type not in REQ_TYPES:
        return {
            "ok": False,
            "error": f"req_type '{req_type}' not valid. Use: {REQ_TYPES}",
        }

    if priority not in PRIORITIES:
        return {
            "ok": False,
            "error": f"priority '{priority}' not valid. Use: {PRIORITIES}",
        }

    if status not in STATUSES:
        return {"ok": False, "error": f"status '{status}' not valid. Use: {STATUSES}"}

    safe_project = slugify(project)

    title_slug = slugify(title)

    now = utcnow()

    index = load_index()

    # Count existing requirements for this project to get sequential ID

    project_reqs = [r for r in index["requirements"] if r.get("project") == project]

    req_number = len(project_reqs) + 1

    req_id = f"REQ-{req_number:03d}"

    note_id = str(uuid.uuid4())

    filename = f"req-{req_number:03d}-{title_slug}.md"

    note_path = _req_dir() / safe_project / filename

    try:
        assert_within_vault(note_path, _raiz())

    except ValueError as exc:
        return {
            "ok": False,
            "error_code": "INVALID_PATH",
            "error": "INVALID_PATH",
            "message": str(exc),
        }

    tags_list = list(tags or [])

    tags_list.extend([safe_project, "requirement", req_type, priority])

    cia_integrity = "high" if priority == "must-have" else "medium"

    frontmatter = Frontmatter()

    frontmatter.set("id", note_id)

    frontmatter.set("req_id", req_id)

    frontmatter.set("title", title)

    frontmatter.set("project", project)

    frontmatter.set("req_type", req_type)

    frontmatter.set("priority", priority)

    frontmatter.lineas(status_frontmatter_lines("vault_requirement_save", status))

    frontmatter.set("createdAt", now)

    frontmatter.set("updatedAt", now)

    if tags_list:
        frontmatter.set("tags", list(dict.fromkeys(tags_list)))

    frontmatter.set("cia_integrity", cia_integrity)

    frontmatter.set("cia_availability", "medium")

    frontmatter.set("cia_sensitivity", "internal")

    frontmatter.set("agent", "system")


    body_sections = []

    body_sections.append(f"## Descripcion\n\n{description}")

    if acceptance_criteria:
        lines = ["## Criterios de Aceptacion\n"]

        for i, criterion in enumerate(acceptance_criteria, 1):
            lines.append(f"{i}. {criterion}")

        body_sections.append("\n".join(lines))

    if related_code:
        rows = ["## Trazabilidad\n", "| Archivo | Rol |", "|---|---|"]

        for code_file in related_code:
            rows.append(f"| `{code_file}` | implementacion |")

        body_sections.append("\n".join(rows))

    if source:
        body_sections.append(f"## Fuente\n\n{source}")

    # Status badge

    status_line = " | ".join(f"**{s}**" if s == status else s for s in STATUSES)

    body_sections.append(f"## Estado\n\n**Estado:** {status_line}")

    final_content = frontmatter.render() + "\n\n" + "\n\n".join(body_sections)

    note_path.parent.mkdir(parents=True, exist_ok=True)

    atomic_write_text(note_path, final_content)

    entry = {
        "docId": note_id,
        "req_id": req_id,
        "project": project,
        "title": title,
        "req_type": req_type,
        "priority": priority,
        "status": status,
        "relPath": str(note_path.relative_to(_raiz())).replace("\\", "/"),
        "related_code": related_code or [],
        "updatedAt": now,
    }

    index["requirements"].append(entry)

    save_index(index)

    return {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(_raiz())).replace("\\", "/"),
        "req_id": req_id,
        "action": "created",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Requirement Save Tool -- ISO/IEC/IEEE 29148 requirement documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Examples:

  python vault_requirement_save.py --project "mi-api" --title "User Authentication" --description "The system must authenticate users via JWT" --type functional --priority must-have



  python vault_requirement_save.py --project "mi-api" --title "Response Time" --description "API must respond in < 200ms at p99" --type non-functional --priority must-have --acceptance_criteria '["p99 latency < 200ms in load tests","No degradation under 1000 concurrent users"]'



  python vault_requirement_save.py --project "mi-api" --title "GDPR Compliance" --description "User data must be deletable on request" --type constraint --priority must-have --related_code "src/user.py,src/gdpr.py"



Notes:

  - req_type: functional | non-functional | constraint | assumption  (ISO/IEC/IEEE 29148)

  - priority: must-have | should-have | nice-to-have | wont-have    (MoSCoW)

  - status: draft | reviewed | approved | implemented | verified | obsolete

  - --related_code accepts comma-separated file paths

  - req_id is auto-generated as REQ-001, REQ-002, etc. per project

""",
    )

    parser.add_argument("--project", required=True, help="Project slug")

    parser.add_argument("--title", required=True, help="Short requirement title")

    parser.add_argument(
        "--description", required=True, help="Full requirement description"
    )

    parser.add_argument(
        "--type", dest="req_type", required=True, help=f"Requirement type: {REQ_TYPES}"
    )

    parser.add_argument(
        "--priority", required=True, help=f"MoSCoW priority: {PRIORITIES}"
    )

    parser.add_argument(
        "--acceptance_criteria", help="JSON array of acceptance criteria strings"
    )

    parser.add_argument(
        "--source", help="Origin of the requirement (stakeholder, document, etc.)"
    )

    parser.add_argument(
        "--status",
        default="draft",
        help=f"Requirement status (default: draft): {STATUSES}",
    )

    parser.add_argument(
        "--related_code", help="Comma-separated list of related source files"
    )

    parser.add_argument("--tags", nargs="*", help="Additional tags")

    args = parser.parse_args()

    def parse_json_arg(val: Optional[str], name: str) -> Optional[Any]:
        if not val:
            return None

        try:
            return json.loads(val)

        except json.JSONDecodeError as e:
            print(json.dumps({"ok": False, "error": f"Invalid JSON in --{name}: {e}"}))

            sys.exit(1)

    related_code_list: Optional[List[str]] = None

    if args.related_code:
        related_code_list = [
            f.strip() for f in args.related_code.split(",") if f.strip()
        ]

    acceptance_criteria = parse_json_arg(
        args.acceptance_criteria, "acceptance_criteria"
    )

    result = vault_requirement_save(
        project=args.project,
        title=args.title,
        description=args.description,
        req_type=args.req_type,
        priority=args.priority,
        acceptance_criteria=acceptance_criteria,
        source=args.source,
        status=args.status,
        related_code=related_code_list,
        tags=args.tags,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_requirement_save"))

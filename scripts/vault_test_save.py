#!/usr/bin/env python3

"""

Vault Test Save Tool -- Save test cases and test documentation (ISO/IEC/IEEE 29119-3)



Saves test cases to 15_Tests/{test_type}/{project}-{slug}.md.

Types: unit, integration, e2e, performance, security, acceptance

Status: not_run, pass, fail, blocked, skip



Usage:

    python vault_test_save.py --project "mi-api" --title "Login success" --test_type unit --description "Test successful login with valid credentials" --preconditions "User exists in DB" --steps '[{"step":1,"action":"Call login(user,pwd)","expected":"Returns AuthToken"}]' --expected_result "AuthToken with valid JWT"

    python vault_test_save.py --project "mi-api" --title "Auth API flow" --test_type integration --description "Full auth flow via HTTP" --related_requirement "REQ-001" --related_code "src/auth.py"

    python vault_test_save.py --project "mi-api" --title "Login performance" --test_type performance --description "Login endpoint under load" --preconditions "1000 concurrent users" --expected_result "p99 < 200ms"

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


def _tests_dir() -> Path:
    return _repo().seccion("15_Tests")


def _index_file() -> Path:
    return _repo().seccion("15_Tests") / ".tests-index.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


TEST_TYPES = ["unit", "integration", "e2e", "performance", "security", "acceptance"]

# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueño.
from vault_vocabulario import opciones as _opciones

STATUSES = _opciones("test_result")


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
        return {"tests": []}


def save_index(data: Dict[str, Any]) -> None:
    _tests_dir().mkdir(parents=True, exist_ok=True)

    atomic_write_json(_index_file(), data)


def vault_test_save(
    project: str,
    title: str,
    test_type: str,
    description: str,
    preconditions: Optional[str] = None,
    steps: Optional[List[Dict[str, Any]]] = None,
    expected_result: Optional[str] = None,
    related_requirement: Optional[str] = None,
    related_code: Optional[List[str]] = None,
    status: str = "not_run",
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if test_type not in TEST_TYPES:
        return {
            "ok": False,
            "error": f"test_type '{test_type}' not valid. Use: {TEST_TYPES}",
        }

    if status not in STATUSES:
        return {"ok": False, "error": f"status '{status}' not valid. Use: {STATUSES}"}

    safe_project = slugify(project)

    title_slug = slugify(title)

    now = utcnow()

    index = load_index()

    # Count existing tests for this project to get sequential ID

    project_tests = [t for t in index["tests"] if t.get("project") == project]

    test_number = len(project_tests) + 1

    test_id = f"TEST-{test_number:03d}"

    note_id = str(uuid.uuid4())

    filename = f"{safe_project}-{title_slug}.md"

    note_path = _tests_dir() / test_type / filename

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

    tags_list.extend([safe_project, "test", test_type, status])

    frontmatter = Frontmatter()

    frontmatter.set("id", note_id)

    frontmatter.set("test_id", test_id)

    frontmatter.set("title", title)

    frontmatter.set("project", project)

    frontmatter.set("test_type", test_type)

    frontmatter.lineas(status_frontmatter_lines("vault_test_save", status))

    if related_requirement:
        frontmatter.set("related_requirement", related_requirement)

    frontmatter.set("createdAt", now)

    frontmatter.set("updatedAt", now)

    if tags_list:
        frontmatter.set("tags", list(dict.fromkeys(tags_list)))

    frontmatter.set("cia_integrity", "medium")

    frontmatter.set("cia_availability", "medium")

    frontmatter.set("cia_sensitivity", "internal")

    frontmatter.set("agent", "system")


    body_sections = []

    body_sections.append(f"## Descripcion\n\n{description}")

    if preconditions:
        body_sections.append(f"## Pre-condiciones\n\n{preconditions}")

    if steps:
        rows = ["## Pasos\n", "| # | Accion | Resultado Esperado |", "|---|---|---|"]

        for s in steps:
            step_num = s.get("step", "")

            action = s.get("action", "")

            expected = s.get("expected", "")

            rows.append(f"| {step_num} | {action} | {expected} |")

        body_sections.append("\n".join(rows))

    if expected_result:
        body_sections.append(f"## Resultado Esperado\n\n{expected_result}")

    if related_requirement or related_code:
        rows = ["## Trazabilidad\n", "| Tipo | Referencia |", "|---|---|"]

        if related_requirement:
            rows.append(f"| Requerimiento | `{related_requirement}` |")

        for code_file in related_code or []:
            rows.append(f"| Codigo | `{code_file}` |")

        body_sections.append("\n".join(rows))

    # Status badge

    status_line = " | ".join(f"**{s}**" if s == status else s for s in STATUSES)

    body_sections.append(f"## Estado\n\n**Estado:** {status_line}")

    final_content = frontmatter.render() + "\n\n" + "\n\n".join(body_sections)

    note_path.parent.mkdir(parents=True, exist_ok=True)

    atomic_write_text(note_path, final_content)

    entry = {
        "docId": note_id,
        "test_id": test_id,
        "project": project,
        "title": title,
        "test_type": test_type,
        "status": status,
        "related_requirement": related_requirement or "",
        "relPath": str(note_path.relative_to(_raiz())).replace("\\", "/"),
        "updatedAt": now,
    }

    index["tests"].append(entry)

    save_index(index)

    return {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(_raiz())).replace("\\", "/"),
        "test_id": test_id,
        "action": "created",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Test Save Tool -- ISO/IEC/IEEE 29119-3 test case documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Examples:

  python vault_test_save.py --project "mi-api" --title "Login success" --test_type unit --description "Test successful login with valid credentials" --preconditions "User exists in DB" --steps '[{"step":1,"action":"Call login(user,pwd)","expected":"Returns AuthToken"}]' --expected_result "AuthToken with valid JWT"



  python vault_test_save.py --project "mi-api" --title "Auth API flow" --test_type integration --description "Full auth flow via HTTP" --related_requirement "REQ-001" --related_code "src/auth.py"



  python vault_test_save.py --project "mi-api" --title "Login performance" --test_type performance --description "Login endpoint under load" --preconditions "1000 concurrent users" --expected_result "p99 < 200ms"



Notes:

  - test_type: unit | integration | e2e | performance | security | acceptance  (ISO/IEC/IEEE 29119-3)

  - status: not_run | pass | fail | blocked | skip

  - --related_code accepts comma-separated file paths

  - --steps JSON format: [{"step": 1, "action": "...", "expected": "..."}]

  - test_id is auto-generated as TEST-001, TEST-002, etc. per project

""",
    )

    parser.add_argument("--project", required=True, help="Project slug")

    parser.add_argument("--title", required=True, help="Short test case title")

    parser.add_argument("--test_type", required=True, help=f"Test type: {TEST_TYPES}")

    parser.add_argument("--description", required=True, help="What is being tested")

    parser.add_argument(
        "--preconditions", help="Setup conditions required before running the test"
    )

    parser.add_argument(
        "--steps",
        help='JSON array of steps: [{"step":1,"action":"...","expected":"..."}]',
    )

    parser.add_argument("--expected_result", help="Overall expected outcome")

    parser.add_argument(
        "--related_requirement", help="Related requirement ID (e.g. REQ-001)"
    )

    parser.add_argument(
        "--related_code", help="Comma-separated list of related source files"
    )

    parser.add_argument(
        "--status",
        default="not_run",
        help=f"Test status (default: not_run): {STATUSES}",
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

    steps = parse_json_arg(args.steps, "steps")

    result = vault_test_save(
        project=args.project,
        title=args.title,
        test_type=args.test_type,
        description=args.description,
        preconditions=args.preconditions,
        steps=steps,
        expected_result=args.expected_result,
        related_requirement=args.related_requirement,
        related_code=related_code_list,
        status=args.status,
        tags=args.tags,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_test_save"))

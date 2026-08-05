#!/usr/bin/env python3

"""

Vault AI Decision Tool -- Log AI agent decisions (ISO/IEC 42001:2023 AIMS)



Records significant decisions made by AI agents with rationale, alternatives,

risks and human oversight status. Saves to 16_AI_Governance/decisions/.



Decision types: architectural, security, data-model, algorithm, configuration, process

Impact levels: low, medium, high, critical



Usage:

    python vault_ai_decision.py --project "mi-api" --title "Use JWT over sessions" --decision_type architectural --description "Decided to use stateless JWT tokens instead of server-side sessions" --rationale "Horizontal scaling requires stateless auth" --impact_level medium

    python vault_ai_decision.py --project "mi-api" --title "Hash algorithm: bcrypt" --decision_type security --description "Using bcrypt with cost factor 12 for password hashing" --rationale "bcrypt is resistant to GPU attacks; cost 12 balances security/performance" --alternatives '["argon2id - more secure but higher memory","sha256 - rejected: no salt by default"]' --risks '["Cost factor may need tuning under high load"]'

    python vault_ai_decision.py --project "mi-api" --title "Shard user table by region" --decision_type data-model --description "User table partitioned by geographic region" --rationale "GDPR data residency requirements" --impact_level high --human_approved

"""

import argparse

import json

import re

import sys

from vault_errors import wrap_main
from vault_lib import slugify_strict, utcnow
from vault_io import (
    write_report,
    atomic_write_text,
    atomic_write_json,
    assert_within_vault,
    VAULT_ROOT,
)
import uuid

from pathlib import Path
from typing import Any, Dict, List, Optional


GOVERNANCE_DIR = VAULT_ROOT / "16_AI_Governance"

DECISIONS_DIR = GOVERNANCE_DIR / "decisions"

INDEX_FILE = GOVERNANCE_DIR / ".decisions-log.json"


DECISION_TYPES = [
    "architectural",
    "security",
    "data-model",
    "algorithm",
    "configuration",
    "process",
]

IMPACT_LEVELS = ["low", "medium", "high", "critical"]


def slugify(text: str) -> str:
    # Delega en el slug canónico (`vault_lib.slugify`). La copia que había
    # aquí divergía del resto: unas borraban los acentos, otras los dejaban
    # en el nombre de fichero. Una sola fuente, un solo nombre de nota.
    return slugify_strict(text)


def load_index() -> Dict[str, Any]:
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):
        return {"decisions": []}


def save_index(data: Dict[str, Any]) -> None:
    GOVERNANCE_DIR.mkdir(parents=True, exist_ok=True)

    atomic_write_json(INDEX_FILE, data)


def vault_ai_decision(
    project: str,
    title: str,
    decision_type: str,
    description: str,
    rationale: str,
    alternatives: Optional[List[str]] = None,
    risks: Optional[List[str]] = None,
    impact_level: str = "medium",
    reversible: bool = True,
    human_approved: bool = False,
    related_code: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if decision_type not in DECISION_TYPES:
        return {
            "ok": False,
            "error": f"decision_type '{decision_type}' not valid. Use: {DECISION_TYPES}",
        }

    if impact_level not in IMPACT_LEVELS:
        return {
            "ok": False,
            "error": f"impact_level '{impact_level}' not valid. Use: {IMPACT_LEVELS}",
        }

    safe_project = slugify(project)

    title_slug = slugify(title)

    now = utcnow()

    index = load_index()

    # Count existing decisions for this project to get sequential ID

    project_decisions = [d for d in index["decisions"] if d.get("project") == project]

    decision_number = len(project_decisions) + 1

    decision_id = f"AID-{decision_number:03d}"

    note_id = str(uuid.uuid4())

    filename = f"{safe_project}-{title_slug}.md"

    note_path = DECISIONS_DIR / filename

    try:
        assert_within_vault(note_path, VAULT_ROOT)

    except ValueError as exc:
        return {
            "ok": False,
            "error_code": "INVALID_PATH",
            "error": "INVALID_PATH",
            "message": str(exc),
        }

    tags_list = list(tags or [])

    tags_list.extend([safe_project, "ai-decision", decision_type, impact_level])

    cia_integrity = "high" if impact_level in ("high", "critical") else "medium"

    frontmatter = ["---"]

    frontmatter.append(f"id: {note_id}")

    frontmatter.append(f"decision_id: {decision_id}")

    frontmatter.append(f"title: {title}")

    frontmatter.append(f"project: {project}")

    frontmatter.append(f"decision_type: {decision_type}")

    frontmatter.append(f"impact_level: {impact_level}")

    frontmatter.append(f"human_approved: {str(human_approved).lower()}")

    frontmatter.append(f"reversible: {str(reversible).lower()}")

    frontmatter.append(f"createdAt: {now}")

    frontmatter.append(f"updatedAt: {now}")

    if tags_list:
        frontmatter.append(f"tags: {json.dumps(list(dict.fromkeys(tags_list)))}")

    frontmatter.append(f"cia_integrity: {cia_integrity}")

    frontmatter.append(f"cia_availability: medium")

    frontmatter.append(f"cia_sensitivity: internal")

    frontmatter.append(f"agent: system")

    frontmatter.append("---")

    body_sections = []

    # Informative header

    approved_str = "Si" if human_approved else "No"

    reversible_str = "Si" if reversible else "No"

    header_info = (
        f"**Proyecto:** {project}  |  **Tipo:** {decision_type}  |  "
        f"**Impacto:** {impact_level}  |  **Reversible:** {reversible_str}  |  "
        f"**Aprobado por humano:** {approved_str}"
    )

    body_sections.append(header_info + "\n")

    body_sections.append(f"## Descripcion\n\n{description}")

    body_sections.append(f"## Justificacion\n\n{rationale}")

    if alternatives:
        lines = ["## Alternativas Consideradas\n"]

        for alt in alternatives:
            lines.append(f"- {alt}")

        body_sections.append("\n".join(lines))

    if risks:
        lines = ["## Riesgos Identificados\n"]

        for risk in risks:
            lines.append(f"- {risk}")

        body_sections.append("\n".join(lines))

    if related_code:
        lines = ["## Codigo Relacionado\n"]

        for code_file in related_code:
            lines.append(f"- `{code_file}`")

        body_sections.append("\n".join(lines))

    body_sections.append(
        "> *Registrado bajo ISO/IEC 42001:2023 — AI Management System*"
    )

    final_content = "\n".join(frontmatter) + "\n\n" + "\n\n".join(body_sections)

    note_path.parent.mkdir(parents=True, exist_ok=True)

    atomic_write_text(note_path, final_content)

    entry = {
        "docId": note_id,
        "decision_id": decision_id,
        "project": project,
        "title": title,
        "decision_type": decision_type,
        "impact_level": impact_level,
        "human_approved": human_approved,
        "reversible": reversible,
        "relPath": str(note_path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "updatedAt": now,
    }

    index["decisions"].append(entry)

    save_index(index)

    return {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "decision_id": decision_id,
        "impact_level": impact_level,
        "action": "created",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault AI Decision Tool -- ISO/IEC 42001:2023 AI decision logging",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Examples:

  python vault_ai_decision.py --project "mi-api" --title "Use JWT over sessions" --decision_type architectural --description "Decided to use stateless JWT tokens instead of server-side sessions" --rationale "Horizontal scaling requires stateless auth" --impact_level medium



  python vault_ai_decision.py --project "mi-api" --title "Hash algorithm: bcrypt" --decision_type security --description "Using bcrypt with cost factor 12 for password hashing" --rationale "bcrypt is resistant to GPU attacks; cost 12 balances security/performance" --alternatives '["argon2id - more secure but higher memory","sha256 - rejected: no salt by default"]' --risks '["Cost factor may need tuning under high load"]'



  python vault_ai_decision.py --project "mi-api" --title "Shard user table by region" --decision_type data-model --description "User table partitioned by geographic region" --rationale "GDPR data residency requirements" --impact_level high --human_approved



Notes:

  - decision_type: architectural | security | data-model | algorithm | configuration | process

  - impact_level: low | medium | high | critical

  - --human_approved is a flag (no value needed), default is false

  - --reversible defaults to true; use --no-reversible to mark as irreversible

  - decision_id is auto-generated as AID-001, AID-002, etc. per project

  - --related_code accepts comma-separated file paths

""",
    )

    parser.add_argument("--project", required=True, help="Project slug")

    parser.add_argument("--title", required=True, help="Short decision title")

    parser.add_argument(
        "--decision_type", required=True, help=f"Decision type: {DECISION_TYPES}"
    )

    parser.add_argument("--description", required=True, help="What decision was made")

    parser.add_argument("--rationale", required=True, help="Why this decision was made")

    parser.add_argument(
        "--alternatives",
        help='JSON array of alternatives considered: ["option A - reason","option B - reason"]',
    )

    parser.add_argument(
        "--risks", help='JSON array of identified risks: ["risk description"]'
    )

    parser.add_argument(
        "--impact_level",
        default="medium",
        help=f"Impact level (default: medium): {IMPACT_LEVELS}",
    )

    parser.add_argument(
        "--reversible",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Whether the decision can be reversed (default: true)",
    )

    parser.add_argument(
        "--human_approved",
        action="store_true",
        help="Flag: decision was reviewed and approved by a human",
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

    alternatives = parse_json_arg(args.alternatives, "alternatives")

    risks = parse_json_arg(args.risks, "risks")

    result = vault_ai_decision(
        project=args.project,
        title=args.title,
        decision_type=args.decision_type,
        description=args.description,
        rationale=args.rationale,
        alternatives=alternatives,
        risks=risks,
        impact_level=args.impact_level,
        reversible=args.reversible,
        human_approved=args.human_approved,
        related_code=related_code_list,
        tags=args.tags,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_ai_decision"))

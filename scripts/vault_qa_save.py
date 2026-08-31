#!/usr/bin/env python3
"""
vault_qa_save.py — QA quality management: plans, metrics, reports and strategy.

Saves QA documents to 21_QA/{type}/{project}-{slug}.md.

Types: test-plan, qa-metrics, qa-report, qa-strategy, coverage-report

Usage:
    python vault_qa_save.py --project "mi-api" --title "Q1 2026 Test Plan" --type test-plan \
        --description "Scope and strategy for Q1 testing"

    python vault_qa_save.py --project "mi-api" --title "Q1 2026 QA Report" --type qa-report \
        --description "QA status report for Q1 2026: test execution, defect rate, coverage"

    python vault_qa_save.py --project "mi-api" --title "Coverage Report" --type coverage-report \
        --description "Test coverage analysis: line coverage, branch coverage, gaps"

    python vault_qa_save.py --project "mi-api" --title "QA Strategy 2026" --type qa-strategy \
        --description "Testing philosophy, levels, automation goals, quality gates"

ISO references: ISO 9001:2015 §9 (performance evaluation), ISO 29119 (software testing), ISO 25010 (quality model)
"""

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import emit_error, wrap_main
from vault_io import (
    indice_compartido,
    write_report,
    atomic_write_text,
    atomic_write_json,
    assert_within_vault,
)
from vault_lib import slugify_strict
from vault_norms_catalog import status_frontmatter_lines

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.autoria.frontmatter import Frontmatter  # noqa: E402

QA_TYPES = ["test-plan", "qa-metrics", "qa-report", "qa-strategy", "coverage-report"]


def _raiz() -> Path:
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    return RepositorioAutoria(construir(root))


def _qa_dir() -> Path:
    return _repo().seccion("21_QA")


def _index_file() -> Path:
    return _repo().seccion("21_QA") / ".qa-index.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def slugify(text: str) -> str:
    return slugify_strict(text)


def load_index() -> Dict[str, Any]:
    try:
        with open(_index_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"qa": []}


def save_index(data: Dict[str, Any]) -> None:
    _qa_dir().mkdir(parents=True, exist_ok=True)
    atomic_write_json(_index_file(), data)


def vault_qa_save(
    project: str,
    title: str,
    qa_type: str,
    description: str,
    related_tests: Optional[List[str]] = None,
    related_requirements: Optional[List[str]] = None,
    coverage_target: Optional[float] = None,
    execution_frequency: Optional[str] = None,
    quality_criteria: Optional[List[str]] = None,
    status: str = "draft",
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if qa_type not in QA_TYPES:
        return emit_error(
            "vault_qa_save",
            "INVALID_VALUE",
            f"type '{qa_type}' not valid. Use: {QA_TYPES}",
        )

    if status not in ("draft", "review", "approved", "published", "archived"):
        return emit_error(
            "vault_qa_save",
            "INVALID_VALUE",
            f"status '{status}' not valid. Use: draft, review, approved, published, archived",
        )

    safe_project = slugify(project)
    title_slug = slugify(title)
    now = utcnow()

    with indice_compartido(_index_file(), {"qa": []}) as index:
        project_docs = [d for d in index["qa"] if d.get("project") == project]
        doc_number = len(project_docs) + 1
        doc_id = f"QA-{doc_number:03d}"
        note_id = str(uuid.uuid4())
        filename = f"{safe_project}-{title_slug}.md"
        note_path = _qa_dir() / qa_type / filename

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
        tags_list.extend([safe_project, "qa", qa_type, status])

        frontmatter = Frontmatter()
        frontmatter.set("id", note_id)
        frontmatter.set("qa_id", doc_id)
        frontmatter.set("title", title)
        frontmatter.set("project", project)
        frontmatter.set("qa_type", qa_type)
        frontmatter.lineas(status_frontmatter_lines("vault_qa_save", status))
        if coverage_target is not None:
            frontmatter.set("coverage_target", coverage_target)
        if execution_frequency:
            frontmatter.set("execution_frequency", execution_frequency)
        frontmatter.set("createdAt", now)
        frontmatter.set("updatedAt", now)
        if tags_list:
            frontmatter.set("tags", list(dict.fromkeys(tags_list)))
        frontmatter.set("cia_integrity", "high")
        frontmatter.set("cia_availability", "medium")
        frontmatter.set("cia_sensitivity", "internal")
        frontmatter.set("agent", "system")

        body_sections = [f"## Descripción\n\n{description}"]

        if related_tests:
            body_sections.append(
                "## Pruebas Relacionadas\n\n"
                + "\n".join(f"- `{t}`" for t in related_tests)
            )

        if related_requirements:
            body_sections.append(
                "## Requerimientos Cubiertos\n\n"
                + "\n".join(f"- `{r}`" for r in related_requirements)
            )

        if coverage_target is not None:
            body_sections.append(f"## Meta de Coverage\n\n`{coverage_target}%` — {quality_criteria[0] if quality_criteria else 'sin criterio especificado'}")

        if execution_frequency:
            body_sections.append(f"## Frecuencia de Ejecución\n\n{execution_frequency}")

        if quality_criteria:
            body_sections.append(
                "## Criterios de Calidad\n\n"
                + "\n".join(f"- {c}" for c in quality_criteria)
            )

        status_line = " | ".join(
            f"**{s}**" if s == status else s
            for s in ["draft", "review", "approved", "published", "archived"]
        )
        body_sections.append(f"## Estado\n\n**Estado:** {status_line}")

        final_content = frontmatter.render() + "\n\n" + "\n\n".join(body_sections)
        note_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(note_path, final_content)

        entry = {
            "docId": note_id,
            "qa_id": doc_id,
            "project": project,
            "title": title,
            "qa_type": qa_type,
            "status": status,
            "coverage_target": coverage_target,
            "relPath": str(note_path.relative_to(_raiz())).replace("\\", "/"),
            "updatedAt": now,
        }
        index["qa"].append(entry)

    return {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(_raiz())).replace("\\", "/"),
        "qa_id": doc_id,
        "action": "created",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault QA Save Tool — ISO 9001/29119/25010 quality management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python vault_qa_save.py --project "mi-api" --title "Q1 2026 Test Plan" --type test-plan \\
      --description "Scope and strategy for Q1 testing" --quality-criteria "coverage > 80%" \\
      --execution-frequency "before each release"

  python vault_qa_save.py --project "mi-api" --title "Q1 2026 QA Report" --type qa-report \\
      --description "QA status report for Q1 2026" --related-tests "TEST-001,TEST-002"

  python vault_qa_save.py --project "mi-api" --title "Coverage Report" --type coverage-report \\
      --description "Test coverage analysis" --coverage-target 85.5

Types:
  test-plan     Plan de pruebas y estrategia (ISO 29119-1)
  qa-metrics   KPIs de calidad: defect-rate, MTBF, pass-rate
  qa-report     Reporte de calidad por período
  qa-strategy   Política y estrategia QA
  coverage-report Reporte de cobertura de tests

Status:
  draft | review | approved | published | archived
""",
    )
    parser.add_argument("--project", required=True, help="Project slug")
    parser.add_argument("--title", required=True, help="Short document title")
    parser.add_argument(
        "--type",
        required=True,
        dest="qa_type",
        help=f"QA document type: {QA_TYPES}",
    )
    parser.add_argument("--description", required=True, help="Document description")
    parser.add_argument(
        "--related-tests",
        help="Comma-separated test IDs (e.g. TEST-001,TEST-002)",
    )
    parser.add_argument(
        "--related-requirements",
        help="Comma-separated requirement IDs",
    )
    parser.add_argument(
        "--coverage-target",
        type=float,
        help="Target test coverage percentage",
    )
    parser.add_argument(
        "--execution-frequency",
        help="How often this plan/report is executed (e.g. 'before each release')",
    )
    parser.add_argument(
        "--quality-criteria",
        nargs="*",
        help="Quality criteria (e.g. 'coverage > 80%' 'defect-rate < 2%')",
    )
    parser.add_argument(
        "--status",
        default="draft",
        help="Status: draft, review, approved, published, archived (default: draft)",
    )
    parser.add_argument("--tags", nargs="*", help="Additional tags")

    args = parser.parse_args()

    related_tests: Optional[List[str]] = None
    if args.related_tests:
        related_tests = [t.strip() for t in args.related_tests.split(",") if t.strip()]

    related_requirements: Optional[List[str]] = None
    if args.related_requirements:
        related_requirements = [r.strip() for r in args.related_requirements.split(",") if r.strip()]

    result = vault_qa_save(
        project=args.project,
        title=args.title,
        qa_type=args.qa_type,
        description=args.description,
        related_tests=related_tests,
        related_requirements=related_requirements,
        coverage_target=args.coverage_target,
        execution_frequency=args.execution_frequency,
        quality_criteria=args.quality_criteria,
        status=args.status,
        tags=args.tags,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_qa_save"))

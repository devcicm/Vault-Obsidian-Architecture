#!/usr/bin/env python3
"""
vault_quality_dashboard.py — Genera el dashboard de calidad operacional en 02_Observability/qa/.

Consume:
  - 00_System/quality-index.json     → vault_quality_check
  - 00_System/tag-registry.json      → vault_tags
  - 21_QA/.qa-index.json           → vault_qa_save
  - 15_Tests/.tests-index.json     → vault_test_save

Genera:
  - 02_Observability/qa/quality-dashboard.md

ISO references: ISO 9001:2015 §9.1 (performance evaluation), ISO 25010 (quality model)

Usage:
    python vault_quality_dashboard.py              # genera dashboard
    python vault_quality_dashboard.py --check      # solo lectura, sin escribir
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from vault_errors import wrap_main
from vault_io import atomic_write_text, get_vault_root, write_report

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vault.autoria.repositorio import RepositorioAutoria
from vault.kernel import construir


def _raiz() -> Path:
    return Path(get_vault_root())


def _repo() -> RepositorioAutoria:
    return RepositorioAutoria(construir(_raiz()))


def _system_dir() -> Path:
    return _repo().dir_sistema


def _quality_index() -> Path:
    return _repo().indice_calidad


def _tag_registry() -> Path:
    return _system_dir() / "tag-registry.json"


def _qa_index() -> Path:
    return _raiz() / "21_QA" / ".qa-index.json"


def _tests_index() -> Path:
    return _raiz() / "15_Tests" / ".tests-index.json"


def _dashboard_path() -> Path:
    return _raiz() / "02_Observability" / "qa" / "quality-dashboard.md"


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _score_label(score: float) -> str:
    if score >= 0.9:
        return "🟢 excellent"
    if score >= 0.7:
        return "🟡 good"
    if score >= 0.5:
        return "🟠 fair"
    return "🔴 poor"


def _build_dashboard() -> str:
    now = utcnow()
    qi = _load_json(_quality_index())
    tag_reg = _load_json(_tag_registry())
    qa_idx = _load_json(_qa_index())
    tests_idx = _load_json(_tests_index())

    if qi is None:
        return (
            "# Quality Dashboard — Sin datos\n\n"
            "> Ejecuta `python scripts/vault_quality_check.py` para generar el índice de calidad.\n"
        )

    sections: Dict[str, Any] = []

    # ── Overall DQ Score ────────────────────────────────────────────────────────
    overall = qi.get("overall_dq_score", 0.0)
    total_notes = qi.get("total_notes", 0)
    notes_below = qi.get("notes_below_07", 0)
    generated_at = qi.get("generated_at", now)

    sections.append("## Salud General\n")
    sections.append(f"| Métrica | Valor |",)
    sections.append("|---|---|")
    sections.append(f"| DQ Score global | {overall:.3f} {_score_label(overall)} |")
    sections.append(f"| Total notas | {total_notes} |")
    sections.append(f"| Notas bajo 0.7 | {notes_below} ({notes_below/max(total_notes,1)*100:.0f}%) |")
    sections.append(f"| Última evaluación | {generated_at} |")

    # ── DQ Scores por dimensión ────────────────────────────────────────────────
    if "scores" in qi:
        dim_rows = []
        for note_path, data in qi.get("notes", {}).items():
            scores = data.get("scores", {})
            for dim, score in scores.items():
                dim_rows.append((dim, score))

        if dim_rows:
            from collections import defaultdict
            dim_totals: Dict[str, float] = defaultdict(float)
            dim_counts: Dict[str, int] = defaultdict(int)
            for dim, score in dim_rows:
                dim_totals[dim] += score
                dim_counts[dim] += 1

            dim_avgs = {d: dim_totals[d] / dim_counts[d] for d in dim_totals}

            sections.append("\n## Scores por Dimensión (DQ)\n")
            sections.append("| Dimensión | Score | Estado |")
            sections.append("|---|---|---|")
            for dim in ["integrity", "consistency", "completeness", "accuracy", "validity", "timeliness", "authenticity", "non_repudiation", "uniqueness"]:
                score = dim_avgs.get(dim, 0.0)
                label = _score_label(score)
                sections.append(f"| {dim} | {score:.3f} {label} |")

    # ── Test Coverage ─────────────────────────────────────────────────────────
    if tests_idx:
        tests = tests_idx.get("tests", [])
        total_tests = len(tests)
        passed = sum(1 for t in tests if t.get("status") == "pass")
        failed = sum(1 for t in tests if t.get("status") == "fail")
        pass_rate = (passed / total_tests * 100) if total_tests > 0 else 0

        sections.append("\n## Cobertura de Tests\n")
        sections.append("| Métrica | Valor |")
        sections.append("|---|---|")
        sections.append(f"| Total tests | {total_tests} |")
        sections.append(f"| Passed | {passed} |")
        sections.append(f"| Failed | {failed} |")
        sections.append(f"| Pass rate | {pass_rate:.1f}% {_score_label(pass_rate/100)} |")
    else:
        sections.append("\n## Tests\n\n_Sin datos de tests. Ejecuta `vault_test_save` para registrar casos._")

    # ── QA Documents ──────────────────────────────────────────────────────────
    if qa_idx:
        qa_docs = qa_idx.get("qa", [])
        sections.append("\n## Documentos QA\n")
        sections.append("| ID | Proyecto | Tipo | Estado |")
        sections.append("|---|---|---|---|")
        for doc in qa_docs[-10:]:
            sections.append(
                f"| `{doc.get('qa_id', '?')}` "
                f"| {doc.get('project', '?')} "
                f"| {doc.get('qa_type', '?')} "
                f"| {doc.get('status', '?')} |"
            )
        if len(qa_docs) > 10:
            sections.append(f"\n_... y {len(qa_docs) - 10} más._")
    else:
        sections.append("\n## Documentos QA\n\n_Sin documentos QA. Ejecuta `vault_qa_save` para crear el primero._")

    # ── Tag Registry ────────────────────────────────────────────────────────
    if tag_reg:
        total_tags = len(tag_reg.get("tags", []))
        sections.append(f"\n## Vocabulario del Vault\n")
        sections.append(f"| Métrica | Valor |")
        sections.append("|---|---|")
        sections.append(f"| Total tags | {total_tags} |")
    else:
        sections.append("\n## Vocabulario del Vault\n\n_Sin registry de tags._")

    # ── Build final markdown ──────────────────────────────────────────────────
    frontmatter = (
        "---\n"
        "title: Quality Dashboard\n"
        "id: quality-dashboard\n"
        f"createdAt: {now}\n"
        f"updatedAt: {now}\n"
        'tags: ["quality", "dashboard", "qa"]\n'
        'type: observability\n'
        "norm_refs: [\"ISO 9001:2015 §9.1\"]\n"
        "---\n"
    )

    body = "# Quality Dashboard — Resumen Operacional\n\n"
    body += (
        "> Generado por `vault_quality_dashboard.py` · "
        f"datos desde {generated_at}\n\n"
    )
    body += "\n".join(sections)
    body += "\n\n---\n*Para detalle por nota, ejecutar `python scripts/vault_quality_check.py --min-score 0.7`*"

    return frontmatter + body


def vault_quality_dashboard(check_only: bool = False) -> Dict[str, Any]:
    """Genera o lee el dashboard de calidad operacional.

    Args:
        check_only: Si True, solo retorna el contenido sin escribir.

    Returns:
        {ok, path, content?} donde content solo existe si check_only=True.
    """
    content = _build_dashboard()
    if check_only:
        return {
            "ok": True,
            "check_only": True,
            "content": content,
        }
    dashboard_path = _dashboard_path()
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(dashboard_path, content)
    return {
        "ok": True,
        **write_report(),
        "path": str(dashboard_path.relative_to(_raiz())).replace("\\", "/"),
        "content_length": len(content),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_quality_dashboard — ISO 9001 §9.1 quality dashboard",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Solo lee y muestra sin escribir",
    )
    args = parser.parse_args()
    result = vault_quality_dashboard(check_only=args.check)
    if args.check:
        print(result["content"])
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_quality_dashboard"))

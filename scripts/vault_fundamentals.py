#!/usr/bin/env python3
"""
vault_fundamentals.py — Data Fundamentals registry & checker.

Defines and verifies the 8 fundamental data principles for the vault:
  F1 INTEGRIDAD       — required structural fields present, frontmatter parseable
  F2 CONSISTENCIA     — outgoing wiki-links resolve; type matches folder section
  F3 COMPLETITUD      — body has content; updatedAt and optional metadata populated
  F4 EXACTITUD        — frontmatter values match reality (path, type↔folder)
  F5 VALIDEZ          — field values within allowed sets (status/type/CIA)
  F6 ACTUALIDAD       — updated within threshold or evergreen
  F7 AUTENTICIDAD     — agent field present (who created/modified)
  F8 NO_REPUDIO       — at least one entry in change-log.json references this note

Writes 00_System/data-fundamentals.json (canonical registry consumed by other tools).

Usage:
    python vault_fundamentals.py                    # regenerate registry JSON
    python vault_fundamentals.py --list             # list all fundamentals
    python vault_fundamentals.py --check PATH       # verify a single note
    python vault_fundamentals.py --coverage         # per-tool coverage report
    python vault_fundamentals.py --doc              # regenerate data-fundamentals.md
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import wrap_main
from vault_lib import read_frontmatter, utcnow
from vault_io import atomic_write_json, atomic_write_text, VAULT_ROOT

SCRIPTS_DIR = Path(__file__).parent
SYSTEM_DIR = VAULT_ROOT / "00_System"
FUNDAMENTALS_JSON = SYSTEM_DIR / "data-fundamentals.json"
FUNDAMENTALS_MD = SYSTEM_DIR / "data-fundamentals.md"
CHANGE_LOG_JSON = SYSTEM_DIR / ".change-log.json"

# ──────────────────────────────────────────────────────────────────────────────
# Canonical registry — single source of truth for the 8 fundamentals
# ──────────────────────────────────────────────────────────────────────────────

FUNDAMENTALS: List[Dict[str, Any]] = [
    {
        "id": "F1",
        "name": "INTEGRIDAD",
        "english": "integrity",
        "description": "Los datos están completos y siguen las reglas definidas, sin que falte información esencial en los registros.",
        "dq_dimension": "integrity",
        "verifies": [
            "Frontmatter parseable (YAML válido)",
            "Campos estructurales obligatorios presentes: id, title, createdAt",
            "No hay corrupción de delimitadores '---'",
        ],
        "frontmatter_fields": ["id", "title", "createdAt"],
        "tools": [
            "vault_quality_check",
            "vault_validate",
            "vault_write",
            "vault_read",
            "vault_pattern_save",
            "vault_diagram_save",
            "vault_flow_save",
            "vault_requirement_save",
            "vault_test_save",
            "vault_infra_save",
            "vault_env_save",
            "vault_restore",
            "vault_migrate_rollback",
            "vault_security_scan",
            "vault_standard_upgrade",
            "vault_fundamentals",
        ],
    },
    {
        "id": "F2",
        "name": "CONSISTENCIA",
        "english": "consistency",
        "description": "La información es uniforme y coherente en todos los sistemas y bases de datos, evitando contradicciones.",
        "dq_dimension": "consistency",
        "verifies": [
            "Todos los wiki-links [[...]] resuelven a notas existentes",
            "El campo type coincide con la sección de carpeta (type:project → 01_Projects/)",
            "Los índices JSON están sincronizados con el contenido",
        ],
        "frontmatter_fields": ["type"],
        "tools": [
            "vault_quality_check",
            "vault_audit",
            "vault_graph",
            "vault_reindex",
            "vault_impact",
            "vault_propagate",
            "vault_relation_add",
            "vault_code_relation",
            "vault_merge",
            "vault_search",
            "vault_list",
            "vault_knowledge_get",
            "vault_pattern_list",
            "vault_infra_map",
            "vault_code_map",
            "vault_code_query",
            "vault_backup_list",
            "vault_migrate_docs",
            "vault_master_index",
            "vault_section_index",
            "vault_project_overview",
            "vault_fundamentals",
        ],
    },
    {
        "id": "F3",
        "name": "COMPLETITUD",
        "english": "completeness",
        "description": "No existen campos vacíos o nulos en los datos obligatorios necesarios para el análisis o la operación.",
        "dq_dimension": "completeness",
        "verifies": [
            "Campo updatedAt presente (ciclo de vida)",
            "Cuerpo de la nota tiene al menos 3 lineas de contenido",
            "Tags requeridos en toda nota de contenido (>=1 tag, salvo index/system)",
        ],
        "frontmatter_fields": ["updatedAt", "tags", "status", "type"],
        "tools": [
            "vault_quality_check",
            "vault_write",
            "vault_audit",
            "vault_append",
            "vault_knowledge_save",
            "vault_runbook_save",
            "vault_read",
            "vault_knowledge_get",
            "vault_diagram_save",
            "vault_flow_save",
            "vault_requirement_save",
            "vault_test_save",
            "vault_infra_save",
            "vault_code_module",
            "vault_env_save",
            "vault_master_index",
            "vault_project_status",
            "vault_project_overview",
            "vault_token_counter",
            "vault_token_service",
            "vault_tokens",
        ],
    },
    {
        "id": "F4",
        "name": "EXACTITUD",
        "english": "accuracy",
        "description": "El dato es una representación fiel de la realidad, siendo preciso y correcto en su contenido.",
        "dq_dimension": "accuracy",
        "verifies": [
            "El campo type coincide con la sección de carpeta donde reside la nota",
            "Si existe campo path en frontmatter, coincide con la ruta real",
            "El stem del archivo coincide con title (sin tildes/espacios convertidos)",
            "La documentación refleja el estado real del código (drift detection)",
        ],
        "frontmatter_fields": ["type", "path"],
        "tools": [
            "vault_quality_check",
            "vault_drift_detect",
            "vault_diff",
            "vault_code_map",
            "vault_code_module",
            "vault_migrate_docs",
            "vault_fundamentals",
        ],
    },
    {
        "id": "F5",
        "name": "VALIDEZ",
        "english": "validity",
        "description": "Los datos siguen los formatos, tipos y estándares de negocio establecidos.",
        "dq_dimension": "validity",
        "verifies": [
            "Valores de status, type en conjuntos permitidos",
            "Campos CIA (cia_integrity, cia_availability, cia_sensitivity) con valores válidos",
            "Timestamps en formato ISO 8601",
            "IDs siguen el formato del esquema",
        ],
        "frontmatter_fields": [
            "status",
            "type",
            "cia_integrity",
            "cia_availability",
            "cia_sensitivity",
        ],
        "tools": [
            "vault_validate",
            "vault_quality_check",
            "vault_env_save",
            "vault_security_scan",
            "vault_fundamentals",
        ],
    },
    {
        "id": "F6",
        "name": "ACTUALIDAD",
        "english": "timeliness",
        "description": "Los datos están disponibles en el momento necesario y reflejan la información más reciente.",
        "dq_dimension": "timeliness",
        "verifies": [
            "Nota actualizada dentro del umbral según cia_integrity (15d para critical/high, 30d default)",
            "O marcada como evergreen: true en frontmatter",
            "updatedAt presente y no en el futuro",
        ],
        "frontmatter_fields": ["updatedAt", "evergreen", "cia_integrity"],
        "tools": [
            "vault_quality_check",
            "vault_audit",
            "vault_drift_detect",
            "vault_diff",
            "vault_backup",
            "vault_project_status",
            "vault_timeline",
            "vault_token_counter",
            "vault_token_service",
            "vault_tokens",
            "vault_fundamentals",
        ],
    },
    {
        "id": "F7",
        "name": "AUTENTICIDAD",
        "english": "authenticity",
        "description": "La fuente de los datos y la identidad de quien los genera o modifica es legítima y verificable.",
        "dq_dimension": "authenticity",
        "verifies": [
            "Campo agent presente en frontmatter (AP-16: identidad del agente)",
            "Valor de agent no vacío y reconocible (claude, user, etc.)",
        ],
        "frontmatter_fields": ["agent"],
        "tools": [
            "vault_quality_check",
            "vault_validate",
            "vault_write",
            "vault_append",
            "vault_knowledge_save",
            "vault_bibliography_save",
            "vault_ai_decision",
            "vault_pattern_save",
            "vault_diagram_save",
            "vault_flow_save",
            "vault_requirement_save",
            "vault_test_save",
            "vault_infra_save",
            "vault_env_save",
        ],
    },
    {
        "id": "F8",
        "name": "NO_REPUDIO",
        "english": "non_repudiation",
        "description": "El autor de una acción o cambio en los datos no puede negar su autoría, dejando un rastro auditable.",
        "dq_dimension": "non_repudiation",
        "verifies": [
            "Al menos una entrada en .change-log.json referencia la ruta de la nota",
            "El cambio incluye timestamp, agent y reason inmutables",
            "Eliminaciones registradas obligatoriamente antes de borrar",
        ],
        "frontmatter_fields": [],
        "tools": [
            "vault_change_log",
            "vault_quality_check",
            "vault_log_error",
            "vault_ai_decision",
            "vault_runbook_log",
            "vault_backup",
            "vault_restore",
            "vault_migrate_rollback",
            "vault_standard_upgrade",
            "vault_timeline",
            "vault_fundamentals",
        ],
    },
]


def _has_change_log_entry(rel_path: str) -> bool:
    if not CHANGE_LOG_JSON.exists():
        return False
    try:
        entries = json.loads(CHANGE_LOG_JSON.read_text(encoding="utf-8"))
        for e in entries:
            if e.get("path") == rel_path or e.get("new_path") == rel_path:
                return True
    except Exception:
        return False
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Per-note verification
# ──────────────────────────────────────────────────────────────────────────────


def check_note(rel_path: str) -> Dict[str, Any]:
    """Verify all 8 fundamentals for a single note. Returns pass/fail per principle."""
    note_path = VAULT_ROOT / rel_path
    if not note_path.exists():
        return {"ok": False, "error": f"Note not found: {rel_path}"}

    fm = read_frontmatter(note_path)
    content = note_path.read_text(encoding="utf-8", errors="ignore")
    body = (
        content.split("---", 2)[2]
        if content.startswith("---") and "---" in content[3:]
        else content
    )
    body_lines = [l for l in body.splitlines() if l.strip()]

    results: Dict[str, Dict[str, Any]] = {}

    # F1 INTEGRIDAD
    f1_pass = bool(fm) and all(
        fm.get(f, "").strip() for f in ("id", "title", "createdAt")
    )
    results["F1"] = {
        "name": "INTEGRIDAD",
        "pass": f1_pass,
        "issues": []
        if f1_pass
        else ["Missing structural fields or frontmatter unparseable"],
    }

    # F2 CONSISTENCIA — type matches folder
    section_type_map = {
        "01_Projects": "project",
        "03_Decisions": "decision",
        "04_Sessions": "session",
        "05_Patterns": "pattern",
        "06_Diagrams": "diagram",
        "07_Knowledge": "knowledge",
        "08_Runbooks": "runbook",
        "09_Infrastructure": "infra",
        "11_Code": "code",
        "12_Bibliography": "bibliography",
        "13_Flows": "flow",
        "14_Requirements": "requirement",
        "15_Tests": "test",
        "16_AI_Governance": "ai_decision",
    }
    folder = rel_path.split("/")[0] if "/" in rel_path else ""
    expected_type = section_type_map.get(folder)
    actual_type = fm.get("type", "").lower()
    f2_issues = []
    if expected_type and actual_type and actual_type != expected_type:
        f2_issues.append(
            f"type '{actual_type}' does not match folder section (expected '{expected_type}')"
        )
    results["F2"] = {"name": "CONSISTENCIA", "pass": not f2_issues, "issues": f2_issues}

    # F3 COMPLETITUD
    f3_issues = []
    if not fm.get("updatedAt"):
        f3_issues.append("Missing updatedAt")
    if len(body_lines) < 3:
        f3_issues.append(
            f"Body has only {len(body_lines)} content line(s), expected >=3"
        )
    fm_tags = fm.get("tags", [])
    is_index = rel_path.endswith("/index.md") or rel_path == "index.md" or Path(rel_path).stem == "index"
    is_system = rel_path.startswith("00_System/") or rel_path == "00_System"
    if not is_index and not is_system and (not fm_tags or len(fm_tags) == 0):
        f3_issues.append("Missing tags — content notes require >=1 tag (AP-26)")
    results["F3"] = {"name": "COMPLETITUD", "pass": not f3_issues, "issues": f3_issues}

    # F4 EXACTITUD
    f4_issues = []
    if expected_type and actual_type and actual_type != expected_type:
        f4_issues.append(f"type='{actual_type}' inconsistent with folder '{folder}'")
    if fm.get("path"):
        declared = fm.get("path", "").replace("\\", "/")
        if declared and declared != rel_path:
            f4_issues.append(
                f"path field='{declared}' differs from actual path='{rel_path}'"
            )
    results["F4"] = {"name": "EXACTITUD", "pass": not f4_issues, "issues": f4_issues}

    # F5 VALIDEZ
    valid_status = {
        "active",
        "draft",
        "review",
        "archived",
        "deprecated",
        "en_progreso",
        "en_desarrollo",
        "in_progress",
        "done",
        "blocked",
        "pending",
        "completado",
        "completed",
        "cancelado",
        "cancelled",
    }
    valid_cia_i = {"critical", "high", "medium", "low"}
    valid_cia_a = {"high", "medium", "low"}
    valid_cia_s = {"public", "internal", "restricted"}
    f5_issues = []
    if "status" in fm and fm["status"].lower().replace("-", "_") not in valid_status:
        f5_issues.append(f"status '{fm['status']}' not in allowed values")
    if "cia_integrity" in fm and fm["cia_integrity"].lower() not in valid_cia_i:
        f5_issues.append(f"cia_integrity '{fm['cia_integrity']}' invalid")
    if "cia_availability" in fm and fm["cia_availability"].lower() not in valid_cia_a:
        f5_issues.append(f"cia_availability '{fm['cia_availability']}' invalid")
    if "cia_sensitivity" in fm and fm["cia_sensitivity"].lower() not in valid_cia_s:
        f5_issues.append(f"cia_sensitivity '{fm['cia_sensitivity']}' invalid")
    results["F5"] = {"name": "VALIDEZ", "pass": not f5_issues, "issues": f5_issues}

    # F6 ACTUALIDAD
    f6_pass = True
    f6_issues = []
    if fm.get("evergreen", "").lower() not in ("true", "yes", "1"):
        updated = fm.get("updatedAt") or fm.get("createdAt") or ""
        if updated:
            try:
                dt = datetime.fromisoformat(updated[:19])
                days = (datetime.now(timezone.utc).replace(tzinfo=None) - dt).days
                threshold = (
                    15
                    if fm.get("cia_integrity", "medium").lower() in ("critical", "high")
                    else 30
                )
                if days > threshold:
                    f6_pass = False
                    f6_issues.append(
                        f"{days} days since update (threshold {threshold}d)"
                    )
            except Exception:
                f6_issues.append(f"Could not parse updatedAt: {updated}")
                f6_pass = False
    results["F6"] = {"name": "ACTUALIDAD", "pass": f6_pass, "issues": f6_issues}

    # F7 AUTENTICIDAD
    f7_pass = bool(fm.get("agent", "").strip())
    results["F7"] = {
        "name": "AUTENTICIDAD",
        "pass": f7_pass,
        "issues": [] if f7_pass else ["Missing 'agent' field in frontmatter (AP-16)"],
    }

    # F8 NO_REPUDIO
    f8_pass = _has_change_log_entry(rel_path)
    results["F8"] = {
        "name": "NO_REPUDIO",
        "pass": f8_pass,
        "issues": [] if f8_pass else ["No change-log entry references this note"],
    }

    passed = sum(1 for r in results.values() if r["pass"])
    return {
        "ok": True,
        "path": rel_path,
        "fundamentals_passed": passed,
        "fundamentals_total": len(results),
        "compliance_score": round(passed / len(results), 3),
        "results": results,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Coverage report
# ──────────────────────────────────────────────────────────────────────────────


def coverage_report() -> Dict[str, Any]:
    """Return matrix of which tools implement which fundamentals."""
    by_tool: Dict[str, List[str]] = {}
    for f in FUNDAMENTALS:
        for tool in f["tools"]:
            by_tool.setdefault(tool, []).append(f["id"])

    return {
        "ok": True,
        "total_fundamentals": len(FUNDAMENTALS),
        "tools_with_coverage": len(by_tool),
        "by_tool": {t: sorted(ids) for t, ids in sorted(by_tool.items())},
        "by_fundamental": {f["id"]: f["tools"] for f in FUNDAMENTALS},
    }


# ──────────────────────────────────────────────────────────────────────────────
# Registry generation
# ──────────────────────────────────────────────────────────────────────────────


def export_registry() -> Dict[str, Any]:
    """Write 00_System/data-fundamentals.json with the canonical registry."""
    data = {
        "version": "v27",
        "generated_at": utcnow(),
        "generated_by": "vault_fundamentals",
        "source": "fundamentos de datos.txt",
        "total": len(FUNDAMENTALS),
        "fundamentals": FUNDAMENTALS,
    }
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(FUNDAMENTALS_JSON, data)
    return {
        "ok": True,
        "path": str(FUNDAMENTALS_JSON.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "total": len(FUNDAMENTALS),
        "generated_at": data["generated_at"],
    }


def export_doc() -> Dict[str, Any]:
    """Write 00_System/data-fundamentals.md as human-readable reference."""
    lines: List[str] = [
        "---",
        "id: data-fundamentals",
        "title: Fundamentos de Datos",
        "type: knowledge",
        "agent: vault_fundamentals",
        f"createdAt: {utcnow()}",
        f"updatedAt: {utcnow()}",
        "cia_integrity: high",
        "cia_availability: high",
        "evergreen: true",
        "---",
        "",
        "# Fundamentos de Datos",
        "",
        "Los 8 principios fundamentales que rigen la calidad y trazabilidad de los datos del vault.",
        "Cada principio se mapea a una dimensión de Data Quality (DQ) verificable por `vault_quality_check`.",
        "",
        "| ID  | Principio        | Dimensión DQ      | Tools que lo implementan                                     |",
        "|-----|------------------|-------------------|--------------------------------------------------------------|",
    ]
    for f in FUNDAMENTALS:
        tools_str = ", ".join(f["tools"])
        lines.append(
            f"| {f['id']}  | {f['name']:16} | {f['dq_dimension']:17} | {tools_str} |"
        )

    lines.extend(["", "---", ""])

    for f in FUNDAMENTALS:
        lines.append(f"## {f['id']} {f['name']}")
        lines.append("")
        lines.append(f"**Definición:** {f['description']}")
        lines.append("")
        lines.append(f"**Dimensión DQ:** `{f['dq_dimension']}`")
        lines.append("")
        lines.append("**Verifica:**")
        for v in f["verifies"]:
            lines.append(f"- {v}")
        lines.append("")
        if f["frontmatter_fields"]:
            lines.append(
                f"**Campos frontmatter:** `{', '.join(f['frontmatter_fields'])}`"
            )
            lines.append("")
        lines.append(f"**Implementado por:** {', '.join(f['tools'])}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Uso")
    lines.append("")
    lines.append("```bash")
    lines.append("# Verificar fundamentos de una nota")
    lines.append(
        "python scripts/vault_fundamentals.py --check 01_Projects/api/overview.md"
    )
    lines.append("")
    lines.append("# Ver cobertura por tool")
    lines.append("python scripts/vault_fundamentals.py --coverage")
    lines.append("")
    lines.append("# Regenerar JSON canonical (data-fundamentals.json)")
    lines.append("python scripts/vault_fundamentals.py")
    lines.append("```")

    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_text(FUNDAMENTALS_MD, "\n".join(lines) + "\n")
    return {
        "ok": True,
        "path": str(FUNDAMENTALS_MD.relative_to(VAULT_ROOT)).replace("\\", "/"),
    }


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_fundamentals — gestion y verificacion de los 8 fundamentos de datos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Los 8 fundamentos: INTEGRIDAD, CONSISTENCIA, COMPLETITUD, EXACTITUD,
VALIDEZ, ACTUALIDAD, AUTENTICIDAD, NO_REPUDIO.

Ejemplos:
  python vault_fundamentals.py                            # genera data-fundamentals.json
  python vault_fundamentals.py --list                     # lista los 8 principios
  python vault_fundamentals.py --check "01_Projects/api/overview.md"
  python vault_fundamentals.py --coverage                 # tools x fundamentos
  python vault_fundamentals.py --doc                      # genera data-fundamentals.md

Notas:
  - Por defecto regenera el registro canonico en 00_System/data-fundamentals.json
  - --check evalua los 8 fundamentos sobre una nota y retorna pass/fail por principio
""",
    )
    parser.add_argument("--list", action="store_true", help="List all 8 fundamentals")
    parser.add_argument(
        "--check", metavar="PATH", help="Verify fundamentals for a single note"
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Per-tool coverage report"
    )
    parser.add_argument(
        "--doc", action="store_true", help="Generate data-fundamentals.md"
    )

    args = parser.parse_args()

    if args.list:
        result = {
            "ok": True,
            "total": len(FUNDAMENTALS),
            "fundamentals": [
                {
                    "id": f["id"],
                    "name": f["name"],
                    "dq_dimension": f["dq_dimension"],
                    "description": f["description"],
                }
                for f in FUNDAMENTALS
            ],
        }
    elif args.check:
        result = check_note(args.check)
    elif args.coverage:
        result = coverage_report()
    elif args.doc:
        result = export_doc()
    else:
        # Default: regenerate registry
        result = export_registry()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_fundamentals"))

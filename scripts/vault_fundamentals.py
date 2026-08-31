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

from vault_errors import emit_error, wrap_main
from vault_lib import read_frontmatter, utcnow
from vault_io import atomic_write_json, atomic_write_text
SCRIPTS_DIR = Path(__file__).parent

# ──────────────────────────────────────────────────────────────────────────────
# superseded_by: vault_fundamentals_catalog (v40.28) — AP-62.
#
# Los cinco registros y `cia_valores` se fueron a una hoja del núcleo. Aqui se
# reexportan para que ningún llamador se rompa (no-derogación), pero entrar por
# esta puerta arrastra el verificador entero y sus cuatro dependencias: quien
# solo quiera el dato lo pide al dueño.
# ──────────────────────────────────────────────────────────────────────────────

from vault_fundamentals_catalog import (  # noqa: F401,E402
    BIGDATA_VS,
    CIA_TRIAD,
    FAIR_PRINCIPLES,
    FRAMEWORK_REGISTRIES,
    FUNDAMENTALS,
    ISO_COVERAGE,
    cia_valores,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGobernanza:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGobernanza(construir(root))


def _system_dir() -> Path:
    return _repo().dir_sistema


def _fundamentals_json() -> Path:
    return _repo().fundamentos_json


def _fundamentals_md() -> Path:
    return _repo().fundamentos_md


def _framework_json() -> Path:
    return _repo().marco_json


def _framework_md() -> Path:
    return _repo().marco_md


def _change_log_json() -> Path:
    return _repo().bitacora_cambios


def framework_ids() -> List[str]:
    """Todos los ids estables del marco — usados por el guard anti-drift de vault_norms."""
    return [entry["id"] for registry in FRAMEWORK_REGISTRIES.values() for entry in registry]


def _has_change_log_entry(rel_path: str) -> bool:
    if not _change_log_json().exists():
        return False
    try:
        entries = json.loads(_change_log_json().read_text(encoding="utf-8"))
        for e in entries:
            if e.get("path") == rel_path or e.get("new_path") == rel_path:
                return True
    except (json.JSONDecodeError, OSError):
        raise
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Per-note verification
# ──────────────────────────────────────────────────────────────────────────────


def check_note(rel_path: str) -> Dict[str, Any]:
    """Verify all 8 fundamentals for a single note. Returns pass/fail per principle."""
    note_path = _raiz() / rel_path
    if not note_path.exists():
        return emit_error("vault_fundamentals", "NOTE_NOT_FOUND", f"Note not found: {rel_path}")

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

    # F2 CONSISTENCIA — el tipo pertenece a la sección donde está archivada
    #
    # Aquí vivía una copia del mapa sección→tipo con UN tipo por sección. Medida
    # contra un vault real, penalizaba cinco de cada seis notas de 01_Projects,
    # todas escritas por las tools de este estándar (AP-44). El criterio ahora
    # es el del registro y solo señala lo verificable: un tipo que es canónico
    # de OTRA sección. Un tipo nuevo no es una violación (AP-39).
    from vault_registry import type_misfiled_in

    folder = rel_path.split("/")[0] if "/" in rel_path else ""
    actual_type = str(fm.get("type", "")).lower()
    f2_issues = []
    deberia = type_misfiled_in(folder, actual_type)
    if deberia:
        f2_issues.append(
            f"type '{actual_type}' es canónico de {' o '.join(deberia)}, no de "
            f"'{folder}' — nota archivada en la sección equivocada"
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
    # La comprobación tipo↔sección estaba aquí *además* de en F2, con la misma
    # regla y distinta redacción: una nota mal archivada bajaba dos dimensiones
    # por un solo defecto. F2 (consistencia) es su sitio; lo propio de F4 es
    # contrastar lo declarado contra lo real, que es la línea de abajo.
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
    valid_cia_i = cia_valores("cia_integrity")
    valid_cia_a = cia_valores("cia_availability")
    valid_cia_s = cia_valores("cia_sensitivity")
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
    _system_dir().mkdir(parents=True, exist_ok=True)
    atomic_write_json(_fundamentals_json(), data)
    return {
        "ok": True,
        "path": str(_fundamentals_json().relative_to(_raiz())).replace("\\", "/"),
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

    _system_dir().mkdir(parents=True, exist_ok=True)
    atomic_write_text(_fundamentals_md(), "\n".join(lines) + "\n")
    return {
        "ok": True,
        "path": str(_fundamentals_md().relative_to(_raiz())).replace("\\", "/"),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Marco de datos y gobernanza — matriz y exportadores (v39)
# ──────────────────────────────────────────────────────────────────────────────

#: Matriz concepto → métrica → umbral → tool → artefacto → enforcement.
#: Es la vista de una pantalla que hace verificable todo el marco. Cada fila
#: apunta a un número que una tool ya produce hoy — no hay filas aspiracionales.
TRACEABILITY_MATRIX: List[Dict[str, str]] = [
    {"concept": "Confidencialidad (CIA-C)", "metric": "hallazgos de secretos expuestos", "threshold": "0", "tool": "vault_security_scan", "artifact": "02_Observability/vulnerabilities/", "enforcement": "guard+audit"},
    {"concept": "Integridad (CIA-I / F1)", "metric": "dq.integrity", "threshold": "0.0–1.0, ≥0.7", "tool": "vault_quality_check", "artifact": "00_System/quality-index.json", "enforcement": "audit"},
    {"concept": "Disponibilidad (CIA-A)", "metric": "backups con manifiesto Merkle verificable", "threshold": "≥1 reciente", "tool": "vault_backup", "artifact": "vault-backups/", "enforcement": "guard (AP-36)"},
    {"concept": "Consistencia (F2)", "metric": "wiki-links rotos", "threshold": "0", "tool": "vault_audit", "artifact": "00_System/graph.json", "enforcement": "guard+audit"},
    {"concept": "Completitud (F3)", "metric": "líneas reales de contenido", "threshold": "≥3", "tool": "vault_write", "artifact": "content gate", "enforcement": "guard"},
    {"concept": "Exactitud (F4)", "metric": "coincidencia type ↔ carpeta", "threshold": "100%", "tool": "vault_validate", "artifact": "vault_registry.SECTIONS", "enforcement": "audit (CN-02)"},
    {"concept": "Validez (F5)", "metric": "status dentro de STATUS_VOCAB", "threshold": "12 valores", "tool": "vault_norms --audit", "artifact": "vault_norms.STATUS_VOCAB", "enforcement": "audit (CN-03)"},
    {"concept": "Oportunidad / Actualidad (F6)", "metric": "antigüedad de updatedAt", "threshold": "30d · 15d si CIA critical|high", "tool": "vault_audit", "artifact": "bloque stale", "enforcement": "audit"},
    {"concept": "Autenticidad (F7)", "metric": "cobertura del campo agent", "threshold": "100%", "tool": "vault_quality_check", "artifact": "frontmatter agent:", "enforcement": "audit (AP-16)"},
    {"concept": "No repudio (F8)", "metric": "entradas en change-log", "threshold": "1 por borrado", "tool": "vault_change_log", "artifact": "00_System/.change-log.json", "enforcement": "audit (SP-01)"},
    {"concept": "Unicidad (DQ-9)", "metric": "duplicados canonical-shadow", "threshold": "0", "tool": "vault_merge --detect", "artifact": "quality-index.json", "enforcement": "audit (AP-17/18)"},
    {"concept": "Localizable (FAIR-F)", "metric": "notas huérfanas", "threshold": "0", "tool": "vault_audit", "artifact": "99_Index/index.md", "enforcement": "audit"},
    {"concept": "Interoperable (FAIR-I)", "metric": "errores de sintaxis de wiki-link", "threshold": "0", "tool": "vault_graph_inspect", "artifact": "graph.json", "enforcement": "guard (AP-22/24)"},
    {"concept": "Reutilizable (FAIR-R)", "metric": "cadena de procedencia completa", "threshold": "agent + timestamps", "tool": "vault_diff", "artifact": ".history/", "enforcement": "audit (PAT-5)"},
    {"concept": "Veracidad (V4)", "metric": "overall_dq_score", "threshold": "≥0.7", "tool": "vault_quality_check", "artifact": "vault_audit.dqHealth", "enforcement": "audit"},
    {"concept": "Valor (V5)", "metric": "health score", "threshold": "0–100, objetivo 100", "tool": "vault_audit", "artifact": "vault_audit.nextActions", "enforcement": "audit"},
    {"concept": "Variabilidad (V6)", "metric": "drift doc ↔ código", "threshold": "0", "tool": "vault_drift_detect", "artifact": "@vault: tags", "enforcement": "audit (AP-08)"},
    {"concept": "Contención (AP-36)", "metric": "escrituras fuera del vault root", "threshold": "0", "tool": "vault_norms --audit", "artifact": "vault_io.get_vault_root()", "enforcement": "guard+audit"},
    {"concept": "Gobernanza de IA", "metric": "decisiones de IA registradas", "threshold": "1 por decisión", "tool": "vault_ai_decision", "artifact": "16_AI_Governance/", "enforcement": "recommended"},
    {"concept": "Auditabilidad", "metric": "operaciones con traza", "threshold": "100%", "tool": "vault_errors_trace", "artifact": "00_System/.tool-trace.json", "enforcement": "automático"},
]


def traceability_matrix() -> Dict[str, Any]:
    """Return the concept → metric → tool → artifact → enforcement matrix."""
    return {
        "ok": True,
        "total": len(TRACEABILITY_MATRIX),
        "generated_at": utcnow(),
        "generated_by": "vault_fundamentals",
        "matrix": TRACEABILITY_MATRIX,
    }


def export_framework() -> Dict[str, Any]:
    """Write 00_System/data-framework.json + .md with the full data framework."""
    data = {
        "version": "v39",
        "generated_at": utcnow(),
        "generated_by": "vault_fundamentals",
        "totals": {name: len(reg) for name, reg in FRAMEWORK_REGISTRIES.items()},
        "registries": FRAMEWORK_REGISTRIES,
        "traceability_matrix": TRACEABILITY_MATRIX,
    }
    _system_dir().mkdir(parents=True, exist_ok=True)
    atomic_write_json(_framework_json(), data)

    lines: List[str] = [
        "---",
        "id: data-framework",
        "title: Marco de Datos y Gobernanza",
        "type: knowledge",
        "agent: vault_fundamentals",
        f"createdAt: {utcnow()}",
        f"updatedAt: {utcnow()}",
        "cia_integrity: high",
        "cia_availability: high",
        "cia_sensitivity: public",
        "evergreen: true",
        "---",
        "",
        "# Marco de Datos y Gobernanza",
        "",
        "Artefacto derivado — generado por `vault_fundamentals --framework`. No editar a mano.",
        "",
        "## Tríada CIA — el pilar fundamental",
        "",
        "| ID | Eje | Campo | Valores | Efecto medible |",
        "|---|---|---|---|---|",
    ]
    for c in CIA_TRIAD:
        lines.append(
            f"| {c['id']} | {c['name']} | `{c['frontmatter_field']}` | "
            f"{', '.join(f'`{v}`' for v in c['values'])} | {c['effect']} |"
        )

    lines += [
        "",
        "## Los 8 Fundamentos de Datos",
        "",
        "| ID | Fundamento | Dimensión DQ | Campos verificados | Tools |",
        "|---|---|---|---|---|",
    ]
    for f in FUNDAMENTALS:
        fields = ", ".join(f"`{x}`" for x in f["frontmatter_fields"]) or "—"
        lines.append(
            f"| {f['id']} | {f['name']} | `{f['dq_dimension']}` | {fields} | {len(f['tools'])} |"
        )

    lines += [
        "",
        "## Principios FAIR",
        "",
        "| ID | Principio | Mecanismo en el vault | Métrica |",
        "|---|---|---|---|",
    ]
    for p in FAIR_PRINCIPLES:
        lines.append(f"| {p['id']} | {p['name']} ({p['spanish']}) | {p['mechanism']} | {p['metric']} |")

    lines += [
        "",
        "## Las V's del Big Data",
        "",
        "| ID | V | Métrica | Artefacto | Control |",
        "|---|---|---|---|---|",
    ]
    for v in BIGDATA_VS:
        lines.append(f"| {v['id']} | {v['name']} | {v['metric']} | `{v['artifact']}` | {v['control']} |")

    lines += [
        "",
        "## Cobertura de normas ISO",
        "",
        "| ID | Norma | Cláusula | Implementado por | Tools |",
        "|---|---|---|---|---|",
    ]
    for i in ISO_COVERAGE:
        lines.append(
            f"| {i['id']} | {i['norm']} | {i['clause']} | {i['implemented_by']} | "
            f"{', '.join(f'`{t}`' for t in i['tools'])} |"
        )

    lines += [
        "",
        "## Matriz de trazabilidad",
        "",
        "| Concepto | Métrica | Umbral | Tool | Artefacto | Enforcement |",
        "|---|---|---|---|---|---|",
    ]
    for m in TRACEABILITY_MATRIX:
        lines.append(
            f"| {m['concept']} | {m['metric']} | {m['threshold']} | `{m['tool']}` | "
            f"`{m['artifact']}` | {m['enforcement']} |"
        )
    lines.append("")

    atomic_write_text(_framework_md(), "\n".join(lines) + "\n")
    return {
        "ok": True,
        "json": str(_framework_json().relative_to(_raiz())).replace("\\", "/"),
        "md": str(_framework_md().relative_to(_raiz())).replace("\\", "/"),
        "totals": data["totals"],
        "matrix_rows": len(TRACEABILITY_MATRIX),
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
  python vault_fundamentals.py --framework                # genera data-framework.json + .md
  python vault_fundamentals.py --matrix                   # matriz concepto -> metrica -> tool

Notas:
  - Por defecto regenera el registro canonico en 00_System/data-fundamentals.json
  - --check evalua los 8 fundamentos sobre una nota y retorna pass/fail por principio
  - --framework exporta el marco completo: triada CIA, F1-F8, FAIR, V's del Big Data,
    cobertura ISO y matriz de trazabilidad. Es la fuente unica que el manifiesto
    documenta y que vault_norms --audit verifica contra el documento (anti-drift).
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
    parser.add_argument(
        "--framework",
        action="store_true",
        help="Generate data-framework.json + .md (CIA, F1-F8, FAIR, V's, ISO)",
    )
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="Print concept -> metric -> tool -> artifact -> enforcement matrix",
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
    elif args.framework:
        result = export_framework()
    elif args.matrix:
        result = traceability_matrix()
    else:
        # Default: regenerate registry
        result = export_registry()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_fundamentals"))

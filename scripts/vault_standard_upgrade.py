#!/usr/bin/env python3
"""
Vault Standard Upgrade Tool -- Detect and apply migrations between standard versions.

Reads 00_System/standard-version.json to find the current applied version,
then applies all pending migrations up to the target version.

Each migration creates missing folders, updates identity fields, and records
what was applied so future runs are idempotent.

Usage:
    python vault_standard_upgrade.py --check
    python vault_standard_upgrade.py --from v20 --to v25
    python vault_standard_upgrade.py --to latest
    python vault_standard_upgrade.py --init v25
"""

import argparse
import json
import sys
from vault_errors import wrap_main
from vault_lib import utcnow
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_registry import standard_folders

# Directorio de las propias tools. No es un side-effect ni una ruta del vault:
# es el sitio desde donde esta tool invoca a sus vecinas, así que sí se deriva
# de `__file__` (AP-36 rige para las escrituras, que van al vault). Faltaba, y
# las dos ramas que lo usan estaban envueltas en `except Exception`, de modo que
# el NameError salía como `fixes_failed: SCRIPTS_DIR is not defined` en
# `standard-version.json` en vez de romper.
SCRIPTS_DIR = Path(__file__).resolve().parent


CURRENT_VERSION = "v40.23"


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.ciclo_de_vida.repositorio import RepositorioCicloDeVida  # noqa: E402
from vault.kernel import construir  # noqa: E402
# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueño.
from vault_vocabulario import opciones as _opciones


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioCicloDeVida:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioCicloDeVida(construir(root))


def _system_dir() -> Path:
    return _repo().dir_sistema


def _version_file() -> Path:
    return _repo().fichero_version


def _identity_file() -> Path:
    return _repo().fichero_identidad


def _live_identity() -> Dict[str, str]:
    """Conteos de la versión corriente, derivados del catálogo canónico.

    Se importa aquí y no arriba para no crear un ciclo: vault_mcp_catalog puede
    acabar importando módulos que importan este. Si el catálogo no fuese
    legible, la migración no debe caerse por un dato informativo.
    """
    try:
        from vault_mcp_catalog import GROUPS, TOOLS_CATALOG

        return {"tools_count": str(len(TOOLS_CATALOG)), "groups_count": str(len(GROUPS))}
    except Exception:
        return {}

MIGRATIONS: Dict[str, Dict[str, Any]] = {
    "v21": {
        "description": "agent field, 12_Bibliography, vault_drift_detect",
        "add_folders": [
            "12_Bibliography/web",
            "12_Bibliography/papers",
            "12_Bibliography/docs",
            "12_Bibliography/apis",
            "12_Bibliography/books",
        ],
        "update_identity": {"tools_count": "38", "groups_count": "17"},
        "notes": [
            "AP-16: add agent: field to new notes",
            "vault_drift_detect mandatory in session protocol",
        ],
    },
    "v22": {
        "description": "vault_drift_detect snapshot/report gates",
        "add_folders": [],
        "update_identity": {},
        "notes": [
            "Session protocol updated: snapshot at start, report at close",
        ],
    },
    "v23": {
        "description": "13_Flows, vault_code_query, IEEE 1016 in vault_code_module",
        "add_folders": [
            "13_Flows/workflow",
            "13_Flows/pipeline",
            "13_Flows/lifecycle",
            "13_Flows/dataflow",
        ],
        "update_identity": {"tools_count": "40", "groups_count": "18"},
        "notes": [
            "vault_code_module now supports --methods, --classes, --constants, --exceptions, --iso_type",
            "vault_code_query: recursive index querying by file/method/class",
        ],
    },
    "v24": {
        "description": "ISO 25010/29148/29119/42001",
        "add_folders": [
            "14_Requirements",
            "15_Tests/unit",
            "15_Tests/integration",
            "15_Tests/e2e",
            "15_Tests/performance",
            "15_Tests/security",
            "15_Tests/acceptance",
            "16_AI_Governance/decisions",
        ],
        "update_identity": {"tools_count": "43", "groups_count": "21"},
        "notes": [
            "vault_code_module --quality for ISO 25010",
            "vault_requirement_save: ISO/IEC/IEEE 29148:2018",
            "vault_test_save: ISO/IEC/IEEE 29119-3:2021",
            "vault_ai_decision: ISO/IEC 42001:2023",
        ],
    },
    "v25": {
        "description": "AP-17~21, PAT-1~5, vault_change_log, vault_standard_upgrade",
        "add_folders": [],
        "update_identity": {"tools_count": "45", "groups_count": "23"},
        "notes": [
            "vault_write guards: AP-20 empty list ratio, AP-21 path-anchored wiki-links",
            "vault_section_index: stem-only wiki-links (AP-21 fix)",
            "vault_audit: AP-17 fuzzy title detection, AP-18 cross-folder hash detection",
            "vault_change_log: mandatory before note deletions",
            "vault_standard_upgrade: version gap detection and migration",
        ],
    },
    "v26": {
        "description": "emit_ok envelope, contracts, manifest, test runner, profiles, validate",
        "add_folders": [],
        "update_identity": {"tools_count": "53", "groups_count": "23"},
        "notes": [
            "vault_compact_contracts: genera tool-contracts.{json,md} desde los scripts",
            "vault_manifest: genera tools-manifest.json con estado active/deprecated/internal",
            "vault_test_runner: smoke/contracts/errors test suite (56/56 passing)",
            "vault_errors: emit_ok(), envelope tool+timestamp automatico en wrap_main",
            "vault_standard_upgrade: --validate compliance check, --set-profile minimal|standard|full",
            "vault_audit: excluye index.md/README.md de AP-17 (eran falsos positivos)",
            "vault_project_status: statusPath -> path; vault_relation_add: erdPath -> path",
        ],
    },
    "v27": {
        "description": "Data Quality framework, CIA schema, 8 Data Fundamentals, graph-aware propagation",
        "add_folders": [],
        "update_identity": {"tools_count": "57", "groups_count": "25"},
        "notes": [
            "vault_fundamentals: 8 Data Fundamentals registry (INTEGRIDAD, CONSISTENCIA, COMPLETITUD, EXACTITUD, VALIDEZ, ACTUALIDAD, AUTENTICIDAD, NO_REPUDIO)",
            "vault_quality_check: DQ scorer extended to 9 dimensions matching the 8 fundamentals + uniqueness",
            "vault_impact: BFS impact analysis on reverse backlink graph (uses 99_Index/graph.json)",
            "vault_propagate: 3 strategies (conservative/transitive/critical-path), 3 actions (notify/queue/reindex)",
            "vault_validate: CIA field validation + agent field validation (F7 AUTENTICIDAD)",
            "vault_change_log: --propagate flag triggers vault_impact + vault_propagate; provides F8 NO_REPUDIO",
            "vault_audit: --refresh-dq flag, dqHealth block, propagationPending, CIA-weighted health score",
            "vault_manifest: DQ/CIA/data_fundamentals metadata per tool, 'Data Quality' + 'Propagación' groups",
            "00_System/data-fundamentals.json: canonical registry of the 8 fundamentals (regenerable)",
            "00_System/data-fundamentals.md: human-readable reference with verification rules per principle",
            "00_System/quality-index.json: DQ scores per note with file_lock coordination",
            "00_System/propagation-queue.json: pending propagation items with priority",
        ],
    },
    "v28": {
        "description": "Field validation, security hardening confirmed, initialization protocol, reference implementation",
        "add_folders": [],
        "update_identity": {"tools_count": "57", "groups_count": "26"},
        "notes": [
            "assert_within_vault() en vault_io.py: previene path traversal (absolutos y ../) en todos los scripts de escritura",
            "CIA frontmatter obligatorio en 12 scripts de escritura: cia_integrity, cia_availability, cia_sensitivity, agent",
            "atomic_write_text / atomic_write_json en todos los paths criticos — elimina escrituras parciales",
            "Protocolo de inicializacion corregido: --init v28 (no --upgrade); vault_section_index para todas las secciones",
            "gitignore pattern: vault-*/scripts/ en repos consumidores (scripts no se re-versionan)",
            "Shell compatibility: args JSON con <> requieren Bash en Windows; PowerShell 5.1 los mangla",
            "Implementacion de referencia: vault-electron-fingerprint (ElectronJS + DP4500), 13 notas, score 100/100",
            "Mapa canonico script→carpeta: corrige discrepancias entre spec y implementacion real",
        ],
    },
    "v29": {
        "description": "Session delta detection, Merkle backup integrity, canonical tag registry, hash-index.json",
        "add_folders": [],
        "update_identity": {"tools_count": "59", "groups_count": "27"},
        "notes": [
            "vault_delta.py (NUEVO): deteccion de cambios entre sesiones via SHA-256 + BFS sobre grafo inverso de backlinks",
            "vault_tags.py (NUEVO): registro canonico de tags, auditoria de orphans/near-dupes, tag-index.md con wiki-links",
            "vault_backup.py: Merkle tree en .manifest.json (merkle_root, merkle_file_count) + --verify para verificacion de integridad",
            "vault_reindex.py: escribe 99_Index/hash-index.json con {hash, size, cia_integrity} por nota",
            "vault_write.py: tag_suggestions no-bloqueante en output cuando nuevos tags tienen similares canonicos",
            "vault_audit.py: bloque tagHealth en output (total_tags, orphaned_tags, near_dupes, untagged_notes_count, tag_health_score)",
            "AP-22 (vault_write + vault_audit): corchetes desbalanceados o [[]] vacios → error bloqueante; ghost_links (targets inexistentes) → warning no-bloqueante en output",
        ],
    },
    "v30": {
        "description": "Norm catalog (AP/PAT/SP/CN), norm_refs auto-embed, vault_norms, vault_code_tag, 34 norms total",
        "add_folders": [],
        "update_identity": {"tools_count": "61", "groups_count": "28"},
        "notes": [
            "vault_norms.py (NUEVO): catálogo canónico de 34 normas (AP-01~23, PAT-1~5, SP-01~03, CN-01~03) con list/show/scan/apply/rebuild",
            "vault_code_tag.py (NUEVO): embebe @norm comments en headers de archivos fuente (5 estilos: line/hash/block/open_close/dash)",
            "vault_write.py: auto-embebe norm_refs en frontmatter via compute_norm_refs(); errores incluyen norm_code + norm_name",
            "vault_audit.py: issues incluyen norm_code por entrada (AP-14/17/18/22); resultado incluye mapa norm_refs",
            "AP-23 (NUEVO): note complexity ceiling — notas >500 líneas deben dividirse",
            "SP-01~03 (NUEVO): protocolo de sesión — delete protocol, forward-link verification, session snapshot",
            "CN-01~03 (NUEVO): convenciones de nomenclatura — kebab-case, numbered folders, status vocabulary",
            "00_System/norm-registry.json: proyección del catálogo para consumo de tools",
            "00_System/code-tag-registry.json: registro de etiquetas de código custom (@norm tags)",
        ],
    },
    "v31": {
        "description": "Producción startup: incident management, SLOs, env matrix, release management (ISO 20000-1, ISO 22301, ISO 27001, ISO 25010, ISO 12207)",
        "add_folders": [
            "02_Observability/incidents",
            "02_Observability/slos",
            "09_Infrastructure/envs",
        ],
        "update_identity": {"tools_count": "61", "groups_count": "30"},
        "notes": [
            "vault_incident_save.py (NUEVO): post-mortems P1-P4 con ISO 20000-1:2018 §8.6 + ISO 22301:2019 §8.4 + ISO 27001:2022 A.16",
            "vault_slo_save.py (NUEVO): SLO/SLI/error-budget con ISO 20000-1:2018 §8.3 + ISO/IEC 25010:2023 reliability",
            "vault_env_matrix.py (NUEVO): matrix dev/staging/prod/dr con ISO 12207:2017 §6.3.4 + ISO 20000-1 §8.5",
            "vault_release_save.py (NUEVO): releases con checklist con ISO 12207:2017 §6.3.7 + ISO 20000-1 §8.5.2",
            "02_Observability/incidents/: subcarpeta para post-mortems estructurados",
            "02_Observability/slos/: subcarpeta para SLO definitions",
            "09_Infrastructure/envs/: subcarpeta para environment matrix",
        ],
    },
    "v32": {
        "description": "Gestión de riesgos y calidad: risk management, privacy/GDPR, non-conformidades (ISO 31000, ISO 27005, ISO 27701, ISO 9001)",
        "add_folders": [
            "02_Observability/risks",
            "02_Observability/quality",
            "09_Infrastructure/privacy",
        ],
        "update_identity": {"tools_count": "65", "groups_count": "31"},
        "notes": [
            "vault_risk_save.py (NUEVO): riesgos Likelihood×Impact con ISO 31000:2018 §6.4 + ISO/IEC 27005:2022 §8-9",
            "vault_privacy_save.py (NUEVO): inventario PII/GDPR con ISO/IEC 27701:2019 + GDPR Art.30 + DPIA auto-detect",
            "vault_ncr_save.py (NUEVO): no-conformidades NCR-YYYY-NNN con ISO 9001:2015 §10.2 + 5-Whys",
            "02_Observability/risks/: riesgos operativos, de seguridad, financieros, legales",
            "02_Observability/quality/: no conformidades y acciones correctivas",
            "09_Infrastructure/privacy/: inventario de tratamiento de datos personales",
        ],
    },
    "v33": {
        "description": "Regex validation module, bracket auto-fix, enhanced content gate",
        "add_folders": [],
        "fixes": ["bracket_anomalies", "path_anchored_links"],
        "update_identity": {"tools_count": "67", "groups_count": "33"},
        "notes": [
            "vault_regex.py (NUEVO): módulo de validación regex para wiki-links",
            "detect_bracket_anomalies(): detecta [[[[, ]]]], [[]] (AP-22)",
            "detect_path_anchored(): detecta [[/note]] (AP-21)",
            "fix_nested_brackets(): auto-corrección de corchetes anidados",
            "fix_whitespace_in_links(): auto-corrección de espacios en links",
            "vault_fix_brackets.py: usa vault_regex para detección más sensible (3+ corchetes)",
            "vault_write.py: AP-21 detection, anomaly detection con auto-fix",
            "vault_audit.py: mayor sensibilidad (3+ vs 4+)",
        ],
    },
    "v34": {
        "description": "MCP orchestrator, catalog system, auto-context persistence, session management",
        "add_folders": [],
        "fixes": [],
        "update_identity": {"tools_count": "69", "groups_count": "33"},
        "notes": [
            "vault_mcp.py (NUEVO): orquestador central del vault",
            "vault_mcp_catalog.py: catálogo de 69 tools con validators",
            "vault_mcp_context.py: gestión de contexto persistido",
            "00_System/vault_context.json: contexto persistido del vault",
            "Sistema de sostenibilidad de versiones: upgrades aplican fixes automáticos",
            "content gate mejorado con validación de wiki-links",
        ],
    },
    "v35": {
        "description": (
            "NORM_CATALOG completeness: AP-24 (bracket imbalance) and AP-25 "
            "(mermaid syntax errors) registered as first-class norms. "
            "Trace file unification: .tool-trace.json consolidated to "
            "00_System/.tool-trace.json only (eliminating the duplicate "
            "at VAULT_ROOT/.tool-trace.json produced by vault_encoding)."
        ),
        "tools_count": "92",
        "update_identity": True,
        "notes": [
            "AP-24 y AP-25 ahora son detectables por vault_norms --list",
            "vault_audit penaliza con AP-24 (-5/nota) y AP-25 (-2/error)",
            "Single source of truth para trace",
            "Eliminada la divergencia que producía traces incompletos",
        ],
    },
    "v36": {
        "description": (
            "SDD (Spec-Driven Development) introduction. atomic_write_text "
            "now cleans temp file on failure (eliminates disk-fill risk). "
            "Vault secret scanning integrated into atomic_write_text hook. "
            "CI workflow (.github/workflows/vault-ci.yml) with pytest + "
            "vault_validate + vault_audit + vault_spec_validate. "
            "Dual SDD: docs/sdd/ (project) + 00_System/skills/vault-sdd-init.md "
            "(skill for other agents to generate their own SDD)."
        ),
        "tools_count": "95",
        "update_identity": True,
        "notes": [
            "vault_secret_scan.py (NUEVO): hook pre-write que aborta si detecta secrets",
            "atomic_write_text garantiza cleanup en error (no temp files huérfanos)",
            "vault_id_check.py: id estable + dedupe de duplicados",
            "vault_fix_brackets.py: AP-26 auto-fix (pipes sin escapar, brackets)",
            "vault_history_compact.py: rotación .history/ (10 versiones/nota)",
            "Skill vault-sdd-init en 00_System/skills/ con logo ASCII",
            "docs/sdd/ generado con 14 archivos bilingües (ES/EN)",
        ],
    },
    "v37": {
        "description": (
            "MCP Server monolítico (JSON-RPC 2.0, transporte stdio + SSE, cero "
            "dependencias npm) + 3 validadores nuevos + mejoras en graph tools."
        ),
        "add_folders": [],
        "tools_count": "76",
        "update_identity": True,
        "notes": [
            "mcp/nodejs/vault-mcp-server.mjs: expone el catálogo como MCP tools",
            "Catálogo canónico sincronizado desde vault_mcp_catalog.py --sync",
            "Sin cambios estructurales en el vault: no hay carpetas ni datos que migrar",
        ],
    },
    "v38": {
        "description": (
            "AP-36 (contención e idempotencia) + coacción de fechas auto-parseadas "
            "por PyYAML en el límite de lectura de frontmatter."
        ),
        "add_folders": [],
        "update_identity": True,
        "notes": [
            "AP-36: toda operación escribe SOLO dentro del vault root",
            "vault_lib.parse_frontmatter coacciona datetime/date a strings ISO",
            "Sin migración de datos: la coacción ocurre en lectura, no reescribe notas",
        ],
    },
    "v39": {
        "description": (
            "Grupo 34 — Memoria de Contexto: eje consulta → contexto. Añade la "
            "sección 17_Preferences/ con sus 5 subcarpetas, destino canónico de "
            "vault_preferences. Marco de Datos y Gobernanza explícito."
        ),
        # Única migración estructural desde v33: sin estas carpetas,
        # vault_preferences no tiene destino en un vault preexistente.
        "add_folders": [
            "17_Preferences",
            "17_Preferences/workflow",
            "17_Preferences/style",
            "17_Preferences/tooling",
            "17_Preferences/constraints",
            "17_Preferences/domain",
            # Secciones 18–20: sin migración, un vault preexistente se queda sin
            # destino y las notas vuelven a repartirse por donde caigan — que es
            # exactamente el estado que motivó crearlas.
            "18_Bugs",
            "18_Bugs/open",
            "18_Bugs/root-causes",
            "18_Bugs/fixed",
            "19_Audits",
            "19_Audits/vocabulary",
            "19_Audits/runs",
            "19_Audits/findings",
            "20_Quarantine",
            "20_Quarantine/unclassified",
            "20_Quarantine/suspicious",
            "20_Quarantine/duplicates",
        ],
        # Los conteos de las migraciones ANTERIORES son historia: describen el
        # estándar tal como era en esa versión y se dejan como literales. El de
        # la versión CORRIENTE no es historia — describe el presente, así que se
        # deriva del registro. Escrito a mano decía 81/34 cuando ya eran otros.
        "update_identity": _live_identity(),
        "notes": [
            "vault_preferences.py (NUEVO): contexto estable del usuario, strength must|should|may",
            "vault_query_parse.py (NUEVO): lenguaje natural → consulta estructurada, determinista",
            "vault_subgraph.py (NUEVO): K semillas / N saltos con decaimiento y peso por predicado",
            "vault_context_pack.py (NUEVO): empaquetado bajo presupuesto de tokens",
            "vault_ingest.py (NUEVO): ingesta gobernada con preflight anti-poison no desactivable",
            "17_Preferences/: sección nueva registrada en vault_registry (owner: vault_preferences)",
            "18_Bugs/, 19_Audits/, 20_Quarantine/ (NUEVAS): secciones derivadas de medir 17 vaults reales",
            "vault_bug_save.py (NUEVO): ciclo del defecto síntoma → causa raíz → corrección verificada",
            "vault_quarantine.py (NUEVO): retención de notas sin destino seguro, sin borrar (no-derogación)",
            "Sin base de datos, sin embeddings y sin servicio externo",
        ],
    },
    "v40": {
        "description": (
            "Contextos acotados: ocho contextos de dominio mas un kernel "
            "compartido, con `vault_arch` como registro ejecutable de fronteras. "
            "Sin migracion estructural: no anade ni renombra una sola carpeta."
        ),
        # Un vault existente NO cambia de forma al subir a v40. El refactor es
        # del toolkit, no del vault, y decirlo aqui importa: una entrada sin
        # `add_folders` es la unica manera de que `--to latest` deje constancia
        # de la version aplicada sin tocar el disco del usuario.
        "add_folders": [],
        "update_identity": _live_identity(),
        "notes": [
            "vault_arch.py (NUEVO): registro CONTEXTS + guard de fronteras por AST + blueprint",
            "vault/ (NUEVO paquete): VaultContext inmutable, puertos Protocol y un repositorio por contexto",
            "AP-49 (NUEVA): vinculo resuelto en tiempo de import — 82 vinculos congelados en 62 modulos, saldados a 0",
            "docs/ARQUITECTURA.md (NUEVO): derivado de `vault_arch --blueprint`, no escrito a mano",
            "La prohibicion del Meta-toolkit deja de ser prosa: se mide por AST (forbidden_writes)",
            "Puerta nueva de AP-05 sobre rutas declaradas en dos repositorios de dominio",
            "Ni un fichero se mueve de scripts/, ni un envelope cambia: los consumidores no se enteran",
        ],
    },
}

VERSION_ORDER = [
    "v19",
    "v20",
    "v21",
    "v22",
    "v23",
    "v24",
    "v25",
    "v26",
    "v27",
    "v28",
    "v29",
    "v30",
    "v31",
    "v32",
    "v33",
    "v34",
    "v35",
    "v36",
    "v37",
    "v38",
    "v39",
    "v40",
]


FIX_TYPES = {
    "bracket_anomalies": {
        "tool": "vault_fix_brackets",
        "auto_apply": True,
        "dry_run_first": True,
        "description": "Corrige [[[[, ]]]], [[]], [[ ]] (AP-22)",
    },
    "path_anchored_links": {
        "tool": "vault_regex",
        "auto_apply": True,
        "description": "Corrige [[/note]] → [[note]] (AP-21)",
    },
    "empty_bullets": {
        "tool": "vault_write",
        "auto_apply": False,
        "description": "AP-20: bullets vacíos - warning only",
    },
}


def _version_index(v: str) -> int:
    try:
        return VERSION_ORDER.index(v)
    except ValueError:
        pass
    # VERSION_ORDER usa la versión mayor ("v39"), pero CURRENT_VERSION y los
    # version files escritos por releases puntuales traen minor ("v39.0",
    # "v34.2"). Sin esta normalización el índice era -1 y _pending_migrations
    # devolvía [] en silencio: `--to latest` no aplicaba NINGUNA migración.
    if isinstance(v, str) and "." in v:
        try:
            return VERSION_ORDER.index(v.split(".", 1)[0])
        except ValueError:
            return -1
    return -1


def _read_version_file() -> Dict[str, Any]:
    if not _version_file().exists():
        return {
            "applied_version": None,
            "applied_at": None,
            "applied_by": None,
            "migrations_applied": [],
        }
    try:
        return json.loads(_version_file().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {
            "applied_version": None,
            "applied_at": None,
            "applied_by": None,
            "migrations_applied": [],
        }


def _write_version_file(data: Dict[str, Any]) -> None:
    _system_dir().mkdir(parents=True, exist_ok=True)
    _version_file().write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


STANDARD_FOLDERS = standard_folders()  # from vault_registry — fuente unica

FM_REQUIRED_FIELDS = ("id", "title", "createdAt")


def _run_compliance_check(target_version: str) -> Dict[str, Any]:
    """Non-blocking compliance check: folders, frontmatter, audit health."""
    gaps: List[Dict[str, Any]] = []

    # 1. Folder check
    missing_folders = [f for f in STANDARD_FOLDERS if not (_raiz() / f).exists()]
    folders_ok = len(missing_folders) == 0
    if missing_folders:
        gaps.append(
            {
                "type": "missing_folders",
                "count": len(missing_folders),
                "severity": "warning",
                "detail": missing_folders,
            }
        )

    # 2. Frontmatter compliance
    md_files = list(_raiz().rglob("*.md"))
    md_files = [f for f in md_files if not any(p.startswith(".") for p in f.parts)]
    total_md = len(md_files)
    compliant_md = 0

    if total_md > 0:
        import re

        for md_path in md_files:
            try:
                text = md_path.read_text(encoding="utf-8", errors="replace")
                fm_match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
                if fm_match:
                    fm_text = fm_match.group(1)
                    if all(f"{field}:" in fm_text for field in FM_REQUIRED_FIELDS):
                        compliant_md += 1
            except Exception:
                pass
        frontmatter_compliance = round(compliant_md / total_md, 2)
    else:
        frontmatter_compliance = 1.0

    if frontmatter_compliance < 0.5:
        gaps.append(
            {
                "type": "low_frontmatter_compliance",
                "count": total_md - compliant_md,
                "severity": "warning",
                "detail": f"{compliant_md}/{total_md} notes have required frontmatter fields",
            }
        )

    # 3. Audit health score (import vault_audit if available)
    audit_score = None
    try:
        import importlib.util

        audit_spec = importlib.util.spec_from_file_location(
            "vault_audit", SCRIPTS_DIR / "vault_audit.py"
        )
        if audit_spec:
            vault_audit_mod = importlib.util.module_from_spec(audit_spec)
            audit_spec.loader.exec_module(vault_audit_mod)
            audit_result = vault_audit_mod.vault_audit()
            audit_score = audit_result.get("healthScore")
    except Exception:
        pass

    compliance_score = round(
        (
            (
                1.0
                if folders_ok
                else max(0, 1 - len(missing_folders) / len(STANDARD_FOLDERS))
            )
            * 0.4
            + frontmatter_compliance * 0.4
            + ((audit_score or 0) / 100) * 0.2
        ),
        2,
    )

    return {
        "applied_version": target_version,
        "compliance_score": compliance_score,
        "folders_ok": folders_ok,
        "missing_folders": missing_folders,
        "frontmatter_compliance": frontmatter_compliance,
        "notes_checked": total_md,
        "audit_score": audit_score,
        "gaps": gaps,
    }


def _pending_migrations(from_version: str, to_version: str) -> List[str]:
    from_idx = _version_index(from_version)
    to_idx = _version_index(to_version)
    if from_idx < 0 or to_idx < 0:
        return []
    return [
        v
        for v in VERSION_ORDER
        if _version_index(v) > from_idx
        and _version_index(v) <= to_idx
        and v in MIGRATIONS
    ]


def _apply_migration(
    version: str, dry_run: bool, fixes_only: bool = False
) -> Dict[str, Any]:
    migration = MIGRATIONS[version]
    folders_created = []
    folders_skipped = []
    fixes_applied = []
    fixes_failed = []

    if not fixes_only:
        for folder in migration.get("add_folders", []):
            folder_path = _raiz() / folder
            if folder_path.exists():
                folders_skipped.append(folder)
            else:
                if not dry_run:
                    folder_path.mkdir(parents=True, exist_ok=True)
                    gitkeep = folder_path / ".gitkeep"
                    gitkeep.touch()
                folders_created.append(folder)

    fixes = migration.get("fixes", [])
    for fix_type in fixes:
        fix_config = FIX_TYPES.get(fix_type)
        if not fix_config:
            continue

        tool_name = fix_config["tool"]
        if dry_run:
            fixes_applied.append(
                {
                    "type": fix_type,
                    "tool": tool_name,
                    "description": fix_config["description"],
                    "action": "dry_run - would execute",
                }
            )
            continue

        # El nombre del script es el de la tool, sin derivaciones. La versión
        # anterior lo reconstruía como `vault_<segunda palabra>.py`, que para
        # `vault_fix_brackets` daba `vault_fix.py` — un archivo inexistente. El
        # fallo quedaba anotado en `standard-version.json` y la migración seguía
        # devolviendo ok, así que el fix nunca se aplicó y nadie lo vio.
        script = SCRIPTS_DIR / f"{tool_name}.py"
        if not script.exists():
            fixes_failed.append(
                {"type": fix_type, "tool": tool_name,
                 "error": f"script no encontrado: {script.name}"}
            )
            continue

        try:
            import subprocess

            result = subprocess.run(
                [sys.executable, script.name],
                cwd=str(SCRIPTS_DIR),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                fixes_applied.append(
                    {
                        "type": fix_type,
                        "tool": tool_name,
                        "description": fix_config["description"],
                        "action": "applied",
                    }
                )
            else:
                fixes_failed.append(
                    {
                        "type": fix_type,
                        "tool": tool_name,
                        "error": result.stderr[:500] if result.stderr else "unknown",
                    }
                )
        except Exception as e:
            fixes_failed.append(
                {"type": fix_type, "tool": tool_name, "error": str(e)[:500]}
            )

    return {
        "version": version,
        "description": migration["description"],
        "folders_created": folders_created,
        "folders_skipped": folders_skipped,
        "notes": migration.get("notes", []),
        "identity_updates": migration.get("update_identity", {}),
        "fixes_applied": fixes_applied,
        "fixes_failed": fixes_failed,
    }


def vault_standard_upgrade(
    from_version: Optional[str] = None,
    to_version: str = CURRENT_VERSION,
    check_only: bool = False,
    init_version: Optional[str] = None,
    agent: str = "claude",
    set_profile: Optional[str] = None,
    validate: bool = False,
    fixes_only: bool = False,
    dry_run: bool = False,
    report_mode: bool = False,
) -> Dict[str, Any]:
    # Handle --set-profile independently
    if set_profile is not None:
        state = _read_version_file()
        state["profile"] = set_profile
        if not state.get("applied_version"):
            state["applied_version"] = CURRENT_VERSION
        _write_version_file(state)
        result: Dict[str, Any] = {
            "ok": True,
            "action": "set_profile",
            "profile": set_profile,
            "path": str(_version_file().relative_to(_raiz())).replace("\\", "/"),
        }
        if validate:
            result["compliance"] = _run_compliance_check(
                state.get("applied_version", CURRENT_VERSION)
            )
        return result

    if init_version:
        data = {
            "applied_version": init_version,
            "applied_at": utcnow(),
            "applied_by": agent,
            "migrations_applied": [],
        }
        _write_version_file(data)

        # Create the 17 base section folders so the container is self-bootstrapping.
        # Without this, --init only writes the version file and the consumer is left
        # with a single 00_System/ folder. The full structure must exist before any
        # vault_write / vault_section_index call can succeed.
        base_folders_created: List[str] = []
        for folder in STANDARD_FOLDERS:
            folder_path = _raiz() / folder
            if not folder_path.exists():
                folder_path.mkdir(parents=True, exist_ok=True)
                base_folders_created.append(folder)
            # Always ensure .gitkeep exists so empty sections survive commits
            gitkeep = folder_path / ".gitkeep"
            if not gitkeep.exists():
                gitkeep.touch()

        # Auto-generate section indexes for every base folder. This makes the vault
        # navigable from the first commit — no manual `for folder in ...; do vault_section_index` loop.
        from vault_section_index import (
            vault_section_index,
        )  # lazy — avoid circular import

        sections_indexed: List[str] = []
        for folder in STANDARD_FOLDERS:
            try:
                res = vault_section_index(folder, include_subdirs=True)
                if res.get("ok"):
                    sections_indexed.append(folder)
            except Exception:
                # index failure must never block init
                pass

        result = {
            "ok": True,
            "action": "init",
            "applied_version": init_version,
            "path": str(_version_file().relative_to(_raiz())).replace("\\", "/"),
            "base_folders_created": base_folders_created,
            "sections_indexed": sections_indexed,
        }
        if validate:
            result["compliance"] = _run_compliance_check(init_version)
        return result

    state = _read_version_file()
    current_applied = from_version or state.get("applied_version") or "v20"

    if to_version == "latest":
        to_version = CURRENT_VERSION

    pending = _pending_migrations(current_applied, to_version)

    if report_mode:
        all_fixes = []
        for v in pending:
            migration = MIGRATIONS.get(v, {})
            fixes = migration.get("fixes", [])
            for fix_type in fixes:
                fix_config = FIX_TYPES.get(fix_type, {})
                all_fixes.append(
                    {
                        "version": v,
                        "type": fix_type,
                        "tool": fix_config.get("tool"),
                        "description": fix_config.get("description"),
                        "auto_apply": fix_config.get("auto_apply", False),
                    }
                )
        result = {
            "ok": True,
            "action": "report",
            "current_version": current_applied,
            "target_version": to_version,
            "pending_migrations": len(pending),
            "available_fixes": all_fixes,
            "fix_types": list(FIX_TYPES.keys()),
        }
        if validate:
            result["compliance"] = _run_compliance_check(current_applied)
        return result

    if not pending:
        # Una versión menor sin migración estructural (v39.0 → v39.1) no tiene
        # nada que aplicar, pero el vault sí tiene algo que declarar: en qué
        # versión está. Sin este sello, `applied_version` se queda en la última
        # versión MAYOR para siempre —`_version_index` compara por mayor— y el
        # vault dice v39.0 mientras corre con las tools de v39.1. Es la misma
        # familia que AP-37: `ok: true` mientras el estado sigue obsoleto.
        # `--check` pregunta; no responde escribiendo. Esta rama comprobaba
        # `dry_run` pero no `check_only`, así que un consumidor que solo quería
        # saber si estaba al día salía sellado en la versión nueva sin haberlo
        # pedido — y el envelope se lo contaba como `action: version_stamped`,
        # que es exactamente lo que no había autorizado.
        sellado = False
        pendiente_de_sellar = (
            current_applied != to_version and to_version == CURRENT_VERSION
        )
        if (not dry_run and not check_only) and pendiente_de_sellar:
            state["applied_version"] = to_version
            state["applied_at"] = utcnow()
            state["applied_by"] = agent
            _write_version_file(state)
            sellado = True
        result = {
            "ok": True,
            "action": "version_stamped" if sellado else "none",
            "message": (
                f"Sin migraciones que aplicar: {current_applied} → {to_version} "
                "no cambia la estructura. Se sella la versión."
                if sellado
                else (
                    # El caso que antes se resolvía escribiendo: hay salto de
                    # versión menor y nadie ha pedido aplicarlo. Se dice, con el
                    # comando exacto, y se deja la decisión donde estaba.
                    f"Salto de versión menor pendiente de sellar: "
                    f"{current_applied} → {to_version}. No cambia la estructura "
                    f"y no se ha escrito nada. Para sellarlo: "
                    f"--to {to_version}"
                    if pendiente_de_sellar
                    else f"Vault is up to date at {current_applied}. No migrations needed."
                )
            ),
            "current_version": to_version if sellado else current_applied,
            "target_version": to_version,
            "version_stamped": sellado,
            # Lo que el consumidor necesita para decidir, y que antes solo podía
            # deducir de que la tool ya se lo hubiera hecho.
            "stamp_pending": pendiente_de_sellar and not sellado,
        }
        if validate:
            result["compliance"] = _run_compliance_check(current_applied)
        return result

    if check_only:
        pending_details = []
        for v in pending:
            m = MIGRATIONS[v]
            pending_details.append(
                {
                    "version": v,
                    "description": m["description"],
                    "folders_to_create": [
                        f
                        for f in m.get("add_folders", [])
                        if not (_raiz() / f).exists()
                    ],
                    "notes": m.get("notes", []),
                }
            )
        result = {
            "ok": True,
            "action": "check",
            "current_version": current_applied,
            "target_version": to_version,
            "pending_count": len(pending),
            "pending_migrations": pending_details,
        }
        if validate:
            result["compliance"] = _run_compliance_check(current_applied)
        return result

    applied_list = []
    all_folders_created = []
    all_fixes_applied = []
    all_fixes_failed = []

    for version in pending:
        migration_result = _apply_migration(
            version, dry_run=dry_run, fixes_only=fixes_only
        )
        applied_list.append(migration_result)
        all_folders_created.extend(migration_result.get("folders_created", []))
        all_fixes_applied.extend(migration_result.get("fixes_applied", []))
        all_fixes_failed.extend(migration_result.get("fixes_failed", []))

    if dry_run:
        return {
            "ok": True,
            "action": "dry_run",
            "current_version": current_applied,
            "target_version": to_version,
            "would_apply": applied_list,
            "would_create_folders": all_folders_created,
            "would_apply_fixes": all_fixes_applied,
        }

    state["applied_version"] = to_version
    state["applied_at"] = utcnow()
    state["applied_by"] = agent
    already = state.get("migrations_applied", [])
    already.extend(pending)
    state["migrations_applied"] = already
    # Se escriben siempre, incluso vacías. Con el `if` anterior, un fallo
    # resuelto quedaba fijado en el registro para siempre: la migración
    # siguiente no lo sobrescribía porque no tenía nada que escribir, y el
    # vault seguía declarando un error que ya no existía.
    state["fixes_applied"] = all_fixes_applied
    state["fixes_failed"] = all_fixes_failed
    _write_version_file(state)

    result = {
        "ok": True,
        "action": "upgraded" if not fixes_only else "fixes_applied",
        "from": current_applied,
        "to": to_version,
        "migrations_applied": applied_list,
        "folders_created": all_folders_created,
        "fixes_applied": all_fixes_applied,
        "fixes_failed": all_fixes_failed,
        "version_file": str(_version_file().relative_to(_raiz())).replace("\\", "/"),
    }
    if validate:
        result["compliance"] = _run_compliance_check(to_version)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Standard Upgrade -- detect and apply version migrations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Solo reportar migraciones pendientes (no aplica nada)
  python vault_standard_upgrade.py --check

  # Actualizar desde v20 hasta v25
  python vault_standard_upgrade.py --from v20 --to v25

  # Actualizar al ultimo version disponible
  python vault_standard_upgrade.py --to latest

  # Inicializar el archivo de version (vault nuevo)
  python vault_standard_upgrade.py --init v25

  # Modo check desde una version especifica
  python vault_standard_upgrade.py --check --from v20

 Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Sin --from, lee la version actual de 00_System/standard-version.json
  - --check no modifica nada, solo reporta
  - --init crea 00_System/standard-version.json si no existe
  - --fixes-only solo ejecuta fixes sin aplicar migraciones
  - --dry-run simula todo sin aplicar cambios
  - --report genera reporte de fixes disponibles
  - Versiones disponibles: v19 a v34
""",
    )
    parser.add_argument(
        "--from",
        dest="from_version",
        help="Current vault version (reads standard-version.json if omitted)",
    )
    parser.add_argument(
        "--to",
        dest="to_version",
        default=CURRENT_VERSION,
        help=f"Target version (default: {CURRENT_VERSION}, or 'latest')",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report pending migrations without applying them",
    )
    parser.add_argument(
        "--init",
        dest="init_version",
        help="Initialize standard-version.json with given version",
    )
    parser.add_argument(
        "--agent", default="claude", help="Agent name for audit trail (default: claude)"
    )
    parser.add_argument(
        "--set-profile",
        dest="set_profile",
        choices=_opciones("detalle"),
        help="Set the tool profile in standard-version.json (minimal=10, standard=30, full=61)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run compliance check: folders, frontmatter, health score (non-blocking)",
    )
    parser.add_argument(
        "--fixes-only",
        action="store_true",
        help="Only execute fixes without applying migrations",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate everything without applying any changes",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate health report without making changes",
    )

    args = parser.parse_args()

    result = vault_standard_upgrade(
        from_version=args.from_version,
        to_version=args.to_version,
        check_only=args.check,
        init_version=args.init_version,
        agent=args.agent,
        set_profile=args.set_profile,
        validate=args.validate,
        fixes_only=args.fixes_only,
        dry_run=args.dry_run,
        report_mode=args.report,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_standard_upgrade"))

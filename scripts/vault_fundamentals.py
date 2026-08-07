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
from vault_io import atomic_write_json, atomic_write_text
SCRIPTS_DIR = Path(__file__).parent

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


# ──────────────────────────────────────────────────────────────────────────────
# Marco de datos y gobernanza (v39) — registros canónicos complementarios
#
# Los 8 fundamentos responden "¿el dato es bueno?". Estos cuatro registros
# responden las otras preguntas del marco: sobre qué pilar se apoyan (CIA),
# qué tan reutilizable es el activo (FAIR), qué escala maneja (V's) y bajo
# qué normas se alinea (ISO). Mismo shape que FUNDAMENTALS: id estable,
# descripción, mecanismo real y tools que lo implementan — nunca teoría suelta.
# ──────────────────────────────────────────────────────────────────────────────

CIA_TRIAD: List[Dict[str, Any]] = [
    {
        "id": "CIA-C",
        "name": "CONFIDENCIALIDAD",
        "english": "confidentiality",
        "description": "El dato solo es accesible para quien debe verlo; el vault marca su nivel de exposición y evita filtrar secretos al grafo.",
        "frontmatter_field": "cia_sensitivity",
        "values": ["public", "internal", "restricted"],
        "default": "internal",
        "effect": "restricted activa revisión en vault_security_scan; sensitive:true en 02_Observability/envs impide volcar el valor del secreto, solo su proveedor y referencia.",
        "tools": [
            "vault_security_scan",
            "vault_env_save",
            "vault_privacy_save",
            "vault_validate",
            "vault_quality_check",
        ],
    },
    {
        "id": "CIA-I",
        "name": "INTEGRIDAD",
        "english": "integrity",
        "description": "El dato no se corrompe ni se altera de forma no rastreable entre escritura y lectura.",
        "frontmatter_field": "cia_integrity",
        "values": ["critical", "high", "medium", "low"],
        "default": "medium",
        "effect": "critical|high endurece el umbral de actualidad de 30d a 15d y penaliza 5 pts (vs 1 pt) en el health score; pondera stale_risk en vault_impact y selecciona la estrategia critical-path en vault_propagate.",
        "tools": [
            "vault_quality_check",
            "vault_audit",
            "vault_impact",
            "vault_propagate",
            "vault_backup",
            "vault_validate",
        ],
    },
    {
        "id": "CIA-A",
        "name": "DISPONIBILIDAD",
        "english": "availability",
        "description": "El dato se puede recuperar cuando se necesita, incluso tras un borrado o una migración fallida.",
        "frontmatter_field": "cia_availability",
        "values": ["high", "medium", "low"],
        "default": "medium",
        "effect": "Respaldado por .history/ en cada escritura, backups con manifiesto Merkle en VAULT_ROOT/vault-backups/ (AP-36) y rollback quirúrgico de migración (AP-10).",
        "tools": [
            "vault_backup",
            "vault_restore",
            "vault_backup_list",
            "vault_migrate_rollback",
            "vault_diff",
            "vault_validate",
        ],
    },
]


FAIR_PRINCIPLES: List[Dict[str, Any]] = [
    {
        "id": "FAIR-F",
        "name": "FINDABLE",
        "spanish": "LOCALIZABLE",
        "description": "Cada nota tiene identificador único y persistente, y es descubrible sin conocer su ruta.",
        "mechanism": "Campo id obligatorio (F1), search-index.json con scoring título×4, índices de sección auto-generados e índice maestro en 99_Index/.",
        "metric": "cobertura de id + notas huérfanas (orphans) en vault_audit",
        "tools": [
            "vault_search",
            "vault_reindex",
            "vault_section_index",
            "vault_master_index",
            "vault_list",
        ],
    },
    {
        "id": "FAIR-A",
        "name": "ACCESSIBLE",
        "spanish": "ACCESIBLE",
        "description": "El dato se lee sin runtime propietario, sin base de datos y sin la herramienta que lo creó.",
        "mechanism": "Markdown plano + YAML en el sistema de archivos. Abre en cualquier editor, versiona en git, se lee sin Obsidian instalado. Las tools son una conveniencia, no un requisito de lectura.",
        "metric": "cero dependencias de lectura — todo artefacto es .md o .json",
        "tools": ["vault_read", "vault_knowledge_get", "vault_project_overview"],
    },
    {
        "id": "FAIR-I",
        "name": "INTEROPERABLE",
        "spanish": "INTEROPERABLE",
        "description": "El dato usa vocabularios y formatos compartidos, y se conecta con otros datos del mismo dominio.",
        "mechanism": "Frontmatter YAML con vocabulario canónico (type, status vía STATUS_VOCAB, tags), wiki-links [[nota]] como aristas del grafo, Mermaid para diagramas, graph.json como representación explícita, MCP como protocolo de consumo.",
        "metric": "broken links = 0 · consistencia type↔carpeta (F4)",
        "tools": [
            "vault_graph",
            "vault_relation_add",
            "vault_diagram_save",
            "vault_norms",
            "vault_mcp_catalog",
        ],
    },
    {
        "id": "FAIR-R",
        "name": "REUSABLE",
        "spanish": "REUTILIZABLE",
        "description": "El dato trae su procedencia y licencia, de modo que otro agente o persona pueda confiar en él y reutilizarlo.",
        "mechanism": "Cadena de procedencia PAT-5 (agent:, createdAt, updatedAt, norm_refs), historial completo en .history/, change-log append-only y LICENSE del repositorio.",
        "metric": "cobertura del campo agent (F7) + entradas de change-log (F8)",
        "tools": [
            "vault_change_log",
            "vault_diff",
            "vault_timeline",
            "vault_delta",
            "vault_code_tag",
        ],
    },
]


BIGDATA_VS: List[Dict[str, Any]] = [
    {
        "id": "V1",
        "name": "VOLUMEN",
        "english": "volume",
        "description": "Cuánto conocimiento acumula el vault sin degradar la navegación.",
        "metric": "total de notas y tamaño del grafo",
        "artifact": "00_System/graph.json · vault_audit.stats",
        "control": "AP-23 (techo de complejidad por nota) e índices por sección evitan que el crecimiento rompa la búsqueda.",
        "tools": ["vault_audit", "vault_graph", "vault_list"],
    },
    {
        "id": "V2",
        "name": "VELOCIDAD",
        "english": "velocity",
        "description": "A qué ritmo cambia el conocimiento entre sesiones.",
        "metric": "cambios por sesión y por ventana temporal",
        "artifact": "00_System/.change-log.json · session-delta",
        "control": "SP-03 exige snapshot antes de operaciones masivas; vault_impact propaga el cambio a los nodos dependientes.",
        "tools": ["vault_change_log", "vault_delta", "vault_impact", "vault_timeline"],
    },
    {
        "id": "V3",
        "name": "VARIEDAD",
        "english": "variety",
        "description": "Cuántas naturalezas distintas de conocimiento conviven bajo el mismo esquema.",
        "metric": "18 secciones canónicas × vocabulario del campo type",
        "artifact": "vault_registry.SECTIONS",
        "control": "CN-02 restringe los destinos a secciones numeradas; F4 (exactitud) verifica que type coincida con la carpeta.",
        "tools": ["vault_write", "vault_validate", "vault_norms", "vault_registry"],
    },
    {
        "id": "V4",
        "name": "VERACIDAD",
        "english": "veracity",
        "description": "Cuánto se puede confiar en lo que el vault afirma. La V que más importa a un agente LLM.",
        "metric": "overall_dq_score (0.0–1.0) y notas bajo umbral 0.7",
        "artifact": "00_System/quality-index.json · vault_audit.dqHealth",
        "control": "AP-01 (documentación alucinada), AP-04 (features aspiracionales), AP-11 (skeleton files) y el content gate de vault_write.",
        "tools": ["vault_quality_check", "vault_audit", "vault_drift_detect", "vault_validate"],
    },
    {
        "id": "V5",
        "name": "VALOR",
        "english": "value",
        "description": "Cuánto del conocimiento almacenado se convierte en decisión útil para el agente.",
        "metric": "health score (0–100) y nextActions pendientes",
        "artifact": "vault_audit.score · vault_audit.nextActions",
        "control": "El audit deja de ser diagnóstico y emite la lista ejecutable de comandos para recuperar 100/100.",
        "tools": ["vault_audit", "vault_project_overview", "vault_onboard"],
    },
    {
        "id": "V6",
        "name": "VARIABILIDAD",
        "english": "variability",
        "description": "Cuánto deriva el significado de una nota respecto al código o la realidad que describe.",
        "metric": "drift detectado entre documentación y fuente",
        "artifact": "vault_drift_detect · @vault: tags en código",
        "control": "AP-08 (documentación anclada a versiones obsoletas) y trazabilidad bidireccional código↔vault.",
        "tools": ["vault_drift_detect", "vault_code_sync", "vault_code_tag"],
    },
]


ISO_COVERAGE: List[Dict[str, Any]] = [
    {
        "id": "ISO-25010",
        "norm": "ISO/IEC 25010:2023",
        "title": "Systems and software quality models",
        "clause": "Modelo de calidad de producto",
        "implemented_by": "Scoring multidimensional de calidad y no conformidades",
        "tools": ["vault_quality_check", "vault_ncr_save"],
    },
    {
        "id": "ISO-42001",
        "norm": "ISO/IEC 42001:2023",
        "title": "Artificial intelligence management system",
        "clause": "Gobernanza de decisiones asistidas por IA",
        "implemented_by": "16_AI_Governance/ — registro de decisiones de IA con responsable y alcance",
        "tools": ["vault_ai_decision"],
    },
    {
        "id": "ISO-29148",
        "norm": "ISO/IEC/IEEE 29148:2018",
        "title": "Requirements engineering",
        "clause": "Especificación y trazabilidad de requerimientos",
        "implemented_by": "14_Requirements/ — requerimientos con criterios de aceptación",
        "tools": ["vault_requirement_save"],
    },
    {
        "id": "ISO-29119",
        "norm": "ISO/IEC/IEEE 29119-3:2021",
        "title": "Software testing — Test documentation",
        "clause": "Documentación de pruebas",
        "implemented_by": "15_Tests/ — casos de prueba enlazados a requerimientos",
        "tools": ["vault_test_save", "vault_test_runner"],
    },
    {
        "id": "ISO-20000",
        "norm": "ISO/IEC 20000-1:2018",
        "title": "Service management system",
        "clause": "Gestión de incidentes y niveles de servicio",
        "implemented_by": "02_Observability/incidents/ y SLOs de producción",
        "tools": ["vault_incident_save", "vault_slo_save"],
    },
    {
        "id": "ISO-22301",
        "norm": "ISO 22301:2019",
        "title": "Business continuity management",
        "clause": "Continuidad y recuperación",
        "implemented_by": "Backups con manifiesto Merkle, restore verificable y runbooks de rollback",
        "tools": ["vault_backup", "vault_restore", "vault_runbook_save"],
    },
    {
        "id": "ISO-12207",
        "norm": "ISO/IEC/IEEE 12207:2017",
        "title": "Software life cycle processes",
        "clause": "Procesos de release y entornos",
        "implemented_by": "Registro de releases y matriz de entornos",
        "tools": ["vault_release_save", "vault_env_matrix"],
    },
    {
        "id": "ISO-31000",
        "norm": "ISO 31000:2018",
        "title": "Risk management",
        "clause": "Identificación, evaluación y tratamiento de riesgos",
        "implemented_by": "02_Observability/risks/ con score likelihood × impact",
        "tools": ["vault_risk_save"],
    },
    {
        "id": "ISO-27001",
        "norm": "ISO/IEC 27001:2022",
        "title": "Information security management",
        "clause": "Controles de seguridad de la información",
        "implemented_by": "Escaneo de secretos, clasificación cia_sensitivity y directivas DS-",
        "tools": ["vault_security_scan", "vault_env_save"],
    },
    {
        "id": "ISO-27005",
        "norm": "ISO/IEC 27005:2022",
        "title": "Information security risk management",
        "clause": "Riesgo de seguridad de la información",
        "implemented_by": "Asignación automática de CIA por tipo y nivel de impacto del riesgo",
        "tools": ["vault_risk_save"],
    },
    {
        "id": "ISO-27701",
        "norm": "ISO/IEC 27701:2019",
        "title": "Privacy information management",
        "clause": "Tratamiento de datos personales (con GDPR Art. 30 y 35)",
        "implemented_by": "09_Infrastructure/privacy/ con detección automática de DPIA",
        "tools": ["vault_privacy_save"],
    },
    {
        "id": "ISO-9001",
        "norm": "ISO 9001:2015",
        "title": "Quality management systems",
        "clause": "§9.2 Auditoría interna · §10.2 No conformidad y acción correctiva",
        "implemented_by": "NCR con ID auto-generado, 5-Whys y verificación de eficacia",
        "tools": ["vault_ncr_save", "vault_audit"],
    },
    {
        "id": "ISO-8601",
        "norm": "ISO 8601",
        "title": "Date and time representation",
        "clause": "Formato de marcas temporales",
        "implemented_by": "Todo timestamp del vault es UTC en formato YYYY-MM-DDTHH:mm:ss.sssZ (AP-13)",
        "tools": ["vault_write", "vault_validate", "vault_lib"],
    },
]


#: Registros del marco, expuestos como mapa para exportadores y guards.
FRAMEWORK_REGISTRIES: Dict[str, List[Dict[str, Any]]] = {
    "cia_triad": CIA_TRIAD,
    "fundamentals": FUNDAMENTALS,
    "fair_principles": FAIR_PRINCIPLES,
    "bigdata_vs": BIGDATA_VS,
    "iso_coverage": ISO_COVERAGE,
}


def cia_valores(campo: str) -> set:
    """Valores admitidos por un campo CIA, según `CIA_TRIAD`.

    El vocabulario estaba escrito a mano dos veces más —en `_check_fundamentals`
    aquí mismo y como constantes de módulo en `vault_validate`— pese a que el
    registro ya lo declara en `values`. Las tres copias coinciden hoy; la que se
    quede atrás cuando el registro cambie reprobará notas válidas o aprobará las
    que no lo son, y en ninguno de los dos casos habrá un test que lo note. La
    asimetría es real y del registro: DISPONIBILIDAD no admite `critical`.
    """
    for c in CIA_TRIAD:
        if c["frontmatter_field"] == campo:
            return set(c["values"])
    return set()


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
    except Exception:
        return False
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Per-note verification
# ──────────────────────────────────────────────────────────────────────────────


def check_note(rel_path: str) -> Dict[str, Any]:
    """Verify all 8 fundamentals for a single note. Returns pass/fail per principle."""
    note_path = _raiz() / rel_path
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
    {"concept": "Confidencialidad (CIA-C)", "metric": "hallazgos de secretos expuestos", "threshold": "0", "tool": "vault_security_scan", "artifact": "02_Observability/security/", "enforcement": "guard+audit"},
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

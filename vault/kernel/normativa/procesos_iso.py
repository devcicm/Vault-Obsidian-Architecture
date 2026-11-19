"""Process registries for the life-cycle, service and QMS standards.

Registry first (AGENTS.md rule 3): what ISO/IEC/IEEE 12207, ISO/IEC 33020,
ISO/IEC 20000-1, ISO 22301 and ISO/IEC/IEEE 90003 ask, mapped to the tool that
records evidence for it, or declared ``fuera``/``hueco`` with the reason. The
registry is alignment, not certification: it says which tool keeps the record,
never that the process is performed well.

Each mapped tool must exist as ``scripts/<tool>.py`` (``comprobar_registros``);
each entry without tools must carry its reason. The data is a kernel leaf: it
imports nothing outside ``typing``/``pathlib``/``re`` so any context can read it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ── ISO/IEC/IEEE 12207:2017 — software life cycle processes (clause 6) ──────

#: Process groups of 12207:2017 §6, in the order of the standard.
GRUPOS_12207: Dict[str, str] = {
    "acuerdo": "Agreement processes (§6.1)",
    "habilitacion": "Organizational project-enabling processes (§6.2)",
    "gestion_tecnica": "Technical management processes (§6.3)",
    "tecnico": "Technical processes (§6.4)",
}

_ORGANIZACION = "es un acto de la organización; el vault no tiene un registro que lo evidencie"

#: Every process of 12207:2017 §6 with the tools that record its evidence, or
#: ``fuera`` with the reason it is out of the product's reach.
PROCESOS_12207: Tuple[Dict[str, Any], ...] = (
    {"id": "6.1.1", "grupo": "acuerdo", "proceso": "Acquisition", "tools": [],
     "fuera": "La adquisición a un proveedor es un contrato de la organización: " + _ORGANIZACION + "."},
    {"id": "6.1.2", "grupo": "acuerdo", "proceso": "Supply", "tools": [],
     "fuera": "El suministro a un cliente es un contrato de la organización: " + _ORGANIZACION + "."},
    {"id": "6.2.1", "grupo": "habilitacion", "proceso": "Life cycle model management", "tools": [],
     "fuera": "Definir la política y el modelo de ciclo de vida " + _ORGANIZACION + "."},
    {"id": "6.2.2", "grupo": "habilitacion", "proceso": "Infrastructure management",
     "tools": ["vault_env_save", "vault_env_matrix"]},
    {"id": "6.2.3", "grupo": "habilitacion", "proceso": "Portfolio management", "tools": [],
     "fuera": "Priorizar y financiar proyectos " + _ORGANIZACION + "."},
    {"id": "6.2.4", "grupo": "habilitacion", "proceso": "Human resource management", "tools": [],
     "fuera": "Competencias y personal " + _ORGANIZACION + "."},
    {"id": "6.2.5", "grupo": "habilitacion", "proceso": "Quality management",
     "tools": ["vault_ncr_save", "vault_quality_check"]},
    {"id": "6.2.6", "grupo": "habilitacion", "proceso": "Knowledge management",
     "tools": ["vault_knowledge_save", "vault_pattern_save"]},
    {"id": "6.3.1", "grupo": "gestion_tecnica", "proceso": "Project planning", "tools": [],
     "fuera": "El plan del proyecto (alcance, calendario, recursos) " + _ORGANIZACION + "."},
    {"id": "6.3.2", "grupo": "gestion_tecnica", "proceso": "Project assessment and control",
     "tools": ["vault_project_status", "vault_audit"]},
    {"id": "6.3.3", "grupo": "gestion_tecnica", "proceso": "Decision management",
     "tools": ["vault_write", "vault_ai_decision"]},
    {"id": "6.3.4", "grupo": "gestion_tecnica", "proceso": "Risk management",
     "tools": ["vault_risk_save"]},
    {"id": "6.3.5", "grupo": "gestion_tecnica", "proceso": "Configuration management",
     "tools": ["vault_release_save", "vault_drift_detect", "vault_undo"]},
    {"id": "6.3.6", "grupo": "gestion_tecnica", "proceso": "Information management",
     "tools": ["vault_write", "vault_contrato_nota", "vault_supersede"]},
    {"id": "6.3.7", "grupo": "gestion_tecnica", "proceso": "Measurement",
     "tools": ["vault_quality_check", "vault_qa_save"]},
    {"id": "6.3.8", "grupo": "gestion_tecnica", "proceso": "Quality assurance",
     "tools": ["vault_audit", "vault_ncr_save"]},
    {"id": "6.4.1", "grupo": "tecnico", "proceso": "Business or mission analysis", "tools": [],
     "fuera": "El análisis de negocio o de misión " + _ORGANIZACION + "."},
    {"id": "6.4.2", "grupo": "tecnico", "proceso": "Stakeholder needs and requirements definition",
     "tools": ["vault_requirement_save"]},
    {"id": "6.4.3", "grupo": "tecnico", "proceso": "System/software requirements definition",
     "tools": ["vault_requirement_save"]},
    {"id": "6.4.4", "grupo": "tecnico", "proceso": "Architecture definition",
     "tools": ["vault_write", "vault_arquitectura_en", "vault_diagram_save"]},
    {"id": "6.4.5", "grupo": "tecnico", "proceso": "Design definition",
     "tools": ["vault_pattern_save", "vault_diagram_save"]},
    {"id": "6.4.6", "grupo": "tecnico", "proceso": "System analysis", "tools": [],
     "fuera": "Los análisis de alternativas y modelos de ingeniería los hace el equipo; "
              "el vault guarda su conclusión como decisión (6.3.3), no el análisis."},
    {"id": "6.4.7", "grupo": "tecnico", "proceso": "Implementation",
     "tools": ["vault_code_map", "vault_code_sync"]},
    {"id": "6.4.8", "grupo": "tecnico", "proceso": "Integration",
     "tools": ["vault_test_save"]},
    {"id": "6.4.9", "grupo": "tecnico", "proceso": "Verification",
     "tools": ["vault_test_save", "vault_test_runner"]},
    {"id": "6.4.10", "grupo": "tecnico", "proceso": "Transition",
     "tools": ["vault_release_save", "vault_env_matrix"]},
    {"id": "6.4.11", "grupo": "tecnico", "proceso": "Validation",
     "tools": ["vault_test_save", "vault_qa_save"]},
    {"id": "6.4.12", "grupo": "tecnico", "proceso": "Operation",
     "tools": ["vault_runbook_save", "vault_slo_save", "vault_incident_save"]},
    {"id": "6.4.13", "grupo": "tecnico", "proceso": "Maintenance",
     "tools": ["vault_bug_save", "vault_incident_save"]},
    {"id": "6.4.14", "grupo": "tecnico", "proceso": "Disposal", "tools": [],
     "fuera": "Retirar un sistema " + _ORGANIZACION + "; el estándar no destruye registros "
              "y lo reemplazado se anota con `superseded_by:`."},
)

# ── ISO/IEC 33020:2019 — process capability (successor of ISO/IEC 15504) ───

#: Capability levels of the ISO/IEC 33020 measurement framework.
NIVELES_CAPACIDAD: Tuple[Tuple[int, str, str], ...] = (
    (0, "incompleto", "incomplete"),
    (1, "realizado", "performed"),
    (2, "gestionado", "managed"),
    (3, "establecido", "established"),
    (4, "predecible", "predictable"),
    (5, "innovador", "innovating"),
)

#: Frontmatter field an assessment record declares: ``{process id: level}``.
CAMPO_CAPACIDAD = "process_capability"

#: Frontmatter fields that identify who assessed and when (optional, reported).
CAMPOS_EVALUACION = ("assessment_method", "assessor", "assessed_at")


def nombre_de_nivel(nivel: int) -> Optional[str]:
    """English name of a 33020 capability level, or None if out of range."""
    for n, _es, en in NIVELES_CAPACIDAD:
        if n == nivel:
            return en
    return None


def validar_capacidad(valor: Any) -> List[str]:
    """Problems of a ``process_capability`` value; empty when it is valid.

    Each key must be a 12207 process id of ``PROCESOS_12207`` and each value
    an integer level 0-5 (``bool`` is not a level).
    """
    if not isinstance(valor, dict) or not valor:
        return [f"{CAMPO_CAPACIDAD} must be a non-empty mapping of 12207 process id to level 0-5"]
    ids = {p["id"] for p in PROCESOS_12207}
    problemas: List[str] = []
    for proceso, nivel in valor.items():
        if str(proceso) not in ids:
            problemas.append(f"unknown 12207 process: {proceso}")
        if isinstance(nivel, bool) or not isinstance(nivel, int) or nombre_de_nivel(nivel) is None:
            problemas.append(f"invalid capability level for {proceso}: {nivel!r} (expected 0-5)")
    return problemas


# ── ISO/IEC 20000-1:2018 — service management system (clause 8) ────────────

#: The operational clauses of 20000-1:2018 §8 with their tools or the gap.
SERVICIO_20000: Tuple[Dict[str, Any], ...] = (
    {"clausula": "§8.2.4", "titulo": "Service catalogue management", "tools": [],
     "hueco": "No hay registro de catálogo de servicios: los servicios aparecen como `service` de los SLO, sin descripción ni dependencias."},
    {"clausula": "§8.3.3", "titulo": "Service level management", "tools": ["vault_slo_save"]},
    {"clausula": "§8.4.3", "titulo": "Capacity management",
     "tools": ["vault_slo_save"],
     "detalle": "SLO de tipo `throughput` (capacidad) y `saturation` (utilización de recursos)."},
    {"clausula": "§8.5.1", "titulo": "Change management", "tools": ["vault_release_save"],
     "detalle": "Cada release es el registro del cambio: cambios incluidos, despliegue, rollback y "
                "`--change_class` (standard, normal, emergency)."},
    {"clausula": "§8.5.3", "titulo": "Release and deployment management", "tools": ["vault_release_save"]},
    {"clausula": "§8.6.1", "titulo": "Incident management", "tools": ["vault_incident_save"]},
    {"clausula": "§8.6.3", "titulo": "Problem management", "tools": ["vault_bug_save"]},
    {"clausula": "§8.7.1", "titulo": "Service availability management",
     "tools": ["vault_slo_save"]},
    {"clausula": "§8.7.2", "titulo": "Service continuity management",
     "tools": ["vault_backup", "vault_restore", "vault_runbook_save"]},
    {"clausula": "§8.3.2", "titulo": "Business relationship management", "tools": [],
     "hueco": "La relación con clientes y su satisfacción " + _ORGANIZACION + "."},
    {"clausula": "§8.3.4", "titulo": "Supplier management", "tools": [],
     "hueco": "Los contratos con proveedores " + _ORGANIZACION + "."},
)

#: Change classes a change record may declare (20000-1 §8.5.1.2).
CLASES_DE_CAMBIO: Tuple[str, ...] = ("standard", "normal", "emergency")

# ── ISO 22301:2019 §8.2.2 — business impact analysis ───────────────────────

#: Fields of a BIA record and what they mean. ``critical_function`` is required.
CAMPOS_BIA: Dict[str, str] = {
    "critical_function": "actividad que soporta un producto o servicio prioritario",
    "impact": "impacto de su interrupción a lo largo del tiempo",
    "rto": "recovery time objective: plazo para reanudarla",
    "rpo": "recovery point objective: pérdida de datos aceptable",
    "mtpd": "maximum tolerable period of disruption",
}

_UNIDADES_MIN = {"min": 1, "m": 1, "h": 60, "d": 1440, "w": 10080}
_DURACION = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(min|m|h|d|w)\s*$", re.I)


def duracion_en_minutos(texto: Any) -> Optional[float]:
    """Minutes of a duration written as ``<n><min|m|h|d|w>``; None otherwise."""
    m = _DURACION.match(str(texto or ""))
    if not m:
        return None
    return float(m.group(1)) * _UNIDADES_MIN[m.group(2).lower()]


def validar_bia(bia: Any) -> List[str]:
    """Problems of a BIA record; empty when it is valid.

    Only the fields of ``CAMPOS_BIA`` are accepted, ``critical_function`` is
    required, durations use ``<n><min|m|h|d|w>`` and the RTO cannot exceed the
    MTPD (22301 §8.2.2: the RTO is set within the maximum tolerable period).
    """
    if not isinstance(bia, dict):
        return ["the BIA must be a JSON object"]
    problemas: List[str] = []
    extra = sorted(set(bia) - set(CAMPOS_BIA))
    if extra:
        problemas.append(f"unknown BIA fields: {extra} (allowed: {sorted(CAMPOS_BIA)})")
    if not str(bia.get("critical_function") or "").strip():
        problemas.append("critical_function is required")
    for campo in ("rto", "rpo", "mtpd"):
        if bia.get(campo) not in (None, "") and duracion_en_minutos(bia[campo]) is None:
            problemas.append(f"{campo} must be a duration like 4h, 30min, 2d: {bia[campo]!r}")
    rto, mtpd = duracion_en_minutos(bia.get("rto")), duracion_en_minutos(bia.get("mtpd"))
    if rto is not None and mtpd is not None and rto > mtpd:
        problemas.append(f"rto ({bia['rto']}) exceeds mtpd ({bia['mtpd']})")
    return problemas


# ── ISO/IEC/IEEE 90003:2018 — ISO 9001:2015 applied to software ─────────────

#: ISO 9001 clauses as 90003 applies them to software, with their executors or
#: the declared gap. Organizational clauses stay gaps (S4).
CLAUSULAS_90003: Tuple[Dict[str, Any], ...] = (
    {"clausula": "§5", "titulo": "Leadership", "tools": [],
     "hueco": "Liderazgo, política de calidad y roles " + _ORGANIZACION + "."},
    {"clausula": "§6.1", "titulo": "Actions to address risks and opportunities",
     "tools": ["vault_risk_save"]},
    {"clausula": "§7.2", "titulo": "Competence", "tools": [],
     "hueco": "La competencia del personal " + _ORGANIZACION + "."},
    {"clausula": "§7.5", "titulo": "Documented information",
     "tools": ["vault_write", "vault_contrato_nota", "vault_supersede"]},
    {"clausula": "§8.1", "titulo": "Operational planning and control",
     "tools": ["vault_release_save", "vault_runbook_save"]},
    {"clausula": "§8.2", "titulo": "Requirements for products and services",
     "tools": ["vault_requirement_save"]},
    {"clausula": "§8.3", "titulo": "Design and development",
     "tools": ["vault_write", "vault_arquitectura_en", "vault_diagram_save", "vault_test_save"]},
    {"clausula": "§8.4", "titulo": "Control of externally provided processes, products and services",
     "tools": [], "hueco": "La evaluación de proveedores " + _ORGANIZACION + "."},
    {"clausula": "§8.5.2", "titulo": "Identification and traceability (configuration management)",
     "tools": ["vault_drift_detect", "vault_undo", "vault_release_save"]},
    {"clausula": "§8.5.5", "titulo": "Post-delivery activities (maintenance)",
     "tools": ["vault_bug_save", "vault_incident_save"]},
    {"clausula": "§8.6", "titulo": "Release of products and services",
     "tools": ["vault_release_save", "vault_test_runner"]},
    {"clausula": "§8.7", "titulo": "Control of nonconforming outputs",
     "tools": ["vault_ncr_save", "vault_bug_save"]},
    {"clausula": "§9.1", "titulo": "Monitoring, measurement, analysis and evaluation",
     "tools": ["vault_quality_check", "vault_qa_save", "vault_slo_save"]},
    {"clausula": "§9.2", "titulo": "Internal audit", "tools": ["vault_audit"]},
    {"clausula": "§9.3", "titulo": "Management review", "tools": [],
     "hueco": "La revisión por la dirección " + _ORGANIZACION + "."},
    {"clausula": "§10.2", "titulo": "Nonconformity and corrective action",
     "tools": ["vault_ncr_save"]},
)

#: Registries checked by ``comprobar_registros``: name → (entries, key, gap field).
REGISTROS: Dict[str, Tuple[Tuple[Dict[str, Any], ...], str, str]] = {
    "procesos_12207": (PROCESOS_12207, "id", "fuera"),
    "servicio_20000": (SERVICIO_20000, "clausula", "hueco"),
    "clausulas_90003": (CLAUSULAS_90003, "clausula", "hueco"),
}


def comprobar_registros(scripts_dir: Path) -> Dict[str, Any]:
    """Every mapped tool exists and every entry without tools gives its reason."""
    scripts_dir = Path(scripts_dir)
    inexistentes: List[Dict[str, str]] = []
    sin_motivo: List[Dict[str, str]] = []
    for nombre, (entradas, clave, hueco) in REGISTROS.items():
        for e in entradas:
            for t in e["tools"]:
                if not (scripts_dir / f"{t}.py").is_file():
                    inexistentes.append({"registro": nombre, "id": e[clave], "tool": t})
            if not e["tools"] and not str(e.get(hueco) or "").strip():
                sin_motivo.append({"registro": nombre, "id": e[clave]})
    return {"ok": not inexistentes and not sin_motivo,
            "tools_inexistentes": inexistentes, "sin_motivo": sin_motivo}


def _cobertura(entradas: Iterable[Dict[str, Any]], clave: str) -> Dict[str, Any]:
    filas = [
        {clave: e[clave], **{k: v for k, v in e.items() if k != clave}}
        for e in entradas
    ]
    con = [f for f in filas if f["tools"]]
    return {
        "total": len(filas),
        "con_registro": len(con),
        "sin_registro": len(filas) - len(con),
        "entradas": filas,
    }


def informe(capacidad: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Read-only coverage report of the three registries.

    ``capacidad`` maps a 12207 process id to its latest assessed level record
    (``{"nivel": int, "nombre": str, "fuente": str, ...}``); each 12207 row
    carries it under ``capacidad`` (None when no assessment names the process).
    """
    capacidad = capacidad or {}
    procesos = _cobertura(PROCESOS_12207, "id")
    for fila in procesos["entradas"]:
        fila["capacidad"] = capacidad.get(fila["id"])
    procesos["por_grupo"] = {
        g: {"total": sum(1 for p in PROCESOS_12207 if p["grupo"] == g),
            "con_registro": sum(1 for p in PROCESOS_12207 if p["grupo"] == g and p["tools"])}
        for g in GRUPOS_12207
    }
    procesos["evaluados"] = sum(1 for f in procesos["entradas"] if f["capacidad"])
    return {
        "procesos_12207": procesos,
        "servicio_20000": _cobertura(SERVICIO_20000, "clausula"),
        "clausulas_90003": _cobertura(CLAUSULAS_90003, "clausula"),
        "niveles_capacidad": [{"nivel": n, "nombre": en} for n, _es, en in NIVELES_CAPACIDAD],
    }

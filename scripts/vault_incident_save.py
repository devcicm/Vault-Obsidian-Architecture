#!/usr/bin/env python3
"""
vault_incident_save.py — Registro de incidentes y post-mortems de producción.

Estándar aplicado:
  ISO 20000-1:2018 §8.6 — Incident management (clasificación P1–P4, ciclo de vida)
  ISO 22301:2019 §8.4   — Business continuity (RTO, RPO, BCDR)
  ISO/IEC 27001:2022 A.16 — Information security incident management

Escribe en: 02_Observability/incidents/{project}-{YYYY-MM-DD}-{slug}.md

Usage:
    python vault_incident_save.py --project my-api --title "API down" --severity P1
    python vault_incident_save.py --project my-api --title "DB latency spike" \
      --severity P2 --status resolved \
      --detected_at "2026-06-01T14:30:00Z" --resolved_at "2026-06-01T16:45:00Z" \
      --impact "Checkout flow degraded for 40% of users" \
      --root_cause "Index missing on orders table after migration" \
      --timeline '[{"time":"14:30","event":"Alert fired"},{"time":"14:45","event":"On-call paged"}]' \
      --action_items '["Add index monitoring","Review migration checklist"]'
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import wrap_main
from vault_io import VAULT_ROOT, assert_within_vault, atomic_write_text, update_section_index
from vault_norms import compute_norm_refs

FOLDER = "02_Observability/incidents"

# ISO 20000-1 severity classification
SEVERITY_LEVELS = {
    "P1": {
        "label": "Critical",
        "description": "Producción caída — todos los usuarios afectados",
        "response_target": "15 min",
        "resolution_target": "4 h",
        "iso_ref": "ISO 20000-1:2018 §8.6.2",
    },
    "P2": {
        "label": "High",
        "description": "Funcionalidad mayor degradada — mayoría de usuarios afectados",
        "response_target": "30 min",
        "resolution_target": "8 h",
        "iso_ref": "ISO 20000-1:2018 §8.6.2",
    },
    "P3": {
        "label": "Medium",
        "description": "Funcionalidad parcial degradada — subconjunto de usuarios",
        "response_target": "2 h",
        "resolution_target": "24 h",
        "iso_ref": "ISO 20000-1:2018 §8.6.2",
    },
    "P4": {
        "label": "Low",
        "description": "Impacto menor — workaround disponible",
        "response_target": "8 h",
        "resolution_target": "72 h",
        "iso_ref": "ISO 20000-1:2018 §8.6.2",
    },
}

VALID_STATUS = ["detected", "investigating", "identified", "mitigating", "resolved", "closed", "post-mortem"]


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _slug(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def _calc_ttd(detected_at: str, resolved_at: str) -> str:
    """Time to detect/resolve in human-readable format."""
    if not (detected_at and resolved_at):
        return "—"
    try:
        d = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
        r = datetime.fromisoformat(resolved_at.replace("Z", "+00:00"))
        delta = r - d
        hours, rem = divmod(int(delta.total_seconds()), 3600)
        mins = rem // 60
        return f"{hours}h {mins}m" if hours else f"{mins}m"
    except Exception:
        return "—"


def vault_incident_save(
    project: str,
    title: str,
    severity: str = "P3",
    status: str = "detected",
    detected_at: Optional[str] = None,
    resolved_at: Optional[str] = None,
    impact: str = "",
    root_cause: str = "",
    timeline: Optional[List[Dict]] = None,
    action_items: Optional[List[str]] = None,
    affected_services: Optional[List[str]] = None,
    rto: str = "",
    rpo: str = "",
    agent: str = "claude",
) -> Dict[str, Any]:
    severity = severity.upper()
    if severity not in SEVERITY_LEVELS:
        return {"ok": False, "error_code": "INVALID_SEVERITY",
                "message": f"severity debe ser P1, P2, P3 o P4. Recibido: {severity}",
                "recovery": {"hint": "Usar --severity P1|P2|P3|P4"}}

    if status not in VALID_STATUS:
        return {"ok": False, "error_code": "INVALID_STATUS",
                "message": f"status inválido: {status}",
                "recovery": {"hint": f"Valores válidos: {', '.join(VALID_STATUS)}"}}

    now = _utcnow()
    detected_at = detected_at or now
    date_prefix = detected_at[:10]
    sev_info = SEVERITY_LEVELS[severity]
    mttr = _calc_ttd(detected_at, resolved_at) if resolved_at else "—"

    timeline = timeline or []
    action_items = action_items or []
    affected_services = affected_services or []

    # Build content
    timeline_md = "\n".join(
        f"| {e.get('time', '—')} | {e.get('event', '')} | {e.get('who', '')} |"
        for e in timeline
    ) or "| — | Sin eventos registrados | |"

    actions_md = "\n".join(f"- [ ] {a}" for a in action_items) or "— Pendiente de definir"
    services_md = ", ".join(f"`{s}`" for s in affected_services) or "— No especificados"

    body = f"""# Incidente: {title}

> **{severity} — {sev_info['label']}**: {sev_info['description']}
> ISO 20000-1:2018 §8.6 | ISO 22301:2019 §8.4

## Datos del incidente

| Campo | Valor |
|---|---|
| **Severidad** | {severity} — {sev_info['label']} |
| **Status** | {status} |
| **Detectado** | {detected_at} |
| **Resuelto** | {resolved_at or '— En curso'} |
| **MTTR** | {mttr} |
| **Servicios afectados** | {services_md} |
| **RTO objetivo** | {rto or sev_info['resolution_target']} |
| **RPO objetivo** | {rpo or '—'} |
| **Target respuesta (ISO 20000)** | {sev_info['response_target']} |
| **Target resolución (ISO 20000)** | {sev_info['resolution_target']} |

## Impacto

{impact or '_Pendiente de documentar el impacto en usuarios y negocio._'}

## Timeline del incidente

| Hora | Evento | Responsable |
|---|---|---|
{timeline_md}

## Causa raíz (RCA)

{root_cause or '_Pendiente de análisis de causa raíz._'}

## Action items (post-mortem)

{actions_md}

## Análisis de causa raíz — 5 Whys

1. ¿Por qué ocurrió el incidente? _Pendiente_
2. ¿Por qué ocurrió la causa anterior? _Pendiente_
3. ¿Por qué ocurrió la causa anterior? _Pendiente_
4. ¿Por qué ocurrió la causa anterior? _Pendiente_
5. ¿Por qué ocurrió la causa anterior? _Pendiente_

## Métricas del incidente

| Métrica | Valor |
|---|---|
| Time to Detect (TTD) | — |
| Time to Mitigate (TTM) | — |
| Time to Resolve (TTR / MTTR) | {mttr} |
| Usuarios afectados | — |
| Pérdida estimada | — |

## Lecciones aprendidas

_Qué salió bien, qué salió mal, qué hacer diferente._

## Referencias

- ISO 20000-1:2018 §8.6 — Incident and service request management
- ISO 22301:2019 §8.4 — Business continuity procedures
- ISO/IEC 27001:2022 A.16 — Information security incident management
"""

    norm_refs = compute_norm_refs(FOLDER, body, [])
    fm_lines = [
        "---",
        f"title: \"Incidente: {title}\"",
        f"id: {uuid.uuid4()}",
        f"createdAt: {now}",
        f"updatedAt: {now}",
        f"tags: {json.dumps(['incident', project, severity.lower(), status])}",
        f"norm_refs: {json.dumps(norm_refs)}",
        f"project: {project}",
        f"severity: {severity}",
        f"status: {status}",
        f"detected_at: {detected_at}",
        f"resolved_at: {resolved_at or ''}",
        f"mttr: {mttr}",
        f"iso_standard: ISO 20000-1:2018 §8.6",
        f"iso_bcm: ISO 22301:2019 §8.4",
        f"cia_integrity: high",
        f"cia_availability: high",
        f"cia_sensitivity: internal",
        f"agent: {agent}",
        "---",
    ]
    full = "\n".join(fm_lines) + "\n\n" + body

    filename = f"{project}-{date_prefix}-{_slug(title)}.md"
    path = VAULT_ROOT / FOLDER / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_within_vault(path, VAULT_ROOT)
    atomic_write_text(path, full)

    update_section_index("02_Observability")

    return {
        "ok": True,
        "path": str(path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "project": project,
        "severity": severity,
        "severity_label": sev_info["label"],
        "status": status,
        "mttr": mttr,
        "action_items_count": len(action_items),
        "iso_standard": "ISO 20000-1:2018 §8.6 / ISO 22301:2019 §8.4",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_incident_save — Registra incidentes y post-mortems (ISO 20000-1 / ISO 22301)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Incidente abierto
  python vault_incident_save.py --project my-api --title "API down" --severity P1

  # Incidente resuelto con post-mortem
  python vault_incident_save.py --project my-api \\
    --title "DB latency spike" --severity P2 --status resolved \\
    --detected_at "2026-06-01T14:30:00Z" --resolved_at "2026-06-01T16:45:00Z" \\
    --impact "Checkout degradado 40% usuarios" \\
    --root_cause "Index faltante tras migración" \\
    --timeline '[{"time":"14:30","event":"Alert fired","who":"PagerDuty"}]' \\
    --action_items '["Agregar monitoreo de índices","Revisar checklist de migraciones"]'
""",
    )
    parser.add_argument("--project",    required=True)
    parser.add_argument("--title",      required=True)
    parser.add_argument("--severity",   default="P3", choices=["P1", "P2", "P3", "P4"])
    parser.add_argument("--status",     default="detected", choices=VALID_STATUS)
    parser.add_argument("--detected_at")
    parser.add_argument("--resolved_at")
    parser.add_argument("--impact",     default="")
    parser.add_argument("--root_cause", default="")
    parser.add_argument("--timeline",   default="[]")
    parser.add_argument("--action_items", default="[]")
    parser.add_argument("--affected_services", default="[]")
    parser.add_argument("--rto",        default="")
    parser.add_argument("--rpo",        default="")
    parser.add_argument("--agent",      default="claude")

    args = parser.parse_args()
    try:
        timeline = json.loads(args.timeline)
        action_items = json.loads(args.action_items)
        affected_services = json.loads(args.affected_services)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error_code": "INVALID_JSON", "message": str(e)}))
        return 1

    result = vault_incident_save(
        project=args.project, title=args.title, severity=args.severity,
        status=args.status, detected_at=args.detected_at, resolved_at=args.resolved_at,
        impact=args.impact, root_cause=args.root_cause,
        timeline=timeline, action_items=action_items,
        affected_services=affected_services,
        rto=args.rto, rpo=args.rpo, agent=args.agent,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_incident_save"))

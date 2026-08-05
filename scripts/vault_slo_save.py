#!/usr/bin/env python3
"""
vault_slo_save.py — Define y registra SLOs (Service Level Objectives) de producción.

Estándar aplicado:
  ISO 20000-1:2018 §8.3   — Service level management (SLA, SLO, reporting)
  ISO/IEC 25010:2023 §4.2 — Reliability: availability, fault tolerance, recoverability
  ISO/IEC 25010:2023 §4.3 — Performance efficiency

Conceptos:
  SLI (Indicator)  — métrica medible: % uptime, latencia p99, error rate
  SLO (Objective)  — target del SLI: ≥ 99.9% uptime en ventana de 30d
  SLA (Agreement)  — compromiso contractual con consecuencias (penalidades)
  Error Budget     — margen de error permitido = 1 - SLO target

Escribe en: 02_Observability/slos/{project}-{service}-{slo_type}.md

Usage:
    python vault_slo_save.py --project my-api --service checkout \\
      --slo_type availability --target 99.9 --window 30d

    python vault_slo_save.py --project my-api --service checkout \\
      --slo_type latency --target 200 --unit ms --percentile p95 \\
      --window 7d --alert_threshold 250
"""

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import wrap_main
from vault_lib import slugify_strict, utcnow
from vault_io import (
    VAULT_ROOT,
    assert_within_vault,
    atomic_write_text,
    write_report,
    update_section_index,
)
from vault_norms import compute_norm_refs

FOLDER = "02_Observability/slos"

# ISO 25010:2023 quality characteristic mapping per SLO type
SLO_TYPES: Dict[str, Dict[str, str]] = {
    "availability": {
        "label": "Disponibilidad",
        "unit_default": "%",
        "direction": "≥",
        "iso_char": "Reliability / Availability",
        "iso_ref": "ISO/IEC 25010:2023 §4.2.1",
        "description": "Porcentaje del tiempo que el servicio está operativo y accesible.",
        "sli_example": "successful_requests / total_requests × 100",
        "good_event": "HTTP 2xx/3xx en < 1s",
        "bad_event": "HTTP 5xx, timeout > 1s, o servicio no alcanzable",
    },
    "latency": {
        "label": "Latencia",
        "unit_default": "ms",
        "direction": "≤",
        "iso_char": "Performance Efficiency / Time Behaviour",
        "iso_ref": "ISO/IEC 25010:2023 §4.3.1",
        "description": "Tiempo de respuesta del servicio en el percentil especificado.",
        "sli_example": "percentile(request_duration_seconds, 0.95) × 1000",
        "good_event": "Request completado bajo el umbral de latencia",
        "bad_event": "Request supera el umbral de latencia",
    },
    "error_rate": {
        "label": "Tasa de error",
        "unit_default": "%",
        "direction": "≤",
        "iso_char": "Reliability / Fault Tolerance",
        "iso_ref": "ISO/IEC 25010:2023 §4.2.2",
        "description": "Porcentaje de requests que resultan en error.",
        "sli_example": "error_requests / total_requests × 100",
        "good_event": "Request sin error (HTTP 2xx/3xx)",
        "bad_event": "Request con error (HTTP 5xx, exception no manejada)",
    },
    "throughput": {
        "label": "Throughput",
        "unit_default": "req/s",
        "direction": "≥",
        "iso_char": "Performance Efficiency / Capacity",
        "iso_ref": "ISO/IEC 25010:2023 §4.3.3",
        "description": "Volumen de requests por segundo que el servicio puede manejar.",
        "sli_example": "rate(requests_total[5m])",
        "good_event": "Servicio procesa requests a la tasa objetivo",
        "bad_event": "Cola creciente, requests rechazados o degradados",
    },
    "durability": {
        "label": "Durabilidad",
        "unit_default": "%",
        "direction": "≥",
        "iso_char": "Reliability / Recoverability",
        "iso_ref": "ISO/IEC 25010:2023 §4.2.4",
        "description": "Probabilidad de que los datos no se pierdan en un período dado.",
        "sli_example": "objects_readable / objects_written × 100",
        "good_event": "Dato escrito recuperable tras fallo",
        "bad_event": "Dato perdido o corrupto",
    },
    "freshness": {
        "label": "Frescura de datos",
        "unit_default": "min",
        "direction": "≤",
        "iso_char": "Reliability / Maturity",
        "iso_ref": "ISO/IEC 25010:2023 §4.2.3",
        "description": "Tiempo máximo de retraso aceptable en pipelines de datos.",
        "sli_example": "current_time - max(data_timestamp)",
        "good_event": "Dato disponible dentro de la ventana de frescura",
        "bad_event": "Dato más antiguo que el umbral de frescura",
    },
    "saturation": {
        "label": "Saturación",
        "unit_default": "%",
        "direction": "≤",
        "iso_char": "Performance Efficiency / Resource Utilization",
        "iso_ref": "ISO/IEC 25010:2023 §4.3.2",
        "description": "Porcentaje de uso del recurso más constraining (CPU, memoria, disco).",
        "sli_example": "max(cpu_usage_percent, memory_usage_percent)",
        "good_event": "Recurso por debajo del umbral de saturación",
        "bad_event": "Recurso supera el umbral (riesgo de degradación inminente)",
    },
}

VALID_WINDOWS = {"7d": 7, "14d": 14, "30d": 30, "60d": 60, "90d": 90, "1y": 365}


def _slug(text: str) -> str:
    # Delega en el slug canónico (`vault_lib.slugify`). La copia que había
    # aquí divergía del resto: unas borraban los acentos, otras los dejaban
    # en el nombre de fichero. Una sola fuente, un solo nombre de nota.
    return slugify_strict(text)


def _calc_error_budget(
    target: float, window: str, unit: str, direction: str
) -> Dict[str, Any]:
    """Compute error budget based on SLO target."""
    window_days = VALID_WINDOWS.get(window, 30)
    window_minutes = window_days * 24 * 60

    if unit == "%" and direction == "≥":
        # Availability / durability style
        allowed_downtime_pct = 100 - target
        allowed_downtime_min = round(window_minutes * allowed_downtime_pct / 100, 1)
        return {
            "allowed_failure_pct": round(allowed_downtime_pct, 4),
            "allowed_downtime_minutes": allowed_downtime_min,
            "allowed_downtime_human": f"{int(allowed_downtime_min // 60)}h {int(allowed_downtime_min % 60)}m",
            "burn_rate_1h": round(allowed_downtime_min / (window_minutes / 60), 2),
        }
    elif unit == "%" and direction == "≤":
        # Error rate style
        return {
            "allowed_failure_pct": target,
            "allowed_errors_per_million": round(target * 10000),
            "burn_rate_fast": f"14.4× (alert: 1h window, 2% budget)",
            "burn_rate_slow": f"1× (alert: {window} window)",
        }
    return {}


def vault_slo_save(
    project: str,
    service: str,
    slo_type: str,
    target: float,
    unit: Optional[str] = None,
    window: str = "30d",
    percentile: str = "",
    description: str = "",
    alert_threshold: Optional[float] = None,
    data_source: str = "",
    consequence: str = "",
    agent: str = "claude",
) -> Dict[str, Any]:
    if slo_type not in SLO_TYPES:
        return {
            "ok": False,
            "error_code": "INVALID_SLO_TYPE",
            "message": f"slo_type debe ser uno de: {', '.join(SLO_TYPES.keys())}",
            "recovery": {"hint": "Ver --help para tipos disponibles"},
        }
    if window not in VALID_WINDOWS:
        return {
            "ok": False,
            "error_code": "INVALID_WINDOW",
            "message": f"window debe ser: {', '.join(VALID_WINDOWS.keys())}",
        }

    slo_info = SLO_TYPES[slo_type]
    unit = unit or slo_info["unit_default"]
    direction = slo_info["direction"]
    now = utcnow()

    alert_threshold = (
        alert_threshold
        if alert_threshold is not None
        else (round(target * 0.995, 3) if direction == "≥" else round(target * 1.1, 3))
    )

    error_budget = _calc_error_budget(target, window, unit, direction)
    eb_lines = "\n".join(f"| {k} | {v} |" for k, v in error_budget.items())

    slo_label = f"{slo_type} {direction} {target}{unit}"
    if percentile:
        slo_label = f"{slo_type} {percentile} {direction} {target}{unit}"

    body = f"""# SLO: {service} — {slo_info["label"]}

> {slo_info["description"]}
> {slo_info["iso_ref"]} — {slo_info["iso_char"]}
> ISO 20000-1:2018 §8.3 — Service level management

## Definición del SLO

| Campo | Valor |
|---|---|
| **Proyecto** | {project} |
| **Servicio** | {service} |
| **Tipo** | {slo_type} — {slo_info["label"]} |
| **SLO** | {slo_label} |
| **Ventana** | {window} (rolling) |
| **Umbral de alerta** | {direction} {alert_threshold}{unit} |
| **ISO característica** | {slo_info["iso_char"]} |

## SLI (Service Level Indicator)

**Qué medir:** {slo_info["description"]}

**Ejemplo de query:**
```
{slo_info["sli_example"]}
```

**Evento bueno:** {slo_info["good_event"]}
**Evento malo:** {slo_info["bad_event"]}

**Fuente de datos:** {data_source or "_Pendiente: URL de dashboard o query de métrica_"}

## Error Budget

| Métrica | Valor |
|---|---|
{eb_lines or "| — | Calcular según tipo de SLO |"}

## Alertas recomendadas (Multi-window, multi-burn-rate)

| Ventana | Burn rate | Severidad | Acción |
|---|---|---|---|
| 1h / 5m | 14.4× | P1 — página inmediato | Investigar ahora |
| 6h / 30m | 6× | P2 — página urgente | Investigar en < 1h |
| 3d / 6h | 1× | P3 — ticket | Investigar en próximos días |

## Consecuencias (SLA)

{consequence or "_Sin consecuencias contractuales definidas aún. Agregar penalidades o créditos si aplica._"}

## Descripción adicional

{description or "_Pendiente de enriquecer con contexto del negocio y dependencias._"}

## Historial de compliance

| Período | Valor medido | Cumplido | Error budget consumido |
|---|---|---|---|
| — | — | — | — |

## Referencias

- ISO 20000-1:2018 §8.3 — Service level management
- ISO/IEC 25010:2023 {slo_info["iso_ref"].split()[-1]} — {slo_info["iso_char"]}
- Google SRE Book — Chapter 4: Service Level Objectives
"""

    norm_refs = compute_norm_refs(FOLDER, body, [])
    fm_lines = [
        "---",
        f'title: "SLO: {service} — {slo_info["label"]}"',
        f"id: {uuid.uuid4()}",
        f"createdAt: {now}",
        f"updatedAt: {now}",
        f"tags: {json.dumps(['slo', 'observability', project, service, slo_type])}",
        f"norm_refs: {json.dumps(norm_refs)}",
        f"project: {project}",
        f"service: {service}",
        f"slo_type: {slo_type}",
        f"target: {target}",
        f"unit: {unit}",
        f"window: {window}",
        f"alert_threshold: {alert_threshold}",
        f"iso_standard: ISO 20000-1:2018 §8.3",
        f"iso_quality: {slo_info['iso_ref']}",
        f"cia_integrity: high",
        f"cia_availability: high",
        f"cia_sensitivity: internal",
        f"agent: {agent}",
        "---",
    ]
    full = "\n".join(fm_lines) + "\n\n" + body

    filename = f"{_slug(project)}-{_slug(service)}-{slo_type}.md"
    path = VAULT_ROOT / FOLDER / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_within_vault(path, VAULT_ROOT)
    atomic_write_text(path, full)

    update_section_index("02_Observability")

    return {
        "ok": True,
        **write_report(),
        "path": str(path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "project": project,
        "service": service,
        "slo_type": slo_type,
        "slo": slo_label,
        "window": window,
        "error_budget": error_budget,
        "iso_standard": f"ISO 20000-1:2018 §8.3 / {slo_info['iso_ref']}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_slo_save — Define SLOs de producción (ISO 20000-1 / ISO 25010)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Tipos de SLO disponibles: {", ".join(SLO_TYPES.keys())}

Ejemplos:
  python vault_slo_save.py --project my-api --service checkout \\
    --slo_type availability --target 99.9 --window 30d

  python vault_slo_save.py --project my-api --service api-gateway \\
    --slo_type latency --target 200 --unit ms --percentile p95 \\
    --window 7d --alert_threshold 300

  python vault_slo_save.py --project my-api --service orders \\
    --slo_type error_rate --target 0.1 --window 30d
""",
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--slo_type", required=True, choices=list(SLO_TYPES.keys()))
    parser.add_argument("--target", required=True, type=float)
    parser.add_argument("--unit", default=None)
    parser.add_argument("--window", default="30d", choices=list(VALID_WINDOWS.keys()))
    parser.add_argument("--percentile", default="")
    parser.add_argument("--description", default="")
    parser.add_argument("--alert_threshold", type=float, default=None)
    parser.add_argument("--data_source", default="")
    parser.add_argument("--consequence", default="")
    parser.add_argument("--agent", default="claude")

    args = parser.parse_args()
    result = vault_slo_save(
        project=args.project,
        service=args.service,
        slo_type=args.slo_type,
        target=args.target,
        unit=args.unit,
        window=args.window,
        percentile=args.percentile,
        description=args.description,
        alert_threshold=args.alert_threshold,
        data_source=args.data_source,
        consequence=args.consequence,
        agent=args.agent,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_slo_save"))

#!/usr/bin/env python3

"""

Vault Log Error Tool — Log errors, antipatterns, vulnerabilities, metrics, alerts, and SLOs



Records observability events with full traceability: severity, context, mitigation.

Supports 7 types: error, antipattern, vulnerability, waf, metric, alert, slo.



Usage:

    python vault_log_error.py --type error --title "SSH Timeout" --description "..." --severity high

    python vault_log_error.py --type vulnerability --title "API Key Exposed" --severity critical

    python vault_log_error.py --type metric --title "Response Time" --description "P99 response time" --severity info --meta '{"service":"api","value":"245ms","unit":"ms","objective":"200ms","tool":"prometheus"}'

    python vault_log_error.py --type alert --title "High CPU" --description "CPU > 80%" --severity high --meta '{"condition":"cpu > 80","threshold":80,"unit":"percent","channel":"slack","runbook":"08_Runbooks/debug/high-cpu.md"}'

    python vault_log_error.py --type slo --title "API Availability" --description "Monthly uptime" --severity info --meta '{"sli":"requests with status < 500","objective":99.9,"window":"30d","burn_rate":"1h budget consumed in 3.6h"}'

"""

import argparse

import json


import uuid

import re

import sys

from vault_errors import emit_error, wrap_main
from vault_lib import yaml_scalar, utcnow, slugify
from vault_io import atomic_write_text, get_vault_root, safe_wikilink, write_report
from datetime import datetime, timezone


from pathlib import Path

from typing import Any, Dict, Optional


TYPE_FOLDERS = {
    "error": "02_Observability/errors",
    "antipattern": "02_Observability/antipatterns",
    "vulnerability": "02_Observability/vulnerabilities",
    "waf": "02_Observability/waf",
    "metric": "02_Observability/metrics",
    "alert": "02_Observability/alerts",
    "slo": "02_Observability/slos",
}


# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueño.
from vault_vocabulario import opciones as _opciones

#: `info` no es una gravedad: es lo que se registra sin que sea un
#: problema. Por eso es una ampliación declarada y no otra escala.
SEVERITIES = _opciones("severidad_con_info")


def generate_metric_content(
    title: str, description: str, severity: str, project: str, meta: Dict[str, Any]
) -> str:
    service = meta.get("service", "N/A")

    value = meta.get("value", "N/A")

    unit = meta.get("unit", "")

    objective = meta.get("objective", "")

    tool = meta.get("tool", "")

    content = f"""# {title}



## METRIC



**Fecha:** {utcnow()}

**Severidad:** {severity.upper()}

**Proyecto:** {project or "General"}



---



## Descripción



{description}



---



## Detalles



| Campo | Valor |

|---|---|

| Servicio | {service} |

| Valor actual | {value} {unit} |

| Objetivo | {objective} {unit} |

| Herramienta | {tool} |

"""

    return content


def generate_alert_content(
    title: str, description: str, severity: str, project: str, meta: Dict[str, Any]
) -> str:
    condition = meta.get("condition", "N/A")

    threshold = meta.get("threshold", "")

    unit = meta.get("unit", "")

    channel = meta.get("channel", "N/A")

    runbook = meta.get("runbook", "")

    content = f"""# {title}



## ALERT



**Fecha:** {utcnow()}

**Severidad:** {severity.upper()}

**Proyecto:** {project or "General"}



---



## Descripción



{description}



---



## Regla



| Campo | Valor |

|---|---|

| Condición | {condition} |

| Umbral | {threshold} {unit} |

| Canal | {channel} |

"""

    if runbook:
        content += f"| Runbook | [[{safe_wikilink(runbook)}]] |\n"

    return content


def generate_slo_content(
    title: str, description: str, severity: str, project: str, meta: Dict[str, Any]
) -> str:
    sli = meta.get("sli", "N/A")

    objective = meta.get("objective", "")

    window = meta.get("window", "")

    burn_rate = meta.get("burn_rate", "")

    content = f"""# {title}



## SLO



**Fecha:** {utcnow()}

**Severidad:** {severity.upper()}

**Proyecto:** {project or "General"}



---



## Descripción



{description}



---



## Definición



| Campo | Valor |

|---|---|

| Indicador (SLI) | {sli} |

| Objetivo | {objective}% |

| Ventana | {window} |

| Burn rate policy | {burn_rate} |

"""

    return content


def vault_log_error(
    error_type: str,
    title: str,
    description: str,
    context: str = "",
    severity: str = "medium",
    project: str = "",
    mitigation: str = "",
    meta: Optional[Dict[str, Any]] = None,
    owasp_category: str = "",
    cwe_id: str = "",
) -> Dict[str, Any]:
    if error_type not in TYPE_FOLDERS:
        return emit_error("vault_log_error", "INVALID_VALUE", f"Tipo inválido: {error_type}. Válidos: {list(TYPE_FOLDERS.keys())}")

    if severity not in SEVERITIES:
        return emit_error("vault_log_error", "INVALID_VALUE", f"Severity inválida: {severity}. Válidos: {SEVERITIES}")

    folder = TYPE_FOLDERS[error_type]

    meta = meta or {}

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    safe_slug = slugify(title)[:50]

    filename = f"{date}-{safe_slug}.md"

    if error_type == "metric":
        content = generate_metric_content(title, description, severity, project, meta)

    elif error_type == "alert":
        content = generate_alert_content(title, description, severity, project, meta)

    elif error_type == "slo":
        content = generate_slo_content(title, description, severity, project, meta)

    else:
        content_lines = [f"# {title}\n"]

        content_lines.append(f"## {error_type.upper()}\n")

        content_lines.append(f"**Fecha:** {utcnow()}")

        content_lines.append(f"**Severidad:** {severity.upper()}")

        content_lines.append(f"**Proyecto:** {project or 'General'}")

        if error_type == "vulnerability" and (owasp_category or cwe_id):
            content_lines.append(f"**OWASP:** {owasp_category or 'N/A'}")
            content_lines.append(f"**CWE:** {cwe_id or 'N/A'}")

        content_lines.append("\n---\n\n## Descripción\n\n" + description)

        if context:
            content_lines.append("\n\n---\n\n## Contexto\n\n" + context)

        if mitigation:
            content_lines.append("\n\n---\n\n## Mitigación\n\n" + mitigation)

        content = "\n".join(content_lines)

    folder_path = get_vault_root() / folder

    folder_path.mkdir(parents=True, exist_ok=True)

    file_path = folder_path / filename

    # v37: wrap content with YAML frontmatter for traceability
    fm_tags = [project, error_type] if project else [error_type]
    frontmatter_parts = [
        f"---",
        f"title: {yaml_scalar(title)}",
        f"id: {str(uuid.uuid4())}",
        f"type: {error_type}",
        f"createdAt: {utcnow()}",
        f"updatedAt: {utcnow()}",
        f"tags: {json.dumps(fm_tags)}",
        f"severity: {severity}",
        f"project: {project}",
    ]
    if error_type == "vulnerability":
        if owasp_category:
            frontmatter_parts.append(f"owasp_category: {owasp_category}")
        if cwe_id:
            frontmatter_parts.append(f"cwe_id: {cwe_id}")
    frontmatter_parts.extend([
        f"cia_integrity: medium",
        f"cia_availability: medium",
        f"cia_sensitivity: internal",
        f"agent: system",
        f"---\n",
    ])
    frontmatter = "\n".join(frontmatter_parts) + "\n\n"

    atomic_write_text(file_path, frontmatter + content)

    return {
        "ok": True,
        **write_report(),
        "path": str(file_path.relative_to(get_vault_root())),
        "type": error_type,
        "severity": severity,
        "title": title,
        "message": f"{error_type.capitalize()} logged successfully",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Log Error Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_log_error.py --type error --title "SSH Timeout" --description "Connection timed out after 30s" --severity high

  python vault_log_error.py --type vulnerability --title "API Key Exposed" --severity critical --description "Key found in git history" --owasp_category "A02" --cwe_id "CWE-798"

  python vault_log_error.py --type metric --title "Response Time" --description "P99 response time" --severity info --meta '{"service":"api","value":"245ms","unit":"ms","objective":"200ms","tool":"prometheus"}'

  python vault_log_error.py --type antipattern --title "God Object" --description "AuthService tiene 2000 lineas" --severity medium --project "mi-api"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Tipos: error, antipattern, vulnerability, waf, metric, alert, slo

  - Severidades: critical, high, medium, low, info

""",
    )

    parser.add_argument("--type", required=True, choices=list(TYPE_FOLDERS.keys()))

    parser.add_argument("--title", required=True)

    parser.add_argument("--description", required=True)

    parser.add_argument("--context", default="")

    parser.add_argument("--severity", default="medium", choices=SEVERITIES)

    parser.add_argument("--project", default="")

    parser.add_argument("--mitigation", default="")

    parser.add_argument("--meta", help="Additional metadata as JSON")

    parser.add_argument("--owasp_category", default="", help="OWASP category: A01-A10 (for vulnerability type)")

    parser.add_argument("--cwe_id", default="", help="CWE ID, e.g. CWE-798 (for vulnerability type)")

    args = parser.parse_args()

    meta = None

    if args.meta:
        try:
            meta = json.loads(args.meta)

        except json.JSONDecodeError:
            pass

    result = vault_log_error(
        args.type,
        args.title,
        args.description,
        args.context,
        args.severity,
        args.project,
        args.mitigation,
        meta,
        args.owasp_category,
        args.cwe_id,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_log_error"))

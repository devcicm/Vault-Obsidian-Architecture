#!/usr/bin/env python3
"""
vault_ncr_save.py — No Conformidades y Acciones Correctivas (ISO 9001:2015).

Estándar aplicado:
  ISO 9001:2015 §10.2  — Non-conformity and corrective action
  ISO 9001:2015 §9.2   — Internal audit (detecta NCRs)
  ISO/IEC 25010:2023   — Quality in use (criterios de no conformidad)

Una NCR documenta un desvío de un requisito — de calidad, proceso, entrega o auditoría.
Las acciones correctivas abordan la causa raíz para prevenir recurrencia.

IDs auto-generados: NCR-YYYY-NNN

Escribe en: 02_Observability/quality/{project}-{YYYY}-{slug}.md

Usage:
    python vault_ncr_save.py --project my-api \\
      --title "API no valida input en endpoint /search" \\
      --ncr_type process --severity major \\
      --detected_by internal \\
      --description "El endpoint /search acepta queries SQL sin sanitizar" \\
      --root_cause "No se aplicó el estándar de validación definido en SP-01" \\
      --corrective_actions '["Añadir validación con Zod","Agregar test de regresión","Revisar todos los endpoints"]'

    python vault_ncr_save.py --project my-api \\
      --title "Deploy sin smoke tests" \\
      --ncr_type process --severity minor \\
      --detected_by audit \\
      --immediate_action "Rollback a versión anterior"
"""

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import wrap_main
from vault_lib import yaml_scalar, slugify_strict, utcnow
from vault_io import assert_within_vault, atomic_write_text, get_vault_root, write_report
from vault_norms_catalog import compute_norm_refs, status_frontmatter_lines
# Los `*_save` viven en `scripts/`; el paquete se importa desde la raiz.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.frontmatter import Frontmatter  # noqa: E402

FOLDER = "02_Observability/quality"

NCR_TYPES: Dict[str, str] = {
    "product": "El producto/software no cumple con requisitos funcionales o de calidad",
    "process": "Un proceso no se ejecutó según el procedimiento definido",
    "service": "El servicio entregado no cumplió con el SLA o requisitos del cliente",
    "documentation": "Documentación faltante, incorrecta o desactualizada",
    "audit": "Hallazgo de auditoría interna o externa",
}

SEVERITY_LEVELS: Dict[str, str] = {
    "critical": "Fallo que impacta directamente la seguridad, conformidad legal o entrega al cliente",
    "major": "Desvío significativo que requiere acción correctiva antes de continuar",
    "minor": "Desvío menor que no impide operación pero debe corregirse",
    "observation": "Oportunidad de mejora — no es non-conformidad estricta",
}

DETECTED_BY = [
    "audit",
    "customer",
    "internal",
    "automated",
    "security_scan",
    "code_review",
]
VALID_STATUS = ["open", "in_progress", "pending_verification", "closed", "cancelled"]


def _slug(text: str) -> str:
    # Delega en el slug canónico (`vault_lib.slugify`). La copia que había
    # aquí divergía del resto: unas borraban los acentos, otras los dejaban
    # en el nombre de fichero. Una sola fuente, un solo nombre de nota.
    return slugify_strict(text)[:60]


def _ncr_id(date_str: str) -> str:
    year = date_str[:4]
    import random

    return f"NCR-{year}-{random.randint(100, 999)}"


def _cia_from_severity(severity: str, ncr_type: str) -> Dict[str, str]:
    if severity == "critical":
        return {
            "integrity": "high",
            "availability": "high",
            "sensitivity": "restricted",
        }
    if severity == "major":
        return {
            "integrity": "high",
            "availability": "medium",
            "sensitivity": "internal",
        }
    return {"integrity": "medium", "availability": "medium", "sensitivity": "internal"}


def vault_ncr_save(
    project: str,
    title: str,
    ncr_type: str = "process",
    severity: str = "major",
    detected_by: str = "internal",
    description: str = "",
    root_cause: str = "",
    immediate_action: str = "",
    corrective_actions: Optional[List[str]] = None,
    target_date: str = "",
    status: str = "open",
    owner: str = "",
    related_requirement: str = "",
    agent: str = "claude",
) -> Dict[str, Any]:
    if ncr_type not in NCR_TYPES:
        return {
            "ok": False,
            "error_code": "INVALID_NCR_TYPE",
            "message": f"ncr_type debe ser: {', '.join(NCR_TYPES.keys())}",
        }
    if severity not in SEVERITY_LEVELS:
        return {
            "ok": False,
            "error_code": "INVALID_SEVERITY",
            "message": f"severity debe ser: {', '.join(SEVERITY_LEVELS.keys())}",
        }
    if detected_by not in DETECTED_BY:
        return {
            "ok": False,
            "error_code": "INVALID_DETECTED_BY",
            "message": f"detected_by debe ser: {', '.join(DETECTED_BY)}",
        }
    if status not in VALID_STATUS:
        return {
            "ok": False,
            "error_code": "INVALID_STATUS",
            "message": f"status debe ser: {', '.join(VALID_STATUS)}",
        }

    now = utcnow()
    ncr_id = _ncr_id(now)
    corrective_actions = corrective_actions or []
    cia = _cia_from_severity(severity, ncr_type)

    actions_md = (
        "\n".join(f"- [ ] {a}" for a in corrective_actions)
        or "— Sin acciones correctivas definidas aún"
    )

    body = f"""# NCR: {title}

> **{ncr_id}** | {severity.upper()} — {SEVERITY_LEVELS[severity][:60]}
> ISO 9001:2015 §10.2 — Nonconformity and corrective action

## Datos de la no conformidad

| Campo | Valor |
|---|---|
| **ID** | {ncr_id} |
| **Tipo** | {ncr_type} — {NCR_TYPES[ncr_type][:60]} |
| **Severidad** | {severity.upper()} |
| **Detectada por** | {detected_by} |
| **Status** | {status} |
| **Propietario** | {owner or "— Sin asignar"} |
| **Fecha límite** | {target_date or "— Sin definir"} |
| **Requisito relacionado** | {related_requirement or "— No especificado"} |

## Descripción (ISO 9001 §10.2.1.a)

{description or "_Pendiente: describir qué se encontró fuera de conformidad y dónde._"}

## Acción inmediata / Contención (ISO 9001 §10.2.1.b)

{immediate_action or "_Pendiente: acción tomada para contener el problema inmediatamente._"}

## Análisis de causa raíz (ISO 9001 §10.2.1.c)

{root_cause or "_Pendiente: identificar la causa raíz usando 5-Whys, Ishikawa o similar._"}

### 5-Whys (completar si aplica)

1. ¿Por qué ocurrió la no conformidad? _Pendiente_
2. ¿Por qué ocurrió la causa anterior? _Pendiente_
3. ¿Por qué ocurrió la causa anterior? _Pendiente_
4. ¿Por qué? _Pendiente_
5. ¿Por qué? _Pendiente — esta es la causa raíz_

## Acciones correctivas (ISO 9001 §10.2.1.d)

{actions_md}

## Verificación de eficacia (ISO 9001 §10.2.1.f)

| Acción | Evidencia de cierre | Verificado por | Fecha |
|---|---|---|---|
| — | — | — | — |

## Lecciones aprendidas

_¿Qué cambio sistémico previene esta categoría de no conformidad en el futuro?_

## Historial

| Fecha | Actor | Cambio |
|---|---|---|
| {now[:10]} | {owner or agent} | NCR abierta |

## Referencias

- ISO 9001:2015 §10.2 — Nonconformity and corrective action
- ISO 9001:2015 §9.2 — Internal audit
- ISO/IEC 25010:2023 — Quality characteristics (criterios de conformidad)
"""

    norm_refs = compute_norm_refs(FOLDER, body, [])
    date_prefix = now[:7]  # YYYY-MM
    fm_lines = Frontmatter()
    fm_lines.set("title", f'NCR: {title}')
    fm_lines.set("id", uuid.uuid4())
    fm_lines.set("ncr_id", ncr_id)
    fm_lines.set("createdAt", now)
    fm_lines.set("updatedAt", now)
    fm_lines.set("tags", ['ncr', 'quality', project, ncr_type, severity])
    fm_lines.set("norm_refs", norm_refs)
    fm_lines.set("project", project)
    fm_lines.set("ncr_type", ncr_type)
    fm_lines.set("severity", severity)
    fm_lines.set("detected_by", detected_by)
    fm_lines.lineas(status_frontmatter_lines("vault_ncr_save", status))
    fm_lines.set("owner", owner, vacio_citado=True)
    fm_lines.set("target_date", target_date, vacio_citado=True)
    fm_lines.set("corrective_actions_count", len(corrective_actions))
    fm_lines.set("iso_standard", "ISO 9001:2015 §10.2")
    fm_lines.set("cia_integrity", cia['integrity'])
    fm_lines.set("cia_availability", cia['availability'])
    fm_lines.set("cia_sensitivity", cia['sensitivity'])
    fm_lines.set("agent", agent)
    full = fm_lines.render() + "\n\n" + body

    filename = f"{_slug(project)}-{date_prefix}-{_slug(title)}.md"
    path = get_vault_root() / FOLDER / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_within_vault(path, get_vault_root())
    atomic_write_text(path, full)
    # El indice de seccion lo dispara el write path del kernel
    # (`vault_io._auto_section_index`) en cuanto se escribe la nota. La
    # llamada explicita que habia aqui lo regeneraba una segunda vez con
    # el mismo contenido: trabajo duplicado que ademas se contaba como
    # escritura en el envelope.

    return {
        "ok": True,
        **write_report(),
        "path": str(path.relative_to(get_vault_root())).replace("\\", "/"),
        "ncr_id": ncr_id,
        "project": project,
        "ncr_type": ncr_type,
        "severity": severity,
        "status": status,
        "corrective_actions_count": len(corrective_actions),
        "iso_standard": "ISO 9001:2015 §10.2",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_ncr_save — Registra no conformidades y acciones correctivas (ISO 9001:2015)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Tipos NCR:   {", ".join(NCR_TYPES.keys())}
Severidades: {", ".join(SEVERITY_LEVELS.keys())}
Detectado por: {", ".join(DETECTED_BY)}

Ejemplos:
  python vault_ncr_save.py --project my-api \\
    --title "API no valida input en /search" \\
    --ncr_type process --severity major \\
    --detected_by internal \\
    --description "El endpoint acepta queries sin sanitizar" \\
    --root_cause "No se aplicó el estándar de validación SP-01" \\
    --corrective_actions '["Validación con Zod","Test de regresión"]'
""",
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--ncr_type", default="process", choices=list(NCR_TYPES.keys()))
    parser.add_argument(
        "--severity", default="major", choices=list(SEVERITY_LEVELS.keys())
    )
    parser.add_argument("--detected_by", default="internal", choices=DETECTED_BY)
    parser.add_argument("--description", default="")
    parser.add_argument("--root_cause", default="")
    parser.add_argument("--immediate_action", default="")
    parser.add_argument("--corrective_actions", default="[]")
    parser.add_argument("--target_date", default="")
    parser.add_argument("--status", default="open", choices=VALID_STATUS)
    parser.add_argument("--owner", default="")
    parser.add_argument("--related_requirement", default="")
    parser.add_argument("--agent", default="claude")

    args = parser.parse_args()
    try:
        corrective_actions = json.loads(args.corrective_actions)
    except json.JSONDecodeError as e:
        print(
            json.dumps({"ok": False, "error_code": "INVALID_JSON", "message": str(e)}, ensure_ascii=False)
        )
        return 1

    result = vault_ncr_save(
        project=args.project,
        title=args.title,
        ncr_type=args.ncr_type,
        severity=args.severity,
        detected_by=args.detected_by,
        description=args.description,
        root_cause=args.root_cause,
        immediate_action=args.immediate_action,
        corrective_actions=corrective_actions,
        target_date=args.target_date,
        status=args.status,
        owner=args.owner,
        related_requirement=args.related_requirement,
        agent=args.agent,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_ncr_save"))

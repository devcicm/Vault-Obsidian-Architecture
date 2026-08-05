#!/usr/bin/env python3
"""
vault_privacy_save.py — Inventario de tratamiento de datos personales (PII/GDPR).

Estándar aplicado:
  ISO/IEC 27701:2019  — Privacy Information Management System (PIMS)
  ISO/IEC 27001:2022  — A.5.34 Privacy and protection of PII
  GDPR Art. 30        — Registro de actividades de tratamiento
  GDPR Art. 35        — Evaluación de impacto (DPIA)

Cada nota documenta UNA actividad de tratamiento (procesamiento de datos).
Escribe en: 09_Infrastructure/privacy/{project}-{slug}.md

Usage:
    python vault_privacy_save.py --project my-api \\
      --title "Registro de usuarios" \\
      --purpose "Autenticación y gestión de cuenta" \\
      --legal_basis contract \\
      --pii_categories '["email","name","phone"]' \\
      --retention_period "Mientras la cuenta esté activa + 2 años" \\
      --data_subjects customers

    python vault_privacy_save.py --project my-api \\
      --title "Analytics de comportamiento" \\
      --purpose "Mejorar UX y detectar patrones de uso" \\
      --legal_basis legitimate_interest \\
      --pii_categories '["behavioral","device_id","ip_address"]' \\
      --dpia_required true --transfers_outside_eu true \\
      --third_parties '["Mixpanel","Google Analytics"]'
"""

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import wrap_main
from vault_lib import utcnow
from vault_io import (
    write_report,
    VAULT_ROOT,
    assert_within_vault,
    atomic_write_text,
    update_section_index,
)
from vault_norms import compute_norm_refs, status_frontmatter_lines

FOLDER = "09_Infrastructure/privacy"

# GDPR Art. 6 + ISO 27701 §6.2.2 — Legal bases
LEGAL_BASES: Dict[str, str] = {
    "consent": "Art. 6(1)(a) — Consentimiento explícito del interesado",
    "contract": "Art. 6(1)(b) — Ejecución de contrato con el interesado",
    "legal_obligation": "Art. 6(1)(c) — Obligación legal del responsable",
    "vital_interest": "Art. 6(1)(d) — Interés vital del interesado u otra persona",
    "public_task": "Art. 6(1)(e) — Misión de interés público o ejercicio de poderes",
    "legitimate_interest": "Art. 6(1)(f) — Interés legítimo del responsable (requiere LIA)",
}

# ISO 27701 §6.9 — PII principal categories
PII_CATEGORIES: Dict[str, str] = {
    "name": "Nombre completo o parcial",
    "email": "Dirección de correo electrónico",
    "phone": "Número de teléfono",
    "address": "Dirección física",
    "national_id": "DNI, pasaporte, número de seguridad social",
    "financial": "Datos bancarios, tarjetas, historial de pagos",
    "health": "Datos de salud, historial médico",
    "biometric": "Huella dactilar, reconocimiento facial, voz",
    "location": "Geolocalización, dirección IP, datos de viaje",
    "behavioral": "Historial de navegación, clics, preferencias",
    "device_id": "ID de dispositivo, cookies, IMEI",
    "ip_address": "Dirección IP (considerada PII en GDPR)",
    "credentials": "Contraseñas hasheadas, tokens de autenticación",
    "professional": "Cargo, empresa, historial laboral",
    "sensitive": "Origen racial, opiniones políticas, religión, orientación sexual",
}

DATA_SUBJECTS = [
    "customers",
    "employees",
    "contractors",
    "minors",
    "prospects",
    "partners",
]

VALID_STATUS = ["active", "under_review", "deprecated", "closed"]

# DPIA triggers (GDPR Art. 35 + CNIL guidelines)
DPIA_TRIGGERS = [
    "sensitive",  # categorías especiales de datos
    "biometric",  # datos biométricos
    "health",  # datos de salud
    "minors",  # datos de menores
]


def _slug(text: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def _dpia_auto_required(pii_categories: List[str], data_subjects: List[str]) -> bool:
    return (
        any(c in DPIA_TRIGGERS for c in pii_categories)
        or "minors" in data_subjects
        or len(pii_categories) >= 5
    )


def vault_privacy_save(
    project: str,
    title: str,
    purpose: str,
    legal_basis: str,
    pii_categories: Optional[List[str]] = None,
    retention_period: str = "",
    data_subjects: Optional[List[str]] = None,
    third_parties: Optional[List[str]] = None,
    transfers_outside_eu: bool = False,
    dpia_required: Optional[bool] = None,
    controller: str = "",
    processor: str = "",
    status: str = "active",
    agent: str = "claude",
) -> Dict[str, Any]:
    if legal_basis not in LEGAL_BASES:
        return {
            "ok": False,
            "error_code": "INVALID_LEGAL_BASIS",
            "message": f"legal_basis debe ser: {', '.join(LEGAL_BASES.keys())}",
        }
    if status not in VALID_STATUS:
        return {
            "ok": False,
            "error_code": "INVALID_STATUS",
            "message": f"status debe ser: {', '.join(VALID_STATUS)}",
        }

    now = utcnow()
    pii_categories = pii_categories or []
    data_subjects = data_subjects or []
    third_parties = third_parties or []

    # DATA_SUBJECTS estaba declarado y nunca se comprobaba. No es cosmético:
    # `minors` es uno de los DPIA_TRIGGERS del GDPR Art. 35, así que escribir
    # "minor" en singular desactivaba el disparador sin que nada lo dijera. El
    # registro que decide una obligación legal tiene que validarse.
    desconocidos = [s for s in data_subjects if s not in DATA_SUBJECTS]
    if desconocidos:
        return {
            "ok": False,
            "error_code": "INVALID_DATA_SUBJECT",
            "message": (
                f"data_subjects fuera del vocabulario: {', '.join(desconocidos)}. "
                f"Válidos: {', '.join(DATA_SUBJECTS)}"
            ),
            "valid_data_subjects": DATA_SUBJECTS,
            "dpia_triggers": DPIA_TRIGGERS,
        }

    # Auto-detect DPIA requirement if not explicitly set
    if dpia_required is None:
        dpia_required = _dpia_auto_required(pii_categories, data_subjects)

    pii_md = (
        "\n".join(
            f"| `{cat}` | {PII_CATEGORIES.get(cat, 'Sin descripción estándar')} |"
            for cat in pii_categories
        )
        or "| — | Sin categorías definidas |"
    )

    subjects_md = ", ".join(data_subjects) or "— No especificados"

    third_md = (
        "\n".join(f"| `{tp}` | — | Pendiente de DPA | — |" for tp in third_parties)
        or "| — | — | — | — |"
    )

    dpia_text = (
        "**Requerida** — iniciar DPIA antes de procesar datos"
        if dpia_required
        else "No requerida (verificar si aplica)"
    )

    body = f"""# Tratamiento de datos: {title}

> ISO/IEC 27701:2019 — Privacy Information Management System
> GDPR Art. 30 — Registro de actividades de tratamiento
> {("GDPR Art. 35 — DPIA requerida" if dpia_required else "GDPR Art. 35 — DPIA no aplicable")}

## Información del tratamiento

| Campo | Valor |
|---|---|
| **Proyecto** | {project} |
| **Propósito** | {purpose} |
| **Base legal** | {LEGAL_BASES[legal_basis]} |
| **Interesados** | {subjects_md} |
| **Retención** | {retention_period or "— Pendiente de definir"} |
| **Responsable** | {controller or "— Pendiente"} |
| **Encargado** | {processor or "— Mismo responsable"} |
| **Status** | {status} |
| **Transferencias fuera UE/EEE** | {"⚠ Sí — documentar mecanismo de transferencia" if transfers_outside_eu else "No"} |
| **DPIA** | {dpia_text} |

## Categorías de datos personales (ISO 27701 §6.9)

| Categoría | Descripción |
|---|---|
{pii_md}

## Terceros receptores (GDPR Art. 30.1.d)

| Tercero | Rol | Data Processing Agreement | País |
|---|---|---|---|
{third_md}

## Derechos de los interesados (GDPR Cap. III)

| Derecho | Mecanismo | SLA |
|---|---|---|
| Acceso (Art. 15) | — Pendiente de implementar — | 30 días |
| Rectificación (Art. 16) | — Pendiente — | 30 días |
| Supresión / Olvido (Art. 17) | — Pendiente — | 30 días |
| Portabilidad (Art. 20) | — Pendiente — | 30 días |
| Oposición (Art. 21) | — Pendiente — | Inmediato |

## Medidas de seguridad técnicas

- [ ] Cifrado en tránsito (TLS 1.2+)
- [ ] Cifrado en reposo (AES-256)
- [ ] Pseudoanonimización donde aplique
- [ ] Control de acceso por roles (RBAC)
- [ ] Registro de accesos a datos personales
- [ ] Política de retención y eliminación automatizada

{f"## DPIA — Data Protection Impact Assessment (Art. 35){chr(10)}{chr(10)}**Estado:** Pendiente de completar antes de iniciar tratamiento.{chr(10)}{chr(10)}- [ ] Descripción sistemática del tratamiento{chr(10)}- [ ] Evaluación de necesidad y proporcionalidad{chr(10)}- [ ] Evaluación de riesgos para los derechos{chr(10)}- [ ] Medidas para abordar los riesgos{chr(10)}- [ ] Consulta previa a la Autoridad de Control (si riesgo alto residual)" if dpia_required else ""}

## Referencias

- ISO/IEC 27701:2019 §6.2.2 — Identify and document purposes
- ISO/IEC 27701:2019 §6.9 — PII principal categories
- GDPR Art. 30 — Records of processing activities
- GDPR Art. 35 — Data protection impact assessment
"""

    norm_refs = compute_norm_refs(FOLDER, body, [])
    fm_lines = [
        "---",
        f"title: {json.dumps(f'Tratamiento: {title}')}",
        f"id: {uuid.uuid4()}",
        f"createdAt: {now}",
        f"updatedAt: {now}",
        f"tags: {json.dumps(['privacy', 'gdpr', 'pii', project, legal_basis])}",
        f"norm_refs: {json.dumps(norm_refs)}",
        f"project: {project}",
        f"legal_basis: {legal_basis}",
        f"pii_categories: {json.dumps(pii_categories)}",
        f"data_subjects: {json.dumps(data_subjects)}",
        f"retention_period: {json.dumps(retention_period)}",
        f"transfers_outside_eu: {json.dumps(transfers_outside_eu)}",
        f"dpia_required: {json.dumps(dpia_required)}",
        *status_frontmatter_lines("vault_privacy_save", status),
        f"iso_standard: ISO/IEC 27701:2019",
        f"gdpr_article: Art. 30",
        f"cia_integrity: high",
        f"cia_availability: medium",
        f"cia_sensitivity: restricted",
        f"agent: {agent}",
        "---",
    ]
    full = "\n".join(fm_lines) + "\n\n" + body

    filename = f"{_slug(project)}-{_slug(title)}.md"
    path = VAULT_ROOT / FOLDER / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_within_vault(path, VAULT_ROOT)
    atomic_write_text(path, full)
    update_section_index("09_Infrastructure")

    return {
        "ok": True,
        **write_report(),
        "path": str(path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "project": project,
        "legal_basis": legal_basis,
        "pii_count": len(pii_categories),
        "dpia_required": dpia_required,
        "transfers_outside_eu": transfers_outside_eu,
        "iso_standard": "ISO/IEC 27701:2019 / GDPR Art. 30",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_privacy_save — Inventario de tratamiento de datos PII (ISO 27701 / GDPR)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Bases legales: {", ".join(LEGAL_BASES.keys())}
Categorías PII: {", ".join(list(PII_CATEGORIES.keys())[:8])}... (y más)

Ejemplos:
  python vault_privacy_save.py --project my-api \\
    --title "Registro de usuarios" \\
    --purpose "Autenticación y gestión de cuenta" \\
    --legal_basis contract \\
    --pii_categories '["email","name","phone"]' \\
    --retention_period "Cuenta activa + 2 años"
""",
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--purpose", required=True)
    parser.add_argument(
        "--legal_basis", required=True, choices=list(LEGAL_BASES.keys())
    )
    parser.add_argument("--pii_categories", default="[]")
    parser.add_argument("--retention_period", default="")
    parser.add_argument("--data_subjects", default="[]")
    parser.add_argument("--third_parties", default="[]")
    parser.add_argument(
        "--transfers_outside_eu", type=lambda x: x.lower() == "true", default=False
    )
    parser.add_argument(
        "--dpia_required", type=lambda x: x.lower() == "true", default=None
    )
    parser.add_argument("--controller", default="")
    parser.add_argument("--processor", default="")
    parser.add_argument("--status", default="active", choices=VALID_STATUS)
    parser.add_argument("--agent", default="claude")

    args = parser.parse_args()
    try:
        pii = json.loads(args.pii_categories)
        subj = json.loads(args.data_subjects)
        thirds = json.loads(args.third_parties)
    except json.JSONDecodeError as e:
        print(
            json.dumps({"ok": False, "error_code": "INVALID_JSON", "message": str(e)})
        )
        return 1

    result = vault_privacy_save(
        project=args.project,
        title=args.title,
        purpose=args.purpose,
        legal_basis=args.legal_basis,
        pii_categories=pii,
        retention_period=args.retention_period,
        data_subjects=subj,
        third_parties=thirds,
        transfers_outside_eu=args.transfers_outside_eu,
        dpia_required=args.dpia_required,
        controller=args.controller,
        processor=args.processor,
        status=args.status,
        agent=args.agent,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_privacy_save"))

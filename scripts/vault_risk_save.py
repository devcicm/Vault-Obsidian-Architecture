#!/usr/bin/env python3
"""
vault_risk_save.py — Registro y tratamiento de riesgos operativos y de seguridad.

Estándar aplicado:
  ISO 31000:2018      — Risk management framework (identificación, análisis, tratamiento)
  ISO/IEC 27005:2022  — Information security risk management (amenazas, vulnerabilidades)

Metodología:
  Risk Score = Likelihood (1–5) × Impact (1–5) → 1–25
  Levels: Low 1–5 | Medium 6–12 | High 13–19 | Critical 20–25

Escribe en: 02_Observability/risks/{project}-{slug}.md

Usage:
    python vault_risk_save.py --project my-api --title "SQL injection en endpoint búsqueda" \\
      --risk_type security --likelihood 3 --impact 5 \\
      --threat "Atacante externo explota input sin sanitizar" \\
      --vulnerability "Parámetro de búsqueda concatenado directamente en query" \\
      --treatment mitigate --controls '["Parametrized queries","WAF rule"]'

    python vault_risk_save.py --project my-api --title "Proveedor cloud cae" \\
      --risk_type operational --likelihood 2 --impact 4 --treatment transfer \\
      --status accepted
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
from vault_norms import compute_norm_refs, status_frontmatter_lines
# Los `*_save` viven en `scripts/`; el paquete se importa desde la raiz.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.frontmatter import Frontmatter  # noqa: E402

FOLDER = "02_Observability/risks"

RISK_TYPES = {
    "security": "Confidencialidad, integridad o disponibilidad de activos de información",
    "operational": "Fallo en procesos, personas, sistemas o eventos externos",
    "financial": "Pérdida económica directa o indirecta",
    "legal": "Incumplimiento regulatorio, contractual o normativo",
    "reputational": "Daño a la imagen o confianza de stakeholders",
    "technical": "Deuda técnica, obsolescencia o dependencias críticas",
}

LIKELIHOOD_LABELS = {
    1: "Raro",
    2: "Improbable",
    3: "Posible",
    4: "Probable",
    5: "Casi certero",
}
IMPACT_LABELS = {
    1: "Negligible",
    2: "Menor",
    3: "Moderado",
    4: "Mayor",
    5: "Catastrófico",
}

VALID_TREATMENTS = ["accept", "mitigate", "transfer", "avoid"]
VALID_STATUS = ["open", "in_treatment", "accepted", "closed"]

TREATMENT_DESC = {
    "accept": "Riesgo aceptado — dentro del apetito de riesgo definido",
    "mitigate": "Controles implementados para reducir probabilidad o impacto",
    "transfer": "Riesgo transferido a tercero (seguro, proveedor, contrato)",
    "avoid": "Actividad eliminada para suprimir el riesgo",
}


def _slug(text: str) -> str:
    # Delega en el slug canónico (`vault_lib.slugify`). La copia que había
    # aquí divergía del resto: unas borraban los acentos, otras los dejaban
    # en el nombre de fichero. Una sola fuente, un solo nombre de nota.
    return slugify_strict(text)[:60]


def _risk_level(score: int) -> str:
    if score <= 5:
        return "Low"
    if score <= 12:
        return "Medium"
    if score <= 19:
        return "High"
    return "Critical"


def _risk_cia(risk_type: str, impact: int) -> Dict[str, str]:
    high = "high" if impact >= 4 else "medium"
    if risk_type == "security":
        return {"integrity": high, "availability": high, "sensitivity": "restricted"}
    if risk_type == "operational":
        return {"integrity": "medium", "availability": high, "sensitivity": "internal"}
    return {"integrity": "medium", "availability": "medium", "sensitivity": "internal"}


def vault_risk_save(
    project: str,
    title: str,
    risk_type: str = "operational",
    likelihood: int = 3,
    impact: int = 3,
    threat: str = "",
    vulnerability: str = "",
    affected_assets: Optional[List[str]] = None,
    treatment: str = "mitigate",
    controls: Optional[List[str]] = None,
    status: str = "open",
    owner: str = "",
    agent: str = "claude",
) -> Dict[str, Any]:
    if risk_type not in RISK_TYPES:
        return {
            "ok": False,
            "error_code": "INVALID_RISK_TYPE",
            "message": f"risk_type debe ser: {', '.join(RISK_TYPES.keys())}",
        }
    if not (1 <= likelihood <= 5):
        return {
            "ok": False,
            "error_code": "INVALID_LIKELIHOOD",
            "message": "likelihood debe ser 1–5",
        }
    if not (1 <= impact <= 5):
        return {
            "ok": False,
            "error_code": "INVALID_IMPACT",
            "message": "impact debe ser 1–5",
        }
    if treatment not in VALID_TREATMENTS:
        return {
            "ok": False,
            "error_code": "INVALID_TREATMENT",
            "message": f"treatment debe ser: {', '.join(VALID_TREATMENTS)}",
        }
    if status not in VALID_STATUS:
        return {
            "ok": False,
            "error_code": "INVALID_STATUS",
            "message": f"status debe ser: {', '.join(VALID_STATUS)}",
        }

    now = utcnow()
    score = likelihood * impact
    level = _risk_level(score)
    cia = _risk_cia(risk_type, impact)
    affected_assets = affected_assets or []
    controls = controls or []

    assets_md = "\n".join(f"- `{a}`" for a in affected_assets) or "— No especificados"
    controls_md = (
        "\n".join(f"- [ ] {c}" for c in controls) or "— Sin controles definidos"
    )

    body = f"""# Riesgo: {title}

> **{level}** — Score {score}/25 (Likelihood {likelihood} × Impact {impact})
> ISO 31000:2018 — Risk management | ISO/IEC 27005:2022 — IS Risk management

## Clasificación

| Campo | Valor |
|---|---|
| **Tipo** | {risk_type} — {RISK_TYPES[risk_type][:60]} |
| **Status** | {status} |
| **Tratamiento** | {treatment} — {TREATMENT_DESC[treatment]} |
| **Propietario** | {owner or "— Sin asignar"} |

## Análisis de riesgo (ISO 31000 §6.4)

| Dimensión | Valor | Descripción |
|---|---|---|
| **Probabilidad** | {likelihood}/5 | {LIKELIHOOD_LABELS[likelihood]} |
| **Impacto** | {impact}/5 | {IMPACT_LABELS[impact]} |
| **Score** | **{score}/25** | **{level}** |

## Amenaza

{threat or "_Pendiente: describir el evento o agente que puede explotar esta vulnerabilidad._"}

## Vulnerabilidad

{vulnerability or "_Pendiente: describir la debilidad que permite que la amenaza se materialice._"}

## Activos afectados

{assets_md}

## Controles de tratamiento (ISO/IEC 27005 §9)

{controls_md}

## Plan de acción

| Acción | Responsable | Fecha límite | Estado |
|---|---|---|---|
| — | — | — | — |

## Métricas de riesgo residual

| Métrica | Pre-tratamiento | Post-tratamiento |
|---|---|---|
| Probabilidad | {likelihood}/5 | — |
| Impacto | {impact}/5 | — |
| Score | {score}/25 | — |
| Nivel | {level} | — |

## Historial de revisiones

| Fecha | Revisor | Cambio |
|---|---|---|
| {now[:10]} | {owner or agent} | Riesgo identificado |

## Referencias

- ISO 31000:2018 §6 — Risk management process
- ISO 31000:2018 §6.4 — Risk analysis
- ISO/IEC 27005:2022 §9 — Information security risk treatment
- ISO/IEC 27005:2022 §8.2 — Threat identification
"""

    norm_refs = compute_norm_refs(FOLDER, body, [])
    fm_lines = Frontmatter()
    fm_lines.set("title", f'Riesgo: {title}')
    fm_lines.set("id", uuid.uuid4())
    fm_lines.set("createdAt", now)
    fm_lines.set("updatedAt", now)
    fm_lines.set("tags", ['risk', project, risk_type, level.lower(), status])
    fm_lines.set("norm_refs", norm_refs)
    fm_lines.set("project", project)
    fm_lines.set("risk_type", risk_type)
    fm_lines.set("likelihood", likelihood)
    fm_lines.set("impact", impact)
    fm_lines.set("score", score)
    fm_lines.set("level", level)
    fm_lines.set("treatment", treatment)
    fm_lines.lineas(status_frontmatter_lines("vault_risk_save", status))
    fm_lines.set("owner", owner, vacio_citado=True)
    fm_lines.set("iso_standard", "ISO 31000:2018")
    fm_lines.set("iso_security_risk", "ISO/IEC 27005:2022")
    fm_lines.set("cia_integrity", cia['integrity'])
    fm_lines.set("cia_availability", cia['availability'])
    fm_lines.set("cia_sensitivity", cia['sensitivity'])
    fm_lines.set("agent", agent)
    full = fm_lines.render() + "\n\n" + body

    filename = f"{_slug(project)}-{_slug(title)}.md"
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
        "project": project,
        "risk_type": risk_type,
        "score": score,
        "level": level,
        "treatment": treatment,
        "status": status,
        "iso_standard": "ISO 31000:2018 / ISO/IEC 27005:2022",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_risk_save — Registra riesgos (ISO 31000:2018 / ISO/IEC 27005:2022)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Tipos de riesgo: {", ".join(RISK_TYPES.keys())}
Tratamientos:   {", ".join(VALID_TREATMENTS)}
Escala:         1=mínimo  5=máximo  (likelihood e impact)

Risk levels:  Low 1-5 | Medium 6-12 | High 13-19 | Critical 20-25

Ejemplos:
  python vault_risk_save.py --project my-api \\
    --title "SQL injection en búsqueda" \\
    --risk_type security --likelihood 3 --impact 5 \\
    --treatment mitigate \\
    --controls '["Parametrized queries","Input validation","WAF"]'

  python vault_risk_save.py --project my-api \\
    --title "Dependencia única en proveedor cloud" \\
    --risk_type operational --likelihood 2 --impact 4 \\
    --treatment transfer --status accepted
""",
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument(
        "--risk_type", default="operational", choices=list(RISK_TYPES.keys())
    )
    parser.add_argument("--likelihood", type=int, default=3, choices=[1, 2, 3, 4, 5])
    parser.add_argument("--impact", type=int, default=3, choices=[1, 2, 3, 4, 5])
    parser.add_argument("--threat", default="")
    parser.add_argument("--vulnerability", default="")
    parser.add_argument("--affected_assets", default="[]")
    parser.add_argument("--treatment", default="mitigate", choices=VALID_TREATMENTS)
    parser.add_argument("--controls", default="[]")
    parser.add_argument("--status", default="open", choices=VALID_STATUS)
    parser.add_argument("--owner", default="")
    parser.add_argument("--agent", default="claude")

    args = parser.parse_args()
    try:
        affected_assets = json.loads(args.affected_assets)
        controls = json.loads(args.controls)
    except json.JSONDecodeError as e:
        print(
            json.dumps({"ok": False, "error_code": "INVALID_JSON", "message": str(e)}, ensure_ascii=False)
        )
        return 1

    result = vault_risk_save(
        project=args.project,
        title=args.title,
        risk_type=args.risk_type,
        likelihood=args.likelihood,
        impact=args.impact,
        threat=args.threat,
        vulnerability=args.vulnerability,
        affected_assets=affected_assets,
        treatment=args.treatment,
        controls=controls,
        status=args.status,
        owner=args.owner,
        agent=args.agent,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_risk_save"))

#!/usr/bin/env python3
"""
vault_env_matrix.py — Documenta la matrix de entornos (dev/staging/prod/dr).

Estándar aplicado:
  ISO/IEC 12207:2017 §6.3.4 — Configuration management (entornos como artefactos)
  ISO 20000-1:2018 §8.5     — Configuration and asset management
  ISO/IEC 27001:2022 A.12   — Operations security (separación de entornos)

Nunca almacena valores de secretos — solo nombres de variables y su clasificación.

Escribe en: 09_Infrastructure/env-matrix/{project}-{env}.md

Usage:
    python vault_env_matrix.py --project my-api --env prod \\
      --services '["api","postgres","redis","celery"]' \\
      --features '{"payments":true,"beta_ui":false,"dark_mode":true}' \\
      --env_vars '["DATABASE_URL","REDIS_URL","STRIPE_SECRET_KEY","JWT_SECRET"]' \\
      --runtime "Node.js 20 LTS" --region "us-east-1"
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
    write_report,
    VAULT_ROOT,
    assert_within_vault,
    atomic_write_text,
    update_section_index,
)
from vault_norms import compute_norm_refs

FOLDER = "09_Infrastructure/env-matrix"

ENV_PROFILES: Dict[str, Dict[str, Any]] = {
    "dev": {
        "label": "Desarrollo",
        "description": "Entorno local de desarrolladores. Datos sintéticos. Sin SLO.",
        "cia_sensitivity": "public",
        "iso_classification": "Development",
        "typical_scale": "1 instancia / docker-compose",
        "data_policy": "Datos de prueba, nunca datos reales",
        "deploy_trigger": "Manual / hot-reload",
    },
    "staging": {
        "label": "Staging / QA",
        "description": "Espejo de producción con datos anonimizados. Validación pre-release.",
        "cia_sensitivity": "internal",
        "iso_classification": "Test",
        "typical_scale": "Misma arquitectura que prod, menor escala",
        "data_policy": "Datos anonimizados o sintéticos. Nunca PII real.",
        "deploy_trigger": "Merge a main / CD automático",
    },
    "prod": {
        "label": "Producción",
        "description": "Entorno de clientes reales. SLOs activos. Acceso restringido.",
        "cia_sensitivity": "restricted",
        "iso_classification": "Production",
        "typical_scale": "Auto-scaling según carga",
        "data_policy": "Datos reales. Cumplimiento GDPR/regulatorio obligatorio.",
        "deploy_trigger": "Manual con aprobación / blue-green",
    },
    "dr": {
        "label": "Disaster Recovery",
        "description": "Réplica de prod en región alternativa. Activa solo en failover.",
        "cia_sensitivity": "restricted",
        "iso_classification": "Production (standby)",
        "typical_scale": "Capacidad reducida — activa en failover",
        "data_policy": "Réplica de producción. Mismas políticas.",
        "deploy_trigger": "Manual — proceso de failover documentado",
    },
    "perf": {
        "label": "Performance / Load Testing",
        "description": "Entorno para pruebas de carga y rendimiento. Datos sintéticos.",
        "cia_sensitivity": "internal",
        "iso_classification": "Test",
        "typical_scale": "Prod-like para pruebas realistas",
        "data_policy": "Datos sintéticos a escala de producción",
        "deploy_trigger": "Manual — antes de releases mayores",
    },
}

SECRET_PREFIXES = (
    "SECRET",
    "KEY",
    "TOKEN",
    "PASSWORD",
    "PASS",
    "CREDENTIAL",
    "PRIVATE",
    "AUTH",
)


#: Alias del slug canónico (ver `vault_lib.slugify`). La versión propia que
#: había aquí borraba los acentos en vez de transliterarlos.
_slug = slugify_strict


def _classify_var(var_name: str) -> str:
    upper = var_name.upper()
    if any(upper.startswith(p) or p in upper for p in SECRET_PREFIXES):
        return "secret"
    if any(x in upper for x in ("URL", "HOST", "PORT", "ENDPOINT", "ADDR")):
        return "connection"
    if any(x in upper for x in ("FEATURE", "FLAG", "ENABLE", "DISABLE")):
        return "feature_flag"
    if any(x in upper for x in ("LOG", "DEBUG", "VERBOSE", "LEVEL")):
        return "logging"
    if any(x in upper for x in ("TIMEOUT", "RETRY", "MAX", "LIMIT", "SIZE")):
        return "tuning"
    return "config"


def vault_env_matrix(
    project: str,
    env: str,
    services: Optional[List[str]] = None,
    features: Optional[Dict[str, bool]] = None,
    env_vars: Optional[List[str]] = None,
    runtime: str = "",
    region: str = "",
    scale: str = "",
    deploy_procedure: str = "",
    rollback_procedure: str = "",
    agent: str = "claude",
) -> Dict[str, Any]:
    if env not in ENV_PROFILES:
        return {
            "ok": False,
            "error_code": "INVALID_ENV",
            "message": f"env debe ser: {', '.join(ENV_PROFILES.keys())}",
        }

    profile = ENV_PROFILES[env]
    now = utcnow()
    services = services or []
    features = features or {}
    env_vars = env_vars or []

    # Classify env vars
    var_groups: Dict[str, List[str]] = {}
    for var in env_vars:
        cls = _classify_var(var)
        var_groups.setdefault(cls, []).append(var)

    services_md = "\n".join(f"- `{s}`" for s in services) or "— Sin servicios definidos"

    features_md = (
        "\n".join(
            f"| `{k}` | {'✓ Activo' if v else '✗ Inactivo'} |"
            for k, v in features.items()
        )
        or "| — | Sin feature flags definidos |"
    )

    def _vars_section(cls: str, emoji: str) -> str:
        vars_list = var_groups.get(cls, [])
        if not vars_list:
            return ""
        return f"\n**{emoji} {cls.replace('_', ' ').capitalize()}:**\n" + "\n".join(
            f"- `{v}`" for v in vars_list
        )

    vars_md = (
        _vars_section("secret", "🔒")
        + _vars_section("connection", "🔗")
        + _vars_section("feature_flag", "🚩")
        + _vars_section("tuning", "⚙️")
        + _vars_section("logging", "📋")
        + _vars_section("config", "📌")
    ) or "— Sin variables documentadas"

    body = f"""# Entorno: {project} — {profile["label"]} ({env.upper()})

> {profile["description"]}
> ISO/IEC 12207:2017 §6.3.4 — Configuration management
> ISO 20000-1:2018 §8.5 — Configuration and asset management
> ISO/IEC 27001:2022 A.12 — Operations security

## Perfil del entorno

| Campo | Valor |
|---|---|
| **Entorno** | {env.upper()} — {profile["label"]} |
| **Clasificación ISO** | {profile["iso_classification"]} |
| **Runtime** | {runtime or "— Pendiente"} |
| **Región / Zona** | {region or "— Pendiente"} |
| **Escala** | {scale or profile["typical_scale"]} |
| **Trigger de deploy** | {profile["deploy_trigger"]} |
| **Política de datos** | {profile["data_policy"]} |
| **Sensibilidad** | {profile["cia_sensitivity"]} |

## Servicios en este entorno

{services_md}

## Feature flags

| Flag | Estado |
|---|---|
{features_md}

## Variables de entorno

> Solo nombres de variables — nunca valores. Los secretos viven en el gestor de secretos.

{vars_md}

## Diferencias respecto a PROD

_Documentar qué es diferente en este entorno vs producción: datos, escala, servicios, timeouts._

## Procedimiento de deploy

{deploy_procedure or "_Pendiente. Usar vault_release_save para documentar el proceso._"}

## Procedimiento de rollback

{rollback_procedure or "_Pendiente. Documentar cómo revertir un deploy en este entorno._"}

## Accesos requeridos

| Recurso | Quién tiene acceso | Cómo solicitar |
|---|---|---|
| — | — | — |

## Checklist de validación post-deploy

- [ ] Health check endpoints responden 200
- [ ] Logs sin errores críticos en primeros 5 min
- [ ] Métricas de latencia dentro de SLO
- [ ] Feature flags en el estado esperado
- [ ] Smoke tests pasando

## Referencias

- ISO/IEC 12207:2017 §6.3.4 — Software configuration management process
- ISO 20000-1:2018 §8.5 — Configuration and asset management
- ISO/IEC 27001:2022 A.12.1 — Operational procedures and responsibilities
"""

    norm_refs = compute_norm_refs(FOLDER, body, [])
    fm_lines = [
        "---",
        f'title: "Entorno: {project} — {profile["label"]} ({env.upper()})"',
        f"id: {uuid.uuid4()}",
        f"createdAt: {now}",
        f"updatedAt: {now}",
        f"tags: {json.dumps(['environment', 'infrastructure', project, env])}",
        f"norm_refs: {json.dumps(norm_refs)}",
        f"project: {project}",
        f"env: {env}",
        f"env_label: {profile['label']}",
        f"runtime: {runtime}",
        f"region: {region}",
        f"iso_classification: {profile['iso_classification']}",
        f"iso_standard: ISO 20000-1:2018 §8.5",
        f"cia_integrity: high",
        f"cia_availability: high",
        f"cia_sensitivity: {profile['cia_sensitivity']}",
        f"agent: {agent}",
        "---",
    ]
    full = "\n".join(fm_lines) + "\n\n" + body

    filename = f"{_slug(project)}-{env}.md"
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
        "env": env,
        "env_label": profile["label"],
        "services_count": len(services),
        "features_count": len(features),
        "vars_count": len(env_vars),
        "vars_classified": {k: len(v) for k, v in var_groups.items()},
        "iso_standard": "ISO 20000-1:2018 §8.5 / ISO/IEC 12207:2017 §6.3.4",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_env_matrix — Documenta matrix de entornos (ISO 20000-1 / ISO 12207)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Entornos disponibles: {", ".join(ENV_PROFILES.keys())}

Ejemplos:
  python vault_env_matrix.py --project my-api --env prod \\
    --services '["api","postgres","redis"]' \\
    --features '{{"payments":true,"beta_ui":false}}' \\
    --env_vars '["DATABASE_URL","STRIPE_SECRET_KEY","JWT_SECRET"]' \\
    --runtime "Node.js 20 LTS" --region "us-east-1"
""",
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--env", required=True, choices=list(ENV_PROFILES.keys()))
    parser.add_argument("--services", default="[]")
    parser.add_argument("--features", default="{}")
    parser.add_argument("--env_vars", default="[]")
    parser.add_argument("--runtime", default="")
    parser.add_argument("--region", default="")
    parser.add_argument("--scale", default="")
    parser.add_argument("--deploy_procedure", default="")
    parser.add_argument("--rollback_procedure", default="")
    parser.add_argument("--agent", default="claude")

    args = parser.parse_args()
    try:
        services = json.loads(args.services)
        features = json.loads(args.features)
        env_vars = json.loads(args.env_vars)
    except json.JSONDecodeError as e:
        print(
            json.dumps({"ok": False, "error_code": "INVALID_JSON", "message": str(e)})
        )
        return 1

    result = vault_env_matrix(
        project=args.project,
        env=args.env,
        services=services,
        features=features,
        env_vars=env_vars,
        runtime=args.runtime,
        region=args.region,
        scale=args.scale,
        deploy_procedure=args.deploy_procedure,
        rollback_procedure=args.rollback_procedure,
        agent=args.agent,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_env_matrix"))

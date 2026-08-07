#!/usr/bin/env python3
"""
vault_release_save.py — Documenta releases y deploys de producción.

Estándar aplicado:
  ISO/IEC 12207:2017 §6.3.7 — Software release management process
  ISO 20000-1:2018 §8.5.2   — Change and release management
  ISO/IEC 25010:2023 §4.5   — Maintainability (deployability)

Crea o actualiza el changelog del proyecto y genera la nota de release.
Escribe en:
  08_Runbooks/deploy/{project}-release-{version}.md   ← procedimiento
  01_Projects/{project}/changelog.md                   ← histórico de versiones

Usage:
    python vault_release_save.py --project my-api --version v1.2.0 \\
      --type minor --status planned \\
      --changes '["feat: nuevo endpoint /health","fix: timeout en checkout"]' \\
      --deploy_steps '["npm run build","docker push","kubectl rollout"]' \\
      --smoke_tests '["GET /health → 200","POST /checkout → 201"]'
"""

import argparse
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import wrap_main
from vault_lib import slugify_strict, utcnow
from vault_io import assert_within_vault, atomic_write_text, file_lock, get_vault_root, update_section_index, write_report
from vault_norms import compute_norm_refs, status_frontmatter_lines

RELEASE_FOLDER = "08_Runbooks/deploy"
CHANGELOG_PATH = "01_Projects/{project}/changelog.md"

RELEASE_TYPES: Dict[str, str] = {
    "major": "Cambio incompatible de API o arquitectura significativa",
    "minor": "Nueva funcionalidad compatible con versiones anteriores",
    "patch": "Corrección de bugs sin cambios de API",
    "hotfix": "Corrección urgente de bug crítico en producción",
    "rollback": "Reversión a versión anterior por incidente",
}

VALID_STATUS = ["planned", "in_progress", "deployed", "rolled_back", "cancelled"]


def _slug(text: str) -> str:
    # Delega en el slug canónico (`vault_lib.slugify`). La copia que había
    # aquí divergía del resto: unas borraban los acentos, otras los dejaban
    # en el nombre de fichero. Una sola fuente, un solo nombre de nota.
    return slugify_strict(text)


def _semver_parts(version: str):
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", version)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return 0, 0, 0


def vault_release_save(
    project: str,
    version: str,
    release_type: str = "minor",
    status: str = "planned",
    changes: Optional[List[str]] = None,
    deploy_steps: Optional[List[str]] = None,
    rollback_steps: Optional[List[str]] = None,
    smoke_tests: Optional[List[str]] = None,
    breaking_changes: Optional[List[str]] = None,
    migrations: Optional[List[str]] = None,
    deploy_at: Optional[str] = None,
    agent: str = "claude",
) -> Dict[str, Any]:
    if release_type not in RELEASE_TYPES:
        return {
            "ok": False,
            "error_code": "INVALID_RELEASE_TYPE",
            "message": f"type debe ser: {', '.join(RELEASE_TYPES.keys())}",
        }
    if status not in VALID_STATUS:
        return {
            "ok": False,
            "error_code": "INVALID_STATUS",
            "message": f"status debe ser: {', '.join(VALID_STATUS)}",
        }

    now = utcnow()
    deploy_at = deploy_at or now
    changes = changes or []
    deploy_steps = deploy_steps or []
    rollback_steps = rollback_steps or []
    smoke_tests = smoke_tests or []
    breaking_changes = breaking_changes or []
    migrations = migrations or []

    changes_md = "\n".join(f"- {c}" for c in changes) or "— Sin cambios documentados"
    breaking_md = (
        "\n".join(f"- **BREAKING**: {c}" for c in breaking_changes)
        or "— Sin breaking changes"
    )
    migrations_md = (
        "\n".join(f"- [ ] {m}" for m in migrations) or "— Sin migraciones requeridas"
    )
    smoke_md = (
        "\n".join(f"- [ ] {t}" for t in smoke_tests) or "— Sin smoke tests definidos"
    )

    def _steps_md(steps: List[str]) -> str:
        return (
            "\n".join(f"{i}. `{s}`" for i, s in enumerate(steps, 1))
            or "— Sin pasos documentados"
        )

    body = f"""# Release {version} — {project}

> **Tipo:** {release_type} — {RELEASE_TYPES[release_type]}
> ISO/IEC 12207:2017 §6.3.7 — Release management
> ISO 20000-1:2018 §8.5.2 — Change and release management

## Estado del release

| Campo | Valor |
|---|---|
| **Versión** | {version} |
| **Tipo** | {release_type} |
| **Status** | {status} |
| **Deploy planificado** | {deploy_at} |
| **ISO process** | ISO/IEC 12207:2017 §6.3.7 |

## Cambios incluidos

{changes_md}

## Breaking changes

{breaking_md}

## Migraciones requeridas

{migrations_md}

## Procedimiento de deploy

{_steps_md(deploy_steps)}

## Smoke tests post-deploy

{smoke_md}

## Procedimiento de rollback

{_steps_md(rollback_steps) if rollback_steps else "_Pendiente: documentar cómo revertir este release._"}

## Checklist pre-deploy

- [ ] Tests pasando en staging
- [ ] Migraciones de BD revisadas y testadas
- [ ] Feature flags configurados correctamente
- [ ] Backups de BD tomados
- [ ] On-call informado del deploy
- [ ] Ventana de mantenimiento comunicada (si aplica)
- [ ] Rollback procedure validada en staging

## Checklist post-deploy

- [ ] Smoke tests pasando
- [ ] Error rate dentro de SLO (primeros 15 min)
- [ ] Latencia dentro de SLO (primeros 15 min)
- [ ] Logs sin errores críticos
- [ ] Alertas silenciadas durante deploy re-activadas
- [ ] Comunicación enviada al equipo

## Referencias

- ISO/IEC 12207:2017 §6.3.7 — Software release management process
- ISO 20000-1:2018 §8.5.2 — Change and release management
- ISO/IEC 25010:2023 §4.5 — Maintainability / Deployability
"""

    norm_refs = compute_norm_refs(RELEASE_FOLDER, body, [])
    version_slug = _slug(version)
    fm_lines = [
        "---",
        f'title: "Release {version} — {project}"',
        f"id: {uuid.uuid4()}",
        f"createdAt: {now}",
        f"updatedAt: {now}",
        f"tags: {json.dumps(['release', 'deploy', project, release_type, version])}",
        f"norm_refs: {json.dumps(norm_refs)}",
        f"project: {project}",
        f"version: {version}",
        f"release_type: {release_type}",
        *status_frontmatter_lines("vault_release_save", status),
        f"deploy_at: {deploy_at}",
        f"breaking_changes: {json.dumps(bool(breaking_changes))}",
        f"migrations_required: {json.dumps(bool(migrations))}",
        f"iso_standard: ISO 20000-1:2018 §8.5.2",
        f"cia_integrity: high",
        f"cia_availability: high",
        f"cia_sensitivity: internal",
        f"agent: {agent}",
        "---",
    ]
    full = "\n".join(fm_lines) + "\n\n" + body

    # Write runbook
    filename = f"{_slug(project)}-release-{version_slug}.md"
    path = get_vault_root() / RELEASE_FOLDER / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_within_vault(path, get_vault_root())
    atomic_write_text(path, full)

    # Update project changelog
    changelog_rel = CHANGELOG_PATH.format(project=project)
    changelog_path = get_vault_root() / changelog_rel
    changelog_path.parent.mkdir(parents=True, exist_ok=True)

    changelog_entry = f"\n### {version} — {deploy_at[:10]} ({release_type})\n\n"
    changelog_entry += changes_md + "\n"
    if breaking_changes:
        changelog_entry += "\n**Breaking changes:**\n" + breaking_md + "\n"

    with file_lock(changelog_path, timeout=10):
        if changelog_path.exists():
            existing = changelog_path.read_text(encoding="utf-8", errors="replace")
            if version not in existing:
                parts = existing.split("\n\n", 1)
                updated = (
                    parts[0]
                    + "\n"
                    + changelog_entry
                    + ("\n\n" + parts[1] if len(parts) > 1 else "")
                )
                atomic_write_text(changelog_path, updated)
        else:
            changelog_header = f"""# {project} — Changelog

> Historial de versiones del proyecto.
> ISO/IEC 12207:2017 §6.3.7 — Release management

"""
            atomic_write_text(changelog_path, changelog_header + changelog_entry)

    update_section_index("08_Runbooks")
    update_section_index("01_Projects")

    return {
        "ok": True,
        **write_report(),
        "path": str(path.relative_to(get_vault_root())).replace("\\", "/"),
        "changelog": changelog_rel,
        "project": project,
        "version": version,
        "release_type": release_type,
        "status": status,
        "changes_count": len(changes),
        "breaking_changes": bool(breaking_changes),
        "migrations_required": bool(migrations),
        "iso_standard": "ISO 20000-1:2018 §8.5.2 / ISO/IEC 12207:2017 §6.3.7",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_release_save — Documenta releases de producción (ISO 20000-1 / ISO 12207)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Tipos: {", ".join(RELEASE_TYPES.keys())}

Ejemplos:
  python vault_release_save.py --project my-api --version v1.2.0 --type minor \\
    --changes '["feat: endpoint /health","fix: timeout checkout"]' \\
    --deploy_steps '["npm run build","docker push","kubectl rollout"]' \\
    --smoke_tests '["GET /health → 200","GET /api/v1/products → 200"]'
""",
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--type",
        dest="release_type",
        default="minor",
        choices=list(RELEASE_TYPES.keys()),
    )
    parser.add_argument("--status", default="planned", choices=VALID_STATUS)
    parser.add_argument("--changes", default="[]")
    parser.add_argument("--deploy_steps", default="[]")
    parser.add_argument("--rollback_steps", default="[]")
    parser.add_argument("--smoke_tests", default="[]")
    parser.add_argument("--breaking_changes", default="[]")
    parser.add_argument("--migrations", default="[]")
    parser.add_argument("--deploy_at", default=None)
    parser.add_argument("--agent", default="claude")

    args = parser.parse_args()
    try:
        changes = json.loads(args.changes)
        deploy_steps = json.loads(args.deploy_steps)
        rollback_steps = json.loads(args.rollback_steps)
        smoke_tests = json.loads(args.smoke_tests)
        breaking = json.loads(args.breaking_changes)
        migrations = json.loads(args.migrations)
    except json.JSONDecodeError as e:
        print(
            json.dumps({"ok": False, "error_code": "INVALID_JSON", "message": str(e)})
        )
        return 1

    result = vault_release_save(
        project=args.project,
        version=args.version,
        release_type=args.release_type,
        status=args.status,
        changes=changes,
        deploy_steps=deploy_steps,
        rollback_steps=rollback_steps,
        smoke_tests=smoke_tests,
        breaking_changes=breaking,
        migrations=migrations,
        deploy_at=args.deploy_at,
        agent=args.agent,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_release_save"))

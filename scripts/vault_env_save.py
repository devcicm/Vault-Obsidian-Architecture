#!/usr/bin/env python3
"""
Vault Env Save Tool — Document environment variables by project and environment

Saves or updates 01_Projects/{slug}/envs.md with environment variable documentation.
Never stores real values — only structure, purpose, and management metadata.

Usage:
    python vault_env_save.py --project "ans" --environment "production" --vars '[{"name":"DATABASE_URL","description":"Connection string","required":true,"sensitive":true,"provider":"k8s-secret"},{"name":"PORT","description":"Server port","required":true,"default":"3000","sensitive":false,"provider":"env-file"}]'
    python vault_env_save.py --project "ans" --environment "dev" --description "Development environment" --vars '[{"name":"DEBUG","description":"Enable debug mode","required":false,"default":"false","sensitive":false,"provider":"env-file"}]'
"""

import argparse
import json
import re
import sys
from vault_errors import wrap_main
from vault_io import atomic_write_text, assert_within_vault, VAULT_ROOT
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

PROJECTS_DIR = VAULT_ROOT / "01_Projects"

PROVIDERS = ["env-file", "k8s-secret", "vault", "ci-secrets", "manual"]
KNOWN_ENVIRONMENTS = ["dev", "staging", "production", "test", "ci"]


def slugify(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


def parse_envs_file(content: str) -> Dict[str, Any]:
    envs: Dict[str, List[Dict]] = {}
    current_env = None

    for line in content.split("\n"):
        env_match = re.match(r"^## (\w+)$", line.strip())
        if env_match:
            current_env = env_match.group(1)
            envs[current_env] = []
            continue

        row_match = re.match(r"^\| `([^`]+)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|", line.strip())
        if row_match and current_env:
            envs[current_env].append(
                {
                    "name": row_match.group(1).strip(),
                    "description": row_match.group(2).strip(),
                    "required": "✓" in row_match.group(3),
                    "default": row_match.group(4).strip().replace("🔒 (secreto)", "").strip(),
                    "sensitive": "🔒" in row_match.group(5),
                    "provider": row_match.group(6).strip(),
                }
            )

    return envs


def generate_envs_table(vars_list: List[Dict]) -> str:
    header = "| Nombre | Descripción | Requerida | Default | Sensible | Proveedor |\n|---|---|---|---|---|---|\n"
    rows = []
    for v in vars_list:
        name_cell = f"`{v.get('name', '')}`"
        desc_cell = v.get("description", "")
        required_cell = "✓" if v.get("required") else "—"
        default_cell = f"`{v.get('default', '')}`" if v.get("default") and not v.get("sensitive") else "🔒 (secreto)"
        sensitive_cell = "🔒" if v.get("sensitive") else "—"
        provider_cell = v.get("provider", "manual")
        rows.append(
            f"| {name_cell} | {desc_cell} | {required_cell} | {default_cell} | {sensitive_cell} | {provider_cell} |"
        )
    return header + "\n".join(rows) + "\n"


def vault_env_save(
    project: str,
    environment: str,
    vars: List[Dict[str, Any]],
    description: Optional[str] = None,
) -> Dict[str, Any]:
    for v in vars:
        if v.get("provider") and v["provider"] not in PROVIDERS:
            return {"ok": False, "error": f"Provider inválido: {v['provider']}. Válidos: {PROVIDERS}"}

    safe_project = slugify(project)
    project_dir = PROJECTS_DIR / safe_project
    project_dir.mkdir(parents=True, exist_ok=True)

    envs_path = project_dir / "envs.md"
    timestamp = _utcnow()

    existing_envs: Dict[str, List[Dict]] = {}
    existing_description = ""

    if envs_path.exists():
        with open(envs_path, "r", encoding="utf-8") as f:
            content = f.read()

        frontmatter_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        if frontmatter_match:
            for line in frontmatter_match.group(1).split("\n"):
                if line.startswith("description:"):
                    existing_description = line.split(":", 1)[1].strip().strip("\"'")

        existing_envs = parse_envs_file(content)
        existing_description = existing_description or description or ""

    final_description = description or existing_description

    try:
        assert_within_vault(envs_path, VAULT_ROOT)
    except ValueError as exc:
        return {"ok": False, "error_code": "INVALID_PATH", "error": "INVALID_PATH", "message": str(exc)}

    frontmatter = ["---"]
    frontmatter.append(f"title: Environment Variables - {project}")
    frontmatter.append(f"project: {project}")
    frontmatter.append(f"type: envs")
    frontmatter.append(f"updatedAt: {timestamp}")
    if final_description:
        frontmatter.append(f"description: {final_description}")
    frontmatter.append(f"cia_integrity: high")
    frontmatter.append(f"cia_availability: medium")
    frontmatter.append(f"cia_sensitivity: restricted")
    frontmatter.append(f"agent: system")
    frontmatter.append("---")

    body = [f"# Environment Variables: {project}\n"]
    if final_description:
        body.append(f"_{final_description}_\n")

    processed_envs = dict(existing_envs)
    processed_envs[environment] = vars

    # Render known environments first in canonical order, then any others
    ordered_envs = [e for e in KNOWN_ENVIRONMENTS if e in processed_envs]
    extra_envs = [e for e in processed_envs if e not in KNOWN_ENVIRONMENTS]
    for env_name in ordered_envs + extra_envs:
        body.append(f"## {env_name}\n")
        body.append(generate_envs_table(processed_envs[env_name]))
        body.append("")

    atomic_write_text(envs_path, "\n".join(frontmatter) + "\n\n" + "\n".join(body))

    return {
        "ok": True,
        "path": str(envs_path.relative_to(VAULT_ROOT)),
        "environment": environment,
        "varCount": len(vars),
        "message": f"envs.md updated with {len(vars)} variables for {environment}",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Env Save Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_env_save.py --project "ans" --environment "production" --vars '[{"name":"DATABASE_URL","description":"Connection string","required":true,"sensitive":true,"provider":"k8s-secret"}]'
  python vault_env_save.py --project "ans" --environment "dev" --description "Development environment" --vars '[{"name":"DEBUG","description":"Enable debug mode","required":false,"default":"false","sensitive":false,"provider":"env-file"}]'
  python vault_env_save.py --project "mi-api" --environment "staging" --vars '[{"name":"PORT","description":"Server port","required":true,"default":"3000","sensitive":false,"provider":"env-file"}]'
  python vault_env_save.py --project "backend" --environment "ci" --vars '[{"name":"CI_TOKEN","description":"CI token","required":true,"sensitive":true,"provider":"ci-secrets"}]'

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Nunca almacena valores reales -- solo estructura, proposito y metadata de gestion
  - Ambientes conocidos: dev, staging, production, test, ci (cualquier nombre custom tambien es valido)
""",
    )
    parser.add_argument("--project", required=True, help="Project slug")
    parser.add_argument("--environment", required=True, help="Environment name (dev, staging, production, test, ci, or any custom name)")
    parser.add_argument("--vars", required=True, help="Variables as JSON array")
    parser.add_argument("--description", help="Environment description")

    args = parser.parse_args()

    try:
        vars_list = json.loads(args.vars)
    except json.JSONDecodeError:
        print(json.dumps({"ok": False, "error": "Invalid JSON in --vars"}))
        return 1

    result = vault_env_save(args.project, args.environment, vars_list, args.description)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_env_save"))

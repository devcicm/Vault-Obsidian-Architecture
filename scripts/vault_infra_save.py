#!/usr/bin/env python3

"""

Vault Infra Save Tool — Save infrastructure components



Saves infrastructure components and auto-generates network map Mermaid diagram.

Components stored in 09_Infrastructure/ subfolders by type.



Usage:

    python vault_infra_save.py --name "proxmox-main" --type "server" --description "Main Proxmox host" --config '{"ip":"192.168.1.10","os":"Proxmox VE 8.1","cpu":"32 cores","ram":"128 GB"}' --location "homelab"

    python vault_infra_save.py --name "postgres-primary" --type "database" --config '{"ip":"192.168.1.30","port":5432,"version":"16"}' --location "homelab" --connections '[{"to":"app-backend","protocol":"TCP","port":5432}]'

"""

import argparse

import json

import re

import sys

from vault_errors import wrap_main
from vault_norms import status_frontmatter_lines
from vault_lib import slugify_strict, utcnow
from datetime import datetime, timezone
from vault_io import (
    write_report,
    atomic_write_text,
    atomic_write_json,
    assert_within_vault,
    VAULT_ROOT,
)
import uuid

from pathlib import Path


from typing import Any, Dict, List, Optional


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


INFRA_DIR = VAULT_ROOT / "09_Infrastructure"

INDEX_FILE = INFRA_DIR / ".infra-index.json"


COMPONENT_TYPES = {
    "server": "servers",
    "vm": "servers",
    "container": "containers",
    "service": "services",
    "database": "databases",
    "queue": "databases",
    "storage": "databases",
    "proxy": "network",
    "loadbalancer": "network",
    "network": "network",
    "firewall": "network",
    "cdn": "network",
    "pipeline": "pipelines",
    "secret": "secrets",
}


LOCATIONS = [
    "local",
    "homelab",
    "vps",
    "cloud-aws",
    "cloud-gcp",
    "cloud-azure",
    "cloud-other",
    "datacenter",
    "hybrid",
]


TYPE_SHAPES = {
    "server": "🖥️ {name}\n{ip}\n{os}",
    "vm": "🖥️ {name}\n{ip}",
    "container": "📦 {name}\n{version}",
    "service": "⚙️ {name}\n:{port}",
    "database": '("{name}\n:{port})',
    "queue": '("{name}\n:{port})',
    "storage": '("{name})',
    "proxy": "[/{name}\n:{port}/]",
    "loadbalancer": "[/{name}]",
    "network": "{{{name}}}",
    "firewall": "{{{name}}}",
    "cdn": "[{name}]",
}


def slugify(text: str) -> str:
    # Delega en el slug canónico (`vault_lib.slugify`). La copia que había
    # aquí divergía del resto: unas borraban los acentos, otras los dejaban
    # en el nombre de fichero. Una sola fuente, un solo nombre de nota.
    return slugify_strict(text)


def load_index() -> Dict[str, Any]:
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "locations" not in data:
                data["locations"] = {}
            return data

    except (FileNotFoundError, json.JSONDecodeError):
        return {"components": [], "locations": {}}


def save_index(data: Dict[str, Any]) -> None:
    INFRA_DIR.mkdir(parents=True, exist_ok=True)

    atomic_write_json(INDEX_FILE, data)


def generate_infra_map(
    components: List[Dict],
    project: Optional[str] = None,
    location: Optional[str] = None,
) -> str:
    if project:
        components = [
            c for c in components if c.get("project", "").lower() == project.lower()
        ]

    if location:
        components = [c for c in components if c.get("location", "") == location]

    by_location: Dict[str, List[Dict]] = {}

    for comp in components:
        loc = comp.get("location", "unknown")

        if loc not in by_location:
            by_location[loc] = []

        by_location[loc].append(comp)

    lines = ["graph LR"]

    for loc, comps in sorted(by_location.items()):
        loc_label = loc.replace("-", " ").title()

        lines.append(f'    subgraph {loc}["🏠 {loc_label}"]')

        for comp in comps:
            name = slugify(comp["name"])

            ctype = comp.get("type", "service")

            config = comp.get("config", {})

            ip = config.get("ip", "")

            port = config.get("port", "")

            os_val = config.get("os", "")

            version = config.get("version", "")

            shape_template = TYPE_SHAPES.get(ctype, '"{name}"')

            node_content = shape_template.format(
                name=comp["name"],
                ip=ip,
                port=port,
                os=os_val,
                version=version,
            )

            lines.append(f"        {name}{node_content}")

        lines.append("    end")

    connections_added = set()

    for comp in components:
        for conn in comp.get("connections", []):
            from_name = slugify(comp["name"])

            to_name = slugify(conn.get("to", ""))

            protocol = conn.get("protocol", "TCP")

            port = conn.get("port", "")

            edge = (from_name, to_name)

            if edge not in connections_added:
                lines.append(f'    {from_name} -->|"{protocol}:{port}"| {to_name}')

                connections_added.add(edge)

    return "\n".join(lines)


def save_infra_map(
    components: List[Dict],
    project: Optional[str] = None,
    location: Optional[str] = None,
) -> Path:
    mermaid_content = generate_infra_map(components, project, location)

    map_path = INFRA_DIR / "infra-map.md"

    frontmatter = ["---"]

    frontmatter.append("title: Infrastructure Map")

    frontmatter.append(f"updatedAt: {utcnow()}")

    if project:
        frontmatter.append(f"project: {project}")

    if location:
        frontmatter.append(f"location: {location}")

    frontmatter.append("---")

    frontmatter.append("\n## Network Map\n\n```mermaid\n" + mermaid_content + "\n```\n")

    atomic_write_text(map_path, "\n".join(frontmatter))

    return map_path


def vault_infra_save(
    name: str,
    type: str,
    description: str,
    config: Dict[str, Any],
    connections: Optional[List[Dict[str, Any]]] = None,
    location: str = "local",
    project: Optional[str] = None,
    status: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    component_type = type.lower()

    if component_type not in COMPONENT_TYPES:
        return {
            "ok": False,
            "error": f"Tipo inválido: {type}. Válidos: {list(COMPONENT_TYPES.keys())}",
        }

    if location not in LOCATIONS:
        return {
            "ok": False,
            "error": f"Ubicación inválida: {location}. Válidas: {LOCATIONS}",
        }

    folder = INFRA_DIR / COMPONENT_TYPES[component_type]

    safe_name = slugify(name)

    filename = f"{safe_name}.md"

    note_path = folder / filename

    timestamp = utcnow()

    try:
        assert_within_vault(note_path, VAULT_ROOT)

    except ValueError as exc:
        return {
            "ok": False,
            "error_code": "INVALID_PATH",
            "error": "INVALID_PATH",
            "message": str(exc),
        }

    cia_sensitivity = "restricted" if component_type == "secret" else "internal"

    cia_integrity = (
        "high" if component_type in ("server", "database", "secret") else "medium"
    )

    frontmatter = ["---"]

    frontmatter.append(f"title: {name}")

    frontmatter.append(f"id: {str(uuid.uuid4())}")

    frontmatter.append(f"type: {component_type}")

    frontmatter.append(f"location: {location}")

    frontmatter.append(f"createdAt: {timestamp}")

    frontmatter.append(f"updatedAt: {timestamp}")

    if project:
        frontmatter.append(f"project: {project}")

    if status:
        frontmatter.extend(status_frontmatter_lines("vault_infra_save", status))

    if tags:
        frontmatter.append(f"tags: {json.dumps(tags)}")

    frontmatter.append(f"cia_integrity: {cia_integrity}")

    frontmatter.append(f"cia_availability: high")

    frontmatter.append(f"cia_sensitivity: {cia_sensitivity}")

    frontmatter.append(f"agent: system")

    frontmatter.append("---")

    body_sections = [f"## Descripción\n\n{description}\n"]

    if component_type == "secret":
        provider = config.get("provider", "N/A")

        scope = config.get("scope", "N/A")

        rotation = config.get("rotation_policy", "N/A")

        owner = config.get("owner", "N/A")

        body_sections.append(f"""## Secreto — Metadatos



| Campo | Valor |

|---|---|

| Proveedor | {provider} |

| Scope | {scope} |

| Política de rotación | {rotation} |

| Owner | {owner} |



> **Nota:** El valor real del secreto nunca se documenta aquí.

""")

    elif component_type == "pipeline":
        platform = config.get("platform", "N/A")

        stages = config.get("stages", [])

        triggers = config.get("trigger", "N/A")

        artifact = config.get("artifact", "N/A")

        body_sections.append(f"""## Pipeline CI/CD



| Campo | Valor |

|---|---|

| Plataforma | {platform} |

| Triggers | {triggers} |

| Artefacto | {artifact} |



**Etapas:**

""")

        if isinstance(stages, list):
            for stage in stages:
                body_sections.append(f"- {stage}")

    else:
        config_content = ["## Configuración\n"]

        for key, value in config.items():
            config_content.append(f"- **{key}**: `{value}`")

        body_sections.append("\n".join(config_content))

    if connections:
        conn_content = ["## Conexiones\n"]

        for conn in connections:
            to = conn.get("to", "")

            protocol = conn.get("protocol", "")

            port = conn.get("port", "")

            desc = conn.get("description", "")

            conn_content.append(f"- → **{to}** ({protocol}:{port})")

            if desc:
                conn_content.append(f"  - {desc}")

        body_sections.append("\n".join(conn_content))

    final_content = "\n".join(frontmatter) + "\n\n" + "\n\n".join(body_sections)

    folder.mkdir(parents=True, exist_ok=True)

    atomic_write_text(note_path, final_content)

    index = load_index()

    new_component = {
        "id": str(uuid.uuid4()),
        "name": name,
        "type": component_type,
        "location": location,
        "config": config,
        "connections": connections or [],
        "project": project,
        "status": status,
        "updatedAt": timestamp,
    }

    for i, comp in enumerate(index["components"]):
        if slugify(comp["name"]) == safe_name:
            index["components"][i] = new_component

            break

    else:
        index["components"].append(new_component)

    if location not in index["locations"]:
        index["locations"][location] = []

    if name not in index["locations"][location]:
        index["locations"][location].append(name)

    save_index(index)

    map_path = save_infra_map(index["components"], project, location)

    return {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "type": component_type,
        "infraMapUpdated": True,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Infra Save Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_infra_save.py --name "proxmox-main" --type "server" --description "Main Proxmox host" --config '{"ip":"192.168.1.10","os":"Proxmox VE 8.1"}' --location "homelab"

  python vault_infra_save.py --name "postgres-primary" --type "database" --config '{"ip":"192.168.1.30","port":5432}' --location "homelab" --connections '[{"to":"app-backend","protocol":"TCP","port":5432}]'

  python vault_infra_save.py --name "api-gateway" --type "proxy" --config '{"ip":"10.0.0.1","port":443}' --location "cloud-aws" --project "mi-api"

  python vault_infra_save.py --name "redis-cache" --type "service" --config '{"ip":"10.0.0.5","port":6379}' --location "local" --status "active"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Actualiza automaticamente el mapa de infraestructura (infra-map.md)

  - Ubicaciones validas: local, homelab, vps, cloud-aws, cloud-gcp, cloud-azure, datacenter, hybrid

""",
    )

    parser.add_argument("--name", required=True, help="Component name")

    parser.add_argument(
        "--type", required=True, help=f"Component type: {list(COMPONENT_TYPES.keys())}"
    )

    parser.add_argument("--description", required=True, help="Component description")

    parser.add_argument("--config", required=True, help="Config as JSON object")

    parser.add_argument("--connections", help="Connections as JSON array")

    parser.add_argument("--location", default="local", help=f"Location: {LOCATIONS}")

    parser.add_argument("--project", help="Optional project")

    parser.add_argument("--status", help="Component status")

    parser.add_argument("--tags", nargs="*", help="Tags")

    args = parser.parse_args()

    try:
        config = json.loads(args.config)

    except json.JSONDecodeError:
        return {"ok": False, "error": "Invalid JSON in --config"}

    connections = None

    if args.connections:
        try:
            connections = json.loads(args.connections)

        except json.JSONDecodeError:
            return {"ok": False, "error": "Invalid JSON in --connections"}

    result = vault_infra_save(
        args.name,
        args.type,
        args.description,
        config,
        connections,
        args.location,
        args.project,
        args.status,
        args.tags,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_infra_save"))

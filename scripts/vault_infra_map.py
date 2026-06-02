#!/usr/bin/env python3
"""
Vault Infra Map Tool — Regenerate infrastructure Mermaid map

Regenerates the infrastructure map from .infra-index.json.
Can filter by project or location for partial maps.

Usage:
    python vault_infra_map.py
    python vault_infra_map.py --project "ans"
    python vault_infra_map.py --location "homelab"
"""

import argparse
import json
import re
import sys
from vault_errors import wrap_main
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

from vault_io import VAULT_ROOT
INFRA_DIR = VAULT_ROOT / "09_Infrastructure"
INDEX_FILE = INFRA_DIR / ".infra-index.json"

LOCATIONS = ["local", "homelab", "vps", "cloud-aws", "cloud-gcp", "cloud-azure", "cloud-other", "datacenter", "hybrid"]

TYPE_SHAPES = {
    "server": "🖥️ {name}\n{ip}\n{os}",
    "vm": "🖥️ {name}\n{ip}",
    "container": "📦 {name}\n{version}",
    "service": "⚙️ {name}\n:{port}",
    "database": '("{name}\n:{port})',
    "queue": '("{name}\n:{port})',
    "storage": '("{name}")',
    "proxy": "[/{name}\n:{port}/]",
    "loadbalancer": "[/{name}]",
    "network": "{{{name}}}",
    "firewall": "{{{name}}}",
    "cdn": "[{name}]",
}


def slugify(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


def load_index() -> Dict[str, Any]:
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"components": [], "locations": {}}


def generate_infra_map(components: List[Dict], project: Optional[str] = None, location: Optional[str] = None) -> str:
    if project:
        components = [c for c in components if c.get("project", "").lower() == project.lower()]
    if location:
        components = [c for c in components if c.get("location", "") == location]

    if not components:
        return "graph LR\n    empty[No components found]"

    by_location: Dict[str, List[Dict]] = {}
    for comp in components:
        loc = comp.get("location", "unknown")
        if loc not in by_location:
            by_location[loc] = []
        by_location[loc].append(comp)

    lines = ["graph LR"]

    for loc, comps in sorted(by_location.items()):
        loc_label = loc.replace("-", " ").title()
        icon = "🏠"
        if loc.startswith("cloud"):
            icon = "☁️"
        elif loc == "datacenter":
            icon = "🏢"
        elif loc == "vps":
            icon = "🌐"

        lines.append(f'    subgraph {loc}["{icon} {loc_label}"]')

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


def vault_infra_map(project: Optional[str] = None, location: Optional[str] = None) -> Dict[str, Any]:
    if location and location not in LOCATIONS:
        return {"ok": False, "error": f"Ubicación inválida: {location}. Válidas: {LOCATIONS}"}

    index = load_index()
    components = index.get("components", [])

    if not components:
        return {
            "ok": True,
            "path": str((INFRA_DIR / "infra-map.md").relative_to(VAULT_ROOT)).replace("\\", "/"),
            "nodesTotal": 0,
            "edgesTotal": 0,
        }

    # Apply filters for counting
    filtered = components
    if project:
        filtered = [c for c in filtered if c.get("project", "").lower() == project.lower()]
    if location:
        filtered = [c for c in filtered if c.get("location", "") == location]

    edges_total = sum(len(c.get("connections", [])) for c in filtered)

    mermaid_content = generate_infra_map(components, project, location)
    map_path = INFRA_DIR / "infra-map.md"

    frontmatter = ["---"]
    frontmatter.append("title: Infrastructure Map")
    frontmatter.append(f"updatedAt: {_utcnow()}")
    if project:
        frontmatter.append(f"project: {project}")
    if location:
        frontmatter.append(f"location: {location}")
    frontmatter.append("---")
    frontmatter.append("\n## Network Map\n\n```mermaid\n" + mermaid_content + "\n```\n")

    with open(map_path, "w", encoding="utf-8") as f:
        f.write("\n".join(frontmatter))

    return {
        "ok": True,
        "path": str(map_path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "nodesTotal": len(filtered),
        "edgesTotal": edges_total,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Infra Map Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_infra_map.py
  python vault_infra_map.py --project "ans"
  python vault_infra_map.py --location "homelab"
  python vault_infra_map.py --project "mi-api" --location "cloud-aws"

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Lee .infra-index.json generado por vault_infra_save.py
  - Genera diagrama Mermaid en 09_Infrastructure/infra-map.md
""",
    )
    parser.add_argument("--project", help="Filter by project")
    parser.add_argument("--location", help=f"Filter by location: {LOCATIONS}")

    args = parser.parse_args()
    result = vault_infra_map(args.project, args.location)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_infra_map"))

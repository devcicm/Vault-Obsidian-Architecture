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

from vault_errors import emit_error, wrap_main, proyecto_registrado
from vault_lib import slugify_strict, utcnow
from datetime import datetime, timezone
from pathlib import Path


from typing import Any, Dict, List, Optional


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


from vault_io import atomic_write_text, write_report

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.grafo.repositorio import RepositorioGrafo  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGrafo:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGrafo(construir(root))


def _infra_dir() -> Path:
    return _repo().dir_infra


def _index_file() -> Path:
    """Resuelto al usarse: como constante de módulo se fijaba al importar (AP-49)."""
    return _infra_dir() / ".infra-index.json"


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
    "storage": '("{name}")',
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
        with open(_index_file(), "r", encoding="utf-8") as f:
            return json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):
        return {"components": [], "locations": {}}


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


def vault_infra_map(
    project: Optional[str] = None, location: Optional[str] = None
) -> Dict[str, Any]:
    if location and location not in LOCATIONS:
        return emit_error("vault_infra_map", "INVALID_VALUE", f"Ubicación inválida: {location}. Válidas: {LOCATIONS}")

    index = load_index()

    components = index.get("components", [])

    # Sin componentes también se escribe: `generate_infra_map` pinta el grafo
    # vacío. Devolver el `path` sin escribirlo (hasta 2026-10-02) dejaba al
    # consumidor ante un fichero inexistente o ante el mapa anterior (AP-44).

    # Apply filters for counting

    filtered = components

    if project:
        filtered = [
            c for c in filtered if c.get("project", "").lower() == project.lower()
        ]

    if location:
        filtered = [c for c in filtered if c.get("location", "") == location]

    edges_total = sum(len(c.get("connections", [])) for c in filtered)

    mermaid_content = generate_infra_map(components, project, location)

    map_path = _infra_dir() / "infra-map.md"

    # AP-46: el bloque lo escribe su dueño; aquí solo se declaran los campos.
    frontmatter = [
        Frontmatter()
        .set("title", "Infrastructure Map")
        .set("updatedAt", utcnow())
        .set("project", project, omitir_vacio=True, texto=True)
        .set("location", location, omitir_vacio=True, texto=True)
        .render()
    ]

    frontmatter.append("\n## Network Map\n\n```mermaid\n" + mermaid_content + "\n```\n")

    # Escritura atómica: era el único sitio que escribía una nota con
    # `open(..., "w")` directo — sin saneado de encoding, sin temp+replace y
    # sin quedar registrada en el ledger de AP-37.
    atomic_write_text(map_path, "\n".join(frontmatter))

    return {
        "ok": True,
        **write_report(),
        "path": str(map_path.relative_to(_raiz())).replace("\\", "/"),
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

    parser.add_argument("--project", type=proyecto_registrado("vault_infra_map"), help="Filter by project")

    parser.add_argument("--location", help=f"Filter by location: {LOCATIONS}")

    args = parser.parse_args()

    result = vault_infra_map(args.project, args.location)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_infra_map"))

#!/usr/bin/env python3
"""
Vault Code Map Tool — Generate or regenerate code map Mermaid diagram

Regenerates 11_Code/{project}/code-map.md from .code-index.json.
Consolidates all modules and relations into a visual graph.

Usage:
    python vault_code_map.py --project "ans"
"""

import argparse
import json
import re
import sys
from vault_errors import wrap_main
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

VAULT_ROOT = Path(__file__).parent.parent
CODE_DIR = VAULT_ROOT / "11_Code"
INDEX_FILE = CODE_DIR / ".code-index.json"


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
        return {"modules": [], "relations": []}


def generate_code_map(project: str, index: Dict[str, Any]) -> str:
    modules = [m for m in index.get("modules", []) if m.get("project", "").lower() == project.lower()]
    relations = [r for r in index.get("relations", []) if r.get("project", "").lower() == project.lower()]

    if not modules:
        return "graph TD\n    empty[No modules documented yet]"

    lines = ["graph TD"]
    node_map = {}

    for i, mod in enumerate(modules):
        title = mod.get("title", mod.get("filePath", ""))
        slug = slugify(Path(mod.get("filePath", title)).stem)
        node_id = f"N{i}"
        lines.append(f'    {node_id}["{title}"]')
        node_map[mod["filePath"]] = node_id

    for rel in relations:
        from_path = rel.get("from", "")
        to_path = rel.get("to", "")
        rel_type = rel.get("type", "")
        cardinality = rel.get("cardinality", "")
        label_str = rel_type
        if cardinality:
            label_str += f" {cardinality}"

        from_id = node_map.get(from_path)
        to_id = node_map.get(to_path)

        if from_id and to_id:
            arrow = "-->"
            if rel_type == "implements":
                arrow = "-.->"
            elif rel_type == "re-exports":
                arrow = "==>"
            if label_str:
                lines.append(f'    {from_id} {arrow}|"{label_str}"| {to_id}')
            else:
                lines.append(f"    {from_id} {arrow} {to_id}")

    return "\n".join(lines)


def vault_code_map(project: str) -> Dict[str, Any]:
    index = load_index()

    safe_project = slugify(project)
    map_dir = CODE_DIR / safe_project
    map_dir.mkdir(parents=True, exist_ok=True)
    map_path = map_dir / "code-map.md"

    mermaid_content = generate_code_map(project, index)

    timestamp = _utcnow()

    frontmatter = ["---"]
    frontmatter.append(f"title: Code Map - {project}")
    frontmatter.append(f"project: {project}")
    frontmatter.append(f"type: code-map")
    frontmatter.append(f"updatedAt: {timestamp}")
    frontmatter.append("---")
    frontmatter.append(f"\n## Code Map: {project}\n")
    frontmatter.append(f"```mermaid\n{mermaid_content}\n```\n")

    with open(map_path, "w", encoding="utf-8") as f:
        f.write("\n".join(frontmatter))

    modules = [m for m in index.get("modules", []) if m.get("project", "").lower() == project.lower()]
    relations = [r for r in index.get("relations", []) if r.get("project", "").lower() == project.lower()]

    return {
        "ok": True,
        "path": str(map_path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "modules": len(modules),
        "relations": len(relations),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Code Map Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_code_map.py --project "ans"
  python vault_code_map.py --project "mi-api"
  python vault_code_map.py --project "backend"

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Lee .code-index.json generado por vault_code_module.py y vault_code_relation.py
  - Genera diagrama Mermaid en 11_Code/{project}/code-map.md
""",
    )
    parser.add_argument("--project", required=True, help="Project slug")

    args = parser.parse_args()
    result = vault_code_map(args.project)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_code_map"))

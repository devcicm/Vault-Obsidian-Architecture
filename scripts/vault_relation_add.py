#!/usr/bin/env python3
"""
Vault Relation Add Tool — Add entity relations and auto-generate ERD

Adds a relation between entities and auto-generates the Mermaid ERD.
Deduplicates relations (same from+to+type won't be added twice).
Saves relations to {proyecto}-relations.json as source of truth.

Usage:
    python vault_relation_add.py --project "mi-api" --from "User" --to "Order" --relation_type "has_many" --cardinality "1:N"
    python vault_relation_add.py --project "ans" --from "ServiceA" --to "ServiceB" --relation_type "calls" --description "Service communication"
"""

import argparse
import json
import re
import sys
from vault_errors import wrap_main
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
from typing import Any, Dict, List, Optional

from vault_io import VAULT_ROOT
DIAGRAMS_DIR = VAULT_ROOT / "06_Diagrams"
ENTITY_DIR = DIAGRAMS_DIR / "entity"
RELATIONS_FILE = ENTITY_DIR / "relations.json"

RELATION_TYPES = [
    "has_one",
    "has_many",
    "belongs_to",
    "many_to_many",
    "implements",
    "extends",
    "depends_on",
    "uses",
    "calls",
    "owns",
    "aggregates",
]

ENTITY_TYPES = ["database", "module", "service", "class", "api", "component"]

RELATION_MERMAID = {
    "has_one": "||--||",
    "has_many": "||--o{",
    "belongs_to": "}o--||",
    "many_to_many": "}o--o{",
    "implements": "..>",
    "extends": "--|>",
    "depends_on": "-->",
    "uses": "-->",
    "calls": "-->",
    "owns": "*--",
    "aggregates": "o--",
}


def slugify(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


def load_relations(project: str) -> Dict[str, Any]:
    project_file = ENTITY_DIR / f"{slugify(project)}-relations.json"
    try:
        with open(project_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"project": project, "relations": []}


def save_relations(project: str, data: Dict[str, Any]) -> None:
    ENTITY_DIR.mkdir(parents=True, exist_ok=True)
    project_file = ENTITY_DIR / f"{slugify(project)}-relations.json"
    with open(project_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def detect_is_database_like(relations: List[Dict]) -> bool:
    db_types = {"has_one", "has_many", "belongs_to", "many_to_many"}
    return any(r.get("relationType") in db_types for r in relations)


def generate_erd_mermaid(project: str, relations: List[Dict]) -> str:
    is_db = detect_is_database_like(relations)

    if is_db:
        lines = ["erDiagram"]
        for rel in relations:
            from_e = slugify(rel["fromEntity"])
            to_e = slugify(rel["toEntity"])
            rel_symbol = RELATION_MERMAID.get(rel["relationType"], "-->")
            label = f'"{rel.get("label", "")}"' if rel.get("label") else ""
            lines.append(f"    {from_e} {rel_symbol} {to_e} {label}")
    else:
        lines = ["graph TD"]
        for rel in relations:
            from_e = slugify(rel["fromEntity"])
            to_e = slugify(rel["toEntity"])
            rel_symbol = RELATION_MERMAID.get(rel["relationType"], "-->")
            if rel_symbol == "-->":
                lines.append(f"    {from_e} --> {to_e}")
            elif rel_symbol == "..>":
                lines.append(f"    {from_e} ..> {to_e}")
            elif rel_symbol == "--|>":
                lines.append(f"    {from_e} --|> {to_e}")

    return "\n".join(lines)


def vault_relation_add(
    project: str,
    from_entity: str,
    to_entity: str,
    relation_type: str,
    cardinality: Optional[str] = None,
    label: Optional[str] = None,
    description: Optional[str] = None,
    entity_type: Optional[str] = None,
) -> Dict[str, Any]:
    relation_type = relation_type.lower()

    if relation_type not in RELATION_TYPES:
        return {"ok": False, "error": f"Tipo inválido: {relation_type}. Válidos: {RELATION_TYPES}"}

    data = load_relations(project)
    relations = data.get("relations", [])

    for rel in relations:
        if rel["fromEntity"] == from_entity and rel["toEntity"] == to_entity and rel["relationType"] == relation_type:
            erd_path = ENTITY_DIR / f"{slugify(project)}-erd.md"
            return {
                "ok": True,
                "path": str(erd_path.relative_to(VAULT_ROOT)).replace("\\", "/"),
                "relationsTotal": len(relations),
                "deduplicated": True,
            }

    new_relation = {
        "id": str(uuid.uuid4()),
        "fromEntity": from_entity,
        "toEntity": to_entity,
        "relationType": relation_type,
        "cardinality": cardinality,
        "label": label,
        "description": description,
        "entityType": entity_type,
        "createdAt": _utcnow(),
    }

    relations.append(new_relation)
    data["relations"] = relations
    save_relations(project, data)

    erd_content = generate_erd_mermaid(project, relations)
    erd_path = ENTITY_DIR / f"{slugify(project)}-erd.md"

    erd_frontmatter = ["---"]
    erd_frontmatter.append(f"title: {project} ERD")
    erd_frontmatter.append(f"project: {project}")
    erd_frontmatter.append(f"updatedAt: {_utcnow()}")
    erd_frontmatter.append("---")
    erd_frontmatter.append(f"\n## Entity Relationship Diagram\n\n```mermaid\n{erd_content}\n```\n")

    with open(erd_path, "w", encoding="utf-8") as f:
        f.write("\n".join(erd_frontmatter))

    return {
        "ok": True,
        "path": str(erd_path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "relationsTotal": len(relations),
        "deduplicated": False,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Relation Add Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_relation_add.py --project "mi-api" --from "User" --to "Order" --relation_type "has_many" --cardinality "1:N"
  python vault_relation_add.py --project "ans" --from "ServiceA" --to "ServiceB" --relation_type "calls" --description "Service communication"
  python vault_relation_add.py --project "backend" --from "AuthModule" --to "UserModule" --relation_type "depends_on" --entity_type "module"
  python vault_relation_add.py --project "mi-api" --from "Product" --to "Category" --relation_type "belongs_to" --cardinality "N:1"

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Tipos de relacion: has_one, has_many, belongs_to, many_to_many, implements, extends, depends_on, uses, calls, owns, aggregates
  - Genera automaticamente ERD en 06_Diagrams/entity/{project}-erd.md
  - Deduplica relaciones con mismo from+to+type
""",
    )
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--from", dest="from_entity", required=True, help="Source entity")
    parser.add_argument("--to", dest="to_entity", required=True, help="Target entity")
    parser.add_argument("--relation_type", required=True, help=f"Relation type: {RELATION_TYPES}")
    parser.add_argument("--cardinality", help="Cardinality (e.g., 1:N)")
    parser.add_argument("--label", help="Optional label for the relation")
    parser.add_argument("--description", help="Relation description")
    parser.add_argument("--entity_type", help=f"Entity type: {ENTITY_TYPES}")

    args = parser.parse_args()
    result = vault_relation_add(
        args.project,
        args.from_entity,
        args.to_entity,
        args.relation_type,
        args.cardinality,
        args.label,
        args.description,
        args.entity_type,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_relation_add"))

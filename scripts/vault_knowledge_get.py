#!/usr/bin/env python3
"""
Vault Knowledge Get Tool — Search and retrieve domain knowledge

Searches the vault for knowledge notes. If there's a strong unique match,
returns the full content automatically.

Usage:
    python vault_knowledge_get.py --query "Stripe API"
    python vault_knowledge_get.py --query "CQRS" --category "glossary"
    python vault_knowledge_get.py --query "password" --project "ans"
"""

import argparse
import json
import re
import sys
from vault_errors import wrap_main
from pathlib import Path
from typing import Any, Dict, List, Optional

VAULT_ROOT = Path(__file__).parent.parent
KNOWLEDGE_DIR = VAULT_ROOT / "07_Knowledge"
INDEX_FILE = VAULT_ROOT / "99_Index" / "search-index.json"

CATEGORIES = ["glossary", "api", "concept", "business-rule", "config", "dependency", "framework"]


def score_note(note: Dict[str, Any], query: str, category: Optional[str], project: Optional[str]) -> float:
    score = 0
    query_lower = query.lower()

    if category and note.get("category", "").lower() != category.lower():
        return 0
    if project and note.get("project", "").lower() != project.lower():
        return 0

    title_lower = note.get("title", "").lower()
    if query_lower in title_lower:
        score += 40
    for word in query_lower.split():
        if word in title_lower:
            score += 4

    preview_lower = note.get("preview", "").lower()
    if query_lower in preview_lower:
        score += 10
    for word in query_lower.split():
        if word in preview_lower:
            score += 1

    return score


def vault_knowledge_get(
    query: str,
    category: Optional[str] = None,
    project: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            index = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"ok": False, "error": "Search index not found. Run vault_index.py first."}

    knowledge_notes = [n for n in index.get("notes", []) if n.get("path", "").startswith("07_Knowledge/")]

    scored = []
    for note in knowledge_notes:
        score = score_note(note, query, category, project)
        if score > 0:
            scored.append({"note": note, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)

    # Fallback: if category filter produced no results, scan files directly (handles stale/partial index)
    if not scored and category:
        for md_file in KNOWLEDGE_DIR.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if not text.startswith("---"):
                continue
            parts = text.split("---", 2)
            if len(parts) < 3:
                continue
            fm = parts[1]
            file_category = ""
            for line in fm.splitlines():
                if line.lower().startswith("category:"):
                    file_category = line.split(":", 1)[1].strip().strip('"').strip("'")
                    break
            if file_category.lower() != category.lower():
                continue
            rel_path = str(md_file.relative_to(VAULT_ROOT)).replace("\\", "/")
            title_match = re.search(r"^title:\s*(.+)$", fm, re.MULTILINE)
            title = title_match.group(1).strip().strip('"') if title_match else md_file.stem
            synthetic_note = {"path": rel_path, "title": title, "category": file_category, "preview": ""}
            score = score_note(synthetic_note, query, None, project)
            if score > 0:
                scored.append({"note": synthetic_note, "score": score})
            else:
                scored.append({"note": synthetic_note, "score": 5})
        scored.sort(key=lambda x: x["score"], reverse=True)

    if not scored:
        return {
            "ok": True,
            "query": query,
            "results": [],
            "message": "No knowledge notes found matching query",
        }

    top = scored[0]
    top_note = top["note"]
    top_score = top["score"]

    results = [
        {
            "path": n["note"]["path"],
            "title": n["note"]["title"],
            "category": n["note"].get("category", ""),
            "score": n["score"],
        }
        for n in scored[:10]
    ]

    auto_read = top_score >= 60 and len(scored) == 1

    result: Dict[str, Any] = {
        "ok": True,
        "query": query,
        "category": category,
        "project": project,
        "total": len(scored),
        "results": results,
    }

    if auto_read:
        note_path = VAULT_ROOT / top_note["path"]
        try:
            with open(note_path, "r", encoding="utf-8") as f:
                content = f.read()
            body = content.split("---", 2)[-1] if content.startswith("---") else content
            result["autoRead"] = True
            result["topMatch"] = {
                "path": top_note["path"],
                "title": top_note["title"],
                "score": top_score,
            }
            result["topContent"] = body.strip()
        except (UnicodeDecodeError, FileNotFoundError):
            pass

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Vault Knowledge Get Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_knowledge_get.py --query "Stripe API"
  python vault_knowledge_get.py --query "CQRS" --category "glossary"
  python vault_knowledge_get.py --query "password" --project "ans"
  python vault_knowledge_get.py --query "database connection" --category "config" --project "mi-api"

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Si hay una coincidencia unica con score>=60, retorna el contenido completo automaticamente
  - Categorias: glossary, api, concept, business-rule, config, dependency, framework
""",
    )
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--category", help=f"Filter by category: {CATEGORIES}")
    parser.add_argument("--project", help="Filter by project")

    args = parser.parse_args()
    result = vault_knowledge_get(args.query, args.category, args.project)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_knowledge_get"))

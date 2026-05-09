#!/usr/bin/env python3
"""
Vault Code Query Tool -- Recursive query of the code documentation index

Allows the agent to ask: "What does src/server.py do?", "Which files have a login method?",
"List all modules in project X", "Show the dependency tree of src/auth.py".

Reads .code-index.json + individual 11_Code/*.md files to return rich documentation.

Usage:
    python vault_code_query.py --project "ans" --file "src/server.py"
    python vault_code_query.py --project "ans" --method "login"
    python vault_code_query.py --project "ans" --class "UserService"
    python vault_code_query.py --project "ans" --list
    python vault_code_query.py --project "ans" --file "src/server.py" --deps
"""

import argparse
import json
import re
import sys
from vault_errors import wrap_main
from pathlib import Path
from typing import Any, Dict, List, Optional


VAULT_ROOT = Path(__file__).parent.parent
CODE_DIR = VAULT_ROOT / "11_Code"
INDEX_FILE = CODE_DIR / ".code-index.json"


def load_index() -> Dict[str, Any]:
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"modules": [], "relations": []}


def parse_frontmatter(content: str) -> Dict[str, Any]:
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}
    fm: Dict[str, Any] = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val.startswith("[") or val.startswith("{"):
                try:
                    val = json.loads(val)  # type: ignore[assignment]
                except json.JSONDecodeError:
                    pass
            fm[key] = val
    return fm


def parse_sections(content: str) -> Dict[str, str]:
    """Extract ## Section content from markdown body."""
    body = re.sub(r"^---\n.*?\n---\n*", "", content, flags=re.DOTALL)
    sections: Dict[str, str] = {}
    current = None
    current_lines: List[str] = []
    for line in body.split("\n"):
        if line.startswith("## "):
            if current:
                sections[current] = "\n".join(current_lines).strip()
            current = line[3:].strip()
            current_lines = []
        else:
            if current:
                current_lines.append(line)
    if current:
        sections[current] = "\n".join(current_lines).strip()
    return sections


def read_module_doc(rel_path: str) -> Dict[str, Any]:
    """Read a code module .md and return structured data."""
    doc_path = VAULT_ROOT / rel_path.replace("/", "\\") if "\\" not in rel_path else VAULT_ROOT / rel_path
    # Normalize
    doc_path = VAULT_ROOT / Path(rel_path)
    if not doc_path.exists():
        return {}
    content = doc_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)
    sections = parse_sections(content)

    return {
        "frontmatter": fm,
        "sections": sections,
        "raw": content,
    }


def find_module(index: Dict[str, Any], project: str, file_query: str) -> Optional[Dict[str, Any]]:
    """Find a module by partial filePath match."""
    project_lower = project.lower()
    query_lower = file_query.lower()
    candidates = [
        m for m in index.get("modules", [])
        if m.get("project", "").lower() == project_lower
        and query_lower in m.get("filePath", "").lower()
    ]
    if not candidates:
        return None
    # Prefer exact match, then shortest
    exact = [c for c in candidates if c.get("filePath", "").lower() == query_lower]
    return exact[0] if exact else sorted(candidates, key=lambda x: len(x.get("filePath", "")))[0]


def get_relations(index: Dict[str, Any], file_path: str) -> Dict[str, List[Dict]]:
    outgoing = [r for r in index.get("relations", []) if r.get("from") == file_path]
    incoming = [r for r in index.get("relations", []) if r.get("to") == file_path]
    return {"outgoing": outgoing, "incoming": incoming}


def cmd_file(index: Dict[str, Any], project: str, file_query: str, deps: bool) -> Dict[str, Any]:
    module = find_module(index, project, file_query)
    if not module:
        return {"ok": False, "error": f"No module found matching '{file_query}' in project '{project}'"}

    rel_path = module.get("relPath", "")
    doc = read_module_doc(rel_path) if rel_path else {}
    fm = doc.get("frontmatter", {})
    sections = doc.get("sections", {})

    result: Dict[str, Any] = {
        "ok": True,
        "file_path": module.get("filePath", ""),
        "title": module.get("title", ""),
        "language": module.get("language", fm.get("language", "")),
        "iso_type": module.get("iso_type", fm.get("iso_type", "")),
        "description": sections.get("Proposito", sections.get("Propósito", "")),
        "exports": module.get("exports", []),
        "methods_index": module.get("methods", []),
        "classes_index": module.get("classes", []),
        "doc_path": rel_path,
    }

    # Parse structured sections from the .md
    methods_section = sections.get("Metodos", sections.get("Métodos", ""))
    if methods_section:
        result["methods_doc"] = methods_section

    classes_section = sections.get("Clases", "")
    if classes_section:
        result["classes_doc"] = classes_section

    constants_section = sections.get("Constantes", "")
    if constants_section:
        result["constants_doc"] = constants_section

    exceptions_section = sections.get("Excepciones", "")
    if exceptions_section:
        result["exceptions_doc"] = exceptions_section

    imports_section = sections.get("Importaciones desde", "")
    if imports_section:
        result["imports_from"] = [
            line.lstrip("- `").rstrip("`")
            for line in imports_section.split("\n")
            if line.strip().startswith("- ")
        ]

    responsibilities_section = sections.get("Responsabilidades", "")
    if responsibilities_section:
        result["responsibilities"] = [
            line.lstrip("- ").strip()
            for line in responsibilities_section.split("\n")
            if line.strip().startswith("- ")
        ]

    if deps:
        result["relations"] = get_relations(index, module.get("filePath", ""))

    return result


def cmd_method(index: Dict[str, Any], project: str, method_query: str) -> Dict[str, Any]:
    project_lower = project.lower()
    query_lower = method_query.lower()

    matches = []
    for module in index.get("modules", []):
        if module.get("project", "").lower() != project_lower:
            continue
        method_names = module.get("methods", [])
        if any(query_lower in m.lower() for m in method_names):
            matches.append({
                "file_path": module.get("filePath", ""),
                "title": module.get("title", ""),
                "language": module.get("language", ""),
                "matched_methods": [m for m in method_names if query_lower in m.lower()],
                "doc_path": module.get("relPath", ""),
            })

    if not matches:
        return {"ok": False, "error": f"No method matching '{method_query}' found in project '{project}'"}

    return {"ok": True, "query": method_query, "matches": matches, "count": len(matches)}


def cmd_class_search(index: Dict[str, Any], project: str, class_query: str) -> Dict[str, Any]:
    project_lower = project.lower()
    query_lower = class_query.lower()

    matches = []
    for module in index.get("modules", []):
        if module.get("project", "").lower() != project_lower:
            continue
        class_names = module.get("classes", [])
        if any(query_lower in c.lower() for c in class_names):
            matches.append({
                "file_path": module.get("filePath", ""),
                "title": module.get("title", ""),
                "language": module.get("language", ""),
                "matched_classes": [c for c in class_names if query_lower in c.lower()],
                "doc_path": module.get("relPath", ""),
            })

    if not matches:
        return {"ok": False, "error": f"No class matching '{class_query}' found in project '{project}'"}

    return {"ok": True, "query": class_query, "matches": matches, "count": len(matches)}


def cmd_list(index: Dict[str, Any], project: str) -> Dict[str, Any]:
    project_lower = project.lower()
    modules = [
        {
            "file_path": m.get("filePath", ""),
            "title": m.get("title", ""),
            "language": m.get("language", ""),
            "iso_type": m.get("iso_type", ""),
            "methods": m.get("methods", []),
            "classes": m.get("classes", []),
            "exports_count": len(m.get("exports", [])),
            "doc_path": m.get("relPath", ""),
            "updatedAt": m.get("updatedAt", ""),
        }
        for m in index.get("modules", [])
        if m.get("project", "").lower() == project_lower
    ]
    return {
        "ok": True,
        "project": project,
        "count": len(modules),
        "modules": sorted(modules, key=lambda x: x["file_path"]),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Code Query Tool -- recursive code index query",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Documentacion completa de un archivo
  python vault_code_query.py --project "ans" --file "src/server.py"

  # Con arbol de dependencias
  python vault_code_query.py --project "ans" --file "src/server.py" --deps

  # Buscar un metodo en todo el proyecto
  python vault_code_query.py --project "ans" --method "login"

  # Buscar una clase
  python vault_code_query.py --project "ans" --class "UserService"

  # Listar todos los modulos del proyecto con sus metodos y clases indexados
  python vault_code_query.py --project "ans" --list

Notas:
  - --file acepta ruta parcial (busca por substring en filePath)
  - --method y --class hacen busqueda case-insensitive en el indice
  - Los datos de metodos y clases solo aparecen si el modulo fue documentado con --methods/--classes
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
""",
    )
    parser.add_argument("--project", required=True, help="Project slug")
    parser.add_argument("--file", help="File path to query (partial match allowed)")
    parser.add_argument("--method", help="Method name to search across all modules")
    parser.add_argument("--class", dest="class_name", help="Class name to search across all modules")
    parser.add_argument("--list", action="store_true", help="List all documented modules for the project")
    parser.add_argument("--deps", action="store_true", help="Include dependency relations (use with --file)")

    args = parser.parse_args()

    if not any([args.file, args.method, args.class_name, args.list]):
        parser.error("Specify one of: --file, --method, --class, --list")

    index = load_index()

    if args.file:
        result = cmd_file(index, args.project, args.file, args.deps)
    elif args.method:
        result = cmd_method(index, args.project, args.method)
    elif args.class_name:
        result = cmd_class_search(index, args.project, args.class_name)
    else:
        result = cmd_list(index, args.project)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_code_query"))

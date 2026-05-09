#!/usr/bin/env python3
"""
Vault Render - Renderizar Mermaid diagrams
"""

import re
import json
import subprocess
import argparse
from pathlib import Path


VAULT_ROOT = Path(__file__).parent.parent


def render_mermaid(chart_type: str = None, output: str = None):
    """Renderizar diagramas Mermaid"""

    # Find all mermaid blocks
    mermaid_blocks = []

    for md in VAULT_ROOT.rglob("*.md"):
        if ".history" in str(md) or md.name.startswith("_"):
            continue

        try:
            content = md.read_text(encoding="utf-8", errors="ignore")

            # Find mermaid code blocks
            pattern = r"```mermaid\s*\n(.*?)```"
            matches = re.findall(pattern, content, re.DOTALL)

            for match in matches:
                chart_type_detected = "graph"

                # Detect chart type
                if match.startswith("graph TD") or match.startswith("graph LR"):
                    chart_type_detected = "flowchart"
                elif match.startswith("erDiagram"):
                    chart_type_detected = "er"
                elif match.startswith("sequenceDiagram"):
                    chart_type_detected = "sequence"
                elif match.startswith("classDiagram"):
                    chart_type_detected = "class"
                elif match.startswith("stateDiagram"):
                    chart_type_detected = "state"

                if chart_type and chart_type != chart_type_detected:
                    continue

                mermaid_blocks.append(
                    {"file": str(md.relative_to(VAULT_ROOT)), "type": chart_type_detected, "chart": match}
                )
        except:
            pass

    if not mermaid_blocks:
        return {"error": "No mermaid blocks found"}

    if output:
        # Render to file
        output_dir = VAULT_ROOT / "06_Diagrams" / "rendered"
        output_dir.mkdir(parents=True, exist_ok=True)

        for block in mermaid_blocks:
            filename = f"{Path(block['file']).stem}-{block['type']}.mmd"
            (output_dir / filename).write_text(f"```mermaid\n{block['chart']}```", encoding="utf-8")

        return {"rendered": len(mermaid_blocks), "output": str(output_dir)}

    # Output summary
    return {"found": len(mermaid_blocks), "blocks": mermaid_blocks}


def generate_diagram_from_relations():
    """Generar diagrama desde relaciones"""

    # Load graph
    graph_file = VAULT_ROOT / "99_Index" / "graph.json"
    if not graph_file.exists():
        return {"error": "No graph.json found"}

    graph = json.loads(graph_file.read_text(encoding="utf-8"))

    # Build mermaid
    md = "# Diagramas de Relaciones\n\n"

    # Entity relationships
    md += "## Entity Relationships\n\n"
    md += "```mermaid\n"
    md += "erDiagram\n"

    # Count relationships
    rels = {}
    for edge in graph.get("edges", []):
        rels[edge["to"]] = rels.get(edge["to"], 0) + 1

    for node in graph.get("nodes", [])[:10]:
        md += f'  {node["id"].replace("-", "_").upper()} "{node["title"]}"\n'

    md += "```\n\n"

    # Flowchart
    md += "## Relationships Flowchart\n\n"
    md += "```mermaid\n"
    md += "graph TD\n"

    for node in graph.get("nodes", []):
        md += f"  {node['id']}[{node['title']}]\n"

    for edge in graph.get("edges", [])[:20]:
        md += f"  {edge['from']} --> {edge['to']}\n"

    md += "```\n"

    dest = VAULT_ROOT / "06_Diagrams" / "generated" / "relations.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(md, encoding="utf-8")

    return {"generated": str(dest)}


def check_mermaid_syntax():
    """Verificar sintaxis Mermaid"""

    issues = []

    for md in VAULT_ROOT.rglob("*.md"):
        if ".history" in str(md) or md.name.startswith("_"):
            continue

        try:
            content = md.read_text(encoding="utf-8", errors="ignore")

            pattern = r"```mermaid\s*\n(.*?)```"
            matches = re.findall(pattern, content, re.DOTALL)

            for match in matches:
                # Basic syntax check
                if match.count("{") != match.count("}"):
                    issues.append((str(md.relative_to(VAULT_ROOT)), "Mismatched braces"))
                if match.count("[") % 2 != 0:
                    issues.append((str(md.relative_to(VAULT_ROOT)), "Mismatched brackets"))
        except:
            pass

    return {"checked": len(list(VAULT_ROOT.rglob("*.md"))), "issues": issues}


def main():
    parser = argparse.ArgumentParser(
        description="Vault Render",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_render.py --render
  python vault_render.py --render --type flowchart
  python vault_render.py --render --output rendered/
  python vault_render.py --generate
  python vault_render.py --check

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - --render escanea todos los bloques ```mermaid``` del vault
  - --generate crea diagramas desde graph.json (requiere vault_graph previo)
  - --check verifica sintaxis basica de llaves y corchetes en bloques mermaid
  - Tipos detectados: flowchart, er, sequence, class, state, graph
""",
    )
    parser.add_argument("--render", "-r", action="store_true", help="Render diagramas")
    parser.add_argument("--generate", "-g", action="store_true", help="Generar desde relaciones")
    parser.add_argument("--check", "-c", action="store_true", help="Verificar sintaxis")
    parser.add_argument("--type", "-t", help="Filtrar tipo")
    parser.add_argument("--output", "-o", help="Output file")

    args = parser.parse_args()

    if args.check:
        result = check_mermaid_syntax()
        print(f"Checked: {result['checked']} files")
        print(f"Issues: {len(result['issues'])}")
        for file, issue in result["issues"][:5]:
            print(f"  - {file}: {issue}")

    elif args.generate:
        result = generate_diagram_from_relations()
        print(f"Generated: {result.get('generated', result.get('error'))}")

    elif args.render:
        if args.output:
            result = render_mermaid(args.type, args.output)
        else:
            result = render_mermaid(args.type)

        if "error" in result:
            print(f"Error: {result['error']}")
        elif "found" in result:
            print(f"Found: {result['found']} mermaid blocks")
        else:
            print(f"Rendered: {result.get('rendered', 0)} -> {result.get('output')}")

    else:
        # Summary
        result = render_mermaid()
        print(f"Mermaid blocks: {result.get('found', 0)}")

        result = check_mermaid_syntax()
        print(f"Sintax issues: {len(result['issues'])}")


if __name__ == "__main__":
    main()

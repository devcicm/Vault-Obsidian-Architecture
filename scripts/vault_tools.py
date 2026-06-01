#!/usr/bin/env python3
"""
Vault Tools - Script unificado para operaciones del vault
"""

import json
import re
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter
from vault_errors import wrap_main


from vault_io import VAULT_ROOT


class VaultTools:
    """Herramientas del vault"""

    def __init__(self):
        self.vault = VAULT_ROOT

    def search(self, query: str, folder: str = None, limit: int = 20):
        """Buscar notas por contenido"""
        results = []

        notes = list(self.vault.rglob("*.md"))
        if folder:
            notes = [n for n in notes if folder in str(n.parent)]

        for md in notes:
            if ".history" in str(md) or md.name.startswith("_"):
                continue

            try:
                content = md.read_text(encoding="utf-8", errors="ignore")
                # Remove frontmatter for search
                if content.startswith("---"):
                    content = content.split("---", 2)[2]

                query_lower = query.lower()
                if query_lower in content.lower():
                    # Get preview
                    idx = content.lower().find(query_lower)
                    preview = content[max(0, idx - 50) : idx + 50].replace("\n", " ")

                    results.append(
                        {
                            "path": str(md.relative_to(self.vault)),
                            "title": md.stem.replace("-", " ").title(),
                            "preview": preview,
                        }
                    )
            except:
                pass

        return results[:limit]

    def list(self, folder: str = None, status: str = None, limit: int = 50):
        """Listar notas"""
        notes = []

        if folder:
            folder_path = self.vault / folder
            if folder_path.exists():
                notes = list(folder_path.glob("*.md"))
        else:
            notes = [n for n in self.vault.rglob("*.md") if ".history" not in str(n) and not n.name.startswith("_")]

        results = []
        for md in notes[:limit]:
            try:
                content = md.read_text(encoding="utf-8", errors="ignore")

                # Extract frontmatter
                title = md.stem.replace("-", " ").title()
                status_val = None
                tags = []

                if content.startswith("---"):
                    lines = content.split("\n")
                    in_fm = False
                    for line in lines:
                        if line.strip() == "---":
                            in_fm = not in_fm
                            continue
                        if in_fm and ":" in line:
                            key, val = line.split(":", 1)
                            if key.strip() == "title":
                                title = val.strip()
                            elif key.strip() == "status":
                                status_val = val.strip()
                            elif key.strip() == "tags":
                                tags = eval(val.strip())

                if status and status_val != status:
                    continue

                results.append(
                    {"path": str(md.relative_to(self.vault)), "title": title, "status": status_val, "tags": tags}
                )
            except:
                pass

        return results

    def diff(self, note_path: str):
        """Mostrar diferencias con versión anterior"""
        history_dir = self.vault / ".history"

        # Find versions
        note_name = Path(note_path).stem
        versions = sorted(history_dir.glob(f"*{note_name}*.md"), key=lambda x: x.stat().st_mtime, reverse=True)

        if not versions:
            return {"error": "No history versions found"}

        current = self.vault / note_path
        if not current.exists():
            return {"error": "Note not found"}

        current_content = current.read_text(encoding="utf-8")

        # Simple diff (line by line)
        older = versions[0].read_text(encoding="utf-8")

        curr_lines = current_content.split("\n")
        old_lines = older.split("\n")

        changes = []
        for i, (c, o) in enumerate(zip(curr_lines, old_lines)):
            if c != o:
                changes.append({"line": i + 1, "old": o[:50], "new": c[:50]})

        return {"current": str(current.relative_to(self.vault)), "version": versions[0].name, "changes": changes[:10]}

    def graph(self):
        """Generar grafo de relaciones"""
        graph = {"nodes": [], "edges": []}

        for md in self.vault.rglob("*.md"):
            if ".history" in str(md) or md.name.startswith("_"):
                continue

            graph["nodes"].append({"id": md.stem, "path": str(md.relative_to(self.vault))})

            try:
                content = md.read_text(encoding="utf-8", errors="ignore")
                for match in re.finditer(r"\[\[([^\]]+)\]\]", content):
                    graph["edges"].append({"from": md.stem, "to": match.group(1)})
            except:
                pass

        # Save
        graph_file = self.vault / "99_Index/graph.json"
        graph_file.parent.mkdir(parents=True, exist_ok=True)
        graph_file.write_text(json.dumps(graph, indent=2), encoding="utf-8")

        return graph

    def backup(self, dest: str = None):
        """Respaldar vault"""
        if not dest:
            dest = f"vault-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"

        shutil.make_archive(dest.replace(".zip", ""), "zip", self.vault)
        return {"backup": dest, "notes": len(list(self.vault.rglob("*.md")))}

    def stats(self):
        """Generar estadísticas"""
        notes = [n for n in self.vault.rglob("*.md") if ".history" not in str(n) and not n.name.startswith("_")]

        by_folder = Counter()
        by_status = Counter()
        by_tag = Counter()

        for md in notes:
            folder = str(md.parent.relative_to(self.vault))
            by_folder[folder] += 1

            try:
                content = md.read_text(encoding="utf-8", errors="ignore")
                if content.startswith("---"):
                    lines = content.split("\n")
                    in_fm = False
                    for line in lines:
                        if line.strip() == "---":
                            in_fm = not in_fm
                            continue
                        if in_fm and ":" in line:
                            key, val = line.split(":", 1)
                            if key.strip() == "status":
                                by_status[val.strip()] += 1
                            elif key.strip() == "tags":
                                tags = eval(val.strip())
                                for t in tags:
                                    by_tag[t] += 1
            except:
                pass

        return {
            "total": len(notes),
            "by_folder": dict(by_folder),
            "by_status": dict(by_status),
            "by_tag": dict(by_tag.most_common(10)),
        }

    def export_json(self, folder: str = None):
        """Exportar notas a JSON"""
        notes = []

        if folder:
            folder_path = self.vault / folder
            if folder_path.exists():
                notes = list(folder_path.glob("*.md"))
        else:
            notes = [n for n in self.vault.rglob("*.md")]

        results = []
        for md in notes:
            if ".history" in str(md) or md.name.startswith("_"):
                continue

            content = md.read_text(encoding="utf-8", errors="ignore")

            # Extract body only
            body = content
            if content.startswith("---"):
                body = content.split("---", 2)[2]

            results.append(
                {
                    "path": str(md.relative_to(self.vault)),
                    "title": md.stem.replace("-", " ").title(),
                    "content": body.strip(),
                }
            )

        output = self.vault / "export.json"
        output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

        return {"exported": len(results), "file": str(output)}

    def clean_orphans(self):
        """Limpiar notas huérfanas (sin backlinks)"""
        all_notes = {n.stem for n in self.vault.rglob("*.md") if ".history" not in str(n)}

        orphans = []

        for md in self.vault.rglob("*.md"):
            if ".history" in str(md) or md.name.startswith("_"):
                continue

            # Check if referenced
            content = md.read_text(encoding="utf-8", errors="ignore")
            referenced = False

            for other in self.vault.rglob("*.md"):
                if other == md or ".history" in str(other):
                    continue
                try:
                    other_content = other.read_text(encoding="utf-8", errors="ignore")
                    if md.stem in other_content:
                        referenced = True
                        break
                except:
                    pass

            if not referenced:
                # Except system notes
                if md.parent.name not in ["00_System"]:
                    orphans.append(str(md.relative_to(self.vault)))

        return {"orphans": orphans[:10], "count": len(orphans)}


def main():
    # Deprecation notice
    print(json.dumps({"_deprecation": {"use_instead": "individual tools", "since": "v26"}}), file=sys.stderr)
    parser = argparse.ArgumentParser(
        description="Vault Tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_tools.py search --query "deploy"
  python vault_tools.py search --query "deploy" --folder "08_Runbooks" --limit 10
  python vault_tools.py list --folder "01_Projects"
  python vault_tools.py stats
  python vault_tools.py diff --note "01_Projects/mi-api/overview.md"
  python vault_tools.py graph
  python vault_tools.py backup --output vault-backup-2024.zip
  python vault_tools.py export --folder "07_Knowledge"
  python vault_tools.py clean

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - El comando 'graph' sobreescribe 99_Index/graph.json
  - El comando 'export' genera export.json en la raiz del vault
""",
    )
    parser.add_argument(
        "command",
        choices=["search", "list", "diff", "graph", "backup", "stats", "export", "clean"],
        help="Comando a ejecutar",
    )
    parser.add_argument("--query", "-q", help="Query de busqueda")
    parser.add_argument("--folder", "-f", help="Carpeta")
    parser.add_argument("--limit", "-l", type=int, default=20, help="Limite de resultados")
    parser.add_argument("--note", "-n", help="Nota para diff")
    parser.add_argument("--output", "-o", help="Archivo de output")

    args = parser.parse_args()
    tools = VaultTools()

    if args.command == "search":
        results = tools.search(args.query or "", args.folder, args.limit)
        print(f"=== SEARCH: {args.query} ===")
        for r in results:
            print(f"  [{r['title']}]")
            print(f"  {r['path']}")

    elif args.command == "list":
        results = tools.list(args.folder, limit=args.limit)
        print(f"=== NOTES: {args.folder or 'all'} ===")
        for r in results:
            status = r["status"] or ""
            print(f"  {r['title']:40} {status}")

    elif args.command == "diff":
        if not args.note:
            print("Error: --note requerido")
            return
        result = tools.diff(args.note)
        print(f"=== DIFF: {args.note} ===")
        print(f"Version: {result.get('version', 'N/A')}")
        for c in result.get("changes", []):
            print(f"  Line {c['line']}: {c['old']} -> {c['new']}")

    elif args.command == "graph":
        result = tools.graph()
        print(f"Graph: {len(result['nodes'])} nodes, {len(result['edges'])} edges")

    elif args.command == "backup":
        result = tools.backup(args.output)
        print(f"Backup: {result['backup']} ({result['notes']} notes)")

    elif args.command == "stats":
        result = tools.stats()
        print("=== STATS ===")
        print(f"Total: {result['total']}")
        print(f"\nBy folder:")
        for f, c in result["by_folder"].items():
            print(f"  {f}: {c}")

    elif args.command == "export":
        result = tools.export_json(args.folder)
        print(f"Exported: {result['exported']} notes to {result['file']}")

    elif args.command == "clean":
        result = tools.clean_orphans()
        print(f"Orphans: {result['count']}")
        for o in result["orphans"]:
            print(f"  - {o}")


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_tools"))

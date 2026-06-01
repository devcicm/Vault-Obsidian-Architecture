#!/usr/bin/env python3
"""
Vault Reorganize Script
Move notes from 10_Migrated to proper sections.
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter
from vault_errors import wrap_main


from vault_io import VAULT_ROOT


def _detect_dest(note: Path, project: str) -> str:
    """Infiere la sección destino a partir del nombre y frontmatter de la nota.

    Orden de resolución:
    1. Campo `folder:` en frontmatter (el agente puede haber anotado el destino)
    2. Patrones en el nombre del archivo
    3. Fallback: 01_Projects/{project}/
    """
    # 1. Read frontmatter hint
    try:
        content = note.read_text(encoding="utf-8", errors="ignore")
        if content.startswith("---"):
            for line in content.split("---", 2)[1].splitlines():
                if line.lower().startswith("folder:"):
                    folder = line.split(":", 1)[1].strip().strip("\"'")
                    if folder:
                        return folder
    except Exception:
        pass

    # 2. Name-based pattern matching
    name = note.stem.lower().replace("-", "_")
    if any(x in name for x in ("architecture", "pattern", "design")):
        return "05_Patterns/architecture"
    if any(x in name for x in ("integration", "adapter", "connector")):
        return "05_Patterns/integration"
    if any(x in name for x in ("code", "module", "class", "function", "lib")):
        return "05_Patterns/code"
    if any(x in name for x in ("deploy", "install", "setup", "provision")):
        return "08_Runbooks/deploy"
    if any(x in name for x in ("runbook", "workflow", "procedure")):
        return "08_Runbooks/deploy"
    if any(x in name for x in ("debug", "fix", "troubleshoot", "incident")):
        return "08_Runbooks/debug"
    if any(x in name for x in ("api", "endpoint", "openapi", "swagger")):
        return "07_Knowledge/apis"
    if any(x in name for x in ("concept", "glossary", "theory", "overview")):
        return "07_Knowledge/concepts"
    if any(x in name for x in ("config", "guide", "env", "settings")):
        return "07_Knowledge/configs"
    if any(x in name for x in ("framework", "library", "sdk", "tool")):
        return "07_Knowledge/frameworks"
    if any(x in name for x in ("dependency", "package", "dep_")):
        return "07_Knowledge/dependencies"
    if any(x in name for x in ("infra", "server", "database", "network", "storage")):
        return "09_Infrastructure/servers"
    if any(x in name for x in ("decision", "adr", "tradeoff")):
        return "03_Decisions"

    # 3. Fallback
    return f"01_Projects/{project}"


def reorganize(project: str = "mi-proyecto", dry_run: bool = False):
    """Mueve notas de 10_Migrated a secciones propias via deteccion automatica.

    No usa rutas hardcodeadas — infiere el destino de cada nota por frontmatter
    y patrones de nombre. Compatible con cualquier proyecto.
    """
    migrated_root = VAULT_ROOT / "10_Migrated"
    if not migrated_root.exists():
        return [], []

    moved = []
    missing = []
    skipped = []

    for note in migrated_root.rglob("*.md"):
        rel = str(note.relative_to(VAULT_ROOT)).replace("\\", "/")
        dest_folder = _detect_dest(note, project)
        slug = note.stem.lower()
        # Strip common prefixes left by vault_migrate (e.g. "agents-", "direct-")
        slug = re.sub(r"^(direct|indirect|agents|guides|deployment|architecture|project|informacion.decrepita)-", "", slug)
        dest_rel = f"{dest_folder}/{slug}.md"
        dest_path = VAULT_ROOT / dest_rel

        if dest_path.exists():
            skipped.append({"src": rel, "dest": dest_rel, "reason": "already_exists"})
            continue

        if dry_run:
            moved.append({"src": rel, "dest": dest_rel, "dry_run": True})
            continue

        try:
            content = note.read_text(encoding="utf-8", errors="ignore")
            # Fix path-anchored wiki-links left by migration
            content = re.sub(r"\[\[10_Migrated/[^|/\]]*?/([^\]|]+)", r"[[\1", content)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_text(content, encoding="utf-8")
            note.unlink()
            moved.append({"src": rel, "dest": dest_rel})
        except Exception as e:
            missing.append({"src": rel, "error": str(e)})

    return moved, missing, skipped


def audit():
    """Audita el vault"""
    by_folder = Counter()
    total = 0
    no_fm = []
    empty = []
    broken = []

    all_notes = {n.stem for n in VAULT_ROOT.rglob("*.md") if ".history" not in str(n) and not n.name.startswith("_")}

    for md in VAULT_ROOT.rglob("*.md"):
        if ".history" in str(md) or md.name.startswith("_"):
            continue

        total += 1
        folder = str(md.parent.relative_to(VAULT_ROOT))
        by_folder[folder] += 1

        # Check empty
        if md.stat().st_size < 50:
            empty.append(str(md.relative_to(VAULT_ROOT)))

        # Check frontmatter
        try:
            content = md.read_text(encoding="utf-8", errors="ignore")
            if not content.startswith("---"):
                no_fm.append(str(md.relative_to(VAULT_ROOT)))

            # Check broken links
            for match in re.finditer(r"\[\[([^\]]+)\]\]", content):
                link = match.group(1).strip()
                if link and not link.startswith("http"):
                    found = any(
                        link.replace("-", "").replace("_", "").lower() == s.replace("-", "").replace("_", "").lower()
                        for s in all_notes
                    )
                    if not found:
                        broken.append((md.stem, link))
        except:
            pass

    return {
        "total": total,
        "by_folder": dict(by_folder),
        "no_frontmatter": no_fm,
        "empty": empty,
        "broken": list(set(broken))[:10],
    }


def regenerate_indexes():
    """Regenera los índices"""
    graph = {"nodes": [], "edges": []}
    search_index = {"version": "1.0", "updatedAt": datetime.now().isoformat()[:19], "notes": []}

    for md in VAULT_ROOT.rglob("*.md"):
        if ".history" in str(md) or md.name.startswith("_"):
            continue

        title = md.stem.replace("-", " ").replace("_", " ").title()
        path = str(md.relative_to(VAULT_ROOT))

        graph["nodes"].append({"id": md.stem, "title": title, "path": path})
        search_index["notes"].append(
            {"path": path, "title": title, "preview": "", "tags": [], "updatedAt": datetime.now().isoformat()[:19]}
        )

        try:
            content = md.read_text(encoding="utf-8", errors="ignore")
            for match in re.finditer(r"\[\[([^\]]+)\]\]", content):
                link = match.group(1).strip()
                if link and not link.startswith("http"):
                    graph["edges"].append({"from": md.stem, "to": link})
        except:
            pass

    # Save
    (VAULT_ROOT / "99_Index/graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    (VAULT_ROOT / "99_Index/search-index.json").write_text(json.dumps(search_index, indent=2), encoding="utf-8")

    return len(graph["nodes"]), len(graph["edges"])


def main():
    # Deprecation notice
    print(json.dumps({"_deprecation": {"use_instead": "vault_migrate_docs", "since": "v26"}}), file=sys.stderr)
    import argparse
    parser = argparse.ArgumentParser(
        description="Vault Reorganize Script -- Move notes from 10_Migrated to proper sections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_reorganize.py reorganize --project mi-api
  python vault_reorganize.py reorganize --project mi-api --dry-run
  python vault_reorganize.py audit
  python vault_reorganize.py index

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - 'reorganize' detecta automaticamente la seccion destino de cada nota en 10_Migrated/
  - El destino se infiere por frontmatter 'folder:' o por patrones en el nombre del archivo
  - 'audit' reporta total de notas, archivos vacios, sin frontmatter y links rotos
  - 'index' regenera 99_Index/graph.json y 99_Index/search-index.json
""",
    )
    parser.add_argument(
        "action",
        choices=["reorganize", "audit", "index"],
        help="Accion a ejecutar",
    )
    parser.add_argument("--project", default="mi-proyecto", help="Slug del proyecto (fallback destino, default: mi-proyecto)")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar movimientos sin ejecutarlos")
    args = parser.parse_args()

    if args.action == "reorganize":
        moved, missing, skipped = reorganize(project=args.project, dry_run=args.dry_run)
        print(f"{'[DRY-RUN] ' if args.dry_run else ''}Moved: {len(moved)} | Errors: {len(missing)} | Skipped: {len(skipped)}")
        for m in moved:
            print(f"  {m['src']} -> {m['dest']}")
        if missing:
            for e in missing:
                print(f"  ERROR: {e}")

        nodes, edges = regenerate_indexes()
        print(f"Indexes regenerated: {nodes} nodes, {edges} edges")

    elif args.action == "audit":
        result = audit()
        print(f"=== VAULT AUDIT ===")
        print(f"Total: {result['total']}")
        print(f"\nBy folder:")
        for f, c in sorted(result["by_folder"].items(), key=lambda x: -x[1]):
            print(f"  {f}: {c}")
        print(f"\nEmpty: {len(result['empty'])}")
        print(f"No frontmatter: {len(result['no_frontmatter'])}")
        print(f"Broken links: {len(result['broken'])}")

    elif args.action == "index":
        nodes, edges = regenerate_indexes()
        print(f"Indexes regenerated: {nodes} nodes, {edges} edges")


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_reorganize"))

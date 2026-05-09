#!/usr/bin/env python3
"""
Vault Reorganize Script
Move notes from 10_Migrated to proper sections.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from collections import Counter


VAULT_DIR = Path(__file__).parent.parent


def reorganize():
    """Reorganiza notas de 10_Migrated a secciones propias"""

    moves = [
        # 01_Projects/ans/ - Project specific
        ("10_Migrated/direct/agents-AI_AGENT_PLAYBOOK.md", "01_Projects/ans/ai-agent-playbook.md"),
        ("10_Migrated/direct/agents-AI_AGENT_INSTRUCTIONS.md", "01_Projects/ans/ai-agent-instructions.md"),
        ("10_Migrated/direct/agents-CLAUDE_CODE_SETUP.md", "01_Projects/ans/claude-code-setup.md"),
        ("10_Migrated/direct/project-FEATURES_LOG.md", "01_Projects/ans/features-log.md"),
        ("10_Migrated/direct/project-MASTER_INDEX.md", "01_Projects/ans/master-index.md"),
        ("10_Migrated/direct/ROOT-README.md", "01_Projects/ans/readme.md"),
        ("10_Migrated/direct/ROOT-CLAUDE.md", "01_Projects/ans/claude.md"),
        # 05_Patterns - Patterns
        ("10_Migrated/direct/architecture-ARCHITECTURE_WHITEPAPER.md", "05_Patterns/architecture/ans-architecture.md"),
        ("10_Migrated/direct/architecture-AI_INTEGRATION_SPEC.md", "05_Patterns/architecture/ai-integration.md"),
        ("10_Migrated/direct/architecture-DEPLOY_SYSTEM.md", "05_Patterns/architecture/deploy-system.md"),
        ("10_Migrated/direct/architecture-LOCAL_RUNNER_IMPLEMENTATION.md", "05_Patterns/code/local-runner.md"),
        ("10_Migrated/direct/guides-RESILIENCE_GUIDE.md", "05_Patterns/code/resilience.md"),
        ("10_Migrated/direct/guides-GUIDE_PLAYBOOK_VERSIONING.md", "05_Patterns/code/playbook-versioning.md"),
        ("10_Migrated/indirect/agents-FILE_FACTORY_GUIDE.md", "05_Patterns/integration/file-factory.md"),
        # 07_Knowledge - Knowledge
        ("10_Migrated/direct/informacion-decrepita-MCP_CAPABILITIES.md", "07_Knowledge/apis/mcp-capabilities.md"),
        ("10_Migrated/direct/informacion-decrepita-MCP_AGENT_GUIDE.md", "07_Knowledge/concepts/mcp-agent-guide.md"),
        ("10_Migrated/direct/guides-ANSIBLE_BINARIES_GUIDE.md", "07_Knowledge/configs/ansible-binaries.md"),
        (
            "10_Migrated/direct/informacion-decrepita-TECHNICAL_ENVIRONMENT_GUIDE.md",
            "07_Knowledge/configs/technical-environment.md",
        ),
        (
            "10_Migrated/direct/informacion-decrepita-DEPLOYMENT_PROFILES.md",
            "07_Knowledge/configs/deployment-profiles.md",
        ),
        (
            "10_Migrated/direct/informacion-decrepita-STORAGE_RESILIENCE_GUIDE.md",
            "07_Knowledge/concepts/storage-resilience.md",
        ),
        (
            "10_Migrated/direct/informacion-decrepita-GUIDE_TRANSFER_SYSTEM.md",
            "07_Knowledge/concepts/transfer-system.md",
        ),
        (
            "10_Migrated/direct/informacion-decrepita-GUIDE_DRIFT_AND_SYNC_ANALYSIS.md",
            "07_Knowledge/concepts/drift-sync.md",
        ),
        ("10_Migrated/direct/CENTRALIZATION_GUIDE.md", "07_Knowledge/configs/centralization.md"),
        # 08_Runbooks - Runbooks
        ("10_Migrated/direct/deployment-RUNBOOK.md", "08_Runbooks/deploy/system-runbook.md"),
        ("10_Migrated/direct/deployment-DEPLOYMENT_WORKFLOW.md", "08_Runbooks/deploy/deployment-workflow.md"),
        ("10_Migrated/direct/deployment-CASE_STUDY_PROXMOX.md", "08_Runbooks/deploy/proxmox-case-study.md"),
        ("10_Migrated/direct/deployment-NODE_INSTALLATION_GUIDE.md", "08_Runbooks/setup/node-installation.md"),
        ("10_Migrated/direct/informacion-decrepita-PROXMOX_REPO_FIX.md", "08_Runbooks/debug/proxmox-repo-fix.md"),
        (
            "10_Migrated/direct/informacion-decrepita-MIKROTIK_RESCUE_GUIDE.md",
            "08_Runbooks/incident/mikrotik-rescue.md",
        ),
        # 09_Infrastructure
        ("09_Infrastructure/servers/proxmox-main.md", "09_Infrastructure/servers/proxmox-main.md"),
        ("09_Infrastructure/services/ans-orchestrator.md", "09_Infrastructure/services/ans-orchestrator.md"),
    ]

    moved = []
    missing = []

    for src, dest_rel in moves:
        src_path = VAULT_DIR / src
        dest_path = VAULT_DIR / dest_rel

        if src_path.exists():
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            content = src_path.read_text(encoding="utf-8", errors="ignore")

            # Update location in frontmatter
            if "migratedFrom:" in content:
                content = content.replace("migratedFrom: ", "migratedFrom: 10_Migrated/")

            # Fix reference links
            content = content.replace("[[10_Migrated/", "[[")

            dest_path.write_text(content, encoding="utf-8")
            moved.append(dest_rel)
        else:
            missing.append(src)

    return moved, missing


def audit():
    """Audita el vault"""
    by_folder = Counter()
    total = 0
    no_fm = []
    empty = []
    broken = []

    all_notes = {n.stem for n in VAULT_DIR.rglob("*.md") if ".history" not in str(n) and not n.name.startswith("_")}

    for md in VAULT_DIR.rglob("*.md"):
        if ".history" in str(md) or md.name.startswith("_"):
            continue

        total += 1
        folder = str(md.parent.relative_to(VAULT_DIR))
        by_folder[folder] += 1

        # Check empty
        if md.stat().st_size < 50:
            empty.append(str(md.relative_to(VAULT_DIR)))

        # Check frontmatter
        try:
            content = md.read_text(encoding="utf-8", errors="ignore")
            if not content.startswith("---"):
                no_fm.append(str(md.relative_to(VAULT_DIR)))

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

    for md in VAULT_DIR.rglob("*.md"):
        if ".history" in str(md) or md.name.startswith("_"):
            continue

        title = md.stem.replace("-", " ").replace("_", " ").title()
        path = str(md.relative_to(VAULT_DIR))

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
    (VAULT_DIR / "99_Index/graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    (VAULT_DIR / "99_Index/search-index.json").write_text(json.dumps(search_index, indent=2), encoding="utf-8")

    return len(graph["nodes"]), len(graph["edges"])


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Vault Reorganize Script -- Move notes from 10_Migrated to proper sections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_reorganize.py reorganize
  python vault_reorganize.py audit
  python vault_reorganize.py index

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - 'reorganize' mueve notas de 10_Migrated a sus secciones destino y regenera indices
  - 'audit' reporta total de notas, archivos vacios, sin frontmatter y links rotos
  - 'index' regenera 99_Index/graph.json y 99_Index/search-index.json
""",
    )
    parser.add_argument(
        "action",
        choices=["reorganize", "audit", "index"],
        help="Accion a ejecutar",
    )
    args = parser.parse_args()

    if args.action == "reorganize":
        moved, missing = reorganize()
        print(f"Moved: {len(moved)} files")
        if missing:
            print(f"Missing: {len(missing)}")
            for m in missing:
                print(f"  - {m}")

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
    main()

#!/usr/bin/env python3

"""

Vault Timeline Tool — Reconstruct chronological trajectory of a topic



Crosses all vault sections to build a chronological narrative of a topic.

Supports query filtering, date ranges, and source-specific searches.



Usage:

    python vault_timeline.py --query "database"

    python vault_timeline.py --query "autenticacion" --project "ans"

    python vault_timeline.py --query "deploy" --from "2026-01-01" --to "2026-05-06"

    python vault_timeline.py --sources "sessions,changelog,decisions,errors"

    python vault_timeline.py --limit 20

"""

import argparse

import json

import re

import sys

from vault_errors import wrap_main
from vault_lib import slugify

from datetime import datetime, timedelta, timezone

from pathlib import Path

from typing import Any, Dict, List, Optional


ALL_SOURCES = [
    "sessions",
    "changelog",
    "decisions",
    "errors",
    "patterns",
    "infra",
    "knowledge",
    "dependencies",
    "runbooks",
]


SESSION_FOLDERS = ["04_Sessions"]

CHANGELOG_PATHS = ["01_Projects"]

DECISION_PATHS = ["03_Decisions"]

ERROR_PATHS = ["02_Observability/errors", "02_Observability/antipatterns"]

PATTERN_PATHS = ["05_Patterns"]

INFRA_PATHS = ["09_Infrastructure"]

KNOWLEDGE_PATHS = ["07_Knowledge"]

DEPENDENCY_PATHS = ["07_Knowledge/dependencies", "07_Knowledge/frameworks"]

RUNBOOK_PATHS = ["08_Runbooks"]


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _index_file() -> Path:
    return _repo().indice_busqueda


def parse_frontmatter(content: str) -> Dict[str, Any]:
    frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)

    if not frontmatter_match:
        return {}

    meta = {}

    for line in frontmatter_match.group(1).split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)

            key = key.strip()

            value = value.strip().strip("\"'")

            if value.startswith("[") or value.startswith("{"):
                try:
                    value = json.loads(value)

                except json.JSONDecodeError:
                    pass

            meta[key] = value

    return meta


def matches_query(text: str, query: str) -> bool:
    if not query:
        return True

    query_lower = query.lower()

    return query_lower in text.lower()


def search_sessions(
    query: str, date_from: str, date_to: str, limit: int
) -> List[Dict[str, Any]]:
    events = []

    for session_folder in SESSION_FOLDERS:
        folder_path = _raiz() / session_folder

        if not folder_path.exists():
            continue

        for note_path in sorted(folder_path.glob("*.md"), reverse=True):
            date_str = note_path.stem

            if date_from and date_str < date_from:
                continue

            if date_to and date_str > date_to:
                continue

            try:
                with open(note_path, "r", encoding="utf-8") as f:
                    content = f.read()

            except (UnicodeDecodeError, PermissionError):
                continue

            if not matches_query(content, query):
                continue

            for line in content.split("\n"):
                line = line.strip()

                if not line or line.startswith("#") or line.startswith("---"):
                    continue

                if re.match(r"^\*\*\d{4}-\d{2}-\d{2}", line):
                    ts_match = re.search(r"^\*\*(\d{4}-\d{2}-\d{2})", line)

                    if ts_match:
                        events.append(
                            {
                                "date": ts_match.group(1),
                                "source": "sessions",
                                "type": "log",
                                "title": line[:80],
                                "excerpt": line[:200],
                                "path": str(note_path.relative_to(_raiz())),
                            }
                        )

                        if len(events) >= limit:
                            return events

    return events


def search_changelog(
    query: str, project: str, date_from: str, date_to: str, limit: int
) -> List[Dict[str, Any]]:
    events = []

    for base_path in CHANGELOG_PATHS:
        project_path = _raiz() / base_path

        if not project_path.exists():
            continue

        for project_folder in project_path.iterdir():
            if not project_folder.is_dir():
                continue

            if project and slugify(project_folder.name) != slugify(project):
                continue

            changelog_path = project_folder / "changelog.md"

            if not changelog_path.exists():
                continue

            try:
                with open(changelog_path, "r", encoding="utf-8") as f:
                    content = f.read()

            except (UnicodeDecodeError, PermissionError):
                continue

            if not matches_query(content, query):
                continue

            for match in re.finditer(
                r"^### (v?\d+\.\d+[^ ]*) — (\d{4}-\d{2}-\d{2})(.*?)(?=^### |\Z)",
                content,
                re.DOTALL | re.MULTILINE,
            ):
                version = match.group(1).strip()

                date_str = match.group(2)

                changes = match.group(3).strip()[:150]

                if date_from and date_str < date_from:
                    continue

                if date_to and date_str > date_to:
                    continue

                events.append(
                    {
                        "date": date_str,
                        "source": "changelog",
                        "type": "version",
                        "title": f"{version} — {changes[:60]}...",
                        "excerpt": changes,
                        "path": str(changelog_path.relative_to(_raiz())),
                    }
                )

                if len(events) >= limit:
                    return events

    return events


def search_notes(
    query: str,
    sources: List[str],
    date_from: str,
    date_to: str,
    project: str,
    limit: int,
) -> List[Dict[str, Any]]:
    try:
        with open(_index_file(), "r", encoding="utf-8") as f:
            index = json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):
        return []

    events = []

    project_lower = project.lower() if project else ""

    for note in index.get("notes", []):
        path = note.get("path", "")

        source = None

        if "03_Decisions/" in path and "decisions" in sources:
            source = "decisions"

        elif "02_Observability/errors/" in path and "errors" in sources:
            source = "errors"

        elif "02_Observability/antipatterns/" in path and "errors" in sources:
            source = "errors"

        elif "05_Patterns/" in path and "patterns" in sources:
            source = "patterns"

        elif "09_Infrastructure/" in path and "infra" in sources:
            source = "infra"

        elif "07_Knowledge/" in path and "knowledge" in sources:
            source = "knowledge"

        elif (
            "07_Knowledge/dependencies/" in path or "07_Knowledge/frameworks/" in path
        ) and "dependencies" in sources:
            source = "dependencies"

        elif "08_Runbooks/" in path and "runbooks" in sources:
            source = "runbooks"

        else:
            continue

        if project_lower:
            tags = note.get("tags", [])

            if isinstance(tags, str):
                tags = [tags]

            if not any(project_lower in str(t).lower() for t in tags):
                continue

        title = note.get("title", "")

        preview = note.get("preview", "")

        full_text = f"{title} {preview}".lower()

        if not matches_query(full_text, query):
            continue

        note_path = _raiz() / path

        if not note_path.exists():
            continue

        try:
            with open(note_path, "r", encoding="utf-8") as f:
                content = f.read()

        except (UnicodeDecodeError, PermissionError):
            continue

        meta = parse_frontmatter(content)

        created = meta.get("createdAt", "")[:10]

        updated = meta.get("updatedAt", "")[:10]

        if created:
            if date_from and created < date_from:
                pass

            else:
                if date_to and created > date_to:
                    pass

                else:
                    events.append(
                        {
                            "date": created,
                            "source": source,
                            "type": "created",
                            "title": title or note_path.stem,
                            "excerpt": preview[:150],
                            "path": path,
                        }
                    )

        if updated and updated != created:
            if date_from and updated < date_from:
                pass

            else:
                if date_to and updated > date_to:
                    pass

                else:
                    events.append(
                        {
                            "date": updated,
                            "source": source,
                            "type": "updated",
                            "title": title or note_path.stem,
                            "excerpt": preview[:150],
                            "path": path,
                        }
                    )

    return events


def vault_timeline(
    query: Optional[str] = None,
    project: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    sources: Optional[List[str]] = None,
    limit: int = 40,
) -> Dict[str, Any]:
    sources = sources or ALL_SOURCES

    query = query or ""

    limit = min(limit, 100)

    if not from_date:
        from_date = "1900-01-01"

    if not to_date:
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    events: List[Dict[str, Any]] = []

    if "sessions" in sources:
        events.extend(search_sessions(query, from_date, to_date, limit))

    if "changelog" in sources:
        events.extend(search_changelog(query, project, from_date, to_date, limit))

    if any(
        s in sources
        for s in [
            "decisions",
            "errors",
            "patterns",
            "infra",
            "knowledge",
            "dependencies",
            "runbooks",
        ]
    ):
        events.extend(search_notes(query, sources, from_date, to_date, project, limit))

    events.sort(
        key=lambda x: (x["date"], 0 if x["type"] == "updated" else 1), reverse=True
    )

    events = events[:limit]

    by_source: Dict[str, int] = {}

    for e in events:
        src = e.get("source", "unknown")

        by_source[src] = by_source.get(src, 0) + 1

    return {
        "ok": True,
        "query": query,
        "project": project,
        "from": from_date,
        "to": to_date,
        "sources": sources,
        "total": len(events),
        "shown": len(events),
        "bySource": by_source,
        "events": events,
        "hint": "Usa vault_read(path) en cualquier evento para ver el contenido completo.",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Timeline Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_timeline.py --query "database"

  python vault_timeline.py --query "autenticacion" --project "ans"

  python vault_timeline.py --query "deploy" --from "2026-01-01" --to "2026-05-06"

  python vault_timeline.py --sources "sessions,changelog,decisions,errors"

  python vault_timeline.py --limit 20



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Cruza sesiones, changelogs, decisiones, errores, patrones, infra, knowledge y runbooks

  - Las fuentes disponibles: sessions, changelog, decisions, errors, patterns, infra, knowledge, dependencies, runbooks

""",
    )

    parser.add_argument("--query", help="Topic to trace")

    parser.add_argument("--project", help="Filter by project")

    parser.add_argument("--from", dest="from_date", help="Start date YYYY-MM-DD")

    parser.add_argument("--to", dest="to_date", help="End date YYYY-MM-DD")

    parser.add_argument("--sources", help=f"Sources: {ALL_SOURCES} (comma-separated)")

    parser.add_argument("--limit", type=int, default=40, help="Max events")

    args = parser.parse_args()

    sources = None

    if args.sources:
        sources = [s.strip() for s in args.sources.split(",")]

    result = vault_timeline(
        args.query,
        args.project,
        args.from_date,
        args.to_date,
        sources,
        args.limit,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_timeline"))

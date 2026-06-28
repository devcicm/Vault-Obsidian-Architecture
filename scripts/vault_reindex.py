#!/usr/bin/env python3

"""

Vault Reindex — Rebuild search-index.json (and optionally graph.json) from existing vault notes.



Use this when search-index.json is empty ({}), corrupted, or missing.

Scans all notes inside the 13 standard vault sections, parses frontmatter,

and rebuilds 99_Index/search-index.json from scratch.



This is the mandatory recovery tool for vaults managed by remote LLMs (DeepSeek,

GPT, Gemini, Claude API) or any harness that does not call vault_write for every

write operation. Run it at session start whenever search returns 0 results.



Usage:

    python vault_reindex.py              # rebuild search-index only

    python vault_reindex.py --graph      # also rebuild graph.json

    python vault_reindex.py --dry-run    # show what would be indexed without writing



Session-start check:

    python vault_reindex.py --check      # exit 0 if index OK, exit 1 if empty/missing

"""

import argparse

import hashlib

import json

import re

import sys

from vault_errors import wrap_main

from vault_lib import parse_frontmatter
from vault_io import atomic_write_json, VAULT_ROOT
from vault_registry import standard_folders
from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Dict, List


INDEX_FILE = VAULT_ROOT / "99_Index" / "search-index.json"

HASH_INDEX = VAULT_ROOT / "99_Index" / "hash-index.json"


VAULT_SECTIONS = set(standard_folders())


def _is_vault_note(path: Path) -> bool:
    try:
        parts = path.relative_to(VAULT_ROOT).parts

    except ValueError:
        return False

    if len(parts) < 2:
        return False

    return parts[0] in VAULT_SECTIONS


def _preview(content: str) -> str:
    body = content.split("---", 2)[-1] if content.count("---") >= 2 else content

    return body.strip()[:200].replace("\n", " ")


def _check_index() -> bool:
    """Return True if index exists and has at least 1 note."""

    if not INDEX_FILE.exists():
        return False

    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))

        return isinstance(data, dict) and len(data.get("notes", [])) > 0

    except (json.JSONDecodeError, OSError):
        return False


def vault_reindex(dry_run: bool = False, rebuild_graph: bool = False) -> Dict[str, Any]:
    notes: List[Dict[str, Any]] = []

    hash_notes: Dict[str, Any] = {}

    skipped = 0

    vault_files = [
        p
        for p in VAULT_ROOT.rglob("*.md")
        if _is_vault_note(p) and not any(part.startswith(".") for part in p.parts)
    ]

    for note_path in sorted(vault_files):
        try:
            content = note_path.read_text(encoding="utf-8")

        except (UnicodeDecodeError, PermissionError):
            skipped += 1

            continue

        rel_path = str(note_path.relative_to(VAULT_ROOT)).replace("\\", "/")

        meta = parse_frontmatter(content)

        title = meta.get("title") or note_path.stem

        tags = meta.get("tags") or []

        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        updated = meta.get("updatedAt") or meta.get("createdAt") or ""

        note_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        notes.append(
            {
                "path": rel_path,
                "title": title,
                "preview": _preview(content),
                "tags": tags,
                "updatedAt": updated,
            }
        )

        hash_notes[rel_path] = {
            "hash": note_hash,
            "size": len(content.encode("utf-8")),
            "cia_integrity": meta.get("cia_integrity", "medium"),
        }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    index_data = {
        "notes": notes,
        "rebuiltAt": now,
        "totalNotes": len(notes),
    }

    hash_index_data = {
        "snapshot_at": now,
        "notes": hash_notes,
    }

    if not dry_run:
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)

        atomic_write_json(INDEX_FILE, index_data)

        atomic_write_json(HASH_INDEX, hash_index_data)

    result: Dict[str, Any] = {
        "ok": True,
        "indexed": len(notes),
        "skipped": skipped,
        "dry_run": dry_run,
        "path": str(INDEX_FILE.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "hash_index": str(HASH_INDEX.relative_to(VAULT_ROOT)).replace("\\", "/"),
    }

    if rebuild_graph and not dry_run:
        try:
            graph_script = Path(__file__).parent / "vault_graph.py"

            if graph_script.exists():
                import subprocess

                proc = subprocess.run(
                    [sys.executable, str(graph_script)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                graph_result = json.loads(proc.stdout) if proc.stdout else {}

                result["graph"] = graph_result.get(
                    "stats", {"error": proc.stderr[:200]}
                )

        except Exception as e:
            result["graph"] = {"error": str(e)}

    # Rebuild section indexes + master index so navigation stays linked
    if not dry_run:
        try:
            from vault_section_index import vault_section_index
            from vault_registry import standard_folders

            for section in standard_folders():
                if section not in ("00_System", "99_Index"):
                    vault_section_index(section)
            from vault_master_index import vault_master_index

            vault_master_index()
            result["indexes_rebuilt"] = True
        except Exception as e:
            result["index_warning"] = str(e)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Reindex -- rebuild search-index.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_reindex.py

  python vault_reindex.py --graph

  python vault_reindex.py --dry-run

  python vault_reindex.py --check



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Usar al inicio de sesion si vault_search retorna 0 resultados

  - --check retorna exit 0 si el indice tiene al menos 1 nota, exit 1 si esta vacio/faltante

""",
    )

    parser.add_argument("--graph", action="store_true", help="Also rebuild graph.json")

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be indexed without writing",
    )

    parser.add_argument(
        "--check", action="store_true", help="Exit 0 if index OK, 1 if empty/missing"
    )

    args = parser.parse_args()

    if args.check:
        ok = _check_index()

        if ok:
            try:
                data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))

                count = len(data.get("notes", []))

            except Exception:
                count = 0

            print(json.dumps({"ok": True, "status": "index_ok", "notes": count}))

            return 0

        else:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "status": "index_empty_or_missing",
                        "action": "run vault_reindex.py",
                    }
                )
            )

            return 1

    result = vault_reindex(dry_run=args.dry_run, rebuild_graph=args.graph)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_reindex"))

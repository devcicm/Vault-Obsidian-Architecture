#!/usr/bin/env python3

"""

Vault Reindex — Rebuild search-index.json (and optionally graph.json) from existing vault notes.



Use this when search-index.json is empty ({}), corrupted, or missing.

Scans all notes inside the standard vault sections -- las que declara

vault_registry.standard_folders(), no una cifra propia: decir "13" era una

tercera verdad sobre cuantas secciones tiene un vault --, parses frontmatter,

and rebuilds 99_Index/search-index.json from scratch.



This is the mandatory recovery tool for vaults managed by remote LLMs (DeepSeek,

GPT, Gemini, Claude API) or any harness that does not call vault_write for every

write operation. Run it at session start whenever search returns 0 results.



Usage:

    python vault_reindex.py              # rebuild search-index only

    python vault_reindex.py --graph      # also rebuild graph.json

    python vault_reindex.py --dry-run    # show what would be indexed without writing



Session-start check:

    python vault_reindex.py --check      # exit 0 si refleja el disco, 1 si hay desfase

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


def _is_vault_note(path: Path, root: Path = None) -> bool:
    try:
        parts = path.relative_to(root or VAULT_ROOT).parts

    except ValueError:
        return False

    if len(parts) < 2:
        return False

    return parts[0] in VAULT_SECTIONS


def _preview(content: str) -> str:
    body = content.split("---", 2)[-1] if content.count("---") >= 2 else content

    return body.strip()[:200].replace("\n", " ")


def _notas_en_disco(root: Path = None) -> List[Path]:
    """Las notas que la reconstrucción indexaría, con SU mismo criterio.

    Se extrae aquí para que la comprobación y la reconstrucción no puedan
    discrepar: si el `--check` contara con un criterio propio, mediría otra cosa
    que el `--fix` y el desfase que reportara no sería el que se arregla
    (AP-44).
    """
    raiz = root or VAULT_ROOT
    return [
        p
        for p in raiz.rglob("*.md")
        if _is_vault_note(p, raiz) and not any(part.startswith(".") for part in p.parts)
    ]


def index_coherence(root: Path = None) -> Dict[str, Any]:
    """Contrasta search-index.json y graph.json contra lo que hay en disco.

    Lo que había antes era `len(notes) > 0`: un índice con UNA entrada sobre un
    vault de 300 notas devolvía `index_ok`. Es una puerta que no mide lo que
    dice medir (familia AP-37), y en la tool cuya única razón de existir es
    reconciliar. Medido al escribir esto: `vault-sandbox` tenía 111 notas en
    disco, 110 en el índice y 100 nodos en el grafo; un vault real, 317 / 290 /
    232. Los dos pasaban.

    Se reportan las dos direcciones, porque significan cosas distintas:
    `missing_in_index` son notas invisibles para `vault_search` —el agente no
    sabe que existen—, y `stale_in_index` son entradas que apuntan a ficheros
    que ya no están: el agente las encuentra y luego no puede abrirlas.

    El grafo se compara aparte y **no** decide el veredicto: se regenera solo
    con `--graph`, y contarlo como fallo convertiría el check en ruido en cada
    vault que no lo pide. Se informa para que el desfase sea visible.
    """
    raiz = Path(root) if root else VAULT_ROOT
    index_file = raiz / "99_Index" / "search-index.json"
    en_disco = {
        str(p.relative_to(raiz)).replace("\\", "/") for p in _notas_en_disco(raiz)
    }

    if not index_file.exists():
        return {
            "ok": False,
            "status": "index_missing",
            "on_disk": len(en_disco),
            "indexed": 0,
            "missing_in_index": sorted(en_disco)[:20],
            "stale_in_index": [],
            "graph_nodes": None,
        }

    try:
        data = json.loads(index_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise json.JSONDecodeError("no es un objeto", "", 0)
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "ok": False,
            "status": "index_corrupt",
            "error": f"{type(exc).__name__}: {exc}",
            "on_disk": len(en_disco),
            "indexed": 0,
            "missing_in_index": sorted(en_disco)[:20],
            "stale_in_index": [],
            "graph_nodes": None,
        }

    indexadas = {
        str(n.get("path", "")).replace("\\", "/")
        for n in data.get("notes", [])
        if n.get("path")
    }
    faltan = sorted(en_disco - indexadas)
    sobran = sorted(indexadas - en_disco)

    nodos = None
    graph_file = raiz / "99_Index" / "graph.json"
    if graph_file.exists():
        try:
            nodos = len(json.loads(graph_file.read_text(encoding="utf-8")).get("nodes", []))
        except (json.JSONDecodeError, OSError):
            nodos = None

    if not en_disco and not indexadas:
        estado = "index_ok"  # vault vacío: un índice vacío lo refleja
    elif faltan or sobran:
        estado = "index_stale"
    else:
        estado = "index_ok"

    return {
        "ok": estado == "index_ok",
        "status": estado,
        "on_disk": len(en_disco),
        "indexed": len(indexadas),
        "missing_in_index": faltan[:20],
        "missing_count": len(faltan),
        "stale_in_index": sobran[:20],
        "stale_count": len(sobran),
        "graph_nodes": nodos,
        "graph_drift": (None if nodos is None else len(en_disco) - nodos),
    }


def _check_index() -> bool:
    """True si el índice refleja el disco. Ver `index_coherence()`."""
    return bool(index_coherence()["ok"])


def vault_reindex(dry_run: bool = False, rebuild_graph: bool = False) -> Dict[str, Any]:
    notes: List[Dict[str, Any]] = []

    hash_notes: Dict[str, Any] = {}

    skipped = 0

    # El mismo criterio que usa `index_coherence()`, y por eso una sola función:
    # dos copias de esta comprensión eran dos definiciones de "qué es una nota
    # indexable" que podían separarse sin que nada fallara.
    vault_files = _notas_en_disco()

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

  - --check retorna exit 0 si el indice REFLEJA el disco, exit 1 si hay desfase

""",
    )

    parser.add_argument("--graph", action="store_true", help="Also rebuild graph.json")

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be indexed without writing",
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 si el índice refleja el disco, 1 si hay desfase",
    )

    args = parser.parse_args()

    if args.check:
        informe = index_coherence()
        informe["tool"] = "vault_reindex"
        if not informe["ok"]:
            informe["action"] = "python vault_reindex.py"
        print(json.dumps(informe, indent=2, ensure_ascii=False))
        return 0 if informe["ok"] else 1

    result = vault_reindex(dry_run=args.dry_run, rebuild_graph=args.graph)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_reindex"))

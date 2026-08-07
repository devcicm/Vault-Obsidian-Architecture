#!/usr/bin/env python3

"""
Vault Move — Reubica notas entre carpetas del vault.

Mueve notas entre carpetas, actualiza todos los wiki-links internos,
actualiza search-index.json y graph.json, y mantiene historial de versiones.

Usage:
    python vault_move.py --from "01_Projects/old/note.md" --to "03_Decisions/note.md"
    python vault_move.py --folder "01_Projects/old" --to "01_Projects/new"
    python vault_move.py --from "01_Projects/foo.md" --to "03_Decisions/foo.md" --dry-run
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from vault_errors import wrap_main
from vault_io import atomic_write_text, write_report


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _system_dir() -> Path:
    return _repo().dir_sistema


def _index_dir() -> Path:
    return _repo().dir_indices


def _search_index() -> Path:
    return _repo().indice_busqueda


def _graph_file() -> Path:
    return _repo().grafo


def _move_log() -> Path:
    return _repo().dir_sistema / "move-log.json"


def load_move_log() -> List[Dict[str, Any]]:
    """Carga el historial de movimientos."""
    if _move_log().exists():
        return json.loads(_move_log().read_text(encoding="utf-8"))
    return []


def save_move_log(log: List[Dict[str, Any]]) -> None:
    """Guarda el historial de movimientos."""
    _system_dir().mkdir(parents=True, exist_ok=True)
    _move_log().write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


def update_wiki_links_in_file(
    file_path: Path, old_stem: str, new_stem: str, old_folder: str, new_folder: str
) -> Dict[str, Any]:
    """Actualiza los wiki-links en un archivo."""
    content = file_path.read_text(encoding="utf-8")
    original = content

    old_link = f"[[{old_stem}]]"
    new_link = f"[[{new_stem}]]"
    content = content.replace(old_link, new_link)

    old_link_with_path = f"[[{old_folder}/{old_stem}]]"
    new_link_with_path = f"[[{new_folder}/{new_stem}]]"
    content = content.replace(old_link_with_path, new_link_with_path)

    old_alias = f"[[{old_folder}/{old_stem}|"
    new_alias = f"[[{new_folder}/{new_stem}|"
    content = content.replace(old_alias, new_alias)

    if content != original:
        atomic_write_text(file_path, content)
        return {"updated": True, "links_changed": True}

    return {"updated": False, "links_changed": False}


def update_search_index(old_path: str, new_path: str) -> Dict[str, Any]:
    """Actualiza search-index.json con la nueva ubicación."""
    if not _search_index().exists():
        return {"updated": False, "reason": "search-index not found"}

    index_data = json.loads(_search_index().read_text(encoding="utf-8"))
    if not isinstance(index_data, dict):
        return {"updated": False, "reason": "search-index con esquema no reconocido"}
    updated = False

    for note in index_data.get("notes", []):
        if not isinstance(note, dict):
            continue
        if note.get("path") == old_path:
            note["path"] = new_path
            note["updated_at"] = datetime.now(timezone.utc).isoformat()
            updated = True

    if updated:
        atomic_write_text(
            _search_index(), json.dumps(index_data, indent=2, ensure_ascii=False)
        )

    return {"updated": updated}


def update_graph(old_path: str, new_path: str, dry_run: bool = False) -> Dict[str, Any]:
    """Actualiza graph.json con la nueva ubicación."""
    if not _graph_file().exists():
        return {"updated": False, "reason": "graph not found"}

    graph_data = json.loads(_graph_file().read_text(encoding="utf-8"))
    if not isinstance(graph_data, dict):
        return {"updated": False, "reason": "graph con esquema no reconocido"}
    old_stem = Path(old_path).stem
    new_stem = Path(new_path).stem
    old_folder = str(Path(old_path).parent)
    new_folder = str(Path(new_path).parent)

    updated = False

    # Los grafos legacy guardan `nodes` como lista de strings (el stem), no de
    # objetos. Un vault preexistente puede traer cualquiera de las dos formas y
    # mover una nota no puede depender de cuál le tocó.
    nodes = graph_data.get("nodes", [])
    for i, node in enumerate(nodes):
        if isinstance(node, str):
            if node == old_stem or node == old_path:
                nodes[i] = new_stem if node == old_stem else new_path
                updated = True
            continue
        if not isinstance(node, dict):
            continue
        if node.get("id") == old_stem or node.get("path") == old_path:
            node["id"] = new_stem
            node["path"] = new_path
            node["title"] = new_stem.replace("-", " ").replace("_", " ").title()
            node["updated_at"] = datetime.now(timezone.utc).isoformat()
            updated = True

    if not dry_run and updated:
        atomic_write_text(
            _graph_file(), json.dumps(graph_data, indent=2, ensure_ascii=False)
        )

    return {"updated": updated}


def move_note(
    from_path: str, to_path: str, dry_run: bool = False, backup: bool = True
) -> Dict[str, Any]:
    """Mueve una nota a una nueva ubicación."""
    source = _raiz() / from_path
    destination = _raiz() / to_path

    if not source.exists():
        return {"ok": False, "error": f"Archivo no encontrado: {from_path}"}

    if destination.exists():
        return {"ok": False, "error": f"Destino ya existe: {to_path}"}

    destination.parent.mkdir(parents=True, exist_ok=True)

    if not dry_run:
        if backup:
            # AP-36: el .bak NO se deja junto al nodo (contamina la sección y el
            # grafo); va a 00_System/.trash/ con timestamp para rastreabilidad.
            trash_dir = _raiz() / "00_System" / ".trash"
            trash_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            backup_path = trash_dir / f"{source.stem}-{ts}{source.suffix}.bak"
            shutil.copy2(source, backup_path)

        shutil.move(str(source), str(destination))

    old_stem = source.stem
    new_stem = destination.stem
    old_folder = str(source.parent.relative_to(_raiz()))
    new_folder = str(destination.parent.relative_to(_raiz()))

    links_updated = 0
    files_checked = 0

    for md in _raiz().rglob("*.md"):
        if ".history" in str(md):
            continue
        if md == destination:
            continue

        files_checked += 1
        result = update_wiki_links_in_file(
            md, old_stem, new_stem, old_folder, new_folder
        )
        if result.get("links_changed"):
            links_updated += 1

    # A partir del shutil.move el movimiento ya es un hecho en disco. Si la
    # actualización de los índices falla (esquema legacy, JSON corrupto), la tool
    # no puede devolver ok:false: eso deja al agente creyendo que no movió nada
    # cuando sí lo hizo. Se degrada a aviso y se pide el reindex.
    degraded: List[str] = []

    def _safe(nombre: str, fn) -> Dict[str, Any]:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - el movimiento ya ocurrió
            degraded.append(f"{nombre}: {type(exc).__name__}: {exc}")
            return {"updated": False, "error": str(exc)}

    search_result = _safe("search-index", lambda: update_search_index(from_path, to_path))
    graph_result = _safe("graph", lambda: update_graph(from_path, to_path, dry_run))

    move_record = {
        "from": from_path,
        "to": to_path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "links_updated": links_updated,
        "files_checked": files_checked,
        "dry_run": dry_run,
    }

    if not dry_run:
        move_log = load_move_log()
        move_log.append(move_record)
        save_move_log(move_log)

    return {
        "ok": True,
        **write_report(),
        "dry_run": dry_run,
        "moved": f"{from_path} -> {to_path}",
        "links_updated": links_updated,
        "files_checked": files_checked,
        "search_index_updated": search_result.get("updated"),
        "graph_updated": graph_result.get("updated"),
        "degraded": degraded,
        "next": "vault_reindex --graph" if degraded else None,
        "record": move_record,
    }


def move_folder(
    from_folder: str, to_folder: str, dry_run: bool = False
) -> Dict[str, Any]:
    """Mueve una carpeta completa."""
    source = _raiz() / from_folder
    destination = _raiz() / to_folder

    if not source.exists():
        return {"ok": False, "error": f"Carpeta no encontrada: {from_folder}"}

    if destination.exists():
        return {"ok": False, "error": f"Destino ya existe: {to_folder}"}

    notes_moved = []

    for md in source.rglob("*.md"):
        if ".history" in str(md):
            continue

        relative = md.relative_to(source)
        new_path = f"{to_folder}/{relative}"

        result = move_note(
            str(from_folder + "/" + relative.name),
            new_path,
            dry_run=dry_run,
            backup=False,
        )

        if result.get("ok"):
            notes_moved.append({"from": str(relative), "to": new_path})

    if not dry_run:
        try:
            shutil.rmtree(source)
        except Exception:
            pass

    return {
        "ok": True,
        **write_report(),
        "dry_run": dry_run,
        "notes_moved": len(notes_moved),
        "details": notes_moved,
    }


def check_move_impact(from_path: str, to_path: str) -> Dict[str, Any]:
    """Analiza el impacto de un movimiento sin ejecutarlo."""
    source = _raiz() / from_path

    if not source.exists():
        return {"ok": False, "error": f"Archivo no encontrado: {from_path}"}

    content = source.read_text(encoding="utf-8")
    old_stem = source.stem
    old_folder = str(source.parent.relative_to(_raiz()))

    wiki_links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)

    backlinks = []
    for md in _raiz().rglob("*.md"):
        if ".history" in str(md):
            continue
        if md == source:
            continue

        try:
            md_content = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if (
            f"[[{old_stem}]]" in md_content
            or f"[[{old_folder}/{old_stem}]]" in md_content
        ):
            backlinks.append(str(md.relative_to(_raiz())))

    return {
        "ok": True,
        **write_report(),
        "source": from_path,
        "destination": to_path,
        "backlinks_count": len(backlinks),
        "backlinks": backlinks,
        "will_update_index": True,
        "will_update_graph": True,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Move - Reubica notas entre carpetas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_move.py --from "01_Projects/old/note.md" --to "03_Decisions/note.md"
  python vault_move.py --folder "01_Projects/old" --to "01_Projects/new"
  python vault_move.py --from "01_Projects/foo.md" --to "03_Decisions/foo.md" --dry-run
  python vault_move.py --impact --from "01_Projects/foo.md" --to "03_Decisions/foo.md"
        """,
    )

    parser.add_argument("--from", dest="from_path", type=str, help="Nota origen")
    parser.add_argument("--to", dest="to_path", type=str, help="Nota destino")
    parser.add_argument(
        "--folder", type=str, help="Carpeta origen (mover toda la carpeta)"
    )
    parser.add_argument(
        "--to-folder", dest="to_folder", type=str, help="Carpeta destino"
    )
    parser.add_argument("--dry-run", action="store_true", help="Simular sin aplicar")
    parser.add_argument(
        "--impact", action="store_true", help="Analizar impacto sin ejecutar"
    )
    parser.add_argument("--json", action="store_true", help="Salida JSON")

    args = parser.parse_args()

    if args.impact:
        if not args.from_path or not args.to_path:
            print("Error: --impact requiere --from y --to")
            return 1
        result = check_move_impact(args.from_path, args.to_path)
    elif args.folder:
        if not args.to_folder:
            print("Error: --folder requiere --to-folder")
            return 1
        result = move_folder(args.folder, args.to_folder, dry_run=args.dry_run)
    elif args.from_path and args.to_path:
        result = move_note(args.from_path, args.to_path, dry_run=args.dry_run)
    else:
        parser.print_help()
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("ok", True):
            if args.dry_run:
                print(f"[SIMULACIÓN] ", end="")
            if "notes_moved" in result:
                print(f"Notas movidas: {result['notes_moved']}")
            else:
                print(f"Movido: {result.get('moved')}")
                print(f"Links actualizados: {result.get('links_updated')}")
                if args.impact:
                    print(f"Backlinks encontrados: {result.get('backlinks_count')}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
            return 1

    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_move"))

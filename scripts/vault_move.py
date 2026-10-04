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

from vault_regex import RE_WIKILINK  # dueño único del patrón (AP-50)

from vault_errors import emit_error, fuera_de_sesion, mensaje_de, wrap_main
from vault_io import (
    assert_within_vault, atomic_write_text, file_lock, tomar_lock, write_report,
)


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.indices_structural import es_nombre_reservado  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _fuera_del_vault(*rutas: str) -> Optional[Dict[str, Any]]:
    """AP-36: el envelope de rechazo si alguna ruta sale del vault, o None.

    Hasta 2026-10-02 nada lo comprobaba: `--from ../x.md` metía en el vault un
    fichero de fuera y borraba el original, `--to ../x.md` sacaba la nota, y
    `--impact` leía lo que se le señalara. La raíz misma tampoco vale: mover el
    vault dentro de sí mismo no es mover una carpeta.
    """
    raiz = _raiz()
    for ruta in rutas:
        try:
            if assert_within_vault(raiz / ruta, raiz) == raiz.resolve():
                raise ValueError(f"'{ruta}' es la raíz del vault, no una ruta dentro de él.")
        except ValueError as exc:
            return emit_error("vault_move", "INVALID_PATH", str(exc))
    return None


def _fuera_de_sesion(*rutas: str) -> Optional[Dict[str, Any]]:
    """AP-63, P5: con la sesión atada, ni el origen ni el destino pueden ser
    de otro proyecto — mover es escribir en los dos. `--impact` solo lee y
    no pasa por aquí."""
    return fuera_de_sesion("vault_move", *(_raiz() / ruta for ruta in rutas))


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


#: Espera máxima por el lock de una nota o de un índice. La misma que
#: `vault_write` y `vault_append`: el move compite con ellos por las mismas notas.
_LOCK_TIMEOUT = 10.0


def _reescribir_json(path: Path, cambiar) -> Dict[str, Any]:
    """Lee, cambia y escribe `path` bajo su lock (F1).

    No es `atomic_update_json`: esa sustituye un esquema que no sea dict por el
    default, y aquí un índice legacy con otra forma se deja como está.
    `cambiar(data)` devuelve True si modificó `data`. Un lock que no se consigue
    sale como TimeoutError, que el llamador declara como degradado.
    """
    with file_lock(path, timeout=_LOCK_TIMEOUT):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"updated": False, "reason": f"{path.name} con esquema no reconocido"}
        updated = cambiar(data)
        if updated:
            atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))
        return {"updated": updated}


def load_move_log() -> List[Dict[str, Any]]:
    """Carga el historial de movimientos."""
    if _move_log().exists():
        return json.loads(_move_log().read_text(encoding="utf-8"))
    return []


def save_move_log(log: List[Dict[str, Any]]) -> None:
    """Guarda el historial de movimientos."""
    _system_dir().mkdir(parents=True, exist_ok=True)
    atomic_write_text(_move_log(), json.dumps(log, indent=2, ensure_ascii=False))


def append_move_log(record: Dict[str, Any]) -> None:
    """Añade una entrada al historial bajo su lock: dos moves en paralelo no se
    comen la entrada del otro (F1)."""
    _system_dir().mkdir(parents=True, exist_ok=True)
    with file_lock(_move_log(), timeout=_LOCK_TIMEOUT):
        log = load_move_log()
        log.append(record)
        save_move_log(log)


def update_wiki_links_in_file(
    file_path: Path, old_stem: str, new_stem: str, old_folder: str, new_folder: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Actualiza los wiki-links en un archivo. Con `dry_run`, solo los cuenta."""
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
        if not dry_run:
            atomic_write_text(file_path, content)
        return {"updated": not dry_run, "links_changed": True}

    return {"updated": False, "links_changed": False}


def update_search_index(old_path: str, new_path: str, dry_run: bool = False) -> Dict[str, Any]:
    """Actualiza search-index.json con la nueva ubicación."""
    if not _search_index().exists():
        return {"updated": False, "reason": "search-index not found"}

    def cambiar(index_data: Dict[str, Any]) -> bool:
        updated = False
        for note in index_data.get("notes", []):
            if not isinstance(note, dict):
                continue
            if note.get("path") == old_path:
                note["path"] = new_path
                note["updated_at"] = datetime.now(timezone.utc).isoformat()
                updated = True
        return updated

    if dry_run:
        index_data = json.loads(_search_index().read_text(encoding="utf-8"))
        if not isinstance(index_data, dict):
            return {"updated": False, "reason": "search-index con esquema no reconocido"}
        return {"updated": cambiar(index_data)}
    return _reescribir_json(_search_index(), cambiar)


def update_graph(old_path: str, new_path: str, dry_run: bool = False) -> Dict[str, Any]:
    """Actualiza graph.json con la nueva ubicación."""
    if not _graph_file().exists():
        return {"updated": False, "reason": "graph not found"}

    old_stem = Path(old_path).stem
    new_stem = Path(new_path).stem
    old_folder = str(Path(old_path).parent)
    new_folder = str(Path(new_path).parent)

    def cambiar(graph_data: Dict[str, Any]) -> bool:
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
        return updated

    if dry_run:
        graph_data = json.loads(_graph_file().read_text(encoding="utf-8"))
        if not isinstance(graph_data, dict):
            return {"updated": False, "reason": "graph con esquema no reconocido"}
        return {"updated": cambiar(graph_data)}
    return _reescribir_json(_graph_file(), cambiar)


def move_note(
    from_path: str, to_path: str, dry_run: bool = False, backup: bool = True
) -> Dict[str, Any]:
    """Mueve una nota a una nueva ubicación."""
    rechazo = _fuera_del_vault(from_path, to_path) or _fuera_de_sesion(from_path, to_path)
    if rechazo:
        return rechazo
    source = _raiz() / from_path
    destination = _raiz() / to_path

    if not source.exists():
        return emit_error("vault_move", "FILE_NOT_FOUND", f"Archivo no encontrado: {from_path}")

    if destination.exists():
        return emit_error("vault_move", "INVALID_PATH", f"El destino ya existe: {to_path}")

    if dry_run:
        return _mover_nota(source, destination, from_path, to_path, dry_run, backup)
    # La nota se mueve bajo su lock: un vault_append o vault_write concurrente
    # no puede escribir en el origen mientras desaparece (F1). Si otro escritor
    # la tiene, no se mueve nada y se dice.
    lock = tomar_lock(source, _LOCK_TIMEOUT)
    if lock is None:
        return {
            **emit_error(
                "vault_move", "NOTE_LOCKED",
                f"Otro escritor tiene {from_path}; no se movió nada.",
            ),
            "path": from_path,
        }
    with lock:
        if not source.exists():
            return emit_error("vault_move", "FILE_NOT_FOUND", f"Archivo no encontrado: {from_path}")
        return _mover_nota(source, destination, from_path, to_path, dry_run, backup)


def _mover_nota(
    source: Path, destination: Path, from_path: str, to_path: str,
    dry_run: bool, backup: bool,
) -> Dict[str, Any]:
    # Con --dry-run nada toca el disco: ni la carpeta destino, ni los enlaces
    # de otras notas, ni el índice. Medido en v40.34: la simulación reescribía
    # `[[a]]` → `[[z]]` en las notas que enlazaban y creaba la carpeta destino
    # con su index.md, dejando enlaces a una nota que no se había movido.
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
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
    # Con `/` aunque corra en Windows: es la forma en que Obsidian escribe el
    # enlace anclado, y con `\` el `[[carpeta/nota]]` no se reescribía nunca.
    old_folder = source.parent.relative_to(_raiz()).as_posix()
    new_folder = destination.parent.relative_to(_raiz()).as_posix()

    links_updated = 0
    files_checked = 0
    links_pending: List[str] = []

    for md in _raiz().rglob("*.md"):
        if ".history" in str(md):
            continue
        if md == destination:
            continue

        files_checked += 1
        # Sonda sin lock: casi ninguna nota enlaza a la movida, y tomar un lock
        # por cada nota del vault sería caro. Solo las que cambian se reescriben,
        # y se releen bajo su lock para no escribir encima de un append (F1).
        sonda = update_wiki_links_in_file(
            md, old_stem, new_stem, old_folder, new_folder, dry_run=True
        )
        if not sonda.get("links_changed"):
            continue
        if dry_run:
            links_updated += 1
            continue
        nota_lock = tomar_lock(md, _LOCK_TIMEOUT)
        if nota_lock is None:
            links_pending.append(md.relative_to(_raiz()).as_posix())
            continue
        with nota_lock:
            result = update_wiki_links_in_file(
                md, old_stem, new_stem, old_folder, new_folder, dry_run=False
            )
        if result.get("links_changed"):
            links_updated += 1

    # A partir del shutil.move el movimiento ya es un hecho en disco. Si la
    # actualización de los índices falla (esquema legacy, JSON corrupto), la tool
    # no puede devolver ok:false: eso deja al agente creyendo que no movió nada
    # cuando sí lo hizo. Se degrada a aviso y se pide el reindex.
    degraded: List[str] = [
        f"links: {rel} tenía el lock tomado; su enlace sigue apuntando a {old_stem}"
        for rel in links_pending
    ]

    def _safe(nombre: str, fn) -> Dict[str, Any]:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - el movimiento ya ocurrió
            degraded.append(f"{nombre}: {type(exc).__name__}: {exc}")
            return {"updated": False, "error": str(exc)}

    search_result = _safe("search-index", lambda: update_search_index(from_path, to_path, dry_run))
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
        _safe("move-log", lambda: append_move_log(move_record))

    return {
        "ok": True,
        **write_report(),
        "dry_run": dry_run,
        "moved": f"{from_path} -> {to_path}",
        "links_updated": links_updated,
        "files_checked": files_checked,
        "search_index_updated": search_result.get("updated"),
        "graph_updated": graph_result.get("updated"),
        "links_pending": links_pending,
        "degraded": degraded,
        "next": "vault_reindex --graph" if degraded else None,
        "record": move_record,
    }


def move_folder(
    from_folder: str, to_folder: str, dry_run: bool = False
) -> Dict[str, Any]:
    """Mueve una carpeta completa: notas, subcarpetas y adjuntos.

    Medido en v40.34: con `relative.name` las notas de una subcarpeta se
    buscaban en la raíz de la carpeta, fallaban con FILE_NOT_FOUND, y el
    `shutil.rmtree(source)` final las borraba junto con todo adjunto que no
    fuera `.md` — con `ok: true`. Ahora nada se borra:

    - todos los destinos se comprueban ANTES de mover nada; si uno existe,
      INVALID_PATH y la carpeta queda intacta;
    - cada fichero conserva su ruta relativa (subcarpetas incluidas);
    - los índices generados (`index.md`) los rehace el destino, así que el
      del origen va a `00_System/.trash/` en vez de a la basura;
    - del origen solo se retiran los directorios que quedan vacíos.
    """
    rechazo = _fuera_del_vault(from_folder, to_folder) or _fuera_de_sesion(from_folder, to_folder)
    if rechazo:
        return rechazo
    source = _raiz() / from_folder
    destination = _raiz() / to_folder

    if not source.exists():
        return emit_error("vault_move", "FOLDER_NOT_FOUND", f"Carpeta no encontrada: {from_folder}")

    if destination.exists():
        return emit_error("vault_move", "INVALID_PATH", f"El destino ya existe: {to_folder}")

    ficheros = sorted(
        f for f in source.rglob("*")
        if f.is_file() and ".history" not in f.parts and ".locks" not in f.parts
    )
    indices = [f for f in ficheros if f.suffix == ".md" and es_nombre_reservado(f.name)]
    notas = [f for f in ficheros if f.suffix == ".md" and f not in indices]
    adjuntos = [f for f in ficheros if f.suffix != ".md"]

    plan = [(f, f.relative_to(source).as_posix()) for f in notas + adjuntos]
    ocupados = [rel for _, rel in plan if (destination / rel).exists()]
    if ocupados:
        return emit_error(
            "vault_move", "INVALID_PATH",
            f"Destinos ya existentes en {to_folder}: {ocupados[:5]}",
        )

    notes_moved = []
    attachments_moved = []
    for k, (f, rel) in enumerate(plan):
        origen = f"{from_folder}/{rel}"
        nuevo = f"{to_folder}/{rel}"
        if f.suffix == ".md":
            result = move_note(origen, nuevo, dry_run=dry_run, backup=False)
            if not result.get("ok"):
                # El plan se comprobó entero; si aun así falla, se para aquí con
                # lo ya movido declarado, y el origen conserva el resto.
                return {
                    **result,
                    "notes_moved": len(notes_moved),
                    "details": notes_moved,
                    "attachments_moved": attachments_moved,
                    "pending": [r for _, r in plan[k:]],
                }
            notes_moved.append({"from": rel, "to": nuevo})
        else:
            if not dry_run:
                (destination / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(destination / rel))
            attachments_moved.append(nuevo)

    trashed = []
    if not dry_run:
        if indices:
            trash_dir = _raiz() / "00_System" / ".trash"
            trash_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            for f in indices:
                rel = f.relative_to(source).as_posix()
                if not f.exists():
                    continue
                apartado = trash_dir / f"{rel.replace('/', '__')}-{ts}.bak"
                shutil.move(str(f), str(apartado))
                trashed.append(apartado.relative_to(_raiz()).as_posix())
        # Solo directorios vacíos, de dentro hacia fuera. Lo que quede (un
        # fichero que llegó durante el movimiento) se queda donde está.
        for d in sorted((p for p in source.rglob("*") if p.is_dir()),
                        key=lambda p: len(p.parts), reverse=True) + [source]:
            try:
                if (d / ".locks").is_dir():
                    (d / ".locks").rmdir()  # solo si está vacío
                d.rmdir()
            except OSError:
                pass

    return {
        "ok": True,
        **write_report(),
        "dry_run": dry_run,
        "notes_moved": len(notes_moved),
        "details": notes_moved,
        "attachments_moved": attachments_moved,
        "indexes_trashed": trashed,
        "source_removed": not source.exists(),
    }


def check_move_impact(from_path: str, to_path: str) -> Dict[str, Any]:
    """Analiza el impacto de un movimiento sin ejecutarlo."""
    rechazo = _fuera_del_vault(from_path, to_path)
    if rechazo:
        return rechazo
    source = _raiz() / from_path

    if not source.exists():
        return emit_error("vault_move", "FILE_NOT_FOUND", f"Archivo no encontrado: {from_path}")

    content = source.read_text(encoding="utf-8")
    old_stem = source.stem
    old_folder = source.parent.relative_to(_raiz()).as_posix()

    wiki_links = RE_WIKILINK.findall(content)

    backlinks = []
    for md in _raiz().rglob("*.md"):
        if ".history" in str(md):
            continue
        if md == source:
            continue

        try:
            md_content = md.read_text(encoding="utf-8", errors="ignore")
        except (UnicodeDecodeError, PermissionError, OSError):
            continue

        if (
            f"[[{old_stem}]]" in md_content
            or f"[[{old_folder}/{old_stem}]]" in md_content
        ):
            backlinks.append(md.relative_to(_raiz()).as_posix())

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
        allow_abbrev=False,
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

    def uso_invalido(mensaje: str) -> int:
        # Con --json (lo que pasa siempre el MCP) la salida entera es un
        # envelope: un «Error:» en texto plano no lo puede leer el servidor.
        if args.json:
            print(json.dumps(emit_error("vault_move", "INVALID_INPUT", mensaje),
                             indent=2, ensure_ascii=False))
        elif mensaje:
            print(f"Error: {mensaje}")
        else:
            parser.print_help()
        return 1

    if args.impact:
        if not args.from_path or not args.to_path:
            return uso_invalido("--impact requiere --from y --to")
        result = check_move_impact(args.from_path, args.to_path)
    elif args.folder:
        if not args.to_folder:
            return uso_invalido("--folder requiere --to-folder")
        result = move_folder(args.folder, args.to_folder, dry_run=args.dry_run)
    elif args.from_path and args.to_path:
        result = move_note(args.from_path, args.to_path, dry_run=args.dry_run)
    elif args.json:
        return uso_invalido("indica --from y --to, o --folder y --to-folder")
    else:
        return uso_invalido("")

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
            print(f"Error: {mensaje_de(result) or 'Unknown error'}")
            return 1

    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_move"))

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
import posixpath
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote, unquote

from vault_regex import RE_WIKILINK  # dueño único del patrón (AP-50)

from vault_errors import emit_error, fuera_de_sesion, mensaje_de, wrap_main
from vault_io import (
    assert_within_vault, atomic_write_text, file_lock, refrescar_grafo, tomar_lock,
    write_report,
)
from vault_lib import indice_de_nombres, resolver_wikilink, utcnow
from vault_registry import motivo_de_destino_invalido, section_types, type_misfiled_in


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402
from vault.kernel.frontmatter_parsing import (  # noqa: E402
    parse_frontmatter_with_body, separar_frontmatter,
)
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
    # La declara y la escribe Grafo, su dueño (deuda #3, residuo, 2026-10-08).
    return _repo().bitacora_movimientos


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
    """Guarda el historial de movimientos. Lo escribe Grafo, su dueño."""
    _repo().escribir_bitacora_movimientos(log)


def append_move_log(record: Dict[str, Any]) -> None:
    """Añade una entrada al historial bajo su lock: dos moves en paralelo no se
    comen la entrada del otro (F1). El lock y la escritura son del dueño."""
    _repo().anotar_movimiento(record, timeout=_LOCK_TIMEOUT)


#: Un wikilink entero, con su `!` de incrustación: el interior se parte a mano
#: porque la barra escapada de una celda de tabla no es un separador que el patrón del
#: dueño (`vault_regex`) conozca, y la reescritura tiene que conservarlo.
_RE_WIKILINK_ENTERO = re.compile(r"(!?)\[\[([^\]\[]+?)\]\]")
#: Destino de un enlace markdown: `[texto](destino)`.
_RE_ENLACE_MD = re.compile(r"(\]\()([^)\s]+)(\))")
_RE_ESQUEMA = re.compile(r"[a-z][a-z0-9+.-]*:", re.IGNORECASE)
_BARRA = chr(92)


def _sin_md(ruta: str) -> str:
    return ruta[:-3] if ruta.lower().endswith(".md") else ruta


def _destino_nuevo(escrito: str, desde: str, new_rel: str) -> str:
    """El destino que sustituye a `escrito`, en su misma forma.

    Desnudo sigue desnudo, con carpeta lleva la ruta nueva desde la raíz y
    relativo (`./`, `../`) sigue relativo a la nota que enlaza.
    """
    sufijo = escrito[-3:] if escrito.lower().endswith(".md") else ""
    nuevo = _sin_md(new_rel)
    if escrito.startswith(("./", "../")):
        nuevo = posixpath.relpath(nuevo, posixpath.dirname(desde) or ".")
        if not nuevo.startswith(".."):
            nuevo = "./" + nuevo
    elif "/" not in escrito:
        nuevo = posixpath.basename(nuevo)
    return nuevo + sufijo


def update_wiki_links_in_file(
    file_path: Path, old_rel: str, new_rel: str, indice: Dict[str, List[str]],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Reescribe en `file_path` todo enlace que resuelve a `old_rel`.

    AP-14 con el criterio del consumidor (AP-44): un enlace apunta a la nota
    movida si Obsidian lo resuelve a ella, y eso lo decide el dueño
    (`vault_lib.resolver_wikilink` sobre `indice_de_nombres`, AP-57), no tres
    `replace` literales. Hasta aquí siete de nueve formas corrientes —alias,
    ancla, mayúsculas, `.md`, enlace markdown, barra escapada de tabla— quedaban rotas
    con `links_pending: []` (medido como consumidor, 2026-10-10). Se conservan
    el ancla, el alias, el `!` y el `.md`. Un enlace que resuelve a varias
    notas no se toca: elegir una sería inventar la identidad, y se devuelve en
    `ambiguous`. Con `dry_run`, solo cuenta.
    """
    content = file_path.read_text(encoding="utf-8")
    desde = file_path.relative_to(_raiz()).as_posix()
    nuevo_contenido, _, ambiguo = _reescribir_enlaces(content, desde, old_rel, new_rel, indice)
    # Por diferencia de texto y no por enlaces casados: `[[b]]` sigue siendo
    # `[[b]]` si solo cambia la carpeta, y reescribir la nota igual dispara su
    # índice de sección, que recreaba la carpeta de origen de un move --folder.
    if nuevo_contenido != content:
        if not dry_run:
            atomic_write_text(file_path, nuevo_contenido)
        return {"updated": not dry_run, "links_changed": True, "ambiguous": ambiguo}

    return {"updated": False, "links_changed": False, "ambiguous": ambiguo}


def _reescribir_enlaces(
    content: str, desde: str, old_rel: str, new_rel: str, indice: Dict[str, List[str]],
):
    """`(texto, enlaces que resuelven a old_rel, hubo alguno ambiguo)`. Puro."""
    ambiguo = False
    cambios = 0

    def wikilink(m: "re.Match[str]") -> str:
        nonlocal ambiguo, cambios
        interior = m.group(2)
        corte = next((i for i, c in enumerate(interior) if c in "#|"), len(interior))
        destino, resto = interior[:corte], interior[corte:]
        escape = ""
        if destino.endswith(_BARRA) and resto.startswith("|"):
            destino, escape = destino[:-1], _BARRA
        ruta, candidatos = resolver_wikilink(destino, Path(desde), indice)
        if ruta != old_rel:
            ambiguo = ambiguo or (not ruta and old_rel in candidatos)
            return m.group(0)
        cambios += 1
        nuevo = _destino_nuevo(destino.strip(), desde, new_rel)
        return f"{m.group(1)}[[{nuevo}{escape}{resto}]]"

    def enlace_md(m: "re.Match[str]") -> str:
        nonlocal ambiguo, cambios
        href = m.group(2)
        ruta_href, almohadilla, ancla = href.partition("#")
        if _RE_ESQUEMA.match(href) or not ruta_href.lower().endswith(".md"):
            return m.group(0)
        claro = unquote(ruta_href)
        if claro.startswith("/"):
            junto = posixpath.normpath(claro.lstrip("/"))
        else:
            junto = posixpath.normpath(posixpath.join(posixpath.dirname(desde), claro))
        if junto == old_rel:
            nuevo = new_rel if claro.startswith("/") else posixpath.relpath(
                new_rel, posixpath.dirname(desde) or ".")
            nuevo = ("/" + nuevo) if claro.startswith("/") else nuevo
        else:
            # Formato «ruta más corta» de Obsidian: se resuelve como un wikilink.
            ruta, candidatos = resolver_wikilink(claro, Path(desde), indice)
            if ruta != old_rel:
                ambiguo = ambiguo or (not ruta and old_rel in candidatos)
                return m.group(0)
            nuevo = _destino_nuevo(claro, desde, new_rel)
        cambios += 1
        if "%" in ruta_href:
            nuevo = quote(nuevo, safe="/.-_~")
        return f"{m.group(1)}{nuevo}{almohadilla}{ancla}{m.group(3)}"

    texto = _RE_ENLACE_MD.sub(enlace_md, _RE_WIKILINK_ENTERO.sub(wikilink, content))
    return texto, cambios, ambiguo


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

    # AP-47: el grafo de hoy guarda `nodes` como dict indexado por ruta, y quien
    # sabe poner y quitar una nota en él es el refresco (`vault_io.refrescar_grafo`,
    # dueño `vault.grafo.refresco`), con el criterio de la reconstrucción. Hasta
    # aquí el bucle de abajo, escrito para las formas legacy, recorría ese dict con
    # `enumerate` y reventaba en cada move (medido como consumidor, 2026-10-10).
    nodes = json.loads(_graph_file().read_text(encoding="utf-8")).get("nodes")
    if isinstance(nodes, dict):
        if dry_run:
            return {"updated": old_path in nodes}
        refresco = refrescar_grafo(_raiz() / new_path, _raiz() / old_path)
        return {"updated": bool(refresco.get("refreshed")),
                **({"reason": refresco["reason"]} if refresco.get("reason") else {})}

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


def _carpeta_de(ruta: str) -> str:
    """La carpeta de una ruta relativa del vault, con `/` ("" si está en la raíz)."""
    ruta = ruta.replace("\\", "/").strip("/")
    return ruta.rsplit("/", 1)[0] if "/" in ruta else ""


def _destino_invalido(origen: str, destino_carpeta: str) -> Optional[Dict[str, Any]]:
    """CN-02 y AP-15: el envelope si el destino no es una sección del vault, o None.

    El criterio es el de `vault_write` (`motivo_de_destino_invalido`): mover
    una nota a una carpeta es escribirla allí. Una sección propia retirada no
    admite notas que vengan de fuera, pero sí reordenar las que ya tiene.
    """
    nueva = origen.replace("\\", "/").split("/")[0] != destino_carpeta.split("/")[0]
    try:
        motivo = motivo_de_destino_invalido(destino_carpeta, _raiz(), nueva=nueva)
    except ValueError as exc:
        return emit_error("vault_move", "DATA_FILE_CORRUPT", str(exc))
    if motivo:
        return emit_error(
            "vault_move", "INVALID_FOLDER", f"CN-02: destino {destino_carpeta!r}: {motivo}.",
            pista="Mover a una sección (vault_section --list enseña las del vault) o "
                  "declarar una propia NN_Nombre con vault_section --add.",
        )
    return None


def _tipo_de(nota: Path) -> Optional[str]:
    try:
        fm, _ = parse_frontmatter_with_body(nota.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None
    tipo = (fm or {}).get("type")
    return str(tipo) if tipo else None


def _tipo_ajeno(destino_carpeta: str, tipo: str) -> Optional[str]:
    """Por qué `tipo` no puede vivir en `destino_carpeta`; None si puede (CN-02)."""
    try:
        otras = type_misfiled_in(destino_carpeta, tipo, _raiz())
    except ValueError:
        return None  # el registro roto ya lo para `_destino_invalido`
    if not otras:
        return None
    seccion = destino_carpeta.split("/")[0]
    return f"type {tipo!r} pertenece a {', '.join(otras)}, no a {seccion}"


def _pista_de_tipo(destino_carpeta: str) -> str:
    seccion = destino_carpeta.split("/")[0]
    try:
        tipos = section_types(seccion, _raiz())
    except ValueError:
        tipos = ()
    validos = ", ".join(tipos) if tipos else "uno que no sea canónico de otra sección"
    return (f"Mover es reclasificar: pasar --type con un tipo de {seccion} ({validos}), "
            "o elegir la sección a la que el tipo pertenece.")


def _reclasificacion(source: Path, from_path: str, to_path: str,
                     note_type: Optional[str]):
    """(envelope de rechazo o None, {"from", "to"} si el tipo cambia o None).

    Hasta 2026-10-07 mover no miraba nada de esto: `03_Decisions/x.md` llegaba
    a `07_Knowledge/` con `type: decision`, que es justo lo que `vault_write`
    rechaza, y `--to scripts/x.md` sacaba la nota de toda sección. Ahora el
    tipo de la nota tiene que poder vivir en el destino, o se cambia con
    `--type`; cambiarlo en silencio sería decidir por el agente qué es la nota.
    """
    destino = _carpeta_de(to_path)
    rechazo = _destino_invalido(from_path, destino)
    if rechazo:
        return rechazo, None
    actual = _tipo_de(source)
    if note_type is not None:
        note_type = note_type.strip()
        motivo = "--type vacío" if not note_type else _tipo_ajeno(destino, note_type)
        if motivo:
            return emit_error("vault_move", "INVALID_INPUT", f"CN-02: {motivo}.",
                              pista=_pista_de_tipo(destino)), None
        return None, ({"from": actual, "to": note_type} if note_type != actual else None)
    motivo = _tipo_ajeno(destino, actual) if actual else None
    if motivo:
        return emit_error("vault_move", "INVALID_INPUT",
                          f"CN-02: {from_path} -> {to_path}: {motivo}.",
                          pista=_pista_de_tipo(destino)), None
    return None, None


def _escribir_tipo(nota: Path, tipo: str) -> None:
    """Fija `type` y refresca `updatedAt` (AP-13) por el dueño del bloque (AP-46)."""
    texto = nota.read_text(encoding="utf-8")
    bloque, cuerpo = separar_frontmatter(texto)
    fm = Frontmatter.editar(bloque or "").set("type", tipo, texto=True)
    if fm.tiene("updatedAt"):
        fm.set("updatedAt", utcnow())
    atomic_write_text(nota, fm.render() + "\n" + cuerpo)


def move_note(
    from_path: str, to_path: str, dry_run: bool = False, backup: bool = True,
    note_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Mueve una nota a una nueva ubicación; con `note_type`, la reclasifica."""
    rechazo = _fuera_del_vault(from_path, to_path) or _fuera_de_sesion(from_path, to_path)
    if rechazo:
        return rechazo
    source = _raiz() / from_path
    destination = _raiz() / to_path

    if not source.exists():
        return emit_error("vault_move", "FILE_NOT_FOUND", f"Archivo no encontrado: {from_path}")

    # AP-36: una nota movida sigue siendo una nota. `--to n.txt` o sin extensión
    # la sacaba de todo lector con `ok: true` (medido como consumidor, 2026-10-10).
    if source.suffix.lower() == ".md" and destination.suffix.lower() != ".md":
        return emit_error("vault_move", "INVALID_PATH",
                          f"AP-36: el destino de una nota tiene que ser .md: {to_path}")

    if destination.exists():
        return emit_error("vault_move", "INVALID_PATH", f"El destino ya existe: {to_path}")

    rechazo, reclasificado = _reclasificacion(source, from_path, to_path, note_type)
    if rechazo:
        return rechazo

    if dry_run:
        return _mover_nota(source, destination, from_path, to_path, dry_run, backup,
                           reclasificado)
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
        return _mover_nota(source, destination, from_path, to_path, dry_run, backup,
                           reclasificado)


def _mover_nota(
    source: Path, destination: Path, from_path: str, to_path: str,
    dry_run: bool, backup: bool, reclasificado: Optional[Dict[str, Any]] = None,
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
        if reclasificado:
            _escribir_tipo(destination, reclasificado["to"])

    old_stem = source.stem
    # AP-14: mover o renombrar no deja enlaces rotos, porque todo enlace que
    # Obsidian resuelve a la nota se reescribe aquí. La resolución es contra el
    # vault de ANTES del movimiento: el índice lleva el origen y no el destino.
    # Con `/` aunque corra en Windows: es la forma en que Obsidian escribe el
    # enlace anclado, y con `\` el `[[carpeta/nota]]` no se reescribía nunca.
    old_rel = source.relative_to(_raiz()).as_posix()
    new_rel = destination.relative_to(_raiz()).as_posix()
    notas = [md for md in _raiz().rglob("*.md") if ".history" not in md.parts]
    universo = {md.relative_to(_raiz()).as_posix() for md in notas} - {new_rel} | {old_rel}
    indice = indice_de_nombres(sorted(universo))

    links_updated = 0
    files_checked = 0
    links_pending: List[str] = []
    links_ambiguous: List[str] = []

    for md in notas:
        if md == destination:
            continue

        files_checked += 1
        # Sonda sin lock: casi ninguna nota enlaza a la movida, y tomar un lock
        # por cada nota del vault sería caro. Solo las que cambian se reescriben,
        # y se releen bajo su lock para no escribir encima de un append (F1).
        sonda = update_wiki_links_in_file(md, old_rel, new_rel, indice, dry_run=True)
        if sonda.get("ambiguous"):
            links_ambiguous.append(md.relative_to(_raiz()).as_posix())
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
            result = update_wiki_links_in_file(md, old_rel, new_rel, indice, dry_run=False)
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
        "reclassified": reclasificado,
        "links_updated": links_updated,
        "files_checked": files_checked,
        "search_index_updated": search_result.get("updated"),
        "graph_updated": graph_result.get("updated"),
        "links_pending": links_pending,
        # Notas con un enlace que resuelve a la movida y a otra a la vez: no se
        # reescribe porque elegir sería inventar la identidad (AP-17).
        "links_ambiguous": links_ambiguous,
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

    rechazo = _destino_invalido(from_folder, to_folder.replace("\\", "/").strip("/"))
    if rechazo:
        return rechazo

    ficheros = sorted(
        f for f in source.rglob("*")
        if f.is_file() and ".history" not in f.parts and ".locks" not in f.parts
    )
    indices = [f for f in ficheros if f.suffix == ".md" and es_nombre_reservado(f.name)]
    notas = [f for f in ficheros if f.suffix == ".md" and f not in indices]
    adjuntos = [f for f in ficheros if f.suffix != ".md"]

    # CN-02 entero antes de mover nada: un tipo ajeno a mitad de la carpeta
    # dejaría la mitad movida. La carpeta no reclasifica; nota a nota, --type.
    ajenos = []
    for f in notas:
        rel = f"{to_folder}/{f.relative_to(source).as_posix()}"
        tipo = _tipo_de(f)
        motivo = _tipo_ajeno(_carpeta_de(rel), tipo) if tipo else None
        if motivo:
            ajenos.append(f"{f.relative_to(source).as_posix()}: {motivo}")
    if ajenos:
        return emit_error(
            "vault_move", "INVALID_INPUT",
            f"CN-02: {len(ajenos)} nota(s) no pueden vivir en {to_folder}: {ajenos[:5]}",
            pista=_pista_de_tipo(to_folder) + " Con --folder no hay --type: moverlas una a una.",
        )

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


def notas_que_enlazan(rel: str) -> List[str]:
    """Notas con algún enlace que resuelve a `rel`, con el criterio de mover (AP-14).

    Es el que `_mover_nota` usa para reescribir: wikilink por nombre o ruta,
    con ancla y alias, y enlace markdown. `vault_delete` lo lee para avisar de
    lo que deja roto; un criterio propio allí sería AP-57.
    """
    notas = [md for md in _raiz().rglob("*.md") if ".history" not in md.parts]
    indice = indice_de_nombres(sorted(md.relative_to(_raiz()).as_posix() for md in notas))
    enlazan = []
    for md in notas:
        desde = md.relative_to(_raiz()).as_posix()
        if desde == rel:
            continue
        try:
            contenido = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _reescribir_enlaces(contenido, desde, rel, rel, indice)[1]:
            enlazan.append(desde)
    return sorted(enlazan)


def check_move_impact(from_path: str, to_path: str) -> Dict[str, Any]:
    """Analiza el impacto de un movimiento sin ejecutarlo."""
    rechazo = _fuera_del_vault(from_path, to_path)
    if rechazo:
        return rechazo
    source = _raiz() / from_path

    if not source.exists():
        return emit_error("vault_move", "FILE_NOT_FOUND", f"Archivo no encontrado: {from_path}")

    content = source.read_text(encoding="utf-8")
    old_rel = source.relative_to(_raiz()).as_posix()

    wiki_links = RE_WIKILINK.findall(content)

    # El mismo criterio con el que `_mover_nota` reescribe (AP-57): el impacto
    # que se anuncia es el que el movimiento va a tener.
    backlinks = notas_que_enlazan(old_rel)

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
        "--type", dest="note_type", type=str,
        help="Nuevo type de la nota (con --from/--to): reclasificarla al cambiar de sección",
    )
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
    elif args.note_type is not None and not (args.from_path and args.to_path):
        return uso_invalido("--type solo vale con --from y --to: se reclasifica nota a nota")
    elif args.folder:
        if not args.to_folder:
            return uso_invalido("--folder requiere --to-folder")
        result = move_folder(args.folder, args.to_folder, dry_run=args.dry_run)
    elif args.from_path and args.to_path:
        result = move_note(args.from_path, args.to_path, dry_run=args.dry_run,
                           note_type=args.note_type)
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

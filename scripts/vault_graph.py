#!/usr/bin/env python3

"""

Vault Graph Tool — Generate wiki-links graph



Scans all wiki-links [[note]] in the vault and generates graph.json.

Returns nodes, edges, orphan notes, and broken links.



Usage:

    python vault_graph.py

"""

import json


import sys

from vault_errors import emit_fallo, wrap_main


from pathlib import Path

from typing import Any, Dict, List, Set

from vault_regex import RE_WIKILINK  # dueño único del patrón (AP-50)


# Configuration

from vault_io import atomic_write_json, write_report
from vault_escaneo_grafo import escanear_wikilinks  # el único escaneo del grafo
from vault_lib import colisiones_de_nombre  # dueño único de la identidad por nombre (AP-57, AP-17)
from vault_registry import ORDERED_SECTIONS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.grafo.refresco import ensamblar_grafo, nodo_de_nota  # noqa: E402
from vault.grafo.repositorio import RepositorioGrafo  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.enumeracion import notas_en_disco  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGrafo:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGrafo(construir(root))


def _graph_file() -> Path:
    return _repo().grafo


def _system_dir() -> Path:
    return _repo().dir_sistema

# `_system_dir()` se usaba en la lectura de `move-log.json` sin estar definido en
# ningún sitio: la rama de nodos movidos lanzaba NameError desde que se escribió.


# Only scan notes inside these standard sections — never root files or scripts/
#
# Derivado de `vault_registry`, no copiado. La copia literal se quedó en 18
# secciones mientras el estándar iba por 22: las notas de `17_Preferences`,
# `18_Bugs`, `19_Audits` y `20_Quarantine` no pasaban `_is_vault_note()` y por
# tanto no existían en `graph.json` — ni como nodo, ni como origen de enlace,
# ni como huérfana. Una sección entraba al estándar y salía invisible del grafo
# sin que nada fallara.
VAULT_SECTIONS = frozenset(ORDERED_SECTIONS)


def _is_vault_note(note_path: Path) -> bool:
    """Return True only for .md files inside a standard vault section.

    superseded_by: vault.kernel.enumeracion.notas_en_disco — `vault_graph` ya
    no enumera con esto (AP-44: el tramo oculto se medía en la ruta absoluta).
    Se conserva el contrato por no-derogación.
    """

    try:
        parts = note_path.relative_to(_raiz()).parts

    except ValueError:
        return False

    if len(parts) < 2:
        return False  # Root-level file (spec doc, README, index.md at root)

    return parts[0] in VAULT_SECTIONS


def extract_wiki_links(content: str) -> List[str]:
    """Extract wiki-links [[note]] from content."""

    return RE_WIKILINK.findall(content)


def _build_slug_map(all_files: List[Path]) -> Dict[str, str]:
    """

    Build a map from possible wiki-link names to relative paths.

    superseded_by: vault_lib.indice_de_nombres. Con `if stem not in slug_map`
    un nombre compartido por dos notas resolvía a la que el recorrido del disco
    diera primero (AP-17); se conserva por la política de no-derogación, pero
    `vault_graph` ya no la usa.

    Handles: bare stem ('identity'), path with subdirs ('01_Projects/overview'),

    and Windows-style paths ('grooming-scheduler/overview\\').

    """

    slug_map: Dict[str, str] = {}

    for p in all_files:
        rel = str(p.relative_to(_raiz())).replace("\\", "/")

        rel_no_ext = rel.lower().removesuffix(".md")

        stem = p.stem.lower()

        # Register by stem (last component without extension)

        if stem not in slug_map:
            slug_map[stem] = rel

        # Register by full relative path without extension

        slug_map[rel_no_ext] = rel

        # Register by last two path components (e.g. 'grooming-scheduler/overview')

        parts = rel_no_ext.split("/")

        if len(parts) >= 2:
            short = "/".join(parts[-2:])

            if short not in slug_map:
                slug_map[short] = rel

    return slug_map


def _resolve_link(slug: str, slug_map: Dict[str, str]) -> str:
    """Try to resolve a wiki-link slug to a vault-relative path.

    superseded_by: vault_lib.resolver_wikilink, que devuelve los candidatos en
    vez de uno solo y quita alias y ancla antes de buscar.
    """

    # Normalize: backslashes, strip trailing separators

    normalized = slug.replace("\\", "/").strip("/").lower()

    # Try exact match

    if normalized in slug_map:
        return slug_map[normalized]

    # Try stem only (last segment)

    stem = normalized.split("/")[-1]

    if stem in slug_map:
        return slug_map[stem]

    return ""


def vault_graph() -> Dict[str, Any]:
    """

    Regenerate graph.json scanning all wiki-links in the vault.



    Returns:

        Nodes, edges, orphan notes, and broken links

    """

    nodes = {}  # path -> {title, type, tags, aliases, links}

    # Las secciones del vault —las del estándar y las propias de
    # `secciones.json`— salen del puerto del núcleo. Hasta v41.2 se barría
    # `ORDERED_SECTIONS` y la nota de una sección propia no era nodo: quien la
    # enlazaba la veía como destino roto. Un registro ilegible es un fallo,
    # no un grafo sin las propias (AP-51).
    from vault.kernel.fallos import FalloDeDominio

    try:
        secciones = _repo().ctx.secciones.ordenadas()
    except FalloDeDominio as fallo:
        return emit_fallo("vault_graph", fallo)

    # El enumerador del núcleo (AP-44, AP-57): el tramo oculto se mide en la
    # ruta relativa al vault. Con `p.parts` absoluto, un vault colgado de
    # `~/.claude/` salía con cero nodos y sin error.
    all_files = notas_en_disco(_raiz(), secciones)

    # Leer el disco es de este productor; parsear el frontmatter, indexar los
    # nombres y resolver los enlaces es del escaneo único que comparte con
    # `vault_graph_merge` (AP-57). Hasta ahora aquí se leían `title:` y `tags:`
    # con un regex por líneas que dejaba vacías las etiquetas en lista de
    # bloque, sin comillas o de una nota CRLF (AP-44).

    repo = _repo()

    contenidos: Dict[str, str] = {}

    for note_path in all_files:
        try:
            with open(note_path, "r", encoding="utf-8") as f:
                contenidos[repo.relativa(note_path)] = f.read()

        except (UnicodeDecodeError, PermissionError):
            continue

    relativas = [repo.relativa(p) for p in all_files]

    escaneo = escanear_wikilinks(contenidos)

    # El nodo y el ensamblado son los mismos que usa el refresco de una nota
    # (`vault.grafo.refresco`): reconstruir y refrescar no pueden discrepar
    # sobre qué es `graph.json` (AP-57). El nodo guarda `aliases` y `links`,
    # que es lo que deja repetir la resolución sin volver a leer el disco.
    #
    # AP-17: un enlace al que responden dos notas sale en `ambiguousLinks`, sin
    # arista. AP-14: el que no resuelve sale en `brokenLinks`, con `targetPath`
    # tal como está escrito (AP-44); es también la evidencia de que **SP-02**
    # —buscar la nota antes de escribir `[[…]]`— no se siguió.
    for rel_path, nota in escaneo["notas"].items():
        nodes[rel_path] = nodo_de_nota(rel_path, nota)

    # Check for deleted nodes from previous graph
    extras = []
    if _graph_file().exists():
        try:
            old_graph = json.loads(_graph_file().read_text(encoding="utf-8"))
            old_nodes = old_graph.get("nodes", {})

            for old_path in old_nodes:
                if old_path not in nodes:
                    old_node = old_nodes[old_path]
                    extras.append(
                        {
                            "from": old_path,
                            "to": "__deleted__",
                            "type": "deleted-node",
                            "original_status": old_node.get("status", "active"),
                        }
                    )
        except (json.JSONDecodeError, PermissionError):
            pass

    # Check for moved nodes from move-log
    move_log = _system_dir() / "move-log.json"
    if move_log.exists():
        try:
            move_data = json.loads(move_log.read_text(encoding="utf-8"))
            for move in move_data:
                old_path = move.get("from")
                new_path = move.get("to")
                if old_path in nodes:
                    nodes[old_path]["status"] = "moved"
                    nodes[old_path]["moved_to"] = new_path
                    nodes[old_path]["moved_at"] = move.get("timestamp")
        except (json.JSONDecodeError, PermissionError):
            pass

    graph_data = ensamblar_grafo(
        nodes, escaneo, extras, colisiones_de_nombre(relativas)
    )
    orphans = graph_data["orphans"]
    broken_links = graph_data["brokenLinks"]
    ambiguous_links = graph_data["ambiguousLinks"]
    name_collisions = graph_data["nameCollisions"]

    _graph_file().parent.mkdir(parents=True, exist_ok=True)

    # Escritura atómica: además de temp+replace, es lo que hace que la
    # regeneración quede contada en el ledger de AP-37. Con `json.dump` directo
    # la tool devolvía `written: 0` habiendo reescrito el grafo entero.
    atomic_write_json(_graph_file(), graph_data)

    return {
        "ok": True,
        **write_report(),
        "savedTo": _repo().relativa(_graph_file()),
        "stats": graph_data["stats"],
        "orphans": orphans[:10],  # Top 10
        "brokenLinks": broken_links[:10],  # Top 10
        "ambiguousLinks": ambiguous_links[:10],  # Top 10
        "nameCollisions": name_collisions[:10],  # Top 10
    }


def refrescar_nota_en_grafo(path) -> Dict[str, Any]:
    """Pone UNA nota en `graph.json` sin reconstruir (AP-47).

    Es lo que hace el gancho del write path tras cada escritura; se publica
    aquí para quien escribe por fuera de `atomic_write_text` y para los tests.
    El dueño del refresco es `vault.grafo.refresco`; esto solo lo compone.
    """
    from vault_io import refrescar_grafo
    from vault.kernel.fallos import FalloDeDominio

    try:
        return refrescar_grafo(Path(path))
    except FalloDeDominio as fallo:
        return emit_fallo("vault_graph", fallo)


def vault_graph_typed() -> Dict[str, Any]:
    """Generate graph-enriched.json with typed predicates (delegates to vault_graph_merge)."""
    from vault_graph_merge import vault_graph_merge
    return vault_graph_merge()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Vault Graph Tool -- Generate wiki-links graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_graph.py
  python vault_graph.py --typed



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Escanea todos los [[wiki-links]] y genera 99_Index/graph.json

  - Detecta notas huerfanas (sin links entrantes) y links rotos

  - --typed genera graph-enriched.json con predicates semanticos de entity + code relations

""",
        allow_abbrev=False,
    )

    parser.add_argument(
        "--typed",
        action="store_true",
        help="Generate graph-enriched.json with typed predicates (merges wiki-links + entity + code relations)",
    )

    args = parser.parse_args()

    if args.typed:
        result = vault_graph_typed()
    else:
        result = vault_graph()

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_graph"))

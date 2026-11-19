#!/usr/bin/env python3

"""

Vault Search Tool — Full-text weighted search



Searches the vault using weighted scoring: title×4 + word matches + preview matches.

Returns up to 20 results ordered by score.



Usage:

    python vault_search.py --query "mcp tools ansible"

    python vault_search.py --query "deployment" --folder "08_Runbooks"

    python vault_search.py --query "api" --tag "mcp"

"""


import argparse

import json

import os
import re

import sys

from vault_errors import emit_error, wrap_main

from pathlib import Path

from typing import Any, Dict, List, Optional


# Configuration


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.normalizacion import STOPWORDS, fold_accents  # noqa: E402
from vault_io import assert_within_vault, is_snapshot_path  # noqa: E402
from vault_lib import parse_frontmatter, separar_frontmatter  # noqa: E402
from vault_entorno import leer as leer_entorno  # dueño del registro (AP-49/05)
from vault.kernel.vigencia import (  # noqa: E402
    ciclo_de_vida, es_seccion_historica, motivo_de_fila, motivo_historico)


def _notas_visibles_en_vivo(root: Path):
    """Read current visible Markdown for MCP; do not follow symlinks or history."""
    notes, skipped = [], []
    def onerror(exc):
        skipped.append(str(exc))
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
        parent = Path(directory)
        dirs[:] = [d for d in dirs if not d.startswith('.') and not is_snapshot_path(d) and not (parent / d).is_symlink()]
        for name in files:
            if name.startswith('.') or not name.lower().endswith('.md'):
                continue
            path = parent / name
            if path.is_symlink():
                continue
            try:
                text = path.read_text(encoding='utf-8')
                meta = parse_frontmatter(text) or {}
                tags = meta.get('tags') or []
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(',') if t.strip()]
                titulo = meta.get('title') or path.stem
                cuerpo = separar_frontmatter(text)[1]
                notes.append({'path': path.relative_to(root).as_posix(),
                              'title': titulo,
                              'preview': cuerpo.strip()[:200].replace('\n', ' '),
                              'tags': tags, 'updatedAt': meta.get('updatedAt') or meta.get('createdAt') or '',
                              **_repo(root).estadisticas_bm25(str(titulo), cuerpo),
                              'lifecycle': ciclo_de_vida(meta)})
            except (OSError, UnicodeError, ValueError) as exc:
                skipped.append(f'{path.relative_to(root).as_posix()}: {type(exc).__name__}')
    return notes, skipped


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _index_file() -> Path:
    return _repo().indice_busqueda


def _forma(texto: str) -> str:
    """AP-44: la forma con que se compara texto — sin acentos ni mayúsculas.

    Hasta 2026-10-10 era `.lower()`: «cancion» no encontraba «Canción» ni
    «CONFIGURACION» a «configuración» (medido como consumidor).
    """
    return fold_accents(texto or "").casefold()


def _en_carpeta(ruta: str, folder: str) -> bool:
    """La carpeta es un componente de la ruta, no un prefijo de texto."""
    folder = folder.strip("/")
    return ruta == folder or ruta.startswith(folder + "/")


#: Lexical rankings `vault_search` can use. `pesos` is the historical one
#: (title x4, tags, 200-character preview); `bm25` scores the whole note with
#: the term statistics `vault_reindex` stores (`vault.indices.bm25`).
RANKINGS = ("pesos", "bm25")

#: The default is a measured decision, not a preference: BM25 is adopted only
#: if the agent bench recall (`recall_pack_ajeno`) does not regress. The
#: numbers are in `scripts/README.md` (vault_search) and the feature log.
RANKING_POR_DEFECTO = "pesos"


def _pasa_filtros(note: Dict[str, Any], folder: Optional[str], tag: Optional[str]) -> bool:
    """Folder and tag filters, shared by every ranking."""
    if folder and not _en_carpeta(note.get("path", ""), folder):
        return False
    # AP-44: la tag se compara con la normalización con que `vault_write` la
    # guardó; `--tag Música` no encontraba la `musica` que él mismo escribió.
    forma = _repo().forma_de_etiqueta if tag else None
    if tag and forma(tag) not in {forma(str(t)) for t in note.get("tags", [])}:
        return False
    return True


def score_note(note: Dict[str, Any], query: str, folder: Optional[str], tag: Optional[str]) -> float:

    """Calculate weighted search score for a note."""

    if not _pasa_filtros(note, folder, tag):

        return 0


    query_lower = _forma(query)

    # Each word scores as a substring, so a stopword matched almost every
    # title ("de" inside "decisions", "index"). Same list as the query parser;
    # a query made only of stopwords keeps them (it is still a question).
    query_words = [w for w in query_lower.split() if w not in STOPWORDS] or query_lower.split()


    score = 0

    title_lower = _forma(note.get("title", ""))


    # Title matches (weight ×4)

    if query_lower in title_lower:

        score += 40

    for word in query_words:

        if word in title_lower:

            score += 4


    # Tag matches

    for tag_item in note.get("tags", []):

        tag_lower = _forma(str(tag_item))

        if query_lower in tag_lower:

            score += 3

        for word in query_words:

            if word in tag_lower:

                score += 1


    # Preview/body matches (weight ×1)

    preview_lower = _forma(note.get("preview", ""))

    if query_lower in preview_lower:

        score += 10

    for word in query_words:

        if word in preview_lower:

            score += 1


    return score


def _pide_historia(folder: Optional[str]) -> bool:
    """Searching inside a section that holds history is asking for history."""
    if not folder:
        return False
    from vault.kernel.contenido import CARPETA_FUENTES

    carpeta = folder.replace("\\", "/").strip("/")
    return es_seccion_historica(carpeta) or _en_carpeta(carpeta + "/x.md", CARPETA_FUENTES)


class _FiltroDeHistoria:
    """Leaves history out of the matches, counting it by reason.

    The rule is `vault.kernel.vigencia` (shared with the context pack); it
    reads the row's `lifecycle`, so no note is read. A row written before the
    row carried it is decided by reading that one matching note.
    """

    def __init__(self, activo: bool) -> None:
        self.activo = activo
        self.excluidas: Dict[str, str] = {}
        self.sin_ciclo = 0

    def _motivo(self, path: str, fila: Dict[str, Any]) -> Optional[str]:
        try:
            return motivo_de_fila(fila)
        except KeyError:
            self.sin_ciclo += 1
        ruta = _raiz() / path
        try:
            assert_within_vault(ruta, _raiz())
            meta = parse_frontmatter(ruta.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeError, ValueError):
            meta = {}
        return motivo_historico(path, meta)

    def excluye(self, nota: Dict[str, Any], filas: Dict[str, Dict[str, Any]]) -> bool:
        path = nota.get("path", "")
        if not self.activo or Path(path).name.lower() == "index.md":
            return False
        motivo = self._motivo(path, filas.get(path, {"path": path}))
        if motivo:
            self.excluidas[path] = motivo
        return bool(motivo)

    def informe(self) -> Dict[str, Any]:
        """Additive envelope field; absent when nothing was left out."""
        if not self.excluidas:
            return {}
        por_motivo: Dict[str, int] = {}
        for motivo in self.excluidas.values():
            por_motivo[motivo] = por_motivo.get(motivo, 0) + 1
        return {"history_excluded": {
            "total": len(self.excluidas),
            "by_reason": dict(sorted(por_motivo.items())),
            "hint": "solo verdad vigente: --incluir-historico devuelve también estas notas",
        }}


def _carpeta_inexistente(folder: str) -> Dict[str, Any]:
    """The error for a `--folder` that is not on disk, by what can fix it.

    Flow QA 2026-11-17 (QA-FL-03): every missing folder was FOLDER_NOT_FOUND,
    whose recovery creates the standard sections that are missing. That only
    fixes a missing standard section; a misspelt folder (`07_Knowlege`) is
    fixed in the argument, so it is UNKNOWN_SECTION with the sections that
    exist (`valid`), as `vault_ingest` publishes them.
    """
    from vault_registry import secciones_del_vault, standard_folders

    raiz = _raiz()
    seccion = folder.replace("\\", "/").strip("/").split("/")[0]
    if seccion in standard_folders() and not (raiz / seccion).exists():
        return emit_error("vault_search", "FOLDER_NOT_FOUND",
                          f"Falta la sección del estándar {seccion}: {folder}")
    try:
        secciones = secciones_del_vault(raiz)
    except ValueError:
        secciones = standard_folders()
    return {**emit_error("vault_search", "UNKNOWN_SECTION",
                         f"--folder {folder!r} no existe en el vault"),
            "valid": [s for s in secciones if (raiz / s).is_dir()]}


def vault_search(query: str, folder: Optional[str] = None, tag: Optional[str] = None,
                 ranking: Optional[str] = None,
                 incluir_historico: bool = False) -> Dict[str, Any]:

    """

    Search the vault with weighted scoring.



    Args:

        query: Search terms (multiple words separated by space)

        folder: Restrict search to a folder (e.g., "02_Observability")

        tag: Filter by frontmatter tag

        ranking: `pesos` or `bm25` (default `RANKING_POR_DEFECTO`)

        incluir_historico: also return history (superseded, archived,
            deprecated, obsolete, revoked, archived sources, quarantine);
            by default only current truth, the rule of the context pack



    Returns:

        Dict with results ordered by score

    """

    # AP-37: una consulta vacía no es una búsqueda; devolvía el vault entero.
    if not (query or "").strip():
        return {**emit_error("vault_search", "INVALID_INPUT", "--query vacío."),
                "query": query, "results": []}

    ranking = ranking or RANKING_POR_DEFECTO
    if ranking not in RANKINGS:
        return {**emit_error("vault_search", "INVALID_INPUT",
                             f"--ranking {ranking!r} no es uno de {', '.join(RANKINGS)}"),
                "query": query, "results": []}

    # Una carpeta que no existe o sale del vault respondía 0 resultados con
    # ok:true, indistinguible de «no hay coincidencias» (AP-51).
    if folder:
        carpeta = _raiz() / folder.strip("/")
        try:
            assert_within_vault(carpeta, _raiz())
        except ValueError as exc:
            return {**emit_error("vault_search", "INVALID_PATH", str(exc)),
                    "query": query, "results": []}
        if not carpeta.is_dir():
            return {**_carpeta_inexistente(folder), "query": query, "results": []}

    live = leer_entorno("VAULT_MCP_LIVE_SEARCH")
    skipped = []
    try:

        if live:
            notes, skipped = _notas_visibles_en_vivo(_raiz())
        else:

            with open(_index_file(), "r", encoding="utf-8") as f:

                index = json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):

        # `query` y `results: []` se conservan: los consumidores que iteran el
        # resultado sin mirar `ok` no empiezan a romperse por esto.
        return {

            **emit_error("vault_search", "INDEX_NOT_FOUND",
                         "Search index not found. Run vault_reindex first."),

            "query": query,

            "results": [],

        }


    if not live:
        notes = index.get("notes", [])
        from vault.runtime import comprobar_coherencia_indices
        coherencia = comprobar_coherencia_indices(_raiz())


    # Score all notes

    avisos: List[str] = []
    usado = ranking
    puntos_bm25: Dict[str, float] = {}
    if ranking == "bm25":
        sin_datos = _repo().filas_sin_estadisticas(notes)
        if sin_datos:
            # A partial BM25 would rank by two scales at once; the honest
            # fallback is the whole old ranking, said out loud.
            usado = "pesos"
            avisos.append(f"bm25: {sin_datos} nota(s) del índice sin estadísticas de "
                          "términos; se usó el ranking por pesos. Ejecuta vault_reindex")
        else:
            puntos_bm25 = _repo().puntuar_bm25(query, notes)

    scored_notes = []
    filas = {n.get("path", ""): n for n in notes}

    for note in notes:

        if usado == "bm25":
            score = (puntos_bm25.get(note.get("path", ""), 0)
                     if _pasa_filtros(note, folder, tag) else 0)
        else:
            score = score_note(note, query, folder, tag)

        if score > 0:

            preview = note.get("preview", "")[:200]

            scored_notes.append(

                {

                    "path": note.get("path", ""),

                    "title": note.get("title", ""),

                    "preview": preview,

                    "tags": note.get("tags", []),

                    "score": score,

                    "updatedAt": note.get("updatedAt", ""),

                }

            )


    # Current truth only (producto-usable S4), before sorting and the cut at 20.
    historia = _FiltroDeHistoria(activo=not incluir_historico and not _pide_historia(folder))
    scored_notes = [n for n in scored_notes if not historia.excluye(n, filas)]
    if historia.sin_ciclo:
        avisos.append(f"vigencia: {historia.sin_ciclo} coincidencia(s) del índice sin ciclo de "
                      "vida; se leyó su nota para filtrar lo histórico. Ejecuta vault_reindex")

    # Sort by score descending

    scored_notes.sort(key=lambda x: x["score"], reverse=True)


    # Return top 20

    results = scored_notes[:20]


    return {

        "ok": True,

        "query": query,

        **({"source": "live_visible_markdown", "incomplete": bool(skipped), "skipped": skipped} if live else {}),
        **({"index_coherence": coherencia} if not live else {}),
        **({"warnings": avisos + (
            ["No se pudo confirmar la frescura del índice de búsqueda; revisa vault_reindex"]
            if not live and coherencia.get("status") != "index_ok" else [])}
           if avisos or (not live and coherencia.get("status") != "index_ok") else {}),
        "ranking": usado,

        "folder": folder,

        "tag": tag,

        "total": len(results),

        # AP-37: el recorte a 20 se declara; antes `total` era lo devuelto y
        # nada decía cuántas coincidencias quedaban fuera.
        "matched": len(scored_notes),

        "truncated": len(scored_notes) > len(results),

        "results": results,

        **historia.informe(),

        "hint": "Use vault_read(path) to get full note content",

    }


def main():

    parser = argparse.ArgumentParser(

        description="Vault Search Tool",

        formatter_class=argparse.RawDescriptionHelpFormatter,

        epilog="""

Ejemplos:

  python vault_search.py --query "mcp tools ansible"

  python vault_search.py --query "deployment" --folder "08_Runbooks"

  python vault_search.py --query "api" --tag "mcp"

  python vault_search.py --query "circuit breaker" --folder "05_Patterns"
  python vault_search.py --query "transporte" --incluir-historico



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Requiere search-index.json generado por vault_reindex.py

  - Score: title×4 + word matches + preview matches (--ranking pesos)
  - --ranking bm25: BM25 sobre la nota entera con las estadisticas del indice
  - Por defecto solo verdad vigente: lo historico sale y se cuenta en history_excluded

""",

        allow_abbrev=False,
    )

    parser.add_argument("--query", required=True, help="Search terms")

    parser.add_argument("--folder", help="Restrict to folder")

    parser.add_argument("--tag", help="Filter by tag")

    parser.add_argument("--incluir-historico", action="store_true",
                        help=("devuelve también lo histórico (superseded_by, archived, "
                              "deprecated, obsolete, revoked, fuentes archivadas, cuarentena); "
                              "por defecto solo verdad vigente"))

    parser.add_argument("--ranking", choices=RANKINGS, default=None,
                        help=("pesos (titulo, tags y extracto) o bm25 (nota entera); "
                              f"por defecto {RANKING_POR_DEFECTO}"))


    args = parser.parse_args()

    result = vault_search(args.query, args.folder, args.tag, ranking=args.ranking,
                          incluir_historico=args.incluir_historico)


    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":

    sys.exit(wrap_main(main, "vault_search"))


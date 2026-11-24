#!/usr/bin/env python3

"""

Vault Pattern List Tool — List patterns by project and status



Lists all registered patterns grouped by state (implementado, en_progreso, planificado, deprecado).

Without filters: shows all patterns. With filters: shows only matching ones.



Usage:

    python vault_pattern_list.py

    python vault_pattern_list.py --project "mi-api"

    python vault_pattern_list.py --type "code"

    python vault_pattern_list.py --status "implementado"

"""


import argparse

import json

import sys

from vault_errors import emit_error, wrap_main, proyecto_registrado

from pathlib import Path

from typing import Any, Dict, List, Optional


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.patrones_diseno import (  # noqa: E402
    CATEGORIAS,
    catalogo_ordenado,
    detectar_patrones,
)
from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir, proyectos as _proyectos  # noqa: E402

# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueno.
from vault_vocabulario import mapa as _mapa


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _patterns_dir() -> Path:
    return _repo().seccion("05_Patterns")


def _index_file() -> Path:
    return _repo().indice_de_seccion("05_Patterns")


def _sin_indice() -> Dict[str, Any]:
    """`INDEX_NOT_FOUND` with the recovery that actually writes the index.

    The catalog's recovery for that code is `vault_reindex --graph`, which
    rebuilds `search-index.json` and `graph.json` but never
    `05_Patterns/index.json`: obeying it returned the same error (measured on
    2026-11-17). The only producer is `vault_pattern_save`, so `run_tool`
    points there, the same fix `vault_tags._sin_registro` applied.

    It points to `--rebuild-index`, not to a save with placeholders: a save
    writes an index holding only its own entry, so a vault whose pattern notes
    were already there still listed none of them (QA-FL-PAT). The rebuild
    reads them all, and on a vault with no notes writes an empty index.
    """
    envelope = emit_error(
        "vault_pattern_list", "INDEX_NOT_FOUND",
        "Pattern index not found. Rebuild it from the pattern notes with "
        "vault_pattern_save --rebuild-index.",
        pista="vault_pattern_save --rebuild-index writes 05_Patterns/index.json "
              "from the notes in 05_Patterns/; any save also creates it.",
    )
    envelope["recovery"]["tool"] = "vault_pattern_save"
    envelope["recovery"]["args"] = ["--rebuild-index"]
    return envelope


def vault_pattern_list(

    project: Optional[str] = None,

    pattern_type: Optional[str] = None,

    status: Optional[str] = None,

) -> Dict[str, Any]:

    es_del = _proyectos.pertenencia_en(_raiz(), project)
    try:

        with open(_index_file(), "r", encoding="utf-8") as f:

            index = json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):

        return _sin_indice()


    patterns = index.get("patterns", [])


    if project:

        patterns = [p for p in patterns if es_del(p.get("project"))]

    if pattern_type:

        patterns = [p for p in patterns if p.get("type", "").lower() == pattern_type.lower()]

    if status:

        status_normalized = status.lower().replace(" ", "_")

        patterns = [p for p in patterns if p.get("status", "").lower() == status_normalized]


    grouped: Dict[str, List[str]] = _mapa("pattern_state", {

        "implementado": [],

        "en_progreso": [],

        "planificado": [],

        "deprecado": [],

        "refactoring": [],

    })


    for p in patterns:

        s = p.get("status", "")

        if s in grouped:

            grouped[s].append(p.get("pattern", ""))

        else:

            grouped["implementado"].append(p.get("pattern", ""))


    return {

        "ok": True,

        "total": len(patterns),

        "grouped": grouped,

        "patterns": patterns,

        "filters": {

            "project": project,

            "type": pattern_type,

            "status": status,

        },

    }


def _patrones_registrados() -> set:
    """Nombres de patrones ya registrados en 05_Patterns/index.json, si existe."""
    try:
        with open(_index_file(), "r", encoding="utf-8") as f:
            index = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return set()
    return {
        str(p.get("pattern", "")).strip()
        for p in index.get("patterns", [])
        if p.get("pattern")
    }


def vault_pattern_catalog(category: Optional[str] = None) -> Dict[str, Any]:
    """Devuelve el catalogo canonico de patrones detectables, categorizado y ordenado."""
    try:
        return catalogo_ordenado(categoria=category)
    except ValueError as exc:
        return emit_error("vault_pattern_list", "INVALID_VALUE", str(exc))


def vault_pattern_detect(
    scan_path: str,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Detecta patrones de diseno y arquitectura en una ruta interna o externa (solo lectura)."""
    objetivo = Path(scan_path)
    if not objetivo.exists():
        return emit_error(
            "vault_pattern_list",
            "FILE_NOT_FOUND",
            f"La ruta a escanear no existe: {scan_path}",
        )
    resuelta = objetivo.resolve()
    try:
        resuelta.relative_to(_raiz().resolve())
        scope = "interno"
    except ValueError:
        scope = "externo"

    try:
        resultado = detectar_patrones(
            resuelta,
            categoria=category,
            registrados=_patrones_registrados(),
        )
    except ValueError as exc:
        return emit_error("vault_pattern_list", "INVALID_VALUE", str(exc))

    resultado["scope"] = scope
    return resultado


def main():

    parser = argparse.ArgumentParser(

        description="Vault Pattern List Tool",

        formatter_class=argparse.RawDescriptionHelpFormatter,

        epilog="""

Ejemplos:

  python vault_pattern_list.py

  python vault_pattern_list.py --project "mi-api"

  python vault_pattern_list.py --type "code"

  python vault_pattern_list.py --status "implementado"

  python vault_pattern_list.py --catalog

  python vault_pattern_list.py --scan-path "/ruta/al/repo"

  python vault_pattern_list.py --scan-path "/ruta/al/repo" --category "estructurales"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Lee 05_Patterns/index.json; si falta, vault_pattern_save --rebuild-index lo reconstruye desde las notas

  - --catalog lista el catalogo canonico categorizado y ordenado (5 categorias)

  - --scan-path escanea un repositorio interno o externo en solo lectura y cruza contra 05_Patterns/index.json

  - Estados: implementado, en_progreso, planificado, deprecado, refactoring

""",

        allow_abbrev=False,
    )

    parser.add_argument("--project", type=proyecto_registrado("vault_pattern_list"), help="Filter by project")

    parser.add_argument("--type", help="Filter by pattern type (design, architecture, code, integration)")

    parser.add_argument("--status", help="Filter by status")

    parser.add_argument(
        "--catalog",
        action="store_true",
        help="List the canonical ordered catalog of detectable design and architecture patterns",
    )

    parser.add_argument(
        "--scan-path",
        help="Scan an internal or external repository or file for design/architecture patterns (read-only)",
    )

    parser.add_argument(
        "--category",
        choices=CATEGORIAS,
        help=f"Filter --catalog or --scan-path by pattern category: {list(CATEGORIAS)}",
    )


    args = parser.parse_args()

    if args.catalog and args.scan_path:
        parser.error("--catalog y --scan-path son mutuamente excluyentes")

    if args.catalog:
        result = vault_pattern_catalog(args.category)
    elif args.scan_path:
        result = vault_pattern_detect(args.scan_path, args.category)
    else:
        result = vault_pattern_list(args.project, args.type, args.status)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":

    sys.exit(wrap_main(main, "vault_pattern_list"))


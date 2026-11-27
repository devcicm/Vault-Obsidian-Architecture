#!/usr/bin/env python3

"""
Vault Section — declara, lista y retira las secciones propias de un vault.

Una sección propia es una carpeta de raíz `NN_Nombre` que el estándar no tiene
y que el vault declara en `00_System/secciones.json`. Desde que está declarada
cuenta como sección (CN-02): sus notas se juzgan con el contrato de contenido y
no como `sin_seccion`. Lo que no se declara sigue siendo CN-02.

La lectura y la validación son de `vault_registry` (`leer_secciones_propias`,
`motivo_de_nombre_invalido`): esta tool es la única que escribe el fichero, y
no repite ninguna de las dos reglas. Retirar no borra nada (no-derogación): la
sección pasa a `retirada`, sus notas siguen siendo de sección y
`superseded_by` dice adónde va lo nuevo.

No es `vault_folder_registry`: aquella registra **subcarpetas dentro** de una
sección; esta declara **secciones** nuevas en la raíz.

Usage:
    python vault_section.py --list
    python vault_section.py --add 22_Scripts --documentacion referencia --description "..."
    python vault_section.py --retire 22_Scripts --superseded-by 23_Automatizacion
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import emit_error, mensaje_de, wrap_main
from vault_io import atomic_write_json, get_vault_root
from vault_registry import (
    DOCUMENTACION_CLASES,
    NUMEROS_PROPIOS,
    ORDERED_SECTIONS,
    SECCIONES_PROPIAS_RUTA,
    leer_secciones_propias,
    motivo_de_destino_invalido,
    motivo_de_nombre_invalido,
    motivo_de_tipos_invalidos,
    secciones_del_vault,
)

TOOL = "vault_section"

#: Versión del formato de `secciones.json`.
ESQUEMA = 1

#: La pista del catálogo para `INVALID_FOLDER` manda usar una sección del
#: estándar, que aquí es justo lo que no se quiere: la del sitio la sustituye.
PISTA_NOMBRE = (f"Una sección propia es NN_Nombre con NN entre {NUMEROS_PROPIOS[0]:02d} y "
                f"{NUMEROS_PROPIOS[1]:02d}, sin repetir número; vault_section --list "
                "enseña las ya declaradas.")


def _leer(raiz: Path):
    """Las propias declaradas, o el envelope de error si el fichero está roto.

    El fichero roto no se reescribe: hacerlo desde `[]` borraría las secciones
    que el vault ya declaró (AP-51).
    """
    try:
        return leer_secciones_propias(raiz), None
    except ValueError as e:
        return None, emit_error(TOOL, "DATA_FILE_CORRUPT", str(e))


def _guardar(raiz: Path, secciones: List[Dict[str, Any]]) -> None:
    atomic_write_json(
        raiz / SECCIONES_PROPIAS_RUTA,
        {"schema": ESQUEMA, "secciones": sorted(secciones, key=lambda s: s["folder"])},
    )


def listar(raiz: Optional[Path] = None) -> Dict[str, Any]:
    """Las propias con su estado, y las carpetas de raíz que no son de ninguna sección."""
    raiz = Path(raiz or get_vault_root())
    propias, error = _leer(raiz)
    if error:
        return error
    todas = set(ORDERED_SECTIONS) | {s["folder"] for s in propias}
    sin_seccion = sorted(
        p.name for p in raiz.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name not in todas
    )
    return {
        "ok": True,
        "written": 0,
        "standard": len(ORDERED_SECTIONS),
        "free_range": list(NUMEROS_PROPIOS),
        "total": len(propias),
        "sections": [
            {**s, "status": s.get("status", "activa"), "exists": (raiz / s["folder"]).is_dir()}
            for s in propias
        ],
        "folders_without_section": sin_seccion,
        # v41.2. Es lo que busca quien sigue la pista de INVALID_FOLDER, y
        # `standard` era solo una cifra: lo decide el dueño de CN-02.
        "writable_sections": [
            s for s in secciones_del_vault(raiz)
            if motivo_de_destino_invalido(s, raiz) is None
        ],
    }


def _normalizar_subcarpeta(sub: str) -> Optional[str]:
    """Valida una subcarpeta relativa a la sección (sin `..`, sin prefijo `.`/`_`)."""
    limpio = (sub or "").replace("\\", "/").strip().strip("/")
    if not limpio:
        return None
    partes = [p for p in limpio.split("/") if p]
    for p in partes:
        if p in (".", "..") or p.startswith((".", "_")) or ":" in p:
            raise ValueError(
                f"subcarpeta invalida {sub!r}: no puede contener '..', ':', ni prefijos '.' o '_'"
            )
    return "/".join(partes)


def _sincronizar_indices_de_seccion(raiz: Path, folder: str) -> Dict[str, Any]:
    """Regenera en secuencia registro de carpetas, indices (seccion + maestro), busqueda y grafo.

    H-23: las 5 escrituras corren en secuencia (cada archivo individual se escribe
    atómicamente vía `atomic_write_*`, pero el bloque completo no es una
    transacción ACID única; cada paso informa su resultado en el envelope).
    Orquesta dentro del propio contexto `indices` (sin cruces nuevos hacia `grafo`:
    `vault_reindex(..., rebuild_graph=True)` delega por el puerto ya declarado).
    """
    from vault.indices.carpetas import ServicioCarpetas
    from vault.indices.repositorio import RepositorioIndices
    from vault.kernel import construir
    from vault_io import get_vault_root, set_vault_root
    import vault_master_index
    import vault_reindex
    import vault_section_index

    previo = None
    try:
        previo = get_vault_root()
    except Exception:  # noqa: BLE001 - puede no haber raiz previa en memoria
        previo = None

    set_vault_root(raiz)
    try:
        repo = RepositorioIndices(construir(raiz))
        res_carpetas = ServicioCarpetas(repo).escanear()
        res_sec = vault_section_index.vault_section_index(folder)
        res_master = vault_master_index.vault_master_index(raiz)
        res_reindex = vault_reindex.vault_reindex(rebuild_graph=True, root=raiz)
        grafo_res = res_reindex.get("graph") or {}
        return {
            "ok": bool(
                res_carpetas.get("ok")
                and res_sec.get("ok")
                and res_master.get("ok")
                and res_reindex.get("ok")
            ),
            "folder_registry": {
                "total": res_carpetas.get("total_folders", 0),
                "added": res_carpetas.get("new_folders", 0),
            },
            "section_index": res_sec.get("index_path") or f"{folder}/index.md",
            "master_index": bool(res_master.get("ok")),
            "search_index": res_reindex.get("notes_indexed", 0),
            "graph": {
                "nodes": (grafo_res.get("stats") or {}).get("totalNodes", grafo_res.get("nodes", 0)),
                "edges": (grafo_res.get("stats") or {}).get("totalEdges", grafo_res.get("edges", 0)),
            },
        }
    finally:
        if previo is not None:
            set_vault_root(previo)


def anadir(folder: str, documentacion: Optional[str], description: str = "",
           raiz: Optional[Path] = None, tipos: Optional[List[str]] = None,
           subfolders: Optional[List[str]] = None, sync: bool = False) -> Dict[str, Any]:
    """Declara `folder` como sección propia y crea la carpeta si no existe.

    Es la salida de CN-02 para una carpeta que el vault necesita: el nombre y
    el número los valida `vault_registry`, no esta función. Con `subfolders`
    crea subcarpetas anidadas bajo la sección; con `sync=True` refresca
    `folder-registry.json`, `index.md`, `99_Index/index.md`, `search-index.json`
    y `graph.json` en la misma operación.
    """
    raiz = Path(raiz or get_vault_root())
    if not documentacion:
        return emit_error(TOOL, "MISSING_REQUIRED_ARG",
                          "--add exige --documentacion (" + ", ".join(DOCUMENTACION_CLASES) + ")")
    motivo = motivo_de_nombre_invalido(folder)
    if motivo:
        return emit_error(TOOL, "INVALID_FOLDER", f"{folder!r}: {motivo}",
                          pista=PISTA_NOMBRE)
    if documentacion not in DOCUMENTACION_CLASES:
        return emit_error(TOOL, "INVALID_VALUE",
                          f"--documentacion {documentacion!r}: debe ser una de "
                          + ", ".join(DOCUMENTACION_CLASES))
    if tipos is not None:
        motivo = motivo_de_tipos_invalidos(tipos)
        if motivo:
            return emit_error(TOOL, "INVALID_VALUE", f"--tipos: {motivo}")
    subcarpetas_limpias: List[str] = []
    if subfolders:
        for sub in subfolders:
            try:
                norm = _normalizar_subcarpeta(sub)
            except ValueError as exc:
                return emit_error(TOOL, "INVALID_FOLDER", str(exc))
            if norm and norm not in subcarpetas_limpias:
                subcarpetas_limpias.append(norm)
    propias, error = _leer(raiz)
    if error:
        return error
    for s in propias:
        if s["folder"][:2] == folder[:2]:
            return emit_error(TOOL, "INVALID_FOLDER",
                              f"{folder!r}: el número {folder[:2]} ya lo declara {s['folder']!r}",
                              pista=PISTA_NOMBRE)
    entrada = {"folder": folder, "documentacion": documentacion, "status": "activa"}
    if description:
        entrada["description"] = description
    if tipos is not None:
        entrada["tipos"] = tipos
    _guardar(raiz, propias + [entrada])
    carpeta = raiz / folder
    creada = not carpeta.is_dir()
    carpeta.mkdir(exist_ok=True)
    subcarpetas_creadas: List[str] = []
    for sub in subcarpetas_limpias:
        ruta_sub = carpeta / sub
        ruta_sub.mkdir(parents=True, exist_ok=True)
        subcarpetas_creadas.append(f"{folder}/{sub}")
    salida: Dict[str, Any] = {
        "ok": True,
        "written": 1,
        "folder": folder,
        "documentacion": documentacion,
        "tipos": tipos,
        "created_folder": creada,
        "subfolders_created": subcarpetas_creadas,
        "registry": SECCIONES_PROPIAS_RUTA,
    }
    if sync or subcarpetas_creadas:
        if sync:
            salida["sync"] = _sincronizar_indices_de_seccion(raiz, folder)
        else:
            from vault.indices.carpetas import ServicioCarpetas
            from vault.indices.repositorio import RepositorioIndices
            from vault.kernel import construir

            res_carp = ServicioCarpetas(RepositorioIndices(construir(raiz))).escanear()
            salida["folder_registry"] = {
                "total": res_carp.get("total_folders", 0),
                "added": res_carp.get("new_folders", 0),
            }
    return salida


def retirar(folder: str, superseded_by: Optional[str] = None,
            raiz: Optional[Path] = None) -> Dict[str, Any]:
    """Marca `folder` como `retirada`; no mueve ni borra ninguna nota."""
    raiz = Path(raiz or get_vault_root())
    if folder in ORDERED_SECTIONS:
        return emit_error(TOOL, "INVALID_FOLDER",
                          f"{folder!r} es del estándar: se retira con superseded_by en el "
                          "registro del estándar, no desde un vault",
                          pista="--retire solo retira secciones propias; vault_section "
                                "--list enseña cuáles son.")
    propias, error = _leer(raiz)
    if error:
        return error
    elegida = next((s for s in propias if s["folder"] == folder), None)
    if elegida is None:
        return emit_error(TOOL, "UNKNOWN_SECTION",
                          f"{folder!r} no está declarada en {SECCIONES_PROPIAS_RUTA}")
    if superseded_by and (superseded_by == folder
                          or superseded_by not in secciones_del_vault(raiz)):
        return emit_error(TOOL, "UNKNOWN_SECTION",
                          f"--superseded-by {superseded_by!r} no es otra sección del vault")
    elegida["status"] = "retirada"
    if superseded_by:
        elegida["superseded_by"] = superseded_by
    _guardar(raiz, propias)
    return {
        "ok": True,
        "written": 1,
        "folder": folder,
        "status": "retirada",
        "superseded_by": superseded_by,
        "registry": SECCIONES_PROPIAS_RUTA,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Section - secciones propias del vault (CN-02)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_section.py --list
  python vault_section.py --add 22_Scripts --documentacion referencia --description "Scripts de despliegue"
  python vault_section.py --retire 22_Scripts --superseded-by 23_Automatizacion
        """,
        allow_abbrev=False,
    )
    accion = parser.add_mutually_exclusive_group()
    accion.add_argument("--list", action="store_true",
                        help="Listar secciones propias y carpetas de raíz sin sección")
    accion.add_argument("--add", type=str, help="Declarar una sección propia NN_Nombre")
    accion.add_argument("--retire", type=str, help="Retirar una sección propia sin borrar nada")
    parser.add_argument("--documentacion", type=str,
                        help="Clase de documento: " + ", ".join(DOCUMENTACION_CLASES))
    parser.add_argument("--description", type=str, default="", help="Qué contiene la sección")
    parser.add_argument("--tipos", type=str,
                        help="Tipos de nota de la sección, separados por comas; el "
                             "primero es el que vault_write escribe si la nota no trae type")
    parser.add_argument("--subfolders", type=str,
                        help="Subcarpetas relativas a crear bajo la sección, separadas por comas "
                             "(ej: switches/core,firewalls)")
    parser.add_argument("--sync", action="store_true",
                        help="Sincroniza folder-registry, index.md, índice maestro, búsqueda y grafo")
    parser.add_argument("--superseded-by", type=str, dest="superseded_by",
                        help="Sección que sustituye a la retirada")
    parser.add_argument("--json", action="store_true", help="Salida JSON")

    args = parser.parse_args()
    if args.add:
        tipos = None if args.tipos is None else [t.strip() for t in args.tipos.split(",")]
        subfolders = (
            None if args.subfolders is None
            else [s.strip() for s in args.subfolders.split(",") if s.strip()]
        )
        result = anadir(
            args.add,
            args.documentacion,
            args.description,
            tipos=tipos,
            subfolders=subfolders,
            sync=args.sync,
        )
    elif args.retire:
        result = retirar(args.retire, args.superseded_by)
    else:
        result = listar()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif not result.get("ok"):
        print(f"Error: {mensaje_de(result) or 'Unknown error'}")
    elif "sections" in result:
        print(f"Secciones del estándar: {result['standard']} · propias: {result['total']} "
              f"(rango libre {result['free_range'][0]:02d}-{result['free_range'][1]:02d})")
        for s in result["sections"]:
            marca = "" if s["exists"] else "  [carpeta ausente]"
            print(f"  - {s['folder']} ({s['documentacion']}, {s['status']}){marca}")
        if result["folders_without_section"]:
            print("\nCarpetas de raíz sin sección (CN-02):")
            for f in result["folders_without_section"]:
                print(f"  - {f}")
    else:
        print(f"{result['folder']}: {result.get('status', 'activa')}")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, TOOL))

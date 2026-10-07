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
    }


def anadir(folder: str, documentacion: Optional[str], description: str = "",
           raiz: Optional[Path] = None, tipos: Optional[List[str]] = None) -> Dict[str, Any]:
    """Declara `folder` como sección propia y crea la carpeta si no existe.

    Es la salida de CN-02 para una carpeta que el vault necesita: el nombre y
    el número los valida `vault_registry`, no esta función.
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
    return {
        "ok": True,
        "written": 1,
        "folder": folder,
        "documentacion": documentacion,
        "tipos": tipos,
        "created_folder": creada,
        "registry": SECCIONES_PROPIAS_RUTA,
    }


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
    parser.add_argument("--superseded-by", type=str, dest="superseded_by",
                        help="Sección que sustituye a la retirada")
    parser.add_argument("--json", action="store_true", help="Salida JSON")

    args = parser.parse_args()
    if args.add:
        tipos = None if args.tipos is None else [t.strip() for t in args.tipos.split(",")]
        result = anadir(args.add, args.documentacion, args.description, tipos=tipos)
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

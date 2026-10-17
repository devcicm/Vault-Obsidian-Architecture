#!/usr/bin/env python3
"""vault_supersede — anota `superseded_by:` en una nota que ya existe, sin tocar su cuerpo.

## Por qué existe

Medido el 2026-10-07 al sanar una copia de /ans: los títulos repetidos (AP-17)
eran una nota curada y su copia migrada. El procedimiento de sanación
(`docs/MODO-AGENTICO-SANACION.md`) dice que la sustituida **no se borra**: se le
escribe `superseded_by: "[[canónica]]"`. Ninguna tool podía hacerlo —
`vault_write` reescribe el cuerpo y su `--meta` no admite la clave—, así que la
copia se anotó a mano. Una norma que prescribe un paso que nadie ejecuta es la
mitad del ciclo `síntoma → norma → guard + audit + heal`.

## Qué decide y qué no

Cuál de las dos manda **no lo decide esta tool**: lo dice quien la llama con
`--by`. La tool solo comprueba que esa decisión se pueda leer después igual
que la leen `vault_audit` y `vault_context_pack`:

- `--by` se resuelve como un wikilink, por nombre de fichero y `aliases:`,
  nunca por `title:` (AP-44), con el dueño `vault_lib.resolver_sustitucion`.
  Roto → `NOTE_NOT_FOUND`; ambiguo → `INVALID_VALUE` con los candidatos.
- No a sí misma, y no si la canónica ya declara que la sustituye esta (ciclo).
- Una decisión distinta ya escrita no se pisa sin `--replace`; la misma no
  se reescribe (`already: true`, `written: false`, AP-37).
- El enlace que escribe es el más corto que resuelve a una sola nota
  (`vault_lib.destino_mas_corto`).

Por defecto mide (dry-run); `--apply` escribe. El cuerpo no cambia; el
frontmatter se edita con `Frontmatter.editar`, que conserva el resto del
bloque. `atomic_write_text` escribe LF sin BOM: una nota CRLF o con BOM cambia
entera, y se declara en `encoding_normalized`.

    python scripts/vault_supersede.py --path 10_Migrated/GUIA.md --by guia
    python scripts/vault_supersede.py --path 10_Migrated/GUIA.md --by "[[guia]]" --apply

No acepta `--root` (regla 1): el destino sale de `vault_io.get_vault_root()`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


from vault_errors import emit_error, fuera_de_sesion, wrap_main
from vault_io import assert_within_vault, atomic_write_text, get_vault_root, is_snapshot_path, tomar_lock
from vault_lib import destino_mas_corto, indice_de_nombres, inventario_de_nombres, resolver_sustitucion
from vault.kernel.frontmatter_escritura import Frontmatter
from vault.kernel.frontmatter_parsing import (
    FrontmatterParseError,
    parse_frontmatter_with_body,
    separar_frontmatter,
)

TOOL = "vault_supersede"
CLAVE = "superseded_by"


def _normalizacion(crudo: bytes) -> List[str]:
    """Lo que `atomic_write_text` cambiará además de la clave (LF sin BOM)."""
    return [nombre for nombre, hay in (("bom", crudo.startswith(b"\xef\xbb\xbf")),
                                       ("crlf", b"\r\n" in crudo)) if hay]


def _datos(texto: str) -> Dict[str, Any]:
    """El frontmatter leído como lo lee el consumidor; `{}` si la nota no tiene."""
    if separar_frontmatter(texto)[0] is None:
        return {}
    return parse_frontmatter_with_body(texto)[0] or {}


def supersede(path: str, by: str, apply: bool = False, replace: bool = False) -> Dict[str, Any]:
    """AP-17: anota en la sombra cuál es su canónica, sin borrarla ni tocar el cuerpo."""
    # AP-17: la sombra queda anotada con `superseded_by`, no borrada.
    raiz = get_vault_root()
    try:
        nota = assert_within_vault(raiz / path, raiz)
    except ValueError as exc:
        return {**emit_error(TOOL, "INVALID_PATH", str(exc), pista="una ruta relativa dentro del vault"),
                "path": path}
    if not nota.is_file():
        return {**emit_error(TOOL, "NOTE_NOT_FOUND", f"Note not found: {path}"), "path": path}
    rel = nota.relative_to(raiz).as_posix()

    relativas, alias_por_ruta = inventario_de_nombres(raiz, is_snapshot_path)
    indice = indice_de_nombres(relativas, alias_por_ruta)
    canonica, candidatos = resolver_sustitucion(by, Path(rel), indice)
    # La sombra no es destino posible (abajo, «no se sustituye a sí misma»), así
    # que tampoco hace ambiguo el nombre: `--by guia` desde `GUIA.md` —el
    # ejemplo documentado— resuelve a la otra nota, igual que sin mayúsculas
    # resuelve Obsidian. Medido el 2026-10-17: fallaba siempre.
    if not canonica and rel in candidatos:
        candidatos = [c for c in candidatos if c != rel]
        if len(candidatos) == 1:
            canonica = candidatos[0]
    if not candidatos:
        return {**emit_error(
            TOOL, "NOTE_NOT_FOUND", f"--by {by!r} no resuelve a ninguna nota",
            pista="--by es un wikilink: nombre de fichero o alias, no el title:. "
                  "Localizar la canónica con vault_search."), "path": rel}
    if not canonica:
        return {**emit_error(
            TOOL, "INVALID_VALUE", f"--by {by!r} resuelve a {len(candidatos)} notas",
            pista="escribir --by con la carpeta, p. ej. "
                  + Path(candidatos[0]).with_suffix("").as_posix()),
            "path": rel, "candidates": candidatos}
    if canonica == rel:
        return {**emit_error(TOOL, "INVALID_VALUE", "una nota no se sustituye a sí misma",
                             pista="--by es la nota que manda, no la sustituida"), "path": rel}

    try:
        crudo = nota.read_bytes()
        texto = crudo.decode("utf-8")
        datos = _datos(texto)
        datos_canonica = _datos((raiz / canonica).read_text(encoding="utf-8"))
    except FrontmatterParseError as exc:
        return {**emit_error(TOOL, "FRONTMATTER_PARSE_ERROR", str(exc),
                             pista="sanar el bloque con vault_frontmatter_heal --apply y repetir"),
                "path": rel}
    except (OSError, UnicodeDecodeError) as exc:
        return {**emit_error(TOOL, "FILE_READ_ERROR", str(exc), exception=exc), "path": rel}

    # INVALID_VALUE y no CIRCULAR_WIKILINK: la recuperación de ese manda a
    # vault_graph_fix, que rompe ciclos de enlaces del cuerpo y no deshace esta
    # decisión.
    if resolver_sustitucion(datos_canonica.get(CLAVE), Path(canonica), indice)[0] == rel:
        return {**emit_error(
            TOOL, "INVALID_VALUE", f"{canonica} ya declara que la sustituye {rel}",
            pista="sería un ciclo: decidir cuál manda y quitar la anotación de la otra"),
            "path": rel, "canonical": canonica}

    valor = f"[[{destino_mas_corto(canonica, indice)}]]"
    previo = datos.get(CLAVE)
    previo = previo if isinstance(previo, str) and previo.strip() else None
    base: Dict[str, Any] = {
        "ok": True, "tool": TOOL, "action": "apply" if apply else "check", "path": rel,
        "canonical": canonica, CLAVE: valor, "previous": previo,
        # AP-37: `written` es el indicador de trabajo; en dry-run es False.
        "written": False, "already": False,
    }
    if previo is not None:
        if resolver_sustitucion(previo, Path(rel), indice)[0] == canonica:
            return {**base, "already": True}
        if not replace:
            return {**emit_error(
                TOOL, "INVALID_VALUE", f"{rel} ya declara {CLAVE}: {previo}",
                pista="es una decisión ya tomada; para cambiarla, repetir con --replace"),
                "path": rel, "previous": previo}

    bloque, cuerpo = separar_frontmatter(texto)
    fm = Frontmatter() if bloque is None else Frontmatter.editar(bloque)
    fm.set(CLAVE, valor, texto=True)
    nuevo = fm.render() + "\n" + (texto.lstrip("﻿") if bloque is None else cuerpo)
    base["encoding_normalized"] = _normalizacion(crudo)
    if not apply:
        return base

    bloqueo = fuera_de_sesion(TOOL, nota)
    if bloqueo:
        return bloqueo
    lock = tomar_lock(nota, 10.0)
    if lock is None:
        return {**emit_error(TOOL, "NOTE_LOCKED", f"{rel} está bloqueada"), "path": rel}
    with lock:
        # AP-54: lo planificado se calculó sobre `crudo`; una edición ajena
        # entremedias se perdería al escribir encima.
        if nota.read_bytes() != crudo:
            return {**emit_error(TOOL, "NOTE_LOCKED", f"{rel} cambió mientras se anotaba"),
                    "path": rel}
        try:
            atomic_write_text(nota, nuevo)
        except (PermissionError, ValueError) as exc:
            return {**emit_error(TOOL, "WRITE_ERROR", str(exc), exception=exc), "path": rel}
    return {**base, "written": True}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_supersede — anota superseded_by en una nota existente",
        allow_abbrev=False)
    ap.add_argument("--path", required=True, help="la nota sustituida, ruta relativa al vault")
    ap.add_argument("--by", required=True,
                    help="la nota que manda, como wikilink: nombre de fichero, alias o ruta")
    ap.add_argument("--apply", action="store_true", help="escribe (por defecto, dry-run)")
    ap.add_argument("--replace", action="store_true",
                    help="sustituir una superseded_by distinta ya escrita")
    args = ap.parse_args()
    r = supersede(args.path, args.by, apply=args.apply, replace=args.replace)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, TOOL))

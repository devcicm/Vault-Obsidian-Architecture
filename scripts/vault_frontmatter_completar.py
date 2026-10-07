#!/usr/bin/env python3
"""vault_frontmatter_completar — pone los campos del contrato que la nota no lleva.

## Por qué existe

`vault_validate` dice qué le falta a una nota y hasta 2026-10-05 su pista era
«los campos que faltan se completan editando la nota». Medido ese día en el
sandbox: 26 notas inválidas, la mayoría por campos ausentes, y una edición a
mano por campo. Una pista que pide trabajo manual repetido es la razón por la
que nadie la sigue.

## Qué pone, y de dónde sale cada valor

Solo lo que `vault_contrato_nota` exige a la clase de la nota (requeridos) y lo
que el escritor pone siempre (recomendados: `type`, `status`). Cada valor va en
el envelope con su `origin`, porque un campo completado no es un campo escrito
por quien hizo la nota y quien revise tiene que poder distinguirlos:

| Campo | Valor | `origin` |
|---|---|---|
| `id` | uuid4 nuevo | `uuid4` |
| `title` | primer `# H1` del cuerpo, o el nombre del fichero | `primer_h1` / `nombre_de_fichero` |
| `createdAt` | el `updatedAt` declarado, o el mtime del fichero | `updatedAt` / `mtime` |
| `updatedAt` | el `createdAt` declarado, o el mtime | `createdAt` / `mtime` |
| `cia_*` | `cia_por_defecto()` (dueño: `CIA_TRIAD`) | `CIA_TRIAD.default` |
| `agent` | `--agent`, `VAULT_AGENT` o `POR_DEFECTO` | `--agent` / `VAULT_AGENT` / `por_defecto` |
| `tags`, `status` | `POR_DEFECTO` del contrato | `por_defecto` |
| `type` | el tipo por defecto de la sección (`SECTION_TYPES`) | `seccion` |

Los valores por defecto son los de `vault_write`, leídos de sus dueños: poner
aquí uno propio sería una segunda opinión sobre el mismo dato (AP-57).

## Lo que no toca

- **Ningún valor que ya está.** Ni para corregirlo: un `cia_integrity` fuera del
  vocabulario es una decisión de quien escribió la nota, no un hueco.
- **Un bloque que no parsea** es de `vault_frontmatter_heal` (AP-56): completar
  encima de un YAML roto sería inventar dónde acaba.
- **Los artefactos derivados** no tienen contrato, y las **instantáneas**
  (`.history/`) valen por no cambiar.
- **Lo que no es nota**: solo las secciones de `ORDERED_SECTIONS`, el mismo
  barrido que `vault_validate`.

    python scripts/vault_frontmatter_completar.py                 # dry-run
    python scripts/vault_frontmatter_completar.py --apply         # escribe
    python scripts/vault_frontmatter_completar.py --path 07_Knowledge/x.md --apply

No acepta `--root` (regla 1): el destino sale de `vault_io.get_vault_root()`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from vault_contrato_nota import POR_DEFECTO, campos_recomendados, clase_de_nota, faltantes
from vault_entorno import leer as _env
from vault_errors import emit_error, fuera_de_sesion, wrap_main
from vault_fundamentals_catalog import cia_por_defecto
from vault_io import assert_within_vault, atomic_write_text, get_vault_root, is_snapshot_path, tomar_lock
from vault_lib import canonical_utc
from vault_registry import ORDERED_SECTIONS, section_default_type
from vault.kernel.frontmatter_escritura import Frontmatter
from vault.kernel.frontmatter_parsing import (
    FrontmatterParseError,
    parse_frontmatter_with_body,
    separar_frontmatter,
)

TOOL = "vault_frontmatter_completar"
_H1 = re.compile(r"^#\s+(.+?)\s*#*\s*$", re.MULTILINE)


def _notas(raiz: Path) -> List[Path]:
    return sorted(
        n for seccion in ORDERED_SECTIONS for n in (raiz / seccion).rglob("*.md")
        if n.is_file() and not is_snapshot_path(n.relative_to(raiz)) and not n.name.startswith("_")
    )


def _mtime(nota: Path) -> str:
    return canonical_utc(datetime.fromtimestamp(nota.stat().st_mtime, timezone.utc).isoformat())


def _valor(campo: str, datos: Dict[str, Any], nota: Path, rel: str, cuerpo: str,
           agent: Optional[str]) -> Tuple[Any, str]:
    """`(valor, origen)` para un campo ausente. Cada rama nombra la norma que salda."""
    if campo == "id":  # AP-12
        return str(uuid.uuid4()), "uuid4"
    if campo == "title":  # AP-12
        h1 = _H1.search(cuerpo)
        return (h1.group(1), "primer_h1") if h1 else (nota.stem, "nombre_de_fichero")
    if campo == "createdAt":  # AP-12, AP-13: una nota no nace después de su última edición
        if datos.get("updatedAt"):
            return canonical_utc(datos["updatedAt"]), "updatedAt"
        return _mtime(nota), "mtime"
    if campo == "updatedAt":  # AP-12
        if datos.get("createdAt"):
            return canonical_utc(datos["createdAt"]), "createdAt"
        return _mtime(nota), "mtime"
    if campo.startswith("cia_"):  # AP-30
        return cia_por_defecto()[campo], "CIA_TRIAD.default"
    if campo == "agent":  # AP-16
        if agent:
            return agent, "--agent"
        if _env("VAULT_AGENT"):  # del registro de entorno, no con default propio
            return _env("VAULT_AGENT"), "VAULT_AGENT"
        return POR_DEFECTO["agent"], "por_defecto"
    if campo == "type":  # AP-27
        return section_default_type(rel.split("/", 1)[0]), "seccion"
    # AP-26 (tags), AP-29 (status)
    return POR_DEFECTO[campo], "por_defecto"


def planificar(nota: Path, rel: str, texto: str, agent: Optional[str] = None
               ) -> Tuple[Optional[Dict[str, Dict[str, Any]]], Optional[str], Optional[str]]:
    """`(campos, texto_nuevo, causa_de_omision)` para una nota.

    `campos` vacío y `texto_nuevo` None si no le falta nada. Una nota sin bloque
    (AP-28) recibe uno entero; un bloque que no parsea no se toca (AP-56).
    """
    if clase_de_nota(rel) == "derivada":
        return {}, None, None
    bloque, cuerpo = separar_frontmatter(texto)
    if bloque is None:
        if texto.lstrip("﻿").startswith("---"):
            return None, None, "frontmatter_ilegible"  # abre y no cierra: AP-56
        datos: Dict[str, Any] = {}
        cuerpo = texto.lstrip("﻿")
        fm = Frontmatter()  # AP-28
    else:
        try:
            datos, _ = parse_frontmatter_with_body(texto)
        except FrontmatterParseError:
            return None, None, "frontmatter_ilegible"
        fm = Frontmatter.editar(bloque)

    ausentes = faltantes(datos, rel) + [c for c in campos_recomendados(rel) if c not in datos]
    campos: Dict[str, Dict[str, Any]] = {}
    for campo in ausentes:
        valor, origen = _valor(campo, datos, nota, rel, cuerpo, agent)
        if valor == "" and campo == "type":
            continue  # sección sin tipo canónico: no hay nada que poner sin inventarlo
        campos[campo] = {"value": valor, "origin": origen}
        fm.set(campo, valor, texto=isinstance(valor, str) and campo not in ("createdAt", "updatedAt"))
    if not campos:
        return {}, None, None
    return campos, fm.render() + "\n" + cuerpo, None


def _normalizacion(nota: Path) -> List[str]:
    """Lo que `atomic_write_text` cambiará además de los campos.

    El write path escribe LF sin BOM, que es el formato del estándar, y esta
    tool no tiene un criterio de codificación propio (AP-57). En una nota CRLF
    o con BOM eso convierte el diff en el fichero entero: se declara aquí para
    que quien revise sepa por qué, en vez de que lo descubra en el commit.
    """
    crudo = nota.read_bytes()
    return [nombre for nombre, hay in (("bom", crudo.startswith(b"\xef\xbb\xbf")),
                                       ("crlf", b"\r\n" in crudo)) if hay]


def _escribir(nota: Path, visto: str, nuevo: str) -> Optional[str]:
    """Escribe `nuevo` si la nota sigue siendo `visto`. Devuelve la causa si no.

    AP-54: el plan se calculó sobre `visto`; una edición ajena entremedias se
    perdería al pegar aquí la versión completada.
    """
    lock = tomar_lock(nota, 10.0)
    if lock is None:
        return "nota_bloqueada"
    with lock:
        if nota.read_text(encoding="utf-8") != visto:
            return "cambio_concurrente"
        try:
            atomic_write_text(nota, nuevo)
        except (PermissionError, ValueError) as exc:
            # El escáner de secretos y la verificación del frontmatter de
            # `atomic_write_text` rechazan aquí; se cuenta, no se esconde.
            # Sin la forma `clave: valor`: es una causa del informe, no una
            # línea de frontmatter, y AP-56 no tiene por qué adivinarlo.
            return f"escritura_rechazada ({type(exc).__name__})"
    return None


def completar(path: Optional[str] = None, apply: bool = False,
              agent: Optional[str] = None) -> Dict[str, Any]:
    raiz = get_vault_root()
    if path:
        try:
            nota = assert_within_vault(raiz / path, raiz)
        except ValueError as exc:
            return {**emit_error(TOOL, "INVALID_PATH", str(exc), pista="una ruta relativa dentro del vault"),
                    "path": path}
        if not nota.is_file():
            return {**emit_error(TOOL, "NOTE_NOT_FOUND", f"Note not found: {path}"), "path": path}
        notas = [nota]
    else:
        notas = _notas(raiz)

    completadas: List[Dict[str, Any]] = []
    omitidas: List[Dict[str, Any]] = []
    escritas = 0
    for nota in notas:
        rel = nota.relative_to(raiz).as_posix()
        try:
            texto = nota.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            omitidas.append({"path": rel, "cause": f"ilegible: {type(exc).__name__}"})
            continue
        campos, nuevo, causa = planificar(nota, rel, texto, agent)
        if causa:
            omitidas.append({"path": rel, "cause": causa,
                             "hint": "python scripts/vault_frontmatter_heal.py --apply"})
            continue
        if not campos:
            continue
        entrada: Dict[str, Any] = {"path": rel, "fields": campos, "written": False,
                                   "encoding_normalized": _normalizacion(nota)}
        if apply:
            bloqueo = fuera_de_sesion(TOOL, nota)
            fallo = bloqueo["error_code"] if bloqueo else _escribir(nota, texto, nuevo)
            if fallo:
                omitidas.append({"path": rel, "cause": fallo})
                continue
            entrada["written"] = True
            escritas += 1
        completadas.append(entrada)

    return {
        "ok": not omitidas and (apply or not completadas),
        "tool": TOOL,
        "action": "apply" if apply else "check",
        "notes_scanned": len(notas),
        "completed": completadas,
        "completed_count": len(completadas),
        # AP-37: cuántas notas cambiaron en disco. En dry-run es cero, y esa
        # es la respuesta correcta.
        "written_count": escritas,
        "skipped": omitidas,
        "skipped_count": len(omitidas),
        "hint": ("Cada valor lleva su origin: un campo completado no lo escribió quien "
                 "hizo la nota, y se revisa antes de darlo por dato."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_frontmatter_completar — pone los campos del contrato que faltan",
        allow_abbrev=False)
    ap.add_argument("--apply", action="store_true", help="escribe (por defecto, dry-run)")
    ap.add_argument("--check", action="store_true", help="solo mide (por defecto)")
    ap.add_argument("--strict", action="store_true", help="exit 1 si queda algo por completar")
    ap.add_argument("--path", help="una sola nota, ruta relativa al vault")
    ap.add_argument("--agent", help="valor de agent para las notas que no lo llevan")
    args = ap.parse_args()

    if args.apply and args.check:
        env = emit_error(TOOL, "CONFLICTING_ARGS",
                         "--apply y --check piden cosas distintas: o mide o escribe",
                         pista="elige uno")
        print(json.dumps(env, ensure_ascii=False))
        return 1

    r = completar(path=args.path, apply=args.apply, agent=args.agent)
    print(json.dumps(r, ensure_ascii=False))
    return 1 if (args.strict or "error_code" in r) and not r["ok"] else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, TOOL))

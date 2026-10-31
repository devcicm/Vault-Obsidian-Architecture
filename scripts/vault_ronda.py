#!/usr/bin/env python3
"""vault_ronda — abre, consulta y cierra la ronda de trabajo de un agente (D-07).

## Por qué existe

Una ronda de trabajo no dejaba rastro propio: las notas de una tanda no tenían
nada que las uniera y `04_Sessions/` solo recibía lo que alguien escribiera a
mano. `vault_session` hacía de contenedor y se archivó en favor de
`vault_delta`; esta tool recupera la ronda sin volver a un contenedor que
duplique identidad. La ronda es una vista: un `round_id` que `vault_write`
estampa en cada nota mientras está abierta, y una nota de sesión al cerrar que
enumera lo que lo lleva.

La decisión de 2026-10-30 es que la ronda la abre **el agente**, vía MCP. Nadie
la abre por él: sin `--abrir`, `vault_write` escribe igual que antes.

## Qué hace

    python scripts/vault_ronda.py --activa
    python scripts/vault_ronda.py --abrir --agente claude --objetivo "sanar 10_Migrated"
    python scripts/vault_ronda.py --cerrar --resumen "tres notas canónicas y dos supersedidas"

- `--abrir` escribe `00_System/ronda-activa.json`. Con otra ya abierta devuelve
  `ROUND_ALREADY_ACTIVE` y no la pisa: dos rondas a la vez harían que cada nota
  perteneciera a la que llegó última.
- `--cerrar` escribe `04_Sessions/ronda-<round_id>.md` por `vault_write` —el
  write path único, AP-46— con las notas que llevan su `round_id`, y quita la
  ronda activa. Sin ronda abierta, `ROUND_NOT_ACTIVE`.
- `--activa` solo lee.

No acepta `--root` (regla 1): el destino sale de `vault_io.get_vault_root()`.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from vault_errors import emit_error, wrap_main
from vault_io import atomic_write_json, get_vault_root, is_snapshot_path, write_report
from vault_lib import destino_mas_corto, indice_de_nombres, inventario_de_nombres
from vault_registry import secciones_del_vault
from vault_write import vault_write

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.ronda import leer_activa, nuevo_round_id, ruta_activa  # noqa: E402
from vault.kernel.enumeracion import notas_en_disco  # noqa: E402
from vault.kernel.frontmatter_parsing import FrontmatterParseError, parse_frontmatter  # noqa: E402

TOOL = "vault_ronda"
SECCION_SESIONES = "04_Sessions"


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()[:19] + "Z"


def _activa_o_error():
    try:
        return leer_activa(get_vault_root()), None
    except ValueError as exc:
        return None, emit_error(
            TOOL, "DATA_FILE_CORRUPT", str(exc),
            pista="revisar 00_System/ronda-activa.json; si la ronda no sigue en curso, borrarlo",
        )


def activa() -> Dict[str, Any]:
    ronda, error = _activa_o_error()
    if error:
        return error
    return {"ok": True, "tool": TOOL, "action": "activa", "active": ronda is not None,
            "round": ronda, **write_report()}


def abrir(agente: str, objetivo: str) -> Dict[str, Any]:
    agente, objetivo = (agente or "").strip(), (objetivo or "").strip()
    if not agente or not objetivo:
        return emit_error(TOOL, "MISSING_REQUIRED_ARG",
                          "--abrir necesita --agente y --objetivo no vacíos")
    ronda, error = _activa_o_error()
    if error:
        return error
    if ronda:
        return {**emit_error(TOOL, "ROUND_ALREADY_ACTIVE",
                             f"la ronda {ronda['round_id']} sigue abierta"),
                "round": ronda}
    ronda = {"round_id": nuevo_round_id(), "agent": agente, "objective": objetivo,
             "opened_at": _ahora()}
    atomic_write_json(ruta_activa(get_vault_root()), ronda)
    return {"ok": True, "tool": TOOL, "action": "abrir", "round": ronda, **write_report()}


def notas_de_la_ronda(round_id: str) -> List[str]:
    """Las notas que llevan `round_id`, por ruta relativa y en orden.

    El frontmatter se lee con el dueño (`parse_frontmatter` del núcleo, que
    lanza en vez de devolver vacío, AP-61); una nota que no se deja leer no es
    de ninguna ronda, y la sanación es de `vault_frontmatter_heal`, no de esta
    tool.
    """
    raiz = get_vault_root()
    encontradas = []
    for nota in notas_en_disco(raiz, secciones_del_vault(raiz), incluir_indices=False):
        try:
            datos = parse_frontmatter(nota.read_text(encoding="utf-8"))
        except (FrontmatterParseError, OSError, UnicodeDecodeError):
            continue
        if datos.get("round_id") == round_id:
            encontradas.append(nota.relative_to(raiz).as_posix())
    return sorted(encontradas)


def _cuerpo(ronda: Dict[str, Any], resumen: str, notas: List[str], cerrada: str) -> str:
    lineas = [
        f"# Ronda {ronda['round_id']}",
        "",
        f"- **Agente:** {ronda['agent']}",
        f"- **Objetivo:** {ronda['objective']}",
        f"- **Abierta:** {ronda['opened_at']}",
        f"- **Cerrada:** {cerrada}",
        "",
        "## Resumen",
        "",
        resumen,
        "",
        "## Notas escritas en la ronda",
        "",
    ]
    if notas:
        # El enlace más corto que resuelve a esa nota y a ninguna otra, con el
        # criterio de Obsidian (AP-44): un `[[nombre]]` repetido apuntaría a la
        # que el editor elija.
        relativas, alias_por_ruta = inventario_de_nombres(get_vault_root(), is_snapshot_path)
        indice = indice_de_nombres(relativas, alias_por_ruta)
        lineas += [f"- [[{destino_mas_corto(n, indice)}]] — `{n}`" for n in notas]
    else:
        lineas.append("Ninguna nota lleva el `round_id` de esta ronda.")
    return "\n".join(lineas) + "\n"


def cerrar(resumen: str) -> Dict[str, Any]:
    resumen = (resumen or "").strip()
    if not resumen:
        return emit_error(TOOL, "MISSING_REQUIRED_ARG", "--cerrar necesita un --resumen no vacío")
    ronda, error = _activa_o_error()
    if error:
        return error
    if not ronda:
        return emit_error(TOOL, "ROUND_NOT_ACTIVE", "no hay ninguna ronda abierta")
    notas = notas_de_la_ronda(ronda["round_id"])
    escrita = vault_write(
        SECCION_SESIONES, f"Ronda {ronda['round_id']}",
        _cuerpo(ronda, resumen, notas, _ahora()),
        tags=["ronda", "session-log"],
        meta={"agent": ronda["agent"], "round_id": ronda["round_id"]},
    )
    if not escrita.get("ok"):
        # La ronda sigue abierta: cerrarla sin su nota borraría el único sitio
        # que dice qué se escribió en ella.
        return {**escrita, "tool": TOOL, "round": ronda}
    ruta_activa(get_vault_root()).unlink()
    return {"ok": True, "tool": TOOL, "action": "cerrar", "round": ronda,
            "session_note": escrita.get("path"), "notes": notas, "closed": True,
            **write_report()}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Abre, consulta y cierra la ronda de trabajo de un agente",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_ronda.py --activa
  python vault_ronda.py --abrir --agente claude --objetivo "sanar 10_Migrated"
  python vault_ronda.py --cerrar --resumen "tres notas canónicas y dos supersedidas"
""",
        allow_abbrev=False,
    )
    accion = parser.add_mutually_exclusive_group()
    accion.add_argument("--abrir", action="store_true", help="Abrir una ronda nueva")
    accion.add_argument("--cerrar", action="store_true", help="Cerrar la ronda abierta")
    accion.add_argument("--activa", action="store_true", help="Consultar la ronda abierta (por defecto)")
    parser.add_argument("--agente", default="", help="Quién abre la ronda (con --abrir)")
    parser.add_argument("--objetivo", default="", help="Para qué se abre (con --abrir)")
    parser.add_argument("--resumen", default="", help="Qué se hizo (con --cerrar)")
    args = parser.parse_args()

    if args.abrir:
        result = abrir(args.agente, args.objetivo)
    elif args.cerrar:
        result = cerrar(args.resumen)
    else:
        result = activa()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, TOOL))

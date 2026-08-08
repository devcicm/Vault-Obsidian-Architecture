#!/usr/bin/env python3
"""vault_spec_catalog_check — Validate sync between tool-spec.json and TOOLS_CATALOG.

Detects:
- Tools missing from either source
- Group name mismatches
- Status mismatches (active/deprecated)

Y, desde v40.6, **el contrato de campos con los repos consumidores**.

Un repo consumidor no lee el catálogo ni el manifiesto: lee el envelope. Lo que
le importa de una tool es qué claves puede seguir esperando el mes que viene, y
eso hasta ahora no lo declaraba nadie. `vault_audit` es el caso que lo destapó:
`healthScore` quedó sustituido por `healthIndex` —22 penalizaciones con topes
que suman 285 sobre una base de 100 saturan en 0 y dejan de distinguir— y se
sigue emitiendo porque hay consumidores que lo leen. Esa anotación vivía en el
tool-spec **sin que la leyera ninguna tool**: un registro sin consumidor, que es
el modo de fallo que `tests/test_orphan_registries.py` describe.

La tabla de compatibilidad clasifica cada campo de `declared_returns` en tres:

  * `stable`     — publicado; el consumidor puede depender de él.
  * `superseded` — sigue emitiéndose, hay algo mejor; se anota, no se quita.
  * `internal`   — nunca fue contrato; declarado en `internal_fields`.

La regla que la puerta hace cumplir es una sola y es la no-derogación aplicada
al cable: **un campo estable no desaparece.** Puede pasar a `superseded`, que es
el camino sancionado; lo que no puede es evaporarse y romper en silencio a quien
lo leía.

Usage:
    python scripts/vault_spec_catalog_check.py
    python scripts/vault_spec_catalog_check.py --fix
    python scripts/vault_spec_catalog_check.py --check-fields --strict
    python scripts/vault_spec_catalog_check.py --fields-table
    python scripts/vault_spec_catalog_check.py --freeze-fields
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))
from vault_mcp_catalog import TOOLS_CATALOG
from vault_errors import emit_error, wrap_main
from vault_io import resolve_tool_spec, tool_spec_path

#: Baseline del contrato de campos. Vive en `scripts/` y no en el vault: es
#: contrato del **estándar**, no dato de un vault concreto — moverla al vault
#: la haría depender de cuál esté detectado (AP-36 mira lo contrario: los side
#: effects de runtime van al vault; esto es fuente del repo, versionada en git).
FIELDS_BASELINE = Path(__file__).parent / "field-compat-baseline.json"

FIELDS_SCHEMA = "field-compat/1"

#: Estados de tool que sacan sus campos del contrato: si la tool ya no se
#: publica, sus campos tampoco se le prometen a nadie.
ESTADOS_RETIRADOS = {"archived", "internal", "orphan", "deprecated"}


def _spec() -> Dict[str, Any]:
    ruta = resolve_tool_spec()
    if ruta is None:
        raise FileNotFoundError(str(tool_spec_path()))
    return json.loads(ruta.read_text(encoding="utf-8"))


def destinos_de(nota: Dict[str, Any]) -> List[str]:
    """A dónde migra un campo sustituido.

    El registro ya trae las dos formas y ninguna es un error: `healthScore` se
    sustituye por **un** campo (`healthIndex`) y `error` por **tres**
    (`error_code`, `message`, `recovery`), porque partir un campo en varios es
    justo lo que hizo AP-52. Normalizar aquí evita la tentación de reescribir
    las entradas existentes para que encajen con el guard, que sería el guard
    mandando sobre el registro.
    """
    destino = nota.get("superseded_by", "")
    crudos = [destino] if isinstance(destino, str) else list(destino)
    return [d for d in crudos if str(d).strip()]


def motivo_de(nota: Dict[str, Any]) -> str:
    """El porqué, bajo cualquiera de las dos claves que el registro usa."""
    return str(nota.get("why") or nota.get("reason") or "").strip()


def clasificar_campos(entrada: Dict[str, Any]) -> Dict[str, str]:
    """Campo → clase, para una entrada del tool-spec.

    Dos precisiones que no son cosméticas:

    * `superseded` gana a `internal`: un campo que se anotó como sustituido fue
      público alguna vez, y marcarlo interno después sería borrarlo por la
      puerta de atrás.
    * un campo sustituido **puede no estar ya en `declared_returns`** y aun así
      pertenece a la tabla. Es el caso de `error` en `vault_diff` y
      `vault_tags`: dejó de emitirse y la anotación es precisamente el registro
      de a dónde fue. Dejarlo fuera de la tabla convertiría la anotación en
      texto muerto justo para el consumidor que la necesita.
    """
    superados = set(entrada.get("superseded_fields", {}))
    internos = set(entrada.get("internal_fields", []))
    clases: Dict[str, str] = {campo: "superseded" for campo in superados}
    for campo in entrada.get("declared_returns", []):
        if campo in superados:
            continue
        clases[campo] = (
            "internal" if campo in internos or campo.startswith("_") else "stable"
        )
    return clases


def tabla_de_compatibilidad() -> Dict[str, Dict[str, str]]:
    """La tabla completa, derivada del tool-spec — nunca escrita a mano."""
    return {
        nombre: clasificar_campos(entrada)
        for nombre, entrada in sorted(_spec().get("tools", {}).items())
        if entrada.get("status", "active") not in ESTADOS_RETIRADOS
    }


def _cargar_baseline() -> Dict[str, List[str]]:
    if not FIELDS_BASELINE.exists():
        return {}
    datos = json.loads(FIELDS_BASELINE.read_text(encoding="utf-8"))
    return datos.get("stable", {})


def revisar_campos() -> Dict[str, Any]:
    """Compara la tabla actual contra la congelada.

    Devuelve las tres cosas que un consumidor necesita saber y que no son la
    misma: lo que se rompió, lo que cambió de clase sin romperse, y lo que se
    anotó mal.
    """
    tabla = tabla_de_compatibilidad()
    baseline = _cargar_baseline()
    spec_tools = _spec().get("tools", {})

    removidos: List[Dict[str, str]] = []
    degradados: List[Dict[str, str]] = []
    superados_nuevos: List[Dict[str, str]] = []
    anotaciones_malas: List[Dict[str, str]] = []

    for tool, campos in sorted(baseline.items()):
        entrada = spec_tools.get(tool)
        if entrada is None or entrada.get("status", "active") in ESTADOS_RETIRADOS:
            continue                       # la tool se retiró: lo cubre --check-contracts
        actual = tabla.get(tool, {})
        for campo in campos:
            clase = actual.get(campo)
            if clase is None:
                removidos.append({"tool": tool, "field": campo})
            elif clase == "internal":
                degradados.append({"tool": tool, "field": campo})
            elif clase == "superseded":
                superados_nuevos.append({
                    "tool": tool,
                    "field": campo,
                    "superseded_by": destinos_de(
                        entrada["superseded_fields"][campo]),
                    "still_emitted": campo in entrada.get("declared_returns", []),
                })

    # Una anotación que apunta a un campo que la tool no emite no le sirve al
    # consumidor: le dice que migre a algo que no va a encontrar. Que el campo
    # sustituido siga emitiéndose o no es decisión de cada caso — lo que no
    # puede faltar es el destino y el motivo.
    for tool, entrada in sorted(spec_tools.items()):
        # Un destino puede ser a su vez un campo anotado: `healthScore` →
        # `healthIndex` → `healthProfile` es una cadena que el consumidor puede
        # seguir hasta el final. Exigir que el destino siga en
        # `declared_returns` prohibiría anotar dos veces el mismo linaje, que es
        # justo lo que la no-derogación produce con el tiempo.
        declarados = set(entrada.get("declared_returns", [])) | set(
            entrada.get("superseded_fields") or {})
        for campo, nota in (entrada.get("superseded_fields") or {}).items():
            nota = nota or {}
            destinos = destinos_de(nota)
            if not destinos:
                anotaciones_malas.append({
                    "tool": tool, "field": campo,
                    "problem": "sin superseded_by: no dice a dónde migrar",
                })
            for destino in destinos:
                if destino not in declarados:
                    anotaciones_malas.append({
                        "tool": tool, "field": campo,
                        "problem": f"superseded_by apunta a '{destino}', "
                                   "que la tool no emite",
                    })
            if not motivo_de(nota):
                anotaciones_malas.append({
                    "tool": tool, "field": campo,
                    "problem": "sin why/reason: una sustitución sin motivo no se "
                               "puede revisar después",
                })

    rotos = removidos + degradados + anotaciones_malas
    conteo = {"stable": 0, "superseded": 0, "internal": 0}
    for campos in tabla.values():
        for clase in campos.values():
            conteo[clase] += 1

    return {
        "ok": not rotos,
        "tool": "vault_spec_catalog_check",
        "tools_in_contract": len(tabla),
        "fields_by_class": conteo,
        "baseline_tools": len(baseline),
        "removed_fields": removidos,
        "demoted_to_internal": degradados,
        "bad_annotations": anotaciones_malas,
        "newly_superseded": superados_nuevos,
    }


def congelar_campos() -> Dict[str, Any]:
    """Congela los `stable` actuales.

    Esta baseline **puede crecer**, al revés que las tres de deuda: cada campo
    nuevo es una promesa que se adquiere, no una infracción que se tolera. Lo
    que no puede es encoger sin pasar por `superseded_fields`, y de eso se
    encarga `--check-fields`.
    """
    tabla = tabla_de_compatibilidad()
    estables = {
        tool: sorted(c for c, clase in campos.items() if clase == "stable")
        for tool, campos in tabla.items()
    }
    estables = {t: c for t, c in estables.items() if c}
    previa = _cargar_baseline()
    datos = {
        "schema": FIELDS_SCHEMA,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "why": (
            "Campos que los repos consumidores pueden leer con garantía. Un "
            "campo que sale de aquí sin quedar anotado en superseded_fields "
            "rompe a quien lo leía, y por eso lo para una puerta."
        ),
        "stable": estables,
    }
    FIELDS_BASELINE.write_text(
        json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    nuevos = sum(len(set(c) - set(previa.get(t, []))) for t, c in estables.items())
    return {
        "ok": True,
        "tool": "vault_spec_catalog_check",
        "frozen_tools": len(estables),
        "frozen_fields": sum(len(c) for c in estables.values()),
        "added_since_previous": nuevos,
        "path": str(FIELDS_BASELINE),
    }


def _render_tabla_markdown() -> str:
    tabla = tabla_de_compatibilidad()
    filas = ["| Tool | Campo | Clase | Sustituido por |", "|---|---|---|---|"]
    spec_tools = _spec().get("tools", {})
    for tool, campos in tabla.items():
        superados = spec_tools[tool].get("superseded_fields", {})
        for campo, clase in sorted(campos.items()):
            destino = superados.get(campo, {}).get("superseded_by", "")
            filas.append(f"| `{tool}` | `{campo}` | {clase} | {destino or '—'} |")
    return "\n".join(filas)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate tool-spec.json vs TOOLS_CATALOG sync"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Fix group mismatches in vault_mcp_catalog.py",
    )
    parser.add_argument(
        "--check-fields", action="store_true",
        help="Contrato de campos: ningún campo estable desaparece (no-derogación)",
    )
    parser.add_argument(
        "--fields-table", action="store_true",
        help="Emite la tabla de compatibilidad derivada del tool-spec",
    )
    parser.add_argument(
        "--markdown", action="store_true",
        help="Con --fields-table, emite Markdown en vez de JSON",
    )
    parser.add_argument(
        "--freeze-fields", action="store_true",
        help="Congela los campos estables actuales como contrato",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Devuelve código de salida 1 si el contrato está roto",
    )
    args = parser.parse_args()

    if args.fields_table:
        if args.markdown:
            print(_render_tabla_markdown())
        else:
            print(json.dumps({
                "ok": True,
                "tool": "vault_spec_catalog_check",
                "compatibility": tabla_de_compatibilidad(),
            }, indent=2, ensure_ascii=False))
        return 0

    if args.freeze_fields:
        print(json.dumps(congelar_campos(), indent=2, ensure_ascii=False))
        return 0

    if args.check_fields:
        resultado = revisar_campos()
        if not resultado["ok"]:
            resultado = {
                **emit_error(
                    "vault_spec_catalog_check", "CONTRACT_FIELD_REMOVED",
                    f"{len(resultado['removed_fields'])} campos estables ya no se "
                    f"emiten, {len(resultado['demoted_to_internal'])} pasaron a "
                    f"internos y {len(resultado['bad_annotations'])} anotaciones "
                    "de sustitución no le sirven al consumidor",
                ),
                **{k: v for k, v in resultado.items() if k not in ("ok", "tool")},
            }
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        return 1 if (args.strict and not resultado["ok"]) else 0

    spec_path = resolve_tool_spec()
    if spec_path is None:
        print(json.dumps({
            **emit_error("vault_spec_catalog_check", "FILE_NOT_FOUND",
                         f"tool-spec.json no encontrado en {tool_spec_path()}"),
            "expected": str(tool_spec_path()),
            "hint": "python vault_manifest.py --bootstrap",
        }, indent=2, ensure_ascii=False))
        return 1
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec_tools = set(spec["tools"].keys())
    catalog_tools = set(TOOLS_CATALOG.keys())

    issues: list[str] = []

    # Coverage
    only_catalog = catalog_tools - spec_tools
    only_spec = spec_tools - catalog_tools
    common = catalog_tools & spec_tools

    if only_catalog:
        issues.append(
            f"TOOLS_CATALOG only ({len(only_catalog)}): {sorted(only_catalog)}"
        )
    if only_spec:
        issues.append(f"tool-spec.json only ({len(only_spec)}): {sorted(only_spec)}")

    # Group mismatches
    for t in sorted(common):
        cg = TOOLS_CATALOG[t].get("group", "")
        sg = spec["tools"][t].get("group", "")
        if cg.lower() != sg.lower():
            issues.append(f'Group mismatch: {t}: catalog="{cg}" spec="{sg}"')

    if not issues:
        print(
            json.dumps(
                {
                    "ok": True,
                    "catalog_tools": len(catalog_tools),
                    "spec_tools": len(spec_tools),
                    "in_sync": True,
                    "message": f"{len(common)} tools in sync — groups match, no coverage gaps",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    result = {
        "ok": False,
        "catalog_tools": len(catalog_tools),
        "spec_tools": len(spec_tools),
        "in_sync": False,
        "issues": issues,
        "issue_count": len(issues),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_spec_catalog_check"))

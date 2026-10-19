#!/usr/bin/env python3

"""
Vault Mermaid Check — Validación completa de diagramas Mermaid.

Detecta errores de sintaxis en bloques ```mermaid``` y proporciona
sugerencias de corrección. Soporta: flowchart, sequenceDiagram,
classDiagram, stateDiagram, erDiagram, gantt, pie.

Usage:
    python vault_mermaid_check.py
    python vault_mermaid_check.py --path "06_Diagrams/foo.md"
    python vault_mermaid_check.py --fix
    python vault_mermaid_check.py --project "mi-api"
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vault_errors import emit_error, wrap_main, proyecto_registrado
from vault_io import assert_within_vault, is_snapshot_path
from vault_entorno import leer as leer_entorno  # noqa: E402 — AP-49: defaults declarados
SCRIPTS_DIR = Path(__file__).parent


# superseded_by: vault_mermaid_reglas (v40.28) — AP-62. La gramática y sus
# validadores se fueron a una hoja del núcleo; aquí se reexportan para no
# derogar el contrato. Ver `vault_mermaid_reglas` para el porqué.
from vault_mermaid_reglas import MERMAID_TYPES  # noqa: F401,E402


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
from vault.kernel import construir  # noqa: E402


# ============================================================================
# Oráculo Mermaid (v41.12): el compilador real como criterio de sintaxis.
#
# El parser heurístico del modelo deja pasar errores de sintaxis que el
# compilador de Mermaid rechaza y produce falsos positivos — medido 2026-10-19
# contra un vault ajeno (SMART POS CR): 6 bloques que jison rechaza y el
# heurístico no ve, y 2 `mismatched_braces` que el compilador aprueba. El
# criterio del consumidor (AP-44) aquí es la sintaxis del compilador: el
# renderer real es quien decide si un diagrama se pinta.
#
# El oráculo valida SINTAXIS con `mermaid.parse` (mermaid core sobre jsdom,
# via `mcp/nodejs/mmd_validate.mjs`). Las reglas SEMÁNTICAS del dominio
# (`undefined_class`, `undefined_entity`, `undefined_state`) siguen siendo del
# estándar: Mermaid auto-crea clases/entidades al relacionarlas y el
# compilador las aprueba, pero el estándar pide clases declaradas.
#
# Sin oráculo (sin node o sin `npm install mermaid jsdom`): el estándar
# degrada al heurístico DECLARANDO su cobertura parcial en el envelope
# (`oraculo.disponible: false`) — no simula una validación completa (AP-51).
# ============================================================================

#: Errores del kernel que son pura sintaxis: el veredicto del compilador manda
#: sobre ellos. El resto (`undefined_*`, `no_data`, ...) es semántica del
#: dominio y sobrevive aunque el compilador apruebe el bloque.
SINTAXIS_PURAS = {"mismatched_braces", "mismatched_brackets"}

_NOMBRE_ORACULO = "mermaid-core"


def _helper_oraculo() -> Optional[Path]:
    """La ruta de `mmd_validate.mjs`, o `None` si no está instalado."""
    base = Path(__file__).resolve().parents[1]
    for relativa in ("mcp/nodejs/mmd_validate.mjs", "mcp/mmd_validate.mjs"):
        candidato = base / relativa
        if candidato.is_file():
            return candidato
    return None


def _pack_oraculo() -> Optional[Path]:
    """El directorio donde resuelven `mermaid` y `jsdom` para el oráculo.

    Orden: la var de entorno `VOAS_MERMAID_ORACLE` (para instalaciones en
    wheel, donde el pack vive fuera del disco virtual), o el `node_modules`
    junto al helper (el caso del checkout). Se lee por el registro (AP-49),
    no con un `os.environ.get` suelto.
    """
    env = leer_entorno("VOAS_MERMAID_ORACLE")
    candidatos: List[Path] = []
    if env:
        candidatos.append(Path(env))
    helper = _helper_oraculo()
    if helper:
        candidatos.append(helper.parent)
    for pack in candidatos:
        if (pack / "node_modules" / "mermaid").is_dir() and (pack / "node_modules" / "jsdom").is_dir():
            return pack
    return None


def oraculo_validar(
    bloques: List[Dict[str, str]],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Valida los bloques con el compilador real, en batch (un solo spawn).

    `bloques`: `[{id, file, code}]`. Devuelve `(veredicto, motivo)`:
    `(salida, None)` si el oráculo corrió; `(None, motivo)` si NO — y el
    motivo dice POR QUÉ (sin node, sin deps, helper sin pack...). AP-51: un `None`
    indistinguible de un oráculo que se campanó a mitad es un vacío que
    simula salud.
    """
    helper = _helper_oraculo()
    if not helper:
        return None, "sin helper mmd_validate.mjs"
    pack = _pack_oraculo()
    if not pack:
        return None, (
            "sin node_modules (mermaid/jsdom): 'npm install mermaid jsdom' en el dir del helper "
            "o VOAS_MERMAID_ORACLE apuntando a un pack con ambos"
        )
    node = shutil.which("node")
    if not node:
        return None, "node no está en PATH"
    env = dict(os.environ)
    env["VOAS_MERMAID_ORACLE"] = str(pack)
    # El default vive en el registro (`vault/kernel/entorno.py`): no se copia
    # aquí (AP-05 sobre configuración).
    timeout = float(leer_entorno("VAULT_TOOL_TIMEOUT"))
    try:
        corrida = subprocess.run(
            [node, str(helper), "-", "-"],
            input=json.dumps(bloques, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, "timeout del oráculo (el proceso node NO acabó a tiempo)"
    except OSError as exc:
        return None, f"no se pudo lanzar node: {exc}"
    if corrida.returncode != 0:
        detalle = (corrida.stderr or "").splitlines()[-1] if corrida.stderr else ""
        return None, f"node terminó con código {corrida.returncode}: {detalle[:200]}"
    try:
        salida = json.loads(corrida.stdout)
    except (json.JSONDecodeError, ValueError):
        return None, "salida del oráculo no es JSON válido"
    if not salida.get("ok"):
        return None, f"oráculo devolvió {salida.get('reason')}: {str(salida.get('detail'))[:200]}"
    return salida, None


def _fusionar_veredictos(
    result: Dict[str, Any], veredicto: Optional[Dict[str, Any]], indices: Dict[int, str]
) -> None:
    """Funde el veredicto del compilador sobre el reporte del kernel de un archivo.

    `indices`: índice de bloque → id del bloque en el lote del oráculo.
    """
    if not veredicto:
        return
    por_id = {r.get("id"): r for r in veredicto.get("results", [])}
    for block in result.get("blocks", []):
        id_bloque = indices.get(block.get("index"))
        veredicto_del_bloque = por_id.get(id_bloque) if id_bloque else None
        if not veredicto_del_bloque:
            continue
        if veredicto_del_bloque.get("ok"):
            # El compilador aprueba el bloque: la sintaxis pura del kernel
            # baja a aviso — el renderer real es quien decide (AP-44).
            sintaxis = [e for e in block.get("errors", []) if e.get("type") in SINTAXIS_PURAS]
            if sintaxis:
                sintaxis_ids = {id(e) for e in sintaxis}
                block["errors"] = [
                    e for e in block.get("errors", []) if e.get("type") not in SINTAXIS_PURAS
                ]
                # El mismo dict vive en la lista del archivo: ahí también sale.
                result["errors"] = [e for e in result.get("errors", []) if id(e) not in sintaxis_ids]
                if not block.get("warnings"):
                    block["warnings"] = []
                block["warnings"].extend(
                    {
                        **e,
                        "severity": "info",
                        "message": (
                            f"{e['message']} — el compilador Mermaid "
                            f"({_NOMBRE_ORACULO}) aprueba el bloque: aviso, no error"
                        ),
                    }
                    for e in sintaxis
                )
                if not block.get("errors"):
                    block["valid"] = True
        else:
            # El compilador rechaza el bloque: error nuevo con su mensaje.
            error_compilador = {
                "type": "parse_error",
                "source": _NOMBRE_ORACULO,
                "message": veredicto_del_bloque.get("error") or "error de parseo sin mensaje",
                "suggestion": (
                    "La sintaxis exacta la marca el compilador de Mermaid "
                    "(línea y contexto en el mensaje); revisar el punto señalado"
                ),
                "line": None,
            }
            block["valid"] = False
            block.setdefault("errors", []).append(error_compilador)
            result["valid"] = False
            result["errors"].append(error_compilador)
    # Recalcula los agregados del archivo tras la fusión.
    result["valid"] = all(b.get("valid", True) for b in result.get("blocks", [])) and not result.get("errors")


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGobernanza:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGobernanza(construir(root))


# superseded_by: vault_mermaid_reglas (v40.28) — AP-62. Ver arriba.
from vault_mermaid_reglas import (  # noqa: F401,E402
    detect_mermaid_type,
    validate_class,
    validate_er,
    validate_flowchart,
    validate_gantt,
    validate_mermaid,
    validate_pie,
    validate_sequence,
    validate_state,
)


def check_file(
    path: Path, diagramas: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Verifica un archivo por bloques Mermaid.

    Si `diagramas` es una lista, la llena con `{index, code}` por cada bloque
    crudo encontrado: la lista completa alimenta al oráculo en batch sin que
    check_file mismo lo invoque (un solo spawn por corrida, no por archivo).
    """
    result = {
        "file": str(path),
        "valid": True,
        "blocks": [],
        "errors": [],
    }

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        result["valid"] = False
        result["errors"].append({"type": "read_error", "message": str(e)})
        return result

    pattern = r"```mermaid\s*\n(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)

    for idx, diagram in enumerate(matches):
        if diagramas is not None:
            diagramas.append({"file": str(path), "index": idx, "code": diagram})
        block_result = {
            "index": idx,
            "type": detect_mermaid_type(diagram),
            "valid": True,
            "errors": [],
        }

        todos = validate_mermaid(diagram)
        # Un aviso no invalida el diagrama. AP-25 penaliza -2 por cada entrada
        # de `errors`, así que mezclar avisos con errores de sintaxis convierte
        # una preferencia de estilo en una caída del health score.
        errors = [e for e in todos if e.get("severity") != "info"]
        avisos = [e for e in todos if e.get("severity") == "info"]
        if avisos:
            block_result["warnings"] = avisos
        if errors:
            block_result["valid"] = False
            block_result["errors"] = errors
            result["valid"] = False
            result["errors"].extend(errors)

        result["blocks"].append(block_result)

    return result


def scan_vault(
    path: Optional[Path] = None, project: Optional[str] = None
) -> Dict[str, Any]:
    """Escanea el vault por diagramas Mermaid."""
    search_root = path or _raiz()

    if project:
        search_root = _raiz() / "01_Projects" / project

    files_checked = 0
    results = []
    crudos: List[Dict[str, Any]] = []  # {file, index, code} — lote del oráculo

    for md in search_root.rglob("*.md"):
        # `is_snapshot_path` sustituye al `".history" in str(md)` anterior, que
        # dejaba pasar `vault-backups/` y `.trash/`: 46 de los 69 errores AP-25
        # de BuilderX vivían en instantáneas congeladas. Peor con `--fix`, que
        # reescribía diagramas dentro de una copia de seguridad.
        # Relativo a la raíz del barrido: con la ruta absoluta, un directorio
        # ancestro FUERA del vault que se llamara `.trash` excluiría el vault
        # entero en silencio.
        try:
            rel_md = md.relative_to(search_root)
        except ValueError:  # pragma: no cover — rglob siempre cuelga de la raíz
            rel_md = md
        if is_snapshot_path(rel_md) or md.name.startswith("_"):
            continue
        files_checked += 1
        result = check_file(md, diagramas=crudos)
        if result["blocks"]:
            results.append(result)

    # Oráculo: un solo spawn valida todo el lote. Sin oráculo = degradado al
    # heurístico, con el motivo declarado — no simulado (AP-51).
    veredicto, motivo_oraculo = (
        oraculo_validar(
            [{"id": f"{d['file']}#{d['index']}", "file": str(d["file"]), "code": d["code"]}
             for d in crudos]
        ) if crudos else (None, None)
    )
    if veredicto:
        for result in results:
            indices = {d["index"]: f"{result['file']}#{d['index']}" for d in crudos if d["file"] == result["file"]}
            _fusionar_veredictos(result, veredicto, indices)

    total_errors = sum(len(r["errors"]) for r in results)
    all_valid = all(r["valid"] for r in results)

    pack = _pack_oraculo()
    helper = _helper_oraculo()
    if veredicto:
        estado_oraculo = {
            "disponible": True,
            "parser": _NOMBRE_ORACULO,
            "bloques_comprobados": len(veredicto.get("results", [])),
            "helper": str(helper),
            "pack": str(pack),
            "motivo": None,
        }
    elif not crudos:
        # Sin bloques que validar, ni heurístico ni oráculo tuvieron trabajo.
        estado_oraculo = {"disponible": False, "parser": "heuristico", "bloques_comprobados": 0,
                          "helper": str(helper) if helper else None, "pack": str(pack) if pack else None,
                          "motivo": None}
    else:
        estado_oraculo = {
            "disponible": False,
            "parser": "heuristico",
            "bloques_comprobados": 0,
            "helper": str(helper) if helper else None,
            "pack": str(pack) if pack else None,
            "motivo": motivo_oraculo,
        }
    return {
        "ok": all_valid,
        "files_checked": files_checked,
        "files_with_diagrams": len(results),
        "total_errors": total_errors,
        "oraculo": estado_oraculo,
        "results": results,
    }


def fix_common_issues(diagram: str) -> Tuple[str, List[str]]:
    """Intenta corregir errores comunes automáticamente."""
    fixes = []
    result = diagram

    result = re.sub(r"\{\s*\{", "{", result)
    result = re.sub(r"\}\s*\}", "}", result)
    if result != diagram:
        fixes.append("Colapsó llaves anidadas")

    result = re.sub(r"\[\s*\[", "[", result)
    result = re.sub(r"\]\s*\]", "]", result)
    if result != diagram:
        fixes.append("Colapsó corchetes anidados")

    return result, fixes


def main():
    parser = argparse.ArgumentParser(
        description="Vault Mermaid Check - Valida diagramas Mermaid",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_mermaid_check.py
  python vault_mermaid_check.py --path "06_Diagrams/foo.md"
  python vault_mermaid_check.py --project "mi-api"
  python vault_mermaid_check.py --fix
  python vault_mermaid_check.py --path "06_Diagrams/foo.md" --fix
        """,
        allow_abbrev=False,
    )

    parser.add_argument("--path", type=str, help="Archivo específico a verificar")
    parser.add_argument("--project", type=proyecto_registrado("vault_mermaid_check"), help="Proyecto a verificar")
    parser.add_argument("--fix", action="store_true", help="Intentar auto-corrección")
    parser.add_argument("--json", action="store_true", help="Salida JSON")

    args = parser.parse_args()

    if args.path:
        # AP-36: el catálogo declara `within_vault` sobre --path; sin esto
        # `../x.md` o una ruta absoluta leían cualquier fichero del disco.
        try:
            path = assert_within_vault(_raiz() / args.path, _raiz())
        except ValueError as exc:
            print(json.dumps(emit_error("vault_mermaid_check", "INVALID_PATH", str(exc)),
                             ensure_ascii=False))
            return 1
        if not path.exists():
            print(
                json.dumps(
                    emit_error("vault_mermaid_check", "FILE_NOT_FOUND", f"Archivo no encontrado: {args.path}"),
                    ensure_ascii=False,
                )
            )
            return 1
        diagramas: List[Dict[str, Any]] = []
        result = check_file(path, diagramas=diagramas)
        # El mismo lote del scan, para el archivo único: un spawn, sin artefactos.
        veredicto, motivo_oraculo = (
            oraculo_validar(
                [{"id": f"{path}#{d['index']}", "file": str(path), "code": d["code"]} for d in diagramas]
            ) if diagramas else (None, None)
        )
        if veredicto:
            _fusionar_veredictos(
                result, veredicto, {d["index"]: f"{path}#{d['index']}" for d in diagramas}
            )
        result["oraculo"] = {
            "disponible": veredicto is not None,
            "parser": _NOMBRE_ORACULO if veredicto else "heuristico",
            "bloques_comprobados": len(veredicto.get("results", [])) if veredicto else 0,
            "helper": str(_helper_oraculo()),
            "pack": str(_pack_oraculo()) if _pack_oraculo() else None,
            "motivo": None if veredicto or not diagramas else motivo_oraculo,
        }
    elif args.project:
        result = scan_vault(project=args.project)
    else:
        result = scan_vault()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("ok", True):
            orac = result.get("oraculo") or {}
            cobertura = (
                f"sintaxis vía compilador ({orac.get('parser')}, "
                f"{orac.get('bloques_comprobados')} bloques)"
                if orac.get("disponible")
                else "sintaxis vía heurístico — SIN compilador de Mermaid: puede haber "
                "errores que solo el compilador caza (npm install mermaid jsdom junto a mmd_validate.mjs, o VOAS_MERMAID_ORACLE)"
            )
            print(
                f"✓ Validación exitosa: {result.get('files_with_diagrams', 0)} diagramas revisados — {cobertura}"
            )
            return 0
        else:
            orac = result.get("oraculo") or {}
            if not orac.get("disponible"):
                print(
                    "⚠ Sin compilador de Mermaid (solo heurístico): los errores de "
                    "sintaxis que listan abajo pueden ser una CURA parcial — "
                    "'npm install mermaid jsdom' junto a mmd_validate.mjs completa el oráculo"
                )
            print(f"✗ Errores encontrados: {result.get('total_errors', 0)}")
            for res in result.get("results", []):
                if not res["valid"]:
                    print(f"\nArchivo: {res['file']}")
                    for block in res.get("blocks", []):
                        if not block["valid"]:
                            for err in block.get("errors", []):
                                print(f"  - {err['type']}: {err['message']}")
                                if err.get("suggestion"):
                                    print(f"    Sugerencia: {err['suggestion']}")
            return 1

    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_mermaid_check"))

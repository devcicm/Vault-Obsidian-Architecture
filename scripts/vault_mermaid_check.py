#!/usr/bin/env python3

"""
Vault Mermaid Check — Validación completa de diagramas Mermaid.

Detecta errores de sintaxis en los bloques de código mermaid del vault
y proporciona sugerencias de corrección. Soporta: flowchart,
sequenceDiagram, classDiagram, stateDiagram, erDiagram, gantt, pie.

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
from vault_io import (
    assert_within_vault,
    escritura_atomica,
    escrituras_en_lote,
    file_lock,
    guarda_secretos,
    is_snapshot_path,
    record_raw_write,
    refrescar_grafo,
    write_report,
)
from vault_lib import RE_BLOQUE_MERMAID  # noqa: E402 — el fence con dueño (AP-57)
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

    pattern = RE_BLOQUE_MERMAID  # el fence con dueño — AP-57 (2026-10-19)
    matches = pattern.findall(content)

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
        # AP-37: el indicador de trabajo se MIDE en el ledger, no se afirma.
        # El scan de solo lectura lleva written: 0 — que enseña que NADA
        # escribió, distinto de un campo ausente que obliga a leer el código.
        **write_report(),
    }


def fix_common_issues(diagram: str) -> Tuple[str, List[str]]:
    """Intenta corregir errores comunes automáticamente.

    superseded_by: los `SANADORES_MERMAID` de este módulo + oráculo (2026-10-19).
    Era un colapso ciego de llaves/corchetes anidados sin criterio de
    aceptación: cambiaba el diagrama sin comprobar si el resultado parsea.
    Se conserva por no-derogación; la sanación vigente es `sanar_bloques`,
    donde el compilador de Mermaid aprueba cada cambio antes de escribirlo.
    """
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


# ============================================================================
# Sanación con oráculo (2026-10-19): el ciclo síntoma → norma → guard + audit +
# heal → test se cierra aquí. AP-25 ya tenía guard (`vault_diagram_save`) y
# audit (esta tool); le faltaba el heal. Los sanadores son transformaciones
# mecánicas clase-a-clase, medidas contra los 6 bloques reales de un vault
# ajeno (SMART POS CR, 2026-10-19). El criterio de aceptación NO es el regex:
# cada propuesta la aprueba el compilador real (`mermaid.parse`) — un bloque
# con varios defectos exige COMPOSICIONES, porque la propuesta parcial de un
# solo sanador sigue parseando mal y el compilador la rechaza.
# ============================================================================


def _san_saltos_literales(diagram: str) -> Optional[str]:
    r"""`\n`/`\t`/`\r\n` literales a saltos reales (bug del generador Python)."""
    if "\\n" not in diagram and "\\t" not in diagram:
        return None
    propuesto = (
        diagram.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
    )
    return propuesto if propuesto != diagram else None


def _san_edge_label_especial(diagram: str) -> Optional[str]:
    r"""Edge label con `()` o `,` sin citar: `-->|false (default)|` → `-->|"false (default)"|`."""
    def cita(m: "re.Match[str]") -> str:
        label = m.group(1)
        if '"' in label:
            return m.group(0)
        if "(" in label or ")" in label or "," in label:
            return f'|"{label}"|'
        return m.group(0)

    propuesto = re.sub(r"\|([^|\n]*)\|", cita, diagram)
    return propuesto if propuesto != diagram else None


def _san_er_etiqueta(diagram: str) -> Optional[str]:
    r"""Relación ER con etiqueta ubicada antes de ` : `:
    `user }o--|| tenant "pertenece a"` → `user }o--|| tenant : "pertenece a"`."""
    primera = next((l for l in diagram.splitlines() if l.strip()), "")
    if not primera.lstrip().startswith("erDiagram"):
        return None
    patron = r"^(\s*[\w-]+\s+[\}|o<>-]+--+[\}|o<>-]+\s+[\w-]+)\s+\"([^\"]+)\"[^\S\n]*$"
    propuesto = re.sub(patron, lambda m: f'{m.group(1)} : "{m.group(2)}"', diagram, flags=re.M)
    return propuesto if propuesto != diagram else None


def _san_label_especial(diagram: str) -> Optional[str]:
    r"""Label de nodo con `()<>{}:,'` sin citar: `A[foo<br/>(bar)]` → `A["foo<br/>(bar)"]`.

    Solo corchetes cuadrados `[...]` — el diamante `A{...}` y demás formas no
    se tocan. Un label que YA tiene comillas no se re-encierra: si una
    comilla aparece antes del cierre, no hay match que envolver.

    Escaneo lineal, no un regex: el equivalente `\[([^"\]\n]*)\]` con un
    callback era cuadrático con tiradas de `[` sin cierre — 4.162 ms con
    20.000 caracteres hostiles, contra un umbral de 50 ms
    (tests/test_filtro_de_expresiones_regulares). El razonamiento es el
    mismo del patrón, posición a posición; cambia el mecanismo, no lo que
    se decide y no lo que envuelve.
    """
    primera = next((l for l in diagram.splitlines() if l.strip()), "")
    if primera.lstrip().startswith("erDiagram"):
        return None  # en ER los corchetes son atributos de entidad, no labels

    especiales = "()<>{}:,"
    cambio = False
    salida: List[str] = []
    for linea in diagram.split("\n"):
        trozos: List[str] = []
        i = 0
        while True:
            abre = linea.find("[", i)
            if abre == -1:
                trozos.append(linea[i:])
                break
            trozos.append(linea[i:abre])
            # La etiqueta acaba en el primer cierre posterior; una comilla
            # antes del cierre excluye el match (la clase del patrón también
            # excluye ambas). Un `\n` no entra: es por línea.
            cierra = linea.find("]", abre + 1)
            comilla = linea.find('"', abre + 1)
            if (cierra == -1 and comilla == -1) or (
                comilla != -1 and (cierra == -1 or comilla < cierra)
            ):
                # Cerrado por comillas o sin cierre eventual: el siguiente
                # candidato es otro `[` (el match del patrón tampoco pudo
                # empezar en este).
                i = abre + 1
                continue
            label = linea[abre + 1: cierra]
            if any(c in label for c in especiales):
                trozos.append(f'["{label}"]')
                cambio = True
            else:
                trozos.append(linea[abre: cierra + 1])
            i = cierra + 1
        salida.append("".join(trozos))
    return "\n".join(salida) if cambio else None


def _san_corchete_abierto(diagram: str) -> Optional[str]:
    r"""Nodo con label abierto al fin de línea: `B[Label2` → `B[Label2]`."""
    lineas = diagram.split("\n")
    cambio = False
    salida = []
    for linea in lineas:
        rstrip = linea.rstrip()
        if rstrip.rfind("[") > rstrip.rfind("]"):
            salida.append(rstrip + "]")
            cambio = True
        else:
            salida.append(linea)
    return "\n".join(salida) if cambio else None


#: El registro de sanadores, con la norma que sostienen. El nombre de la tool
#: está en `SANADORES` de `vault/kernel/norms_catalog.py`; el par lo sostiene
#: este módulo nombrando AP-25 en el docstring de `sanar_bloques` (AP-55).
SANADORES_MERMAID: List[Tuple[str, Any]] = [
    ("saltos_literales", _san_saltos_literales),
    ("edge_label_especial", _san_edge_label_especial),
    ("er_etiqueta", _san_er_etiqueta),
    ("label_especial", _san_label_especial),
    ("corchete_abierto", _san_corchete_abierto),
]

_PATRON_BLOQUE = RE_BLOQUE_MERMAID  # el fence con dueño — AP-57 (2026-10-19)


def curar_bloques(
    rotos: Dict[str, str], verificar: Any
) -> Tuple[Dict[str, Tuple[str, List[str]]], List[str]]:
    """Sana los bloques que el compilador rechaza, con el compilador de árbitro.

    `rotos`: `{id_del_bloque: code}`; `verificar`: callable que recibe una
    lista de códigos y devuelve un `ok` booleano alineado por posición (el
    oráculo en batch). Devuelve `(sanados, no_salvables)`: `sanados[id]` es
    `(code_curado, sanadores_aplicados)`; `no_salvables` son los ids que ni
    con todas las composiciones de sanadores el compilador aprueba — y esos
    NO se escriben: una cura no verificada es un defecto nuevo (AP-25).
    """
    import itertools

    sanados: Dict[str, Tuple[str, List[str]]] = {}
    actual = dict(rotos)
    for _ronda in range(6):
        propuestas: List[Tuple[str, str, List[str]]] = []
        for id_bloque, code in actual.items():
            fns = [
                (nombre, fn)
                for nombre, fn in SANADORES_MERMAID
                if fn(code) is not None and fn(code) != code
            ]
            if not fns:
                continue
            # Composiciones por tamaño creciente: el compilador aprueba la
            # más pequeña que deje el bloque parseando — mínimo cambio que
            # cura (y preferencia de sanadores en orden canónico).
            for tam in range(1, len(fns) + 1):
                for combo in itertools.combinations(fns, tam):
                    candidato = code
                    for _nombre, fn in combo:
                        candidato = fn(candidato)
                    if candidato != code:
                        nombres = [nombre for nombre, _fn in combo]
                        propuestas.append((id_bloque, candidato, nombres))
        if not propuestas:
            break
        veredictos = verificar([p[1] for p in propuestas])
        for (id_bloque, candidato, nombres), ok in zip(propuestas, veredictos):
            if ok and id_bloque not in sanados:
                sanados[id_bloque] = (candidato, nombres)
        actual = {k: v for k, v in actual.items() if k not in sanados}
    no_salvables = list(actual)
    return sanados, no_salvables


def sanar_bloques(
    diagnostico: Dict[str, Any], dry_run: bool = False
) -> Dict[str, Any]:
    """Sana los bloques que el compilador rechaza en el vault señalado. AP-25.

    Ciclo completo del heal: toma el diagnóstico de esta corrida (cada
    bloque con `parse_error` del compilador), propone composiciones de
    sanadores mecánicos y las VERIFICA con el compilador antes de escribir
    (AP-44: el criterio es el renderer real, no el regex). Solo se escribe
    lo que el compilador aprueba; lo no salvable queda declarado intacto.

    Escritura por la puerta de exactitud del estándar: `file_lock` →
    `record_raw_write` (ledger AP-37) → `escritura_atomica` con
    `guarda_secretos` en guardas (escaneo I1/I5 sin el saneado, que aplicaría
    mutaciones después del criterio de aceptación) → `refrescar_grafo` fuera
    del lock. `--dry-run` propone y reporta sin tocar un byte.
    """
    def id_de(file: str, index: int) -> str:
        return f"{file}#{index}"

    # Los rotos con su code: re-lectura fresca del mismo patrón que usó el
    # diagnóstico (misma corrida, el contenido no cambió en medio).
    results = diagnostico.get("results") or []
    if not results and diagnostico.get("file"):
        results = [diagnostico]
    rotos: Dict[str, str] = {}
    errores_rotos: Dict[str, str] = {}
    for result in results:
        if result.get("valid", True):
            continue
        archivo = result["file"]
        try:
            texto = Path(archivo).read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            errores_rotos[f"{archivo}:read"] = str(exc)
            continue
        codigos = {m.start(): m.group(1) for m in _PATRON_BLOQUE.finditer(texto)}
        indices = sorted(codigos)
        for block in result.get("blocks", []):
            if block.get("valid", True):
                continue
            if not any(e.get("type") == "parse_error" for e in block.get("errors", [])):
                continue  # solo lo que el compilador rechaza: el resto es del audit
            index_sp = block.get("index", 0)
            if index_sp >= len(indices):
                continue
            id_bloque = id_de(archivo, index_sp)
            rotos[id_bloque] = codigos[indices[index_sp]]
            errores_rotos[id_bloque] = next(
                (
                    e.get("message", "")
                    for e in block.get("errors", [])
                    if e.get("type") == "parse_error"
                ),
                "",
            )

    if not rotos:
        return {
            "ok": True,
            "healed": 0,
            "clean": len(results),
            "sanados": [],
            "no_salvables": [],
            "escritos": [],
            "motivo": None,
            "dry_run": dry_run,
            **write_report(),
        }
    oraculo = diagnostico.get("oraculo") or {}
    if not oraculo.get("disponible"):
        return {
            "ok": False,
            "healed": 0,
            "rotos": len(rotos),
            "sanados": [],
            "no_salvables": [],
            "escritos": [],
            "motivo": (
                "hay bloques que el compilador rechaza pero el oráculo no corrió: "
                f"sin criterio de aceptación no se escribe ({oraculo.get('motivo')})"
            ),
            "dry_run": dry_run,
            **write_report(),
        }

    def verificar(codigos: List[str]) -> List[bool]:
        entrada = [{"id": f"b{i}", "file": "x", "code": c} for i, c in enumerate(codigos)]
        veredicto, _ = oraculo_validar(entrada)
        if not veredicto:
            # El oráculo se campanó a mitad del heal: sin veredicto NO se
            # aprueba nada — vacío que simula salud sería AP-51.
            return [False] * len(codigos)
        return [bool(r.get("ok")) for r in veredicto.get("results", [])]

    sanados, no_salvables = curar_bloques(rotos, verificar)

    # Agrupa los reemplazos por archivo y reconstruye el texto completo.
    por_archivo: Dict[str, Dict[int, str]] = {}
    for id_bloque, (curado, _nombres) in sanados.items():
        archivo, _, index = id_bloque.rpartition("#")
        por_archivo.setdefault(archivo, {})[int(index)] = curado

    escritos: List[str] = []
    cambios_fallidos: List[Dict[str, str]] = []
    if not dry_run and por_archivo:
        # El bloque llegó AQUÍ solo si el compilador lo aprobó. `atomic_write_text`
        # es el escritor canónico de notas, pero aplica `sanitize_content`
        # (NFC, comillas tipográficas, guiones) DESPUÉS de lo que el compilador
        # aprobó: la mutación no verificada invalidaría el criterio de
        # aceptación. Por eso la escritura va por la puerta de exactitud del
        # estándar: `record_raw_write` (ledger AP-37) + `escritura_atomica` con
        # `guarda_secretos` en guardas (escaneo I1/I5 sin saneado) +
        # `file_lock`, y el grafo refrescado una vez por el cierre del lote
        # (AP-47: con 500 diagramas rotos, un refresco de grafo por nota era
        # el 55 % del tiempo en la medida de `vault_frontmatter_completar`).
        # Segundo motivo válido del write en crudo, documentado en
        # `vault.kernel.ledger.record_raw_write`.
        vroot = _raiz()
        with escrituras_en_lote():
            for archivo, reemplazos in por_archivo.items():
                path = Path(archivo)
                try:
                    texto = path.read_text(encoding="utf-8", errors="ignore")
                    nuevo = _recomponer_texto(texto, reemplazos)
                    assert_within_vault(path, vroot)
                    with file_lock(path):
                        record_raw_write(path, nuevo)
                        escritura_atomica(path, nuevo, guardas=[guarda_secretos])
                    refrescar_grafo(path)
                    escritos.append(archivo)
                except (OSError, ValueError) as exc:
                    cambios_fallidos.append({"file": archivo, "motivo": str(exc)[:200]})

    sanados_lista = [
        {
            "id": id_bloque,
            **({"file": id_bloque.rpartition("#")[0]} if "#" in id_bloque else {}),
            **({"bloque": int(id_bloque.rpartition("#")[2])} if "#" in id_bloque else {}),
            "sanadores": nombres,
            "error_original": errores_rotos.get(id_bloque, ""),
            "code_curado": curado if dry_run else None,
        }
        for id_bloque, (curado, nombres) in sorted(sanados.items())
    ]
    no_salvables_lista = [
        {
            "id": id_bloque,
            "error_activo": errores_rotos.get(id_bloque, ""),
            "detalle": (
                "ninguna composición de sanadores mecánicos deja el bloque "
                "parseando; se corrige a mano o se declara no salvable"
            ),
        }
        for id_bloque in no_salvables
    ]
    return {
        "ok": not no_salvables and not cambios_fallidos,
        "healed": len(sanados) if not dry_run else 0,
        "propuestos": len(sanados) if dry_run else None,
        "sanados": sanados_lista,
        "no_salvables": no_salvables_lista,
        "escritos": escritos,
        "fallidos": cambios_fallidos,
        "motivo": None,
        "dry_run": dry_run,
        **write_report(),
    }


def _recomponer_texto(texto: str, reemplazos: Dict[int, str]) -> str:
    """Reemplaza los bloques del mapa por índice, sin tocar el resto del texto.

    El fence se reconstruye DESDE EL PROPIO match (posiciones del span): se
    conserva la forma original del archivo —fence, espacios, salto— y el
    único byte que cambia es el cuerpo del bloque que el compilador aprobó.
    """
    partes: List[str] = []
    ultimo = 0
    for idx, m in enumerate(_PATRON_BLOQUE.finditer(texto)):
        partes.append(texto[ultimo: m.start()])
        if idx in reemplazos:
            partes.append(
                texto[m.start(): m.start(1)] + reemplazos[idx] + texto[m.end(1): m.end()]
            )
        else:
            partes.append(m.group(0))
        ultimo = m.end()
    partes.append(texto[ultimo:])
    return "".join(partes)


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
    parser.add_argument("--fix", action="store_true", help="Sanar los bloques que el compilador rechaza (requiere el oráculo)")
    parser.add_argument("--dry-run", action="store_true", help="Con --fix: propone y reporta sin escribir")
    parser.add_argument("--json", action="store_true", help="Salida JSON")

    args = parser.parse_args()

    # ── heal de AP-25: diagnosticar → sanar → re-diagnosticar ──
    if args.fix:

        def _diagnosticar() -> Dict[str, Any]:
            if args.path:
                # La misma guardia de lectura del modo verificación.
                try:
                    path = assert_within_vault(_raiz() / args.path, _raiz())
                except ValueError as exc:
                    print(json.dumps(emit_error(
                        "vault_mermaid_check", "INVALID_PATH", str(exc)
                    ), ensure_ascii=False))
                    raise SystemExit(1)
                if not path.exists():
                    print(json.dumps(emit_error(
                        "vault_mermaid_check", "FILE_NOT_FOUND", f"Archivo no encontrado: {args.path}"
                    ), ensure_ascii=False))
                    raise SystemExit(1)
                diagramas: List[Dict[str, Any]] = []
                result = check_file(path, diagramas=diagramas)
                _veredicto, _motivo = (
                    oraculo_validar(
                        [{"id": f"{path}#{d['index']}", "file": str(path), "code": d["code"]}
                         for d in diagramas]
                    ) if diagramas else (None, None)
                )
                if _veredicto:
                    _fusionar_veredictos(
                        result, _veredicto,
                        {d["index"]: f"{path}#{d['index']}" for d in diagramas},
                    )
                result["oraculo"] = {
                    "disponible": _veredicto is not None,
                    "parser": _NOMBRE_ORACULO if _veredicto else "heuristico",
                    "bloques_comprobados": len(_veredicto.get("results", [])) if _veredicto else 0,
                    "helper": str(_helper_oraculo()),
                    "pack": str(_pack_oraculo()) if _pack_oraculo() else None,
                    "motivo": None if _veredicto or not diagramas else _motivo,
                }
                return result
            if args.project:
                return scan_vault(project=args.project)
            return scan_vault()

        antes = _diagnosticar()
        sanacion = sanar_bloques(antes, dry_run=args.dry_run)
        despues = _diagnosticar()  # el estado del vault tras el intento
        despues["sanacion"] = sanacion
        # AP-37: el indicador del ledger entra por los returns de `scan_vault`
        # y `sanar_bloques` (el spread de `write_report()`), no se re-monta aquí.

        if args.json:
            print(json.dumps(despues, indent=2, ensure_ascii=False))
        else:
            sanados = sanacion.get("sanados") or []
            no_salv = sanacion.get("no_salvables") or []
            if sanacion.get("dry_run"):
                print(f"⏺ Dry-run: {len(sanados)} bloque(s) se sanarían, {len(no_salv)} no salvable(s) — nada se escribió")
            else:
                print(f"⏺ Sanación: {sanacion.get('healed', 0)} bloque(s) sanado(s), {len(no_salv)} no salvable(s)")
            for s in sanados:
                print(f"  ✓ {s['id']} — {', '.join(s['sanadores'])}")
            for s in no_salv:
                print(f"  ✗ {s['id']} — {s.get('error_activo', '')[:120]}")
            total_errores = despues.get("total_errors", sum(len(r.get("errors", [])) for r in despues.get("results", [])) if "results" in despues else len(despues.get("errors", [])))
            if total_errores:
                print(f"  (persisten {total_errores} error(es) en el vault tras la sanación)")
        return 0 if (sanacion.get("ok") and despues.get("ok", True)) else 1

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

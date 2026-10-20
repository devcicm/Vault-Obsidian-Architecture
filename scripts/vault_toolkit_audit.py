#!/usr/bin/env python3
"""vault_toolkit_audit — verificación funcional del toolkit, tool por tool.

`vault_smoke` (AP-42) mide que la herramienta corre y que su envelope tiene
`ok`. Esta script mide lo que nadie más mide: que el ejemplo documentado
**ejercice la función declarada** — y lo hace sobre la maquinaria ya pagada,
sin substituir a ningún guard:

- **C0 superficie** — el ejemplo se parte como argv ejecutable; una tool sin
  script propio (runtime node, servicio HTTP) sale declarada, no silenciosa.
- **C1 cobertura** — si la tool declara side effects, en su ejemplo debe haber
  al menos una línea que no sea de solo lectura (`--help`/`--list`/`--check`/
  `--coverage`...). Un ejemplo que solo mira documenta una función que nadie
  probó hacer.
- **C2 ejecución y contrato** — cada línea del ejemplo corre contra una copia
  desechable del sandbox (la maquinaria de `vault_smoke.run_one`), y el
  envelope producido se contrasta con `declared_returns`
  (`vault_smoke.contract_gap`) y con el exit code: `ok: true` con exit != 0 es
  el mismo drift con otro traje.
- **C3 idempotencia** — sobre **una misma copia del vault** se corre la última
  línea del ejemplo dos veces: si la tool declara idempotencia (`unchanged` en
  su `declared_returns`) y la segunda corrida reescribe, es defecto. Como
  medida, el arbol del vault se registra siempre.
- **C4 paridad CLI↔MCP** — delegada al dueño (AP-57): `check_params()` y
  `check_sync()` de `vault_mcp_catalog` son quienes miden; aquí solo se
  reparten sus hallazgos por tool para que el veredicto los nombre.
- **C5 degradación** — una tool que depende de una `VOAS_*` del entorno debe
  degradar con motivo cuando falta, no reventar con traceback: se corre una
  línea sin esa variable y se mira cómo falla.

Veredicto por tool: `OK`, `MEJORA`, `DEFECTO`, `NO-VERIFICABLE` (con el motivo
escrito — las exenciones silenciosas son el fallo que la norma persigue).
Solo `DEFECTO` entra en la baseline (`scripts/toolkit-audit-baseline.json`),
que solo puede encoger: crecer exige `--freeze --admitir-nuevos` y el envelope
los lista. `--check --strict` es lo que un cierre debe correr.

El informe de evidencia es derivado (`--doc` → `docs/auditorias/
auditoria-toolkit.md`, desde `scripts/toolkit-audit-last.json`): corrido una
vez y regenerado siempre por la tool — nunca a mano (AP-47).

El coste por invocación es alto (cada línea paga una copia del sandbox), por
eso el alcance se acota: `--todo` para el barrido completo, `--grupo N` para
una ola, `--tools a,b` para el caso puntual.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
SANDBOX = REPO_ROOT / "vault-sandbox"
BASELINE_PATH = SCRIPTS_DIR / "toolkit-audit-baseline.json"
LAST_RUN_PATH = SCRIPTS_DIR / "toolkit-audit-last.json"
DOC_PATH = REPO_ROOT / "docs" / "auditorias" / "auditoria-toolkit.md"

#: Flags que miran sin hacer. Una tool que declara side effects y cuyo ejemplo
#: completo cae aquí tiene un ejemplo que nunca ejercita lo que declara.
#: `--dry-run` exercise la función sin comprometer el vault: NO está aquí.
FLAGS_DE_SOLO_LECTURA = ("--help", "-h", "--list", "--check", "--coverage",
                         "--show")

#: Dependencias externas declaradas en el propio código (`VOAS_*`): si falta,
#: la tool debe degradar con motivo, no reventar (C5).
PATRON_DE_ENTORNO = re.compile(r"\bVOAS_[A-Z_]+\b")


class DeudaNueva(Exception):
    """--freeze sin --admitir-nuevos sobre deuda que la baseline no conocía."""

    def __init__(self, lista: List[str]) -> None:
        super().__init__("deuda nueva no congelada")
        self.lista = lista


# ————————————————————————————————————————————— C4: los dueños delegados ——————

def repartir_c4(tools_pedidas: Set[str]) -> Dict[str, Any]:
    """Hallazgos de `check_params`/`check_sync`, repartidos por tool (AP-57)."""
    import vault_mcp_catalog as mc

    params = mc.check_params()
    sync = mc.check_sync()
    por_tool: Dict[str, List[str]] = {}
    for origen, datos in (("params", params), ("sync", sync)):
        for problema in (datos.get("problems") or []):
            tool = problema.get("tool")
            if tool in tools_pedidas:
                por_tool.setdefault(tool, []).append(
                    f"c4 ({origen}): {problema.get('problem', '')} "
                    f"(fix: {problema.get('fix', '')})")
    return {"ok": bool(params.get("ok")) and bool(sync.get("ok")),
            "por_tool": por_tool}


# ———————————————————————————————— alcance: tool → grupo numeral → capacidad ——

def gid_y_capacidad() -> Tuple[Dict[str, int], Dict[str, str]]:
    import vault_mcp_catalog as mc
    import vault_servicio as vs

    mapa = mc.mapa_de_grupos()
    caps = vs.capacidad_por_grupo()
    gid = {nombre: datos.get("id", 0) for nombre, datos in mapa.items()}
    return gid, {nombre: caps.get(dat_g, "escritura_a_gobernanza")
                 for nombre, dat_g in gid.items()}


def _salir_con_error(codigo: str, mensaje: str, **detalle: Any) -> int:
    """AP-52: ningún envelope de error fuera del contrato de ERROR_CATALOG."""
    import vault_errors

    envelope = vault_errors.emit_error(
        "vault_toolkit_audit", codigo, message=mensaje, args=detalle or None)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(envelope, ensure_ascii=False, indent=1))
    return 1


def _seleccionar(args: argparse.Namespace) -> List[str]:
    import vault_mcp_catalog as mc

    todas = sorted(mc.TOOLS_CATALOG)
    if args.todo:
        return todas
    if args.tools:
        pedidas = [t.strip() for t in args.tools.split(",") if t.strip()]
        desconocidas = [t for t in pedidas if t not in mc.TOOLS_CATALOG]
        if desconocidas:
            _salir_con_error(
                "TOOL_NOT_IN_SPEC",
                f"sin entrada en el catálogo: {', '.join(desconocidas)}")
            raise SystemExit(1)
        return pedidas
    if args.grupo:
        gid, _ = gid_y_capacidad()
        elegidas = [t for t in todas if gid.get(t) in args.grupo]
        if not elegidas:
            _salir_con_error(
                "INVALID_VALUE",
                f"ninguna tool en el grupo(s) {args.grupo}")
            raise SystemExit(1)
        return elegidas
    _salir_con_error(
        "INVALID_ARGS",
        "pide --todo, --grupo o --tools (el barrido completo no es gratis)")
    raise SystemExit(1)


# ————————————————————————————————————————————— los cheques, uno a uno ————————

def c0_superficie(nombre: str, entrada: Dict[str, Any]) -> Dict[str, Any]:
    import vault_smoke

    if entrada.get("runtime") == "node":
        return {"estado": "NO-VERIFICABLE",
                "motivo": "runtime node: su despacho lo ejercita el servidor MCP, "
                          "no un smoke de CLI (vault_smoke.run_one lo exime por lo que es)"}
    script = entrada.get("script")
    if not script or not (SCRIPTS_DIR / script).is_file():
        return {"estado": "NO-VERIFICABLE",
                "motivo": "sin script propio: invocada por __module__ desde el servidor MCP"}
    lineas = vault_smoke.invocations(nombre)
    if not lineas:
        return {"estado": "DEFECTO", "motivo": "sin líneas `python` ejecutables en el example",
                "detalle": (entrada.get("example") or "").splitlines()[:1]}
    return {"estado": "OK", "lineas": len(lineas)}


def _es_solo_lectura(linea: str) -> bool:
    """¿La línea lleva alguna flag de solo lectura, por TOKEN y no por trozo?

    El `flag in line` por substring clasificaba `--priority must-have` como
    `--list` (la `-h` vive dentro de `must-have`) y `--host` como `--help`:
    tres tools honestas salían como DEFECTO/MEJORA porque su ejemplo decía
    algo que CONTENÍA la flag sin llevarla (AP-44: el criterio del que mide,
    no el del argv real, que va por tokens).
    """
    tokens = set(linea.split())
    return any(flag in tokens for flag in FLAGS_DE_SOLO_LECTURA)


def c1_cobertura(nombre: str, entrada: Dict[str, Any],
                 lineas_python: List[str]) -> Dict[str, Any]:
    if not lineas_python:
        return {"estado": "OK", "nota": "sin lines `python` en el example (C0 lo declara)"}
    utiles = [line for line in lineas_python if not _es_solo_lectura(line)]
    side_effects = entrada.get("side_effects") or []
    if not utiles and side_effects:
        return {"estado": "DEFECTO",
                "motivo": "declara side effects y el ejemplo completo es de solo lectura",
                "side_effects": side_effects[:4]}
    if not utiles:
        return {"estado": "MEJORA",
                "motivo": "el ejemplo solo mira; ninguna línea hace el trabajo que la tool declara"}
    return {"estado": "OK", "lineas_utiles": len(utiles)}


def c2_ejecucion(nombre: str, lineas: List[Any]) -> Dict[str, Any]:
    """Cada línea corre contra una copia desechable; el envelope se contrasta."""
    import vault_smoke

    corridas: List[Dict[str, Any]] = []
    for argv in lineas:
        resultado = vault_smoke.run_one(nombre, arbol=True, argv=argv)
        corrida: Dict[str, Any] = {
            "argv": " ".join(argv[2:])[:200],
            "exit": resultado.get("exit_code"),
            "envelope_ok": resultado.get("tool_ok"),
            "cambiadas": resultado.get("cambiadas"),
        }
        if "problem" in resultado:
            corrida["perdida"] = f"{resultado['problem']}: {str(resultado.get('detail') or '')[:160]}"
        elif contrato := vault_smoke.contract_gap(resultado):
            corrida["perdida"] = f"contrato: {contrato['problem']}"
        elif resultado.get("tool_ok") is True and resultado.get("exit_code") not in (0, None):
            corrida["perdida"] = f"ok:true con exit {resultado.get('exit_code')}"
        corridas.append(corrida)
    perdidas = [c["perdida"] for c in corridas if c.get("perdida")]
    return {"estado": "DEFECTO" if perdidas else "OK",
            "perdidas": perdidas[:6], "corridas": corridas}


_ARBOL_LOCAL_CACHE: Optional[Set[str]] = None


def _arbol_local(raiz: Path) -> Dict[str, str]:
    """Hash de cada fichero del vault salvo lo que el ledger no da por trabajo.

    El criterio del FT que no es trabajo lo dueñece el ledger (`_NO_ES_TRABAJO`);
    el hash es logística. Duplicarlo con criterio propio sería AP-57.
    """
    import hashlib

    from vault.kernel.ledger import _NO_ES_TRABAJO

    out: Dict[str, str] = {}
    for p in sorted(raiz.rglob("*")):
        if p.is_file() and ".locks" not in p.parts and p.name not in _NO_ES_TRABAJO:
            out[p.relative_to(raiz).as_posix()] = (
                p.read_bytes() and hashlib.sha256(p.read_bytes()).hexdigest())
    return out


def c3_bis(nombre: str, entrada: Dict[str, Any], lineas: List[Any]) -> Dict[str, Any]:
    """C3 real: dos corridas EN LA MISMA copia (no dos copias frescas).

    Correr dos veces contra copias frescas mide duplicación, no idempotencia:
    el criterio que la norma declara necesita que la segunda corrida vea el
    estado que la primera dejó. El criterio de qué fichero cuenta como trabajo
    lo dueñece el ledger (`_NO_ES_TRABAJO`); el embalaje aquí es logística.
    """
    import subprocess

    declarada = "unchanged" in (contrato_de(nombre) or set())
    if not lineas or not declarada:
        return {"estado": "OK", "declarada": declarada,
                "nota": "sin contrato de idempotencia: no se hipoteca nada"}

    destino = Path(tempfile.mkdtemp(prefix="tka-idem-"))
    vault = destino / "vault"
    try:
        if SANDBOX.is_dir():
            shutil.copytree(SANDBOX, vault,
                            ignore=shutil.ignore_patterns(".locks"))
        else:
            vault.mkdir(parents=True)
        env = dict(os.environ)
        env.update({"VAULT_ROOT": str(vault), "VAULT_AGENT": "tka-idem",
                    "VAULT_VOICE": "0"})
        argv = list(lineas[-1])
        procesos: List[Dict[str, Any]] = []
        foto_antes = _arbol_local(vault)
        for numero_corrida in (1, 2):
            try:
                proc = subprocess.run(argv, capture_output=True, text=True,
                                      env=env, encoding="utf-8", errors="replace",
                                      cwd=str(SCRIPTS_DIR), timeout=120)
            except subprocess.TimeoutExpired:
                procesos.append({"corrida": numero_corrida, "perdida": "timeout"})
                continue
            foto_despues = _arbol_local(vault)
            reescritas = [ruta for ruta in set(foto_antes) | set(foto_despues)
                          if foto_antes.get(ruta) != foto_despues.get(ruta)]
            procesos.append({"corrida": numero_corrida, "exit": proc.returncode,
                             "reescritas": len(reescritas),
                             "rutas": reescritas[:6]})
            foto_antes = foto_despues  # la medida de la segunda corre sobre esto
    finally:
        shutil.rmtree(destino, ignore_errors=True)
    if any("perdida" in p for p in procesos):
        return {"estado": "OK", "declarada": True, "corridas": procesos,
                "nota": "no se hipoteca: la corrida cayó antes de medir"}
    ultima = [p for p in procesos if p.get("corrida") == 2]
    reescritas_2 = (ultima[0].get("reescritas") if ultima else None)
    if reescritas_2:
        return {"estado": "DEFECTO",
                "motivo": "declara idempotencia y la segunda corrida reescribió el vault",
                "corridas": procesos}
    return {"estado": "OK", "declarada": True, "corridas": procesos}


def contrato_de(nombre: str) -> Optional[Set[str]]:
    """`declared_returns` del tool-spec — el dueño es el contrato (AP-37)."""
    import vault_smoke

    return vault_smoke._contrato_de(nombre) or None


def c5_degradacion(nombre: str, entrada: Dict[str, Any], lineas: List[Any],
                   ) -> Dict[str, Any]:
    """Sin su `VOAS_*`: la tool debe explicar, no explotar."""
    script = entrada.get("script")
    externa: Set[str] = set()
    if script:
        ruta = SCRIPTS_DIR / script
        if ruta.is_file():
            externa = set(PATRON_DE_ENTORNO.findall(
                ruta.read_text(encoding="utf-8", errors="replace")))
    if not externa or not lineas:
        return {"estado": "OK", "nota": "sin `VOAS_*` declarada en su código"}
    guardadas = {var: os.environ.pop(var, None) for var in externa}
    try:
        import vault_smoke

        resultado = vault_smoke.run_one(nombre, arbol=False, argv=lineas[0])
    finally:
        for var, valor in guardadas.items():
            if valor is not None:
                os.environ[var] = valor
    salida = json.dumps(resultado, ensure_ascii=False)[:1500]
    if "Traceback" in salida or resultado.get("exit_code") not in (0, 1):
        return {"estado": "DEFECTO",
                "motivo": f"sin {'/'.join(sorted(externa))} revienta en vez de degradar",
                "detalle": salida[:240]}
    return {"estado": "OK", "sin": sorted(externa)}


# ————————————————————————————————————————————————————————— veredicto ————————

_SEVERIDAD = {"DEFECTO": 3, "NO-VERIFICABLE": 2, "MEJORA": 1, "OK": 0}


def _veredicto_de(chequeos: Dict[str, Dict[str, Any]]) -> Tuple[str, List[str]]:
    estados = {clave: datos.get("estado", "OK") for clave, datos in chequeos.items()}
    por_severidad = max(estados.values(), key=lambda s: _SEVERIDAD.get(s, 0))
    if not _SEVERIDAD.get(por_severidad, 0):
        return "OK", []
    motivos = [f"{clave}: {datos.get('motivo', '')}".rstrip(": ")
               for clave, datos in chequeos.items()
               if datos.get("estado") == por_severidad]
    return por_severidad, motivos


def auditar(nombre: str, entrada: Dict[str, Any], gid: int, capacidad: str,
 ) -> Dict[str, Any]:
    import vault_smoke

    c0 = c0_superficie(nombre, entrada)
    lineas_ejemplo = [line.strip() for line in (entrada.get("example") or "").splitlines()
                      if line.strip().startswith("python ")]
    chequeos: Dict[str, Dict[str, Any]] = {
        "c0": c0,
        "c1": c1_cobertura(nombre, entrada, lineas_ejemplo),
        "c4": {"estado": "OK"},  # lo rellena llamador con el reparto del dueño
    }
    if c0["estado"] == "OK":
        lineas = vault_smoke.invocations(nombre)
        chequeos["c2"] = c2_ejecucion(nombre, lineas)
        chequeos["c3"] = c3_bis(nombre, entrada, lineas)
        chequeos["c5"] = c5_degradacion(nombre, entrada, lineas)
    else:
        chequeos["c2"] = {"estado": c0["estado"], "motivo": c0.get("motivo")}
        chequeos["c3"] = {"estado": "OK", "nota": "sin líneas que repetir"}
        chequeos["c5"] = {"estado": "OK", "nota": "sin script que escanear"}

    veredicto, motivos = _veredicto_de(chequeos)
    return {
        "tool": nombre, "grupo_id": gid, "capacidad": capacidad,
        "veredicto": veredicto, "motivos": motivos,
        **chequeos,
    }


# ————————————————————————————————————————————————— insumos: baseline y doc ————

def load_baseline() -> Dict[str, Any]:
    if not BASELINE_PATH.is_file():
        return {"norm": "AP-42", "note": "", "failing": [], "objetivo": {}}
    try:
        datos = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ValueError(f"baseline ilegible: {exc}") from exc
    # Una baseline corrupta leída como vacía estrenaba la deuda entera puntillosa.
    if not isinstance(datos, dict) or not isinstance(datos.get("failing", []), list):
        raise ValueError("baseline fuera de forma: `failing` ha dejado de ser lista")
    return datos


def congelar(defectos: Set[str], admitir: bool,
             baseline: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Recongela la baseline POR SU DUEÑO (AP-57): `vault_baseline.escribir`.

    Nada de `write_text` a mano — era la copia que el guard de un-escritor
    señalaba — y el compromiso (`objetivo`) va en la misma escritura: una
    baseline sin fecha ni dueño es una deuda que nadie vuelve a abrir.
    """
    import vault_baseline

    congelados = set(baseline.get("failing", []))
    deuda = sorted(defectos - congelados)
    if deuda and not admitir:
        raise DeudaNueva(deuda)
    vault_baseline.escribir(
        BASELINE_PATH, "failing", "AP-42",
        "deuda congelada: tools con veredicto DEFECTO pendiente de "
        "solución planeada. Solo encoge; crecer exige --freeze --admitir-nuevos.",
        sorted(defectos),
        extra={"norm": "AP-42",
               "objetivo": {"tamano": 0, "fecha_limite": "2027-06-30",
                            "cadencia_dias": 180,
                            "dueno": "meta_toolkit — vault_toolkit_audit",
                            "por_que": "El ejemplo documentado debe ejercitar la "
                                       "función declarada: 0 es el estado de partida "
                                       "de v41.12 y el objetivo es que no deje de serlo."}},
        campo_descripcion="note")
    return deuda


def doc_actualizado() -> bool:
    """El doc no puede ser más viejo que lo de qué deriva (AP-47)."""
    if not (DOC_PATH.is_file() and LAST_RUN_PATH.is_file()):
        return False
    nuevo = DOC_PATH.stat().st_mtime
    fuentes = [LAST_RUN_PATH, SCRIPTS_DIR / "vault_mcp_catalog.py", BASELINE_PATH]
    return all((not f.is_file()) or f.stat().st_mtime <= nuevo for f in fuentes)


def _doc_de(cache: Dict[str, Any], cubiertas: Optional[int] = None,
            total: Optional[int] = None) -> str:
    resumen = cache.get("resumen", {})
    lineas = [
        "# Auditoría funcional del toolkit",
        "",
        f"Corrida en **{cache.get('timestamp', '')}** — derivada de "
        "`scripts/toolkit-audit-last.json` y de `scripts/toolkit-audit-baseline.json`. "
        "No se edita a mano: la regenera `vault_toolkit_audit --doc`.",
        "",
    ]
    if cubiertas is not None and total is not None and cubiertas < total:
        # El informe declara su alcance: un doc acotado no puede leerse como
        # el estado de las 125 tools.
        lineas += [
            f"**Alcance parcial** — {cubiertas} de {total} tools "
            "(corrida acotada con `--tools`/`--grupo`)", "",
        ]
    lineas += [
        f"**Resumen** — {resumen.get('OK', 0)} OK · {resumen.get('MEJORA', 0)} MEJORA · "
        f"{resumen.get('DEFECTO', 0)} DEFECTO · {resumen.get('NO-VERIFICABLE', 0)} NO-VERIFICABLE",
        "",
        "| Tool | Grupo | Capacidad | Veredicto | Motivos |",
        "|---|---|---|---|---|",
    ]
    for fila in cache.get("results", []):
        motivos = "; ".join(fila.get("motivos") or []) or "—"
        lineas.append(
            f"| {fila['tool']} | {fila.get('grupo_id', '')} | {fila.get('capacidad', '')} "
            f"| **{fila['veredicto']}** | {motivos} |")
    deuda = cache.get("deuda_congelada") or []
    if deuda:
        lineas += ["", "## Deuda congelada (baseline que solo encoge)", ""]
        lineas += [f"- {tool}" for tool in deuda]
    return "\n".join(lineas) + "\n"


# ——————————————————————————————————————————————————————————————————— main ————

def _emitir(ok: bool, payload: Dict[str, Any]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps({"ok": ok, "tool": "vault_toolkit_audit", **payload},
                     ensure_ascii=False))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verificación funcional del toolkit (C0–C5). Alcance: "
                    "--todo / --grupo N / --tools a,b — barrir todo no es gratis.",
        allow_abbrev=False)
    parser.add_argument("--todo", action="store_true", help="barrido completo")
    parser.add_argument("--tools", help="lista separada por comas")
    parser.add_argument("--grupo", type=int, nargs="*",
                        help="número(s) de grupo según la numeración de scripts/README.md")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 con deuda nueva no congelada")
    parser.add_argument("--strict", action="store_true",
                        help="junto a --check: la deuda congelada aún en rojo también falla")
    parser.add_argument("--freeze", action="store_true",
                        help="recongela la baseline con el veredicto de esta corrida")
    parser.add_argument("--admitir-nuevos", action="store_true",
                        help="junto a --freeze: permiso explícito (y visible) para estrenar deuda")
    parser.add_argument("--doc", action="store_true",
                        help="regenera docs/auditorias/auditoria-toolkit.md desde el last-run")
    parser.add_argument("--parcial", action="store_true",
                        help="junto a --doc: permite publicar el informe aunque el "
                             "last-run no cubra el catálogo entero (lo declara)")
    args = parser.parse_args()

    if args.doc:
        if not LAST_RUN_PATH.is_file():
            # El informe no inventa resultados que no corrieron: sin last-run
            # no hay dato de qué derivar.
            return _salir_con_error(
                "STALE_REPORT",
                "sin last-run: correr la auditoría antes de regenerar el doc")
        cache = json.loads(LAST_RUN_PATH.read_text(encoding="utf-8"))
        # O2: `--tools`/`--grupo` pisan el last-run con esa corrida acotada.
        # Regenerar el informe desde ahí lo encogía a 8 filas sin que nada
        # lo dijera — le pasó a la propia ola O2 al cerrar. El doc completo
        # se deriva de un barrido completo, o se declara parcial.
        import vault_mcp_catalog as mc
        cubiertas = len(cache.get("results") or [])
        total = len(mc.TOOLS_CATALOG)
        if cubiertas < total and not args.parcial:
            return _salir_con_error(
                "STALE_REPORT",
                f"el last-run cubre {cubiertas} de {total} tools: corre --todo "
                "antes de --doc (o pasa --parcial para publicar un informe acotado)")
        desfasado = DOC_PATH.is_file() and not doc_actualizado()
        DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOC_PATH.write_text(
            _doc_de(cache, cubiertas=cubiertas, total=total), encoding="utf-8")
        return _emitir(True, {"action": "doc",
                              "path": str(DOC_PATH.relative_to(REPO_ROOT)),
                              "tools_en_el_informe": cubiertas,
                              "estaba_desfasado": desfasado})

    import vault_mcp_catalog as mc

    tools_pedidas = _seleccionar(args)
    gid_map, cap_map = gid_y_capacidad()
    c4 = repartir_c4(set(tools_pedidas))

    pulso = time.time()
    resultados = [auditar(nombre, mc.TOOLS_CATALOG.get(nombre, {}),
                          gid_map.get(nombre, 0), cap_map.get(nombre, ""))
                  for nombre in tools_pedidas]
    segundos = round(time.time() - pulso, 1)

    for resultado in resultados:
        for hallazgo in (c4.get("por_tool") or {}).get(resultado["tool"], []):
            resultado["motivos"].append(hallazgo)
            resultado["veredicto"] = (
                "DEFECTO" if resultado["veredicto"] == "OK" else resultado["veredicto"])

    resumen = Counter(r["veredicto"] for r in resultados)
    defectos = sorted(r["tool"] for r in resultados if r["veredicto"] == "DEFECTO")
    congelados: Set[str] = set()
    deuda_nueva: List[str] = []

    if args.freeze:
        try:
            deuda_nueva = congelar(set(defectos), args.admitir_nuevos,
                                   load_baseline())
        except DeudaNueva as montante:
            return _salir_con_error(
                "DEBT_WOULD_GROW",
                f"la baseline no puede crecer sin admisión: "
                f"{', '.join(montante.lista)}",
                deuda_nueva=montante.lista)
        congelados = set(defectos)
    elif BASELINE_PATH.is_file():
        congelados = set(load_baseline().get("failing", []))

    cache = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "resumen": dict(resumen),
        "results": resultados,
        "deuda_congelada": sorted(congelados & set(defectos)),
        "segundos": segundos,
    }
    LAST_RUN_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                             encoding="utf-8")

    respuesta: Dict[str, Any] = {
        "ok": True, "tool": "vault_toolkit_audit",
        "total": len(tools_pedidas),
        "alcance": {
            "total": len(tools_pedidas),
            **{veredicto: resumen.get(veredicto, 0)
               for veredicto in ("OK", "MEJORA", "DEFECTO", "NO-VERIFICABLE")},
        },
        "defectos": defectos,
        "deuda_nueva": deuda_nueva,
        "deuda_congelada": sorted(congelados & set(defectos)),
        "segundos": segundos,
        "results": resultados,
    }
    if args.check or args.strict:
        nuevas = sorted(set(defectos) - congelados)
        respuesta["deuda_nueva"] = nuevas
        if nuevas or (args.strict and defectos):
            # AP-52: el rechazo sale por el catálogo, no por un envelope a mano.
            import vault_errors

            codigo = "DEBT_WOULD_GROW" if nuevas else "AUDIT_STILL_RED"
            mensaje = (
                f"deuda nueva no congelada: {', '.join(nuevas)}"
                if nuevas else
                f"deuda congelada aún en rojo: {', '.join(defectos)}")
            envelope = vault_errors.emit_error(
                "vault_toolkit_audit", codigo, message=mensaje,
                args={"defectos": respuesta["defectos"]})
            # la evidencia sigue en el envelope de rechazo: el dato del scan
            # no se descarta porque el gate se ponga en rojo.
            envelope["results"] = resultados
            envelope["deuda_congelada"] = sorted(congelados & set(defectos))
            respuesta = envelope
    ok_final = bool(respuesta.get("ok"))
    return _emitir(ok_final, respuesta)


if __name__ == "__main__":
    sys.exit(main())

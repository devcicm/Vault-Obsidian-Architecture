#!/usr/bin/env python3
"""vault_smoke — AP-42: ninguna tool se publica sin haberse ejecutado nunca.

El síntoma: 84 de 86 tools responden a `--help` y 31 aparecen nombradas en algún
test. Las demás nunca se ejecutan — ni en CI ni en la suite — y aun así se
publican por MCP como superficie disponible. `--help` solo demuestra que el
`argparse` se construye; no que el módulo importe sus dependencias, ni que la
tool emita el JSON que su contrato promete. AP-40 es la prueba de que esa
distancia se llena de defectos silenciosos: la mitad del catálogo publicaba
params que su propia CLI rechazaba, con un guard en verde encima.

Qué comprueba este smoke, deliberadamente poco:

  1. la tool arranca y termina dentro del timeout,
  2. su última línea de stdout es JSON,
  3. ese JSON tiene un campo `ok`.

Lo que **no** comprueba: que la invocación tenga éxito. Un `ok: false` bien
formado es un aprobado — el ejemplo del catálogo apunta a rutas que el sandbox
no tiene, y rechazarlas educadamente es exactamente el contrato. Lo que se
persigue es el fallo mudo: el traceback, el stdout vacío, el cuelgue.

La invocación no se escribe a mano: se toma del `example` del catálogo, que es
lo que la documentación le promete al usuario. Si el ejemplo documentado no
corre, el defecto es real aunque la tool funcione con otros argumentos.

Cada tool corre contra una **copia desechable** del vault de pruebas, así que
un ejemplo con escritura no contamina el sandbox ni a la tool siguiente.

    python scripts/vault_smoke.py --check      # corre el smoke y reporta
    python scripts/vault_smoke.py --strict     # exit 1 si la deuda CRECIÓ
    python scripts/vault_smoke.py --freeze     # recongela la baseline
    python scripts/vault_smoke.py --tool vault_write
"""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

# La configuración se lee del registro único, no con un default por punto
# de uso. Ver `vault_entorno.py`.
from vault_entorno import leer as _env

from vault_errors import wrap_main
from vault_mcp_catalog import TOOLS_CATALOG

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
BASELINE_PATH = SCRIPTS_DIR / "smoke-baseline.json"
SANDBOX = REPO_ROOT / "vault-sandbox"
SMOKE_TIMEOUT = _env("VAULT_SMOKE_TIMEOUT")


# Excepciones declaradas, no ocultas: una tool que por diseño no termina no
# tiene invocación de smoke posible. Se nombran aquí con su motivo para que la
# exención sea auditable — omitirlas del barrido en silencio sería el mismo
# fallo que la norma persigue.
SIN_SMOKE = {
    "vault_token_service": "servicio HTTP: no retorna por diseño",
}


def invocation(tool: str) -> Optional[List[str]]:
    """Primera línea del `example` del catálogo, como argv ejecutable."""
    entrada = TOOLS_CATALOG.get(tool) or {}
    script = entrada.get("script")
    if not script or not (SCRIPTS_DIR / script).is_file():
        return None
    for linea in (entrada.get("example") or "").splitlines():
        linea = linea.strip()
        if not linea.startswith("python "):
            continue
        try:
            partes = shlex.split(linea, posix=False)
        except ValueError:
            return None
        # `posix=False` conserva las comillas de los valores: hay que quitarlas
        # a mano, porque en POSIX el ejemplo con `\n` embebido se destroza.
        partes = [p[1:-1] if len(p) > 1 and p[0] == p[-1] == '"' else p for p in partes]
        return _con_json(script, [sys.executable, str(SCRIPTS_DIR / script)] + partes[2:])
    return [sys.executable, str(SCRIPTS_DIR / script), "--help"]


def _con_json(script: str, argv: List[str]) -> List[str]:
    """Una tool con `--json` habla en JSON solo si se lo piden.

    Su modo por defecto es texto para una persona, y eso es legítimo: lo que
    AP-42 mide es el contrato de máquina, que es el que consume el servidor MCP.
    """
    from vault_mcp_catalog import argparse_params

    if "--json" not in argv and "json" in argparse_params(script):
        return argv + ["--json"]
    return argv


def run_one(tool: str) -> Dict[str, Any]:
    """Ejecuta una tool contra una copia desechable del sandbox."""
    if tool in SIN_SMOKE:
        return {"tool": tool, "ok": True, "skipped": SIN_SMOKE[tool]}
    argv = invocation(tool)
    if argv is None:
        entrada = TOOLS_CATALOG.get(tool) or {}
        if entrada.get("runtime") == "node":
            # Implementada nativa en el servidor MCP. AP-42 mide el smoke de la
            # CLI Python; su equivalente aquí es que el .mjs la despache, y eso
            # lo comprueba test_source_hygiene, no este barrido.
            return {"tool": tool, "ok": True, "skipped": "runtime node (vault-mcp-server.mjs)"}
        if not entrada.get("script") or not (SCRIPTS_DIR / entrada["script"]).is_file():
            return {"tool": tool, "ok": True, "skipped": "sin script en el repo"}
        # El ejemplo existe pero no se deja convertir en argv (comillas sin
        # cerrar, típicamente). Es un fallo, no una exención: un ejemplo que no
        # se puede ejecutar tampoco lo puede copiar un usuario.
        return {"tool": tool, "ok": False, "problem": "el `example` no es una invocación válida",
                "detail": (entrada.get("example") or "").splitlines()[:1]}

    destino = Path(tempfile.mkdtemp(prefix="vault-smoke-"))
    vault = destino / "vault"
    try:
        if SANDBOX.is_dir():
            shutil.copytree(SANDBOX, vault)
        else:
            vault.mkdir(parents=True)
        env = dict(os.environ)
        env.update({
            "VAULT_ROOT": str(vault),
            "VAULT_AGENT": "vault-smoke",
            "PYTHONIOENCODING": "utf-8",
            "VAULT_VOICE": "0",  # el refuerzo AP-43 no es lo que se mide aquí
        })
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, env=env,
                                  encoding="utf-8", errors="replace",
                                  timeout=SMOKE_TIMEOUT, cwd=str(SCRIPTS_DIR))
        except subprocess.TimeoutExpired:
            return {"tool": tool, "ok": False, "problem": "timeout",
                    "detail": f"no terminó en {SMOKE_TIMEOUT}s"}
    finally:
        shutil.rmtree(destino, ignore_errors=True)

    salida = (proc.stdout or "").strip()
    if not salida:
        cola = (proc.stderr or "").strip().splitlines()[-1:] or ["(sin stderr)"]
        return {"tool": tool, "ok": False, "problem": "sin salida",
                "detail": cola[0][:300], "exit_code": proc.returncode}
    # Las tools emiten unas el JSON compacto en una línea y otras con indent=2:
    # se intenta el bloque completo antes de caer a la última línea.
    datos = None
    for candidato in (salida, salida.splitlines()[-1]):
        try:
            datos = json.loads(candidato)
            break
        except ValueError:
            continue
    if datos is None:
        return {"tool": tool, "ok": False, "problem": "la salida no es JSON",
                "detail": salida.splitlines()[-1][:300], "exit_code": proc.returncode}
    if not isinstance(datos, dict) or "ok" not in datos:
        return {"tool": tool, "ok": False, "problem": "JSON sin campo `ok`",
                "detail": str(sorted(datos)[:8]) if isinstance(datos, dict) else type(datos).__name__}
    # Los campos devueltos viajan con el resultado para que `--contract` pueda
    # contrastarlos sin volver a ejecutar las 91 tools.
    return {"tool": tool, "ok": True, "tool_ok": datos["ok"],
            "returned": sorted(datos), "exit_code": proc.returncode}


def _contrato_de(tool: str) -> set:
    """`declared_returns` del tool-spec, o conjunto vacío si no hay contrato."""
    try:
        import vault_io

        ruta = Path(vault_io.resolve_tool_spec())
        entradas = json.loads(ruta.read_text(encoding="utf-8")).get("tools", {})
    except Exception:
        return set()
    return set((entradas.get(tool) or {}).get("declared_returns", []))


#: Campos que aparecen solo cuando la tool falla. Su ausencia en una ejecución
#: correcta no es un incumplimiento del contrato.
_SOLO_EN_ERROR = {"error", "error_code", "message", "traceback", "recovery",
                  "severity", "category", "hint"}


def contract_gap(resultado: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """¿El envelope real cubre algo de lo que su contrato promete? (AP-37)

    El smoke comprobaba que la salida fuese un JSON con `ok`, que es
    literalmente la señal que AP-37 declara insuficiente: `ok: true` sin
    indicador de trabajo. 41 de las 91 tools del catálogo no aparecen en ningún
    test, así que para ellas ese `ok` era **toda** la verificación que existía.

    No se exige el contrato entero: `declared_returns` es la unión sobre todos
    los modos de la tool, y el smoke ejecuta un solo ejemplo, así que faltar
    campos de otro modo es normal. Lo que no es normal es no devolver
    **ninguno** — eso significa que el contrato publicado no describe a esta
    tool por el camino que se acaba de ejecutar, que es AP-42 con el envelope
    en la mano.
    """
    tool = resultado["tool"]
    if resultado.get("skipped") or "returned" not in resultado:
        return None
    declarados = _contrato_de(tool) - _SOLO_EN_ERROR
    if not declarados:
        return None
    devueltos = set(resultado["returned"])
    if declarados & devueltos:
        return None
    return {
        "tool": tool,
        "problem": "el envelope no cubre ningún campo de su contrato",
        "declared": sorted(declarados)[:10],
        "returned": sorted(devueltos)[:10],
    }


def load_baseline() -> List[str]:
    if not BASELINE_PATH.is_file():
        return []
    try:
        return list(json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("failing", []))
    except (OSError, ValueError):
        return []


def smoke(tools: Optional[List[str]] = None) -> Dict[str, Any]:
    objetivo = tools or sorted(TOOLS_CATALOG)
    resultados = [run_one(t) for t in objetivo]
    fallos = [r for r in resultados if not r["ok"]]
    huecos = [g for g in (contract_gap(r) for r in resultados) if g]
    baseline = load_baseline()
    nuevos = sorted(r["tool"] for r in fallos if r["tool"] not in baseline)
    saldados = sorted(t for t in baseline if t not in {r["tool"] for r in fallos})
    return {
        # Los huecos de contrato son puerta dura, no baseline: medidos sobre las
        # 91 tools salieron dos, y los dos eran arreglables el mismo día
        # (`vault_sdd_init` mezclaba informe humano y envelope en stdout;
        # `vault_change_log` declaraba solo el campo del modo de escritura). Una
        # baseline aquí solo serviría para congelar deuda que no existe.
        "ok": not nuevos and not huecos,
        "tool": "vault_smoke",
        "action": "check",
        "checked": len(resultados),
        "passing": len(resultados) - len(fallos),
        "failing": len(fallos),
        "baseline": len(baseline),
        "new_offenders": nuevos,
        "resolved": saldados,
        "failures": sorted(fallos, key=lambda r: r["tool"]),
        "contract_gaps": sorted(huecos, key=lambda g: g["tool"]),
        "contract_gaps_total": len(huecos),
        "hint": "La baseline solo puede encoger: tras saldar deuda, vault_smoke --freeze.",
    }


def freeze() -> Dict[str, Any]:
    r = smoke()
    fallando = sorted(f["tool"] for f in r["failures"])
    previa = load_baseline()
    if len(fallando) > len(previa) and BASELINE_PATH.is_file():
        return {"ok": False, "tool": "vault_smoke", "action": "freeze", "frozen": 0,
                "error": "la baseline no puede crecer",
                "detail": f"{len(previa)} -> {len(fallando)}; arregla {r['new_offenders']}"}
    BASELINE_PATH.write_text(
        json.dumps({
            "norm": "AP-42",
            "note": "Tools cuyo ejemplo documentado no emite un JSON con `ok`. "
                    "Esta lista solo puede encoger.",
            "failing": fallando,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"ok": True, "tool": "vault_smoke", "action": "freeze", "frozen": len(fallando),
            "path": str(BASELINE_PATH.relative_to(REPO_ROOT))}


def main() -> int:
    p = argparse.ArgumentParser(description="vault_smoke — AP-42: toda tool se ejecuta al menos una vez")
    p.add_argument("--check", action="store_true", help="Corre el smoke sobre el catálogo")
    p.add_argument("--strict", action="store_true", help="Exit 1 si la deuda creció")
    p.add_argument("--freeze", action="store_true", help="Recongela la baseline")
    p.add_argument("--tool", help="Ejecuta el smoke de una sola tool")
    args = p.parse_args()

    if args.freeze:
        r = freeze()
    elif args.tool:
        r = smoke([args.tool])
    else:
        r = smoke()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 1 if (args.strict and not r["ok"]) else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_smoke", timeout=3600))

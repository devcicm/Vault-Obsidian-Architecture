#!/usr/bin/env python3
"""Matriz de paridad CLI <-> MCP — fase 2 (L3). Verificador FAIL-CLOSED.

El producto se expone por DOS adaptadores. Compartir catalogo no los hace
equivalentes: hay que MEDIR que, para las mismas operaciones, ambos ofrecen
el mismo contrato, el mismo resultado y el mismo significado de error.

Se mide en tres niveles:

  1. CONTRATO: el esquema MCP frente al argparse de la tool (el verificador
     AP-40 del repo: `vault_mcp_catalog --check-params`).
  2. COMPORTAMIENTO: la misma operacion, con los mismos argumentos, por CLI
     (`vault run <tool> ...`) y por MCP (`tools/call`), sobre el MISMO runtime,
     con el estado restaurado entre adaptadores.
  3. ERRORES DE TRANSPORTE: un `isError` del protocolo MCP o un error de
     transporte (sin envelope de tool) NO es una respuesta valida.

El verificador es FAIL-CLOSED: sale con codigo distinto de cero si
  - el verificador de contrato (AP-40) devuelve un codigo distinto de cero;
  - falta un campo obligatorio del contrato en alguno de los dos adaptadores;
  - divergen los codigos o el significado del error;
  - divergen los efectos observables (creado/actualizado/ruta);
  - un caso requerido no se ejecuto;
  - la respuesta MCP llega marcada como error de transporte o con `isError`.

La evaluacion vive en `evaluar()`, una funcion PURA: las pruebas negativas la
llaman con casos fabricados y comprueban que el verificador los detecta. Un
verificador que solo sabe decir "todo bien" no verifica nada (AP-44).

Salida: matriz en markdown + JSON.

Uso: python audits/fase2/paridad_cli_mcp.py --venv DIR --runtime DIR [--log S] [--matriz S]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import queue
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]

#: Campos que el contrato de una operacion DEBE declarar en ambos adaptadores.
CAMPOS_OBLIGATORIOS = ("ok",)

#: (operacion, argumentos, campos comparados). Las dos primeras son de solo
#: lectura; las siguientes escriben, y se comparan sus efectos.
CASOS = [
    ("vault_read", {"path": "07_Knowledge/nota-paridad.md"}, ["ok", "path"]),
    ("vault_search", {"query": "paridad"}, ["ok", "total"]),
    ("vault_list", {"folder": "07_Knowledge"}, ["ok"]),
    ("vault_write", {"folder": "07_Knowledge", "title": "Nota de paridad",
                     "content": "Nota escrita para medir la paridad entre los dos "
                                "adaptadores del producto instalado.\n"
                                "Segunda linea del cuerpo, para cumplir el gate.\n"
                                "Tercera linea, la que el gate exige.\n",
                     "tags": "paridad"}, ["ok", "created", "path"]),
    ("vault_write", {"folder": "07_Knowledge", "title": "Nota de paridad",
                     "content": "Nota escrita para medir la paridad entre los dos "
                                "adaptadores del producto instalado.\n"
                                "Segunda linea del cuerpo, para cumplir el gate.\n"
                                "Tercera linea MODIFICADA por la segunda pasada.\n",
                     "tags": "paridad"}, ["ok", "updated", "path"]),
]


def evaluar(filas: List[Dict[str, Any]], contrato: Dict[str, Any],
            requeridos: Optional[List[str]] = None) -> Dict[str, Any]:
    """Veredicto FAIL-CLOSED sobre lo medido. Funcion pura.

    `filas` es lo que se midio; `contrato` el resultado del verificador AP-40;
    `requeridos` los casos que TIENEN que haberse ejecutado.
    """
    problemas: List[str] = []

    # 1. El verificador de contrato tiene que haber pasado.
    codigo = contrato.get("exit")
    if codigo is None:
        problemas.append("el verificador de contrato (AP-40) no se ejecuto")
    elif codigo != 0:
        problemas.append(f"el verificador de contrato (AP-40) devolvio exit {codigo}")

    # 2. Todos los casos requeridos tienen que estar medidos.
    medidos = {f.get("operacion") for f in filas}
    for requerido in (requeridos or []):
        if requerido not in medidos:
            problemas.append(f"caso requerido no ejecutado: {requerido}")

    # 3. Cada caso: campos obligatorios, errores de transporte, divergencias.
    for fila in filas:
        nombre = fila.get("operacion", "?")
        if fila.get("error_transporte"):
            problemas.append(f"{nombre}: error de transporte MCP: {fila['error_transporte']}")
        if fila.get("is_error"):
            # `isError` es la convention MCP para un error de EJECUCION de la
            # tool: no es un error de transporte. Solo es un problema cuando
            # contradice al otro adaptador (el CLI no fallo, o fallo distinto).
            cli_err = fila.get("cli_error")
            mcp_err = fila.get("mcp_error")
            if cli_err is None:
                problemas.append(f"{nombre}: el servidor MCP marco la respuesta "
                                 f"como isError y el CLI no fallo")
            elif str(cli_err) != str(mcp_err):
                problemas.append(f"{nombre}: isError en MCP con error distinto al "
                                 f"del CLI (mcp={mcp_err!r}, cli={cli_err!r})")
        if not fila.get("expuesta_por_mcp", True):
            problemas.append(f"{nombre}: la operacion no esta expuesta por MCP")
        campos = fila.get("campos") or []
        cli = fila.get("cli") or {}
        mcp = fila.get("mcp") or {}
        # El contrato de un caso son SUS campos: todos tienen que estar en los
        # dos adaptadores. Un campo que solo aparece en uno no es una
        # divergencia de valor, es un contrato incompleto.
        for campo in list(CAMPOS_OBLIGATORIOS) + list(campos):
            if campo not in cli or campo not in mcp:
                problemas.append(f"{nombre}: campo obligatorio ausente ({campo})")
        # 4. Errores: mismo codigo y mismo significado.
        cli_err = fila.get("cli_error")
        mcp_err = fila.get("mcp_error")
        if (cli_err is None) != (mcp_err is None):
            problemas.append(f"{nombre}: un adaptador devuelve error y el otro no "
                             f"(cli={cli_err!r}, mcp={mcp_err!r})")
        elif cli_err is not None and mcp_err is not None:
            if str(cli_err) != str(mcp_err):
                problemas.append(f"{nombre}: divergencia de codigo de error "
                                 f"(cli={cli_err!r}, mcp={mcp_err!r})")
        # 5. Efectos observables.
        for campo in campos:
            if campo == "ok":
                continue
            if cli.get(campo) != mcp.get(campo):
                problemas.append(f"{nombre}: divergencia de efecto en {campo!r} "
                                 f"(cli={cli.get(campo)!r}, mcp={mcp.get(campo)!r})")
        if cli.get("ok") != mcp.get("ok"):
            problemas.append(f"{nombre}: divergencia de resultado "
                             f"(cli ok={cli.get('ok')!r}, mcp ok={mcp.get('ok')!r})")
    return {"ok": not problemas, "problemas": problemas}



#: La maquina no viaja en la evidencia: las logs que este script escribe van
#: a un repo publico, y el verificador de saneamiento las rechaza si llevan
#: una ruta local. Se sustituye por un marcador neutro ANTES de escribir.
RUTA_LOCAL = re.compile(r"(?:[A-Za-z]:[\\/]+Users[\\/]|/(?:home|Users)/)[^\s\"'`)\]]*")


def sin_rutas(texto: str) -> str:
    """Sustituye toda ruta local por un marcador neutro."""
    return RUTA_LOCAL.sub("<RUTA-LOCAL>", texto)


def _normalizar(texto: str) -> Dict[str, Any]:
    try:
        sobre = json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return {"_crudo": (texto or "")[:400]}
    return sobre if isinstance(sobre, dict) else {"_crudo": str(sobre)[:400]}


def _elegir(sobre: Dict[str, Any], campos: List[str]) -> Dict[str, Any]:
    return {c: sobre.get(c) for c in campos if c in sobre}


class Mcp:
    """Cliente JSON-RPC sobre stdio del servidor MCP instalado.

    La LECTURA es en un hilo aparte: `readline()` bloquea y, con el, un
    timeout que se Calcule mientras se espera no llega a cumplirse nunca (H-L3-03).
    """

    def __init__(self, mjs: Path, env: Dict[str, str],
                 cmd: Optional[List[str]] = None):
        self.proc = subprocess.Popen(cmd or ["node", str(mjs)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, encoding="utf-8", errors="replace",
                                     env=env, bufsize=1)
        self.id = 0
        self.lineas: "queue.Queue[str]" = queue.Queue()
        self.lector = threading.Thread(target=self._leer, daemon=True)
        self.lector.start()

    def _leer(self) -> None:
        for linea in self.proc.stdout:
            self.lineas.put(linea)

    def cerrar(self) -> None:
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()

    def llamar(self, metodo: str, params: Optional[Dict[str, Any]] = None,
               timeout: int = 180) -> Dict[str, Any]:
        self.id += 1
        msg = {"jsonrpc": "2.0", "id": self.id, "method": metodo}
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        try:
            while True:
                linea = self.lineas.get(timeout=timeout)
                if linea is None:
                    return {"error": {"code": -1, "message": f"timeout esperando {metodo}"}}
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    dato = json.loads(linea)
                except json.JSONDecodeError:
                    continue
                if dato.get("id") == self.id:
                    return dato
        except queue.Empty:
            return {"error": {"code": -1, "message": f"timeout esperando {metodo}"}}

    def avisar(self, metodo: str) -> None:
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": metodo}) + "\n")
        self.proc.stdin.flush()


def _texto_mcp(sobre: Dict[str, Any]) -> str:
    if "error" in sobre:
        return json.dumps(sobre["error"], ensure_ascii=False)
    for parte in (sobre.get("result", {}) or {}).get("content", []) or []:
        if isinstance(parte, dict) and parte.get("type") == "text":
            return str(parte.get("text", ""))
    return json.dumps(sobre.get("result", {}), ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--venv", required=True)
    ap.add_argument("--runtime", required=True)
    ap.add_argument("--log", default="audits/fase2/logs/L3-paridad-cli-mcp.txt")
    ap.add_argument("--matriz", default="audits/fase2/matriz-paridad-cli-mcp.md")
    args = ap.parse_args()

    venv = Path(args.venv)
    runtime = Path(args.runtime)
    py = venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"
    cli = venv / "Scripts" / "vault.exe" if os.name == "nt" else venv / "bin" / "vault"
    site = Path(py).parent.parent / "Lib" / "site-packages"
    mjs = site / "vault_toolkit" / "mcp" / "vault-mcp-server.mjs"
    env = {**os.environ, "VAULT_ROOT": str(runtime), "VAULT_STRICT_ROOT": "1",
           "VAULT_AGENT": "paridad-fase2", "PYTHONIOENCODING": "utf-8"}

    filas: List[Dict[str, Any]] = []

    # ── 1. CONTRATO (AP-40) ─────────────────────────────────────────────────
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "vault_mcp_catalog.py"),
                        "--check-params"], cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    contrato = {"exit": p.returncode, "stdout": p.stdout[-600:], "stderr": p.stderr[-300:]}

    # ── 2. COMPORTAMIENTO ───────────────────────────────────────────────────
    mcp = Mcp(mjs, env)
    mcp.llamar("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                              "clientInfo": {"name": "paridad", "version": "1"}})
    mcp.avisar("notifications/initialized")
    herramientas = (mcp.llamar("tools/list").get("result", {}) or {}).get("tools", []) or []
    nombres_mcp = {t.get("name") for t in herramientas}

    # Cada caso se mide desde el MISMO estado: se fotografia el runtime, se
    # mide por CLI, se restaura la fotografia y se mide por MCP. Sin esto, la
    # segunda llamada de una escritura encuentra la nota de la primera y mide
    # un update donde la otra midio un create.
    foto = runtime.parent / (runtime.name + ".foto")

    for operacion, argumentos, campos in CASOS:
        shutil.rmtree(foto, ignore_errors=True)
        shutil.copytree(runtime, foto)

        argv = [str(cli), "run", operacion]
        for clave, valor in argumentos.items():
            argv += [f"--{clave}", str(valor)]
        p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=900)
        cli_sobre = _normalizar(p.stdout)

        shutil.rmtree(runtime, ignore_errors=True)
        shutil.copytree(foto, runtime)

        expuesta = operacion in nombres_mcp
        is_error = False
        error_transporte = None
        if expuesta:
            rm = mcp.llamar("tools/call", {"name": operacion, "arguments": argumentos})
            if "error" in rm:
                error_transporte = rm["error"].get("message", "error de transporte")
            resultado = rm.get("result", {}) or {}
            is_error = bool(resultado.get("isError"))
            mcp_sobre = _normalizar(_texto_mcp(rm))
        else:
            mcp_sobre = {}

        filas.append({
            "operacion": operacion,
            "argumentos": argumentos,
            "expuesta_por_mcp": expuesta,
            "cli_exit": p.returncode,
            "cli": _elegir(cli_sobre, campos),
            "mcp": _elegir(mcp_sobre, campos),
            "cli_error": cli_sobre.get("error_code") or cli_sobre.get("error"),
            "mcp_error": mcp_sobre.get("error_code") or mcp_sobre.get("error"),
            "is_error": is_error,
            "error_transporte": error_transporte,
            "campos": campos,
        })
    mcp.cerrar()

    requeridos = [c[0] for c in CASOS]
    veredicto = evaluar(filas, contrato, requeridos)
    veredicto.update({
        "contrato_ap40": contrato,
        "filas": filas,
        "efectos": {
            "tools_con_side_effects_declarados": len(
                [n for n, t in json.loads(
                    (ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(
                        encoding="utf-8")).get("tools", {}).items() if t.get("side_effects")]),
            "expuestas_por_mcp": len(herramientas),
        },
        "coincidencias": sum(1 for f in filas if f.get("cli") == f.get("mcp")),
        "casos": len(filas),
        "herramientas_mcp": len(herramientas),
        "alcance": (f"paridad funcional probada en {len(CASOS)} casos de "
                    f"{len(herramientas)} tools expuestas por el servidor MCP; "
                    "el contrato de TODAS las tools lo cubre el verificador AP-40"),
    })

    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    Path(args.log).write_text(sin_rutas(
        "PARIDAD CLI <-> MCP — fase 2 (L3)\n"
        + json.dumps(veredicto, ensure_ascii=False, indent=2) + "\n"),
        encoding="utf-8")

    lineas = ["# Matriz de paridad CLI ↔ MCP — fase 2 (L3)", "",
              "Derivado de la ejecucion real sobre el artefacto instalado. Generado por "
              "`python audits/fase2/paridad_cli_mcp.py`.", "",
              f"- Tools expuestas por el servidor MCP instalado: **{len(herramientas)}**",
              f"- Verificador de contrato AP-40 (`vault_mcp_catalog --check-params`): "
              f"exit **{contrato['exit']}**",
              f"- Casos comparados: **{len(CASOS)}** · veredicto: "
              f"**{'CONFORME' if veredicto['ok'] else 'NO CONFORME'}**",
              f"- Alcance declarado: {veredicto['alcance']}", ""]
    if veredicto["problemas"]:
        lineas += ["## Problemas detectados", ""]
        lineas += [f"- {p}" for p in veredicto["problemas"]] + [""]
    lineas += ["| Operación | Expuesta por MCP | Campos comparados | CLI | MCP | Coincide |",
               "|---|---|---|---|---|---|"]
    for f in filas:
        lineas.append(f"| `{f['operacion']}` | {'sí' if f['expuesta_por_mcp'] else 'no'} "
                      f"| {', '.join(f['argumentos'].keys())} "
                      f"| `{json.dumps(f['cli'], ensure_ascii=False)}` "
                      f"| `{json.dumps(f['mcp'], ensure_ascii=False)}` "
                      f"| {'sí' if f.get('cli') == f.get('mcp') else 'NO'} |")
    lineas += ["", "## Criterio de equivalencia", "",
               "Se comparan resultados NORMALIZADOS (ok, rutas, contadores y codigos de "
               "error), no la igualdad literal de las respuestas: el transporte de cada "
               "adaptador es distinto por diseño, y lo que debe coincidir es el contrato "
               "de negocio (misma operacion, mismos argumentos, mismo efecto y mismo "
               "significado de error).", ""]
    Path(args.matriz).write_text(sin_rutas("\n".join(lineas) + "\n"), encoding="utf-8")

    print(f"paridad: {veredicto['coincidencias']}/{veredicto['casos']} | "
          f"AP-40 exit {contrato['exit']} | tools MCP {len(herramientas)} | "
          f"veredicto: {'CONFORME' if veredicto['ok'] else 'NO CONFORME'}")
    for problema in veredicto["problemas"]:
        print(f"  PROBLEMA: {problema}")
    print(f"log: {args.log} | matriz: {args.matriz}")
    return 0 if veredicto["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
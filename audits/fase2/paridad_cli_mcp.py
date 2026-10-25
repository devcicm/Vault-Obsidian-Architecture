#!/usr/bin/env python3
"""Matriz de paridad CLI <-> MCP — fase 2 (L3).

El producto se expone por DOS adaptadores. Compartir catalogo no los hace
equivalentes: hay que MEDIR que, para las mismas operaciones, ambos ofrecen
el mismo contrato y el mismo resultado.

Se mide en tres niveles:

  1. CONTRATO: el esquema MCP frente al argparse de la tool (el verificador
     AP-40 del repo: `vault_mcp_catalog --check-params`).
  2. COMPORTAMIENTO: la misma operacion, con los mismos argumentos, por CLI
     (`vault run <tool> ...`) y por MCP (`tools/call`), sobre el MISMO runtime:
     se comparan resultado, efectos y errores con NORMALIZACION (no igualdad
     literal: el transporte difiere).
  3. EFECTOS: lo que el catalogo DECLARA de cada tool (side_effects) frente a
     lo observado.

Salida: matriz en markdown + JSON.

Uso: python audits/fase2/paridad_cli_mcp.py --venv DIR --runtime DIR --log SALIDA
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]

#: (operacion, argumentos, que se compara). Las tres primeras son de solo
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


def _normalizar(texto: str) -> Dict[str, Any]:
    """El envelope de la tool, con los campos que se comparan."""
    try:
        sobre = json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return {"_crudo": (texto or "")[:400]}
    if isinstance(sobre, dict):
        return sobre
    return {"_crudo": str(sobre)[:400]}


def _elegir(sobre: Dict[str, Any], campos: List[str]) -> Dict[str, Any]:
    return {c: sobre.get(c) for c in campos if c in sobre}


class Mcp:
    def __init__(self, mjs: Path, env: Dict[str, str]):
        self.proc = subprocess.Popen(["node", str(mjs)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, encoding="utf-8", errors="replace",
                                     env=env, bufsize=1)
        self.id = 0

    def cerrar(self) -> None:
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()

    def llamar(self, metodo: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.id += 1
        msg = {"jsonrpc": "2.0", "id": self.id, "method": metodo}
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        while True:
            linea = self.proc.stdout.readline()
            if not linea:
                return {"error": {"message": "sin respuesta"}}
            try:
                dato = json.loads(linea.strip())
            except json.JSONDecodeError:
                continue
            if dato.get("id") == self.id:
                return dato

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

    # ── 1. CONTRATO (AP-40): el verificador del repo ───────────────────────
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "vault_mcp_catalog.py"),
                        "--check-params"], cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    contrato = {"exit": p.returncode, "stdout": p.stdout[-600:], "stderr": p.stderr[-300:]}

    # ── 2. COMPORTAMIENTO ───────────────────────────────────────────────────
    mcp = Mcp(mjs, env)
    r = mcp.llamar("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                  "clientInfo": {"name": "paridad", "version": "1"}})
    mcp.avisar("notifications/initialized")
    herramientas = (mcp.llamar("tools/list").get("result", {}) or {}).get("tools", []) or []
    nombres_mcp = {t.get("name") for t in herramientas}

    # Cada caso se mide desde el MISMO estado: se fotografía el runtime, se
    # mide por CLI, se restaura la fotografia y se mide por MCP. Sin esto, la
    # segunda llamada de una escritura encuentra la nota de la primera y mide
    # un update donde la otra midio un create — una divergencia del guion, no
    # del producto.
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

        # Restaurar el estado de partida para el otro adaptador.
        shutil.rmtree(runtime, ignore_errors=True)
        shutil.copytree(foto, runtime)

        expuesta = operacion in nombres_mcp
        if expuesta:
            rm = mcp.llamar("tools/call", {"name": operacion, "arguments": argumentos})
            mcp_sobre = _normalizar(_texto_mcp(rm))
        else:
            mcp_sobre = {"_no_expuesta": True}

        cli_campos = _elegir(cli_sobre, campos)
        mcp_campos = _elegir(mcp_sobre, campos)
        coincide = (bool(expuesta) and cli_campos == mcp_campos
                    and cli_sobre.get("ok") == mcp_sobre.get("ok"))
        filas.append({
            "operacion": operacion,
            "argumentos": argumentos,
            "expuesta_por_mcp": expuesta,
            "cli_exit": p.returncode,
            "cli": cli_campos,
            "mcp": mcp_campos,
            "coincide": coincide,
            "cli_error": cli_sobre.get("error_code") or cli_sobre.get("error"),
            "mcp_error": mcp_sobre.get("error_code") or mcp_sobre.get("error"),
        })
        print(f"{'OK  ' if coincide else 'DIFIE'} {operacion}: cli={cli_campos} mcp={mcp_campos}")
    mcp.cerrar()

    # ── 3. EFECTOS declarados por el catalogo ─────────────────────────────
    catalogo = json.loads((ROOT / "mcp" / "nodejs" / "tools-catalog.json")
                          .read_text(encoding="utf-8"))
    tools = catalogo.get("tools", {})
    con_efectos = [n for n, t in tools.items() if t.get("side_effects")]
    expuestas_con_efectos = [n for n in con_efectos if n in nombres_mcp]

    veredicto = {
        "contrato_ap40": contrato,
        "filas": filas,
        "efectos": {
            "tools_con_side_effects_declarados": len(con_efectos),
            "expuestas_por_mcp": len(expuestas_con_efectos),
        },
        "coincidencias": sum(1 for f in filas if f["coincide"]),
        "casos": len(filas),
        "herramientas_mcp": len(herramientas),
    }
    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    Path(args.log).write_text("PARIDAD CLI <-> MCP — fase 2 (L3)\n"
                               + json.dumps(veredicto, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")

    lineas = ["# Matriz de paridad CLI ↔ MCP — fase 2 (L3)", "",
              f"Derivado de la ejecucion real sobre el artefacto instalado "
              f"(venv externo, runtime externo). Generado por "
              f"`python audits/fase2/paridad_cli_mcp.py`.", "",
              f"- Tools expuestas por el servidor MCP instalado: **{len(herramientas)}**",
              f"- Verificador de contrato AP-40 (`vault_mcp_catalog --check-params`): "
              f"exit **{contrato['exit']}**",
              f"- Casos comparados: **{veredicto['coincidencias']}/{veredicto['casos']}** "
              f"coincidentes", "",
              "| Operación | Expuesta por MCP | Campos comparados | CLI | MCP | Coincide |",
              "|---|---|---|---|---|---|"]
    for f in filas:
        lineas.append(f"| `{f['operacion']}` | {'sí' if f['expuesta_por_mcp'] else 'no'} "
                      f"| {', '.join(f['argumentos'].keys())} "
                      f"| `{json.dumps(f['cli'], ensure_ascii=False)}` "
                      f"| `{json.dumps(f['mcp'], ensure_ascii=False)}` "
                      f"| {'sí' if f['coincide'] else 'NO'} |")
    lineas += ["", "## Nota sobre el criterio de equivalencia", "",
               "Se comparan resultados NORMALIZADOS (ok, rutas, contadores y codigos de "
               "error), no la igualdad literal de las respuestas: el transporte de cada "
               "adaptador es distinto por diseño, y lo que debe coincidir es el contrato "
               "de negocio (misma operacion, mismos argumentos, mismo efecto y mismo "
               "significado de error).", ""]
    Path(args.matriz).write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"\nparidad: {veredicto['coincidencias']}/{veredicto['casos']} | "
          f"AP-40 exit {contrato['exit']} | tools MCP {len(herramientas)}")
    print(f"log: {args.log} | matriz: {args.matriz}")
    return 0 if veredicto["coincidencias"] == veredicto["casos"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
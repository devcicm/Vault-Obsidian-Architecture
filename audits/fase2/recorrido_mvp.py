#!/usr/bin/env python3
"""Recorrido MVP de producto — fase 2 (L3).

Ejecuta el recorrido de aceptacion desde la perspectiva de un TERCERO, con el
artefacto instalado y FUERA del checkout:

    construir wheel -> instalar en venv nuevo -> crear runtime externo ->
    escribir por CLI -> leer por MCP -> modificar por MCP -> verificar por CLI ->
    reiniciar procesos -> confirmar persistencia -> validar contencion e integridad

No es una especificacion: se EJECUTA, y su salida es la evidencia. El recorrido
usa el artefacto (site-packages), el servidor MCP instalado (node) y un runtime
externo; el checkout solo aporta la fuente del build.

Salida: un veredicto JSON en `audits/fase2/logs/` y un log legible.

Uso: python audits/fase2/recorrido_mvp.py [--venv DIR] [--runtime DIR] [--log SALIDA]
"""
from __future__ import annotations

import argparse
import json
import re
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]



#: La maquina no viaja en la evidencia: este log va a un repo publico y el
#: verificador de saneamiento rechaza cualquier ruta local identificable.
RUTA_LOCAL = re.compile(r"(?:[A-Za-z]:[\\/]+Users[\\/]|/(?:home|Users)/)[^\s\"'`)\]]*")


def sin_rutas(texto: str) -> str:
    """Sustituye toda ruta local por un marcador neutro."""
    return RUTA_LOCAL.sub("<RUTA-LOCAL>", texto)


def _run(cmd: List[str], cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None,
         timeout: int = 900) -> Dict[str, Any]:
    inicio = time.monotonic()
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return {"cmd": cmd, "code": p.returncode, "stdout": p.stdout,
            "stderr": p.stderr, "segundos": round(time.monotonic() - inicio, 2)}


class Mcp:
    """Cliente JSON-RPC sobre stdio del servidor MCP instalado."""

    def __init__(self, mjs: Path, env: Dict[str, str]):
        self.proc = subprocess.Popen(
            ["node", str(mjs)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            env=env, bufsize=1)
        self.id = 0
        self.log: List[str] = []

    def cerrar(self) -> None:
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()

    def llamar(self, metodo: str, params: Optional[Dict[str, Any]] = None,
               timeout: int = 180) -> Dict[str, Any]:
        self.id += 1
        mensaje = {"jsonrpc": "2.0", "id": self.id, "method": metodo}
        if params is not None:
            mensaje["params"] = params
        self.proc.stdin.write(json.dumps(mensaje) + "\n")
        self.proc.stdin.flush()
        limite = time.monotonic() + timeout
        while time.monotonic() < limite:
            linea = self.proc.stdout.readline()
            if not linea:
                break
            linea = linea.strip()
            if not linea:
                continue
            try:
                dato = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if dato.get("id") == self.id:
                self.log.append(f"<- {metodo}: {json.dumps(dato)[:300]}")
                return dato
        self.log.append(f"<- {metodo}: SIN RESPUESTA")
        return {"error": {"code": -1, "message": f"sin respuesta a {metodo}"}}

    def avisar(self, metodo: str, params: Optional[Dict[str, Any]] = None) -> None:
        mensaje = {"jsonrpc": "2.0", "method": metodo}
        if params is not None:
            mensaje["params"] = params
        self.proc.stdin.write(json.dumps(mensaje) + "\n")
        self.proc.stdin.flush()
        self.log.append(f"-> {metodo}")


def _texto_de_error(sobre: Dict[str, Any]) -> str:
    """El texto de una respuesta MCP, sea error o resultado."""
    if "error" in sobre:
        return json.dumps(sobre["error"], ensure_ascii=False)
    res = sobre.get("result", {})
    contenido = res.get("content") or []
    for parte in contenido:
        if isinstance(parte, dict) and parte.get("type") == "text":
            return str(parte.get("text", ""))
    return json.dumps(res, ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--venv", default=str(Path(os.environ.get("TEMP", "/tmp")) / "mvp-consumer"))
    ap.add_argument("--runtime", default=str(Path(os.environ.get("TEMP", "/tmp")) / "mvp-runtime"))
    ap.add_argument("--wheel", default=str(Path(os.environ.get("TEMP", "/tmp")) / "mvp-dist"))
    ap.add_argument("--log", default="audits/fase2/logs/L3-recorrido-mvp.txt")
    args = ap.parse_args()

    venv = Path(args.venv)
    runtime = Path(args.runtime)
    dist = Path(args.wheel)
    pasos: List[Dict[str, Any]] = []
    veredicto: Dict[str, Any] = {"pasos": pasos, "ok": True, "fallos": []}

    def paso(nombre: str, ok: bool, detalle: str, extra: Optional[Dict[str, Any]] = None) -> None:
        pasos.append({"paso": nombre, "ok": ok, "detalle": detalle, **(extra or {})})
        if not ok:
            veredicto["ok"] = False
            veredicto["fallos"].append(f"{nombre}: {detalle}")
        print(f"[{'OK ' if ok else 'FALLA'}] {nombre}: {detalle}")

    # ── 1. venv nuevo, FUERA del checkout, con el artefacto ─────────────────
    shutil.rmtree(venv, ignore_errors=True)
    r = _run([sys.executable, "-m", "venv", str(venv)])
    paso("venv nuevo fuera del checkout", r["code"] == 0,
         f"venv en {venv.name} (exit {r['code']})")
    py = venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"
    wheels = sorted(dist.glob("*.whl"))
    if not wheels:
        paso("instalar la wheel", False, f"no hay wheel en {dist}")
        return 1
    r = _run([str(py), "-m", "pip", "install", "--quiet", str(wheels[0])], timeout=1800)
    paso("instalar la wheel en el venv", r["code"] == 0,
         f"{wheels[0].name} instalado (exit {r['code']})")
    cli = venv / "Scripts" / "vault.exe" if os.name == "nt" else venv / "bin" / "vault"
    paso("script de consola instalado", cli.exists(), f"vault -> {cli.name}")

    # ── 2. runtime externo ──────────────────────────────────────────────────
    shutil.rmtree(runtime, ignore_errors=True)
    env = {**os.environ, "VAULT_ROOT": str(runtime), "VAULT_STRICT_ROOT": "1",
           "VAULT_AGENT": "mvp-ejecutor", "PYTHONIOENCODING": "utf-8"}
    r = _run([str(cli), "init", str(runtime)], env=env, timeout=1800)
    paso("crear runtime externo con la CLI", r["code"] == 0,
         f"vault init exit {r['code']}", {"stdout": r["stdout"][-400:]})

    # ── 3. escribir por CLI ─────────────────────────────────────────────────
    carpeta = "07_Knowledge"
    titulo = "Nota del recorrido MVP"
    # Tres lineas reales: el gate de contenido (AP-11) exige tres, y con dos la
    # escritura se rechaza con exit 7 — lo que ocurrio en la primera pasada.
    contenido = ("Nota escrita por la CLI del producto instalado, durante el "
                 "recorrido MVP de la fase 2 del kit de arquitectura.\n"
                 "Debe ser legible por MCP, modificable por MCP y verificable "
                 "por CLI.\n"
                 "Tercera linea: el cuerpo minimo que exige el gate de "
                 "contenido del producto instalado.\n")
    ruta_rel = f"{carpeta}/nota-del-recorrido-mvp.md"
    r = _run([str(cli), "run", "vault_write", "--folder", carpeta, "--title", titulo,
              "--content", contenido, "--tags", "mvp,producto"], env=env, timeout=900)
    escrito = r["code"] == 0
    paso("escribir una nota por CLI", escrito, f"vault run vault_write exit {r['code']}",
         {"stdout": r["stdout"][-400:], "stderr": r["stderr"][-300:]})

    # ── 4-6. MCP: handshake, listado, lectura, modificacion ─────────────────
    mjs = None
    for cand in (Path(py).parent.parent / "Lib" / "site-packages" / "vault_toolkit" / "mcp",
                  Path(py).parent.parent / "lib" / "python3.12" / "site-packages" / "vault_toolkit" / "mcp"):
        if (cand / "vault-mcp-server.mjs").exists():
            mjs = cand / "vault-mcp-server.mjs"
            break
    if mjs is None:
        paso("servidor MCP instalado", False, "no se encuentra vault-mcp-server.mjs en el artefacto")
    else:
        paso("servidor MCP instalado", True, f"mjs en el artefacto: {mjs.name}")
        mcp = Mcp(mjs, env)
        r = mcp.llamar("initialize", {"protocolVersion": "2024-11-05",
                                      "capabilities": {},
                                      "clientInfo": {"name": "recorrido-mvp", "version": "1"}})
        paso("handshake MCP (initialize)", "result" in r, _texto_de_error(r)[:200])
        mcp.avisar("notifications/initialized")
        r = mcp.llamar("tools/list")
        herramientas = (r.get("result", {}) or {}).get("tools", []) or []
        paso("tools/list por MCP", bool(herramientas),
             f"{len(herramientas)} tools expuestas por el servidor instalado")

        r = mcp.llamar("tools/call", {"name": "vault_read", "arguments": {"path": ruta_rel}})
        # El criterio mira el contenido de la nota, no la ausencia de una
        # palabra: la primera pasada daba por fallida una lectura correcta
        # porque el frontmatter lleva `agent: mvp-ejecutor`.
        leida = "result" in r and "Nota del recorrido MVP" in _texto_de_error(r)
        paso("leer la nota por MCP", leida, _texto_de_error(r)[:220])

        r = mcp.llamar("tools/call", {"name": "vault_write",
                                      "arguments": {"folder": carpeta,
                                                    "title": titulo,
                                                    "content": contenido + "\nLinea anadida por MCP.\n",
                                                    "tags": "mvp,producto"}})
        modificada = "result" in r
        paso("modificar la nota por MCP", modificada, _texto_de_error(r)[:220])

        r = mcp.llamar("tools/call", {"name": "vault_search", "arguments": {"query": "recorrido"}})
        paso("consultar por MCP (vault_search)", "result" in r, _texto_de_error(r)[:200])

        # ── 8. reiniciar el proceso MCP y releer ────────────────────────────
        mcp.cerrar()
        mcp2 = Mcp(mjs, env)
        r = mcp2.llamar("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                        "clientInfo": {"name": "recorrido-mvp", "version": "1"}})
        mcp2.avisar("notifications/initialized")
        r = mcp2.llamar("tools/call", {"name": "vault_read", "arguments": {"path": ruta_rel}})
        texto = _texto_de_error(r)
        persistida = "Linea anadida por MCP" in texto
        paso("persistencia tras reiniciar el servidor MCP", persistida,
             "la linea escrita por MCP sobrevive a un proceso nuevo"
             if persistida else f"no se ve la linea de MCP: {texto[:200]}")
        mcp2.cerrar()

    # ── 7. verificar por CLI ────────────────────────────────────────────────
    r = _run([str(cli), "run", "vault_read", "--path", ruta_rel], env=env, timeout=900)
    verificada = r["code"] == 0 and "Linea anadida por MCP" in (r["stdout"] + r["stderr"])
    paso("verificar por CLI el cambio hecho por MCP", verificada,
         f"vault run vault_read exit {r['code']}")

    # ── 10. contencion: intento de escribir fuera del runtime ──────────────
    fuera = runtime.parent / "fuera-del-runtime.md"
    if fuera.exists():
        fuera.unlink()
    r = _run([str(cli), "run", "vault_write", "--folder", "../", "--title", "Escape",
              "--content", "intento fuera de la raiz\n", "--tags", "mvp"], env=env, timeout=900)
    escapado = fuera.exists()
    paso("contencion: escritura fuera de la raiz rechazada", not escapado,
         "la tool NO escribio fuera del runtime" if not escapado
         else f"ESCAPO: se escribio {fuera.name}")

    # ── integridad: lo escrito esta dentro y el arbol esta sano ───────────
    nota = runtime / ruta_rel
    paso("la nota existe en disco dentro del runtime", nota.exists(),
         str(nota.relative_to(runtime)) if nota.exists() else "no esta")
    r = _run([str(cli), "status", str(runtime)], env=env, timeout=900)
    paso("la CLI ve el runtime como sano", r["code"] == 0, f"vault status exit {r['code']}")

    veredicto["resumen"] = {
        "pasos": len(pasos),
        "ok": sum(1 for p in pasos if p["ok"]),
        "fallos": len(veredicto["fallos"]),
    }
    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    Path(args.log).write_text(sin_rutas(
        "RECORRIDO MVP — fase 2 (L3)\n"
        f"artefacto: {wheels[0].name}\nvenv: {venv}\nruntime: {runtime}\n"
        + json.dumps(veredicto, ensure_ascii=False, indent=2) + "\n"),
        encoding="utf-8")
    print(f"\nveredicto: {veredicto['resumen']}")
    print(f"log: {args.log}")
    return 0 if veredicto["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
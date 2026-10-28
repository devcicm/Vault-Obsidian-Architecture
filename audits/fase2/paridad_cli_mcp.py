#!/usr/bin/env python3
"""Matriz de paridad CLI <-> MCP — fase 2 (L3). Verificador FAIL-CLOSED.

Dos adaptadores, un producto. Compartir catalogo no los hace equivalentes: hay
que MEDIR que, para las mismas operaciones y los mismos escenarios, ofrecen el
mismo contrato, el mismo resultado y los mismos EFECTOS observables.

IDENTIDAD POR ESCENARIO (H-L3-05). Un caso no se identifica por el nombre de
la operacion: `vault_write` aparece en dos escenarios (crear, actualizar) y son
dos casos distintos. Cada caso lleva un `case_id` estable, y el verificador
exige que se ejecute CADA id, rechaza ids duplicados y rechaza ids no
previstos.

EFECTOS REALES. No basta con que las respuestas JSON coincidan: se mide el
estado del runtime antes y despues de cada pasada (ficheros creados, modificados
y eliminados, con su contenido normalizado —los campos volatiles como id,
createdAt y updatedAt se enmascaran porque cambian entre dos ejecuciones
identicas—) y se comparan los efectos de la CLI con los del MCP. Ademas se
comprueba que no se modifica nada FUERA del runtime autorizado.

Fallo cerrado: sale con codigo distinto de cero si
  - el verificador de contrato (AP-40) devuelve un codigo distinto de cero;
  - falta un caso requerido, hay ids duplicados o hay ids no previstos;
  - falta un campo obligatorio del contrato en algun adaptador;
  - divergen los codigos o el significado del error;
  - divergen los efectos observables (respuesta o ficheros);
  - el exit code de la CLI y su envelope no coinciden;
  - se modifico algo fuera del runtime autorizado;
  - la respuesta MCP llega con `isError` que contradice al otro adaptador, o
    como error de transporte.

La evaluacion vive en `evaluar()`, una funcion PURA: las pruebas negativas la
llaman con casos fabricados. Un verificador que solo sabe decir "todo bien" no
verifica nada (AP-44).

Salida: matriz en markdown + JSON.

Uso: python audits/fase2/paridad_cli_mcp.py --venv DIR --runtime DIR [--log S] [--matriz S]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import queue
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]

#: Campos que el contrato de una operacion DEBE declarar en ambos adaptadores.
CAMPOS_OBLIGATORIOS = ("ok",)

#: Campos volatiles que cambian entre dos ejecuciones identicas: se enmascaran
#: para comparar el CONTENIDO, no el ruido.
VOLATILES = (("id", r"[0-9a-fA-F-]{36}"), ("createdAt", r"[^\\n]+"),
             ("updatedAt", r"[^\\n]+"))

CASOS: List[Dict[str, Any]] = [
    {
        "case_id": "READ_MISSING",
        "tool": "vault_read",
        "scenario": "leer una nota que no existe",
        "args": {"path": "07_Knowledge/nota-paridad.md"},
        "campos": ["ok", "path"],
        "escritura": False,
    },
    {
        "case_id": "SEARCH_HITS",
        "tool": "vault_search",
        "scenario": "buscar un termino presente",
        "args": {"query": "paridad"},
        "campos": ["ok", "total"],
        "escritura": False,
    },
    {
        "case_id": "LIST_FOLDER",
        "tool": "vault_list",
        "scenario": "listar una carpeta",
        "args": {"folder": "07_Knowledge"},
        "campos": ["ok"],
        "escritura": False,
    },
    {
        "case_id": "WRITE_CREATE",
        "tool": "vault_write",
        "scenario": "crear una nota nueva",
        "args": {"folder": "07_Knowledge", "title": "Nota de paridad",
                 "content": "Nota escrita para medir la paridad entre los dos "
                            "adaptadores del producto instalado.\n"
                            "Segunda linea del cuerpo, para cumplir el gate.\n"
                            "Tercera linea, la que el gate exige.\n",
                 "tags": "paridad"},
        "campos": ["ok", "created", "path"],
        "escritura": True,
    },
    {
        "case_id": "WRITE_UPDATE",
        "tool": "vault_write",
        "scenario": "actualizar la nota ya creada",
        # Precondicion determinista: la nota tiene que existir. Se crea con la
        # CLI antes de fotografiar el estado.
        "preparar": [{"folder": "07_Knowledge", "title": "Nota de paridad",
                      "content": "Nota escrita para medir la paridad entre los dos "
                                 "adaptadores del producto instalado.\n"
                                 "Segunda linea del cuerpo, para cumplir el gate.\n"
                                 "Tercera linea, la que el gate exige.\n",
                      "tags": "paridad"}],
        "args": {"folder": "07_Knowledge", "title": "Nota de paridad",
                 "content": "Nota escrita para medir la paridad entre los dos "
                            "adaptadores del producto instalado.\n"
                            "Segunda linea del cuerpo, para cumplir el gate.\n"
                            "Tercera linea MODIFICADA por la segunda pasada.\n",
                 "tags": "paridad"},
        "campos": ["ok", "updated", "path"],
        "escritura": True,
    },
]

RUTA_LOCAL = re.compile(r"(?:[A-Za-z]:[\\/]+Users[\\/]|/(?:home|Users)/)[^\s\"'`)\]]*")


def sin_rutas(texto: str) -> str:
    """La maquina no viaja en la evidencia: sustituye toda ruta local."""
    return RUTA_LOCAL.sub("<RUTA-LOCAL>", texto)


#: Marcas de tiempo y uuid: cambian entre dos ejecuciones identicas y no son
#: diferencia funcional. Se enmascaran para comparar el EFECTO y no el ruido.
MARCA_TIEMPO = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}[:-]\d{2}[:-]\d{2}(?:\.\d+)?Z?")

#: Rastro de la LLAMADA, no estado del producto: el servidor MCP deja su propio
#: log de traza y el vault lleva la traza de tools y un contador de voz. Se
#: comparan porque un efecto real del producto no es "el contador subio una
#: vez mas": eso lo escribe la propia llamada.
TELEMETRIA = {
    "00_System/.tool-trace.json",
    "00_System/.mcp-trace-log.json",
    "00_System/.voice-counter",
}
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _normalizar_contenido(texto: str) -> str:
    """Enmascara lo volatil para comparar contenido y no ruido."""
    for campo, _patron in VOLATILES:
        texto = re.sub(rf"^({campo}:\s*).*$", rf"\1<{campo}>", texto, flags=re.M)
    texto = MARCA_TIEMPO.sub("<TS>", texto)
    texto = UUID.sub("<UUID>", texto)
    return texto


def _normalizar_ruta(ruta: str) -> str:
    """El nombre de un fichero puede llevar marca de tiempo (el historico de
    versiones del vault los nombra asi): el nombre es volatil, el conjunto de
    ficheros tocados es lo que se compara."""
    return MARCA_TIEMPO.sub("<TS>", ruta)


def _huellas(raiz: Path) -> Dict[str, str]:
    """Huella normalizada de cada fichero del arbol."""
    salida: Dict[str, str] = {}
    if not raiz.exists():
        return salida
    for ruta in sorted(raiz.rglob("*")):
        if not ruta.is_file():
            continue
        relativa = _normalizar_ruta(ruta.relative_to(raiz).as_posix())
        if relativa in TELEMETRIA:
            continue
        try:
            datos = ruta.read_bytes()
        except OSError:
            continue
        try:
            texto = datos.decode("utf-8")
        except UnicodeDecodeError:
            texto = repr(datos)
        salida[relativa] = hashlib.sha256(
            _normalizar_contenido(texto).encode("utf-8")).hexdigest()
    return salida


def _efectos(antes: Dict[str, str], despues: Dict[str, str]) -> Dict[str, Any]:
    """Los cambios observables: creados, modificados, eliminados y sus huellas."""
    return {
        "creados": sorted(set(despues) - set(antes)),
        "eliminados": sorted(set(antes) - set(despues)),
        "modificados": sorted(f for f in set(antes) & set(despues)
                              if antes[f] != despues[f]),
        "huellas": {f: despues[f] for f in sorted(despues)
                    if f not in antes or antes[f] != despues[f]},
    }


def evaluar(filas: List[Dict[str, Any]], contrato: Dict[str, Any],
            requeridos: Optional[List[str]] = None,
            previstos: Optional[List[str]] = None) -> Dict[str, Any]:
    """Veredicto FAIL-CLOSED sobre lo medido. Funcion pura."""
    problemas: List[str] = []

    codigo = contrato.get("exit")
    if codigo is None:
        problemas.append("el verificador de contrato (AP-40) no se ejecuto")
    elif codigo != 0:
        problemas.append(f"el verificador de contrato (AP-40) devolvio exit {codigo}")

    ids = [f.get("case_id") for f in filas]
    medidos = set(ids)
    for requerido in (requeridos or []):
        if requerido not in medidos:
            problemas.append(f"caso requerido no ejecutado: {requerido}")
    duplicados = sorted({i for i in ids if ids.count(i) > 1})
    for duplicado in duplicados:
        problemas.append(f"case_id duplicado: {duplicado}")
    # Un id que se midio y no estaba previsto tambien es un fallo: el guion
    # de la medicion no puede crecer sin que alguien lo mire.
    for medido in sorted(medidos):
        if previstos and medido not in previstos:
            problemas.append(f"case_id no previsto en la medicion: {medido}")

    for fila in filas:
        nombre = fila.get("case_id") or fila.get("operacion", "?")
        if fila.get("error_transporte"):
            problemas.append(f"{nombre}: error de transporte MCP: {fila['error_transporte']}")
        if fila.get("is_error"):
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
        for campo in list(CAMPOS_OBLIGATORIOS) + list(campos):
            if campo not in cli or campo not in mcp:
                problemas.append(f"{nombre}: campo obligatorio ausente ({campo})")
        cli_err = fila.get("cli_error")
        mcp_err = fila.get("mcp_error")
        if (cli_err is None) != (mcp_err is None):
            problemas.append(f"{nombre}: un adaptador devuelve error y el otro no "
                             f"(cli={cli_err!r}, mcp={mcp_err!r})")
        elif cli_err is not None and str(cli_err) != str(mcp_err):
            problemas.append(f"{nombre}: divergencia de codigo de error "
                             f"(cli={cli_err!r}, mcp={mcp_err!r})")
        for campo in campos:
            if campo == "ok":
                continue
            if cli.get(campo) != mcp.get(campo):
                problemas.append(f"{nombre}: divergencia de efecto en {campo!r} "
                                 f"(cli={cli.get(campo)!r}, mcp={mcp.get(campo)!r})")
        if cli.get("ok") != mcp.get("ok"):
            problemas.append(f"{nombre}: divergencia de resultado "
                             f"(cli ok={cli.get('ok')!r}, mcp ok={mcp.get('ok')!r})")
        # Efectos reales: el conjunto de ficheros afectados y su contenido
        # normalizado tienen que coincidir entre los dos adaptadores.
        efectos_cli = fila.get("efectos_cli") or {}
        efectos_mcp = fila.get("efectos_mcp") or {}
        if efectos_cli or efectos_mcp:
            if efectos_cli.get("creados") != efectos_mcp.get("creados"):
                problemas.append(f"{nombre}: efectos divergentes (creados "
                                 f"cli={efectos_cli.get('creados')} "
                                 f"mcp={efectos_mcp.get('creados')})")
            if efectos_cli.get("modificados") != efectos_mcp.get("modificados"):
                problemas.append(f"{nombre}: efectos divergentes (modificados)")
            if efectos_cli.get("eliminados") != efectos_mcp.get("eliminados"):
                problemas.append(f"{nombre}: efectos divergentes (eliminados)")
            if efectos_cli.get("huellas") != efectos_mcp.get("huellas"):
                problemas.append(f"{nombre}: las huellas finales de los ficheros "
                                 f"afectados difieren entre CLI y MCP")
        for lado, cambios in (("CLI", fila.get("externos_cli") or {}),
                               ("MCP", fila.get("externos_mcp") or {})):
            for clase in ("creados", "modificados", "eliminados"):
                if cambios.get(clase):
                    problemas.append(f"{nombre}: efecto FUERA del runtime "
                                     f"autorizado por {lado} ({clase}: "
                                     f"{cambios[clase]})")
        if fila.get("no_verificados"):
            problemas.append(f"{nombre}: ficheros no verificables durante la "
                             f"medicion: {fila['no_verificados']}")
        # El exit code de la CLI y su envelope tienen que concordar.
        if fila.get("cli_exit") is not None and "ok" in cli:
            fallo_con_envelope_ok = (fila["cli_exit"] != 0) and bool(cli.get("ok"))
            if fallo_con_envelope_ok and not cli_err:
                problemas.append(f"{nombre}: el exit code de la CLI es "
                                 f"{fila['cli_exit']} pero su envelope dice ok")
    return {"ok": not problemas, "problemas": problemas}


def _normalizar(texto: str) -> Dict[str, Any]:
    try:
        sobre = json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return {"_crudo": (texto or "")[:400]}
    return sobre if isinstance(sobre, dict) else {"_crudo": str(sobre)[:400]}


def _elegir(sobre: Dict[str, Any], campos: List[str]) -> Dict[str, Any]:
    return {c: sobre.get(c) for c in campos if c in sobre}


def detectar_cambios(antes: Dict[str, str], despues: Dict[str, str]) -> Dict[str, Any]:
    """Los cambios entre dos estados, por huella de contenido.

    Devuelve creados, modificados y eliminados. Un fichero que conserva el
    nombre pero cambia de contenido es MODIFICADO: comparar solo nombres no
    ve esa diferencia (H-F2-02).
    """
    return {
        "creados": sorted(set(despues) - set(antes)),
        "eliminados": sorted(set(antes) - set(despues)),
        "modificados": sorted(
            ruta
            for ruta in set(antes) & set(despues)
            if antes[ruta] != despues[ruta]
        ),
    }


def clasificar_cambios(cambios: Dict[str, List[str]],
                       internos: Tuple[str, ...]) -> Dict[str, Dict[str, List[str]]]:
    """Parte los cambios en INTERNOS (runtime autorizado) y EXTERNOS (fuera).

    Un cambio EXTERNO es un efecto prohibido; los INTERNOS son el efecto
    esperado de la operacion. La distincion es de rutas, con exclusiones
    declaradas para los entornos de la propia prueba.
    """
    reparto: Dict[str, Dict[str, List[str]]] = {
        "internos": {"creados": [], "modificados": [], "eliminados": []},
        "externos": {"creados": [], "modificados": [], "eliminados": []},
    }
    for clase in ("creados", "modificados", "eliminados"):
        for ruta in cambios[clase]:
            destino = (reparto["internos"]
                       if any(ruta.startswith(p) for p in internos)
                       else reparto["externos"])
            destino[clase].append(ruta)
    return reparto


def _huellas_del_entorno(raiz: Path,
                          excluidos: Tuple[str, ...] = ()) -> Dict[str, str]:
    """Huellas del entorno, sin los directorios excluidos de la prueba.

    Los que no se pueden leer se DEVUELVEN en 'no_verificados': no se pueden
    ignorar como si no existieran (H-F2-02).
    """
    salida: Dict[str, str] = {}
    no_verificados: List[str] = []
    for ruta in sorted(raiz.rglob("*")):
        if not ruta.is_file():
            continue
        relativa = ruta.relative_to(raiz).as_posix()
        if any(relativa.startswith(p) for p in excluidos):
            continue
        try:
            datos = ruta.read_bytes()
        except OSError:
            no_verificados.append(relativa)
            continue
        try:
            texto = datos.decode("utf-8")
        except UnicodeDecodeError:
            texto = repr(datos)
        salida[relativa] = hashlib.sha256(
            _normalizar_contenido(texto).encode("utf-8")).hexdigest()
    salida["__no_verificados__"] = no_verificados  # tipo: ignore[assignment]
    return salida


def _sin_no_verificados(huellas: Dict[str, Any]) -> List[str]:
    valor = huellas.get("__no_verificados__", [])
    return list(valor) if isinstance(valor, list) else []


class Mcp:
    """Cliente JSON-RPC sobre stdio del servidor MCP instalado.

    PLAZO GLOBAL (H-L3-06): un unico deadline monotonico gobierna toda la
    llamada. Un `queue.get(timeout=...)` por linea renovaba el plazo en cada
    linea recibida, de modo que un goteo de notificaciones sin la respuesta
    esperada podia alargar la espera sin limite. Con el deadline, el plazo se
    respeta aunque lleguen lineas.
    """

    def __init__(self, mjs: Path, env: Dict[str, str],
                 cmd: Optional[List[str]] = None):
        self.proc = subprocess.Popen(cmd or ["node", str(mjs)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, encoding="utf-8", errors="replace",
                                     env=env, bufsize=1)
        self.id = 0
        self.lineas: "queue.Queue[Optional[str]]" = queue.Queue()
        self.lector = threading.Thread(target=self._leer, daemon=True)
        self.lector.start()
        self.terminado = False

    def _leer(self) -> None:
        try:
            for linea in self.proc.stdout:
                self.lineas.put(linea)
        finally:
            self.lineas.put(None)

    def cerrar(self) -> None:
        self.terminado = True
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
        try:
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError) as exc:
            return {"error": {"code": -1, "message": f"el proceso MCP no acepta "
                                                     f"la peticion: {exc}"}}
        deadline = time.monotonic() + timeout
        while True:
            restante = deadline - time.monotonic()
            if restante <= 0:
                return {"error": {"code": -1, "message": "timeout"}}
            try:
                linea = self.lineas.get(timeout=restante)
            except queue.Empty:
                return {"error": {"code": -1, "message": "timeout"}}
            if linea is None:
                return {"error": {"code": -1, "message": "el proceso MCP termino"}}
            linea = linea.strip()
            if not linea:
                continue
            try:
                dato = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if dato.get("id") == self.id:
                return dato
            # Linea con otro id (notificacion o respuesta ajena): se ignora,
            # pero el PLAZO GLOBAL sigue corriendo: no se renueva.

    def avisar(self, metodo: str) -> None:
        try:
            self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": metodo}) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            pass


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
    # Windows: Lib/site-packages. POSIX: lib/python3.X/site-packages. Solo
    # estaba la primera: en Linux el verificador arrancaba el MCP sobre un
    # fichero ausente (mismo defecto que tenia recorrido_terceros_r07).
    sitios = [venv / "Lib" / "site-packages", *sorted(venv.glob("lib/python3*/site-packages"))]
    site = next((s for s in sitios if (s / "vault_toolkit").is_dir()), sitios[0])
    mjs = site / "vault_toolkit" / "mcp" / "vault-mcp-server.mjs"
    env = {**os.environ, "VAULT_ROOT": str(runtime), "VAULT_STRICT_ROOT": "1",
           "VAULT_AGENT": "paridad-fase2", "PYTHONIOENCODING": "utf-8"}
    padre = runtime.parent

    filas: List[Dict[str, Any]] = []

    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "vault_mcp_catalog.py"),
                        "--check-params"], cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    contrato = {"exit": p.returncode, "stdout": p.stdout[-600:], "stderr": p.stderr[-300:]}

    mcp = Mcp(mjs, env)
    mcp.llamar("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                              "clientInfo": {"name": "paridad", "version": "1"}})
    mcp.avisar("notifications/initialized")
    herramientas = (mcp.llamar("tools/list").get("result", {}) or {}).get("tools", []) or []
    nombres_mcp = {t.get("name") for t in herramientas}

    foto = parent_ = padre / (runtime.name + ".foto")

    def _argv(tool: str, argumentos: Dict[str, Any]) -> List[str]:
        argv = [str(cli), "run", tool]
        for clave, valor in argumentos.items():
            argv += [f"--{clave}", str(valor)]
        return argv

    for caso in CASOS:
        # Estado de partida determinista: la precondicion del caso, si la hay.
        for preparacion in caso.get("preparar", []):
            subprocess.run(_argv(caso["tool"], preparacion), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", env=env,
                           timeout=900)
        shutil.rmtree(foto, ignore_errors=True)
        shutil.copytree(runtime, foto)
        antes_cli = _huellas(runtime)
        excluidos = (runtime.name + "/", "venv-consumer/", "venv-runner/",
                     "dist/", "dist-clean/", "foto/")
        antes_entorno = _huellas_del_entorno(padre, excluidos)

        argv = _argv(caso["tool"], caso["args"])
        p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=900)
        cli_sobre = _normalizar(p.stdout)
        efectos_cli = _efectos(antes_cli, _huellas(runtime))
        cambios_cli = detectar_cambios(antes_entorno, _huellas_del_entorno(padre, excluidos))
        reparto_cli = clasificar_cambios(cambios_cli, internos=(runtime.name + "/",))
        fuera_cli = sorted(reparto_cli["externos"]["creados"]
                           + reparto_cli["externos"]["modificados"]
                           + reparto_cli["externos"]["eliminados"])
        sin_verificar_cli = reparto_cli["externos"].get("__no_verificados__", [])

        shutil.rmtree(runtime, ignore_errors=True)
        shutil.copytree(foto, runtime)
        antes_mcp = _huellas(runtime)
        antes_entorno_mcp = _huellas_del_entorno(padre, excluidos)

        expuesta = caso["tool"] in nombres_mcp
        is_error = False
        error_transporte = None
        if expuesta:
            rm = mcp.llamar("tools/call", {"name": caso["tool"],
                                            "arguments": caso["args"]})
            if "error" in rm:
                error_transporte = rm["error"].get("message", "error de transporte")
            is_error = bool((rm.get("result", {}) or {}).get("isError"))
            mcp_sobre = _normalizar(_texto_mcp(rm))
        else:
            mcp_sobre = {}
        efectos_mcp = _efectos(antes_mcp, _huellas(runtime))
        cambios_mcp = detectar_cambios(antes_entorno_mcp, _huellas_del_entorno(padre, excluidos))
        reparto_mcp = clasificar_cambios(cambios_mcp, internos=(runtime.name + "/",))
        fuera_mcp = sorted(reparto_mcp["externos"]["creados"]
                           + reparto_mcp["externos"]["modificados"]
                           + reparto_mcp["externos"]["eliminados"])
        sin_verificar_mcp = reparto_mcp["externos"].get("__no_verificados__", [])

        filas.append({
            "case_id": caso["case_id"],
            "operacion": caso["tool"],
            "escenario": caso.get("scenario", ""),
            "argumentos": caso["args"],
            "expuesta_por_mcp": expuesta,
            "cli_exit": p.returncode,
            "cli": _elegir(cli_sobre, caso["campos"]),
            "mcp": _elegir(mcp_sobre, caso["campos"]),
            "cli_error": cli_sobre.get("error_code") or cli_sobre.get("error"),
            "mcp_error": mcp_sobre.get("error_code") or mcp_sobre.get("error"),
            "is_error": is_error,
            "error_transporte": error_transporte,
            "campos": caso["campos"],
            "efectos_cli": efectos_cli,
            "efectos_mcp": efectos_mcp,
            "fuera_del_runtime_cli": fuera_cli,
            "fuera_del_runtime_mcp": fuera_mcp,
            "externos_cli": reparto_cli["externos"],
            "externos_mcp": reparto_mcp["externos"],
            "no_verificados": sorted(set(sin_verificar_cli) | set(sin_verificar_mcp)),
        })
        print(f"medido {caso['case_id']}: cli={filas[-1]['cli']} mcp={filas[-1]['mcp']} "
              f"efectos cli={efectos_cli['creados'] + efectos_cli['modificados']} "
              f"mcp={efectos_mcp['creados'] + efectos_mcp['modificados']}")
    mcp.cerrar()
    shutil.rmtree(foto, ignore_errors=True)

    requeridos = [c["case_id"] for c in CASOS]
    previstos = list(requeridos)
    veredicto = evaluar(filas, contrato, requeridos, previstos)
    veredicto.update({
        "contrato_ap40": contrato,
        "filas": filas,
        "casos_requeridos": requeridos,
        "herramientas_mcp": len(herramientas),
        "coincidencias": sum(1 for f in filas if f.get("cli") == f.get("mcp")),
        "casos": len(filas),
        "alcance": (f"paridad funcional probada en {len(CASOS)} casos con identidad "
                    f"propia (operacion + escenario) de {len(herramientas)} tools "
                    f"expuestas por el servidor MCP; el contrato de TODAS las tools lo "
                    f"cubre el verificador AP-40"),
    })

    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    Path(args.log).write_text(sin_rutas(
        "PARIDAD CLI <-> MCP — fase 2 (L3)\n"
        + json.dumps(veredicto, ensure_ascii=False, indent=2) + "\n"), encoding="utf-8")

    lineas = ["# Matriz de paridad CLI ↔ MCP — fase 2 (L3)", "",
              "Derivado de la ejecucion real sobre el artefacto instalado. Generado por "
              "`python audits/fase2/paridad_cli_mcp.py`.", "",
              f"- Tools expuestas por el servidor MCP instalado: **{len(herramientas)}**",
              f"- Verificador de contrato AP-40 (`vault_mcp_catalog --check-params`): "
              f"exit **{contrato['exit']}**",
              f"- Casos medidos: **{len(CASOS)}** (identidad propia por escenario) · "
              f"veredicto: **{'CONFORME' if veredicto['ok'] else 'NO CONFORME'}**",
              f"- Alcance: {veredicto['alcance']}", ""]
    if veredicto["problemas"]:
        lineas += ["## Problemas detectados", ""] + [f"- {p}" for p in veredicto["problemas"]] + [""]
    lineas += ["| case_id | Operación | Escenario | CLI | MCP | Efectos (CLI) | Efectos (MCP) | Coincide |",
               "|---|---|---|---|---|---|---|---|"]
    for f in filas:
        ec, em = f["efectos_cli"], f["efectos_mcp"]
        coincide = (f["cli"] == f["mcp"] and ec.get("creados") == em.get("creados")
                    and ec.get("modificados") == em.get("modificados")
                    and ec.get("huellas") == em.get("huellas"))
        lineas.append(f"| `{f['case_id']}` | `{f['operacion']}` | {f['escenario']} "
                      f"| `{json.dumps(f['cli'], ensure_ascii=False)}` "
                      f"| `{json.dumps(f['mcp'], ensure_ascii=False)}` "
                      f"| {ec.get('creados', []) + ec.get('modificados', [])} "
                      f"| {em.get('creados', []) + em.get('modificados', [])} "
                      f"| {'sí' if coincide else 'NO'} |")
    lineas += ["", "## Criterio de equivalencia", "",
               "Se comparan resultados NORMALIZADOS (ok, rutas, contadores y codigos de "
               "error) Y los EFECTOS REALES sobre el runtime: ficheros creados, "
               "modificados y eliminados, con su contenido normalizado (los campos "
               "volatiles —id, createdAt, updatedAt— se enmascaran porque cambian entre "
               "dos ejecuciones identicas). Ademas se comprueba que no se modifica nada "
               "FUERA del runtime autorizado.", ""]
    Path(args.matriz).write_text(sin_rutas("\n".join(lineas) + "\n"), encoding="utf-8")

    print(f"\nparidad: {veredicto['coincidencias']}/{veredicto['casos']} | "
          f"AP-40 exit {contrato['exit']} | tools MCP {len(herramientas)} | "
          f"veredicto: {'CONFORME' if veredicto['ok'] else 'NO CONFORME'}")
    for problema in veredicto["problemas"]:
        print(f"  PROBLEMA: {problema}")
    print(f"log: {args.log} | matriz: {args.matriz}")
    return 0 if veredicto["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
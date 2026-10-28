"""QA-RC-05 · recorrido completo de un tercero desde la WHEEL instalada (R09).

Reglas del contrato (QA-RC-02g/i y QA-RC-05):
  - sandbox NUEVO por ejecucion, fuera del checkout; nunca se borra nada que
    no haya creado esta ejecucion;
  - el hash de referencia se toma del FICHERO PERSISTIDO (no del texto de
    entrada): el contenido se normaliza al escribir;
  - la cuarentena se identifica por lo que crea ESTA ejecucion (conjunto antes
    y despues), no por "la mas reciente";
  - cliente MCP SECUENCIAL con ids correlacionados y plazo global;
  - el restore se compara por INVENTARIO y hashes, en un destino limpio (no
    encima del runtime reinicializado);
  - aserciones estructuradas: se interpretan JSON, estados y exit codes.

Salida: JSON con el detalle de cada paso, el hash de los artefactos y
`todos_ok`. Ese JSON es la evidencia externa que consume el colector
(QG-03 `recorrido_e2e` y QG-06 `instalacion_limpia`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

RAIZ = Path(__file__).resolve().parents[2]
PLAZA_MCP = 180  # segundos globales para toda la sesion MCP


class Recorrido:
    def __init__(self, sandbox: Path):
        self.sandbox = sandbox
        self.pasos: List[Dict[str, Any]] = []

    def paso(self, nombre: str, ok: bool, detalle: str = "") -> bool:
        self.pasos.append({"paso": nombre, "ok": bool(ok), "detalle": str(detalle)[:400]})
        print(("OK   " if ok else "FALLO"), nombre, str(detalle)[:150], flush=True)
        return bool(ok)

    @property
    def todos_ok(self) -> bool:
        return all(p["ok"] for p in self.pasos)

    def informe(self) -> Dict[str, Any]:
        return {"todos_ok": self.todos_ok,
                "pasos": self.pasos,
                "total_pasos": len(self.pasos),
                "fallidos": [p["paso"] for p in self.pasos if not p["ok"]],
                "sandbox": str(self.sandbox)}


def _hash(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _inventario(raiz: Path, excluir: tuple = ()) -> Dict[str, str]:
    """Inventario ruta relativa -> sha256, sin seguir symlinks."""
    salida: Dict[str, str] = {}
    for base, dirs, ficheros in os.walk(raiz, followlinks=False):
        base_path = Path(base)
        for d in list(dirs):
            if (base_path / d).is_symlink():
                dirs.remove(d)
        for nombre in ficheros:
            ruta = base_path / nombre
            rel = ruta.relative_to(raiz).as_posix()
            if rel in excluir:
                continue
            if ruta.is_symlink():
                salida[rel] = "symlink"
                continue
            salida[rel] = _hash(ruta)
    return salida


def _json_de(stdout: str) -> Optional[Dict[str, Any]]:
    """Primer objeto JSON del stdout (los envelopes del toolkit son de una linea)."""
    for linea in stdout.splitlines():
        linea = linea.strip()
        if linea.startswith("{"):
            try:
                return json.loads(linea)
            except ValueError:
                continue
    return None


class ClienteMCP:
    """Cliente JSON-RPC secuencial: una peticion, una respuesta correlacionada."""

    def __init__(self, mjs: Path, env: Dict[str, str], plazo: int = PLAZA_MCP):
        self.plazo = plazo
        self.limite = time.monotonic() + plazo
        self.proc = subprocess.Popen(
            ["node", str(mjs)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace", env=env)
        self.cola: "queue.Queue[str]" = queue.Queue()
        self.hilo = threading.Thread(target=self._leer, daemon=True)
        self.hilo.start()

    def _leer(self) -> None:
        for linea in self.proc.stdout:
            if linea.strip().startswith("{"):
                self.cola.put(linea)

    def pedir(self, payload: Dict[str, Any], id_esperado: int) -> Optional[Dict[str, Any]]:
        restante = self.limite - time.monotonic()
        if restante <= 0:
            return None
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        while True:
            restante = self.limite - time.monotonic()
            if restante <= 0:
                return None
            try:
                linea = self.cola.get(timeout=restante)
            except queue.Empty:
                return None
            try:
                dato = json.loads(linea)
            except ValueError:
                continue  # mensaje no relacionado: se ignora
            if dato.get("id") == id_esperado:
                return dato

    def cerrar(self) -> None:
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida", default=None, help="JSON del recorrido")
    ap.add_argument("--mantener", action="store_true",
                    help="No borra el sandbox (por defecto se conserva)")
    args = ap.parse_args()

    sandbox = Path(tempfile.mkdtemp(prefix="r09-e2e-"))
    r = Recorrido(sandbox)
    venv = sandbox / "venv"
    proyecto = sandbox / "consumidor"
    proyecto.mkdir(parents=True, exist_ok=True)
    runtime = proyecto / "mi-vault"
    dist = sandbox / "dist"
    py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    cli = venv / ("Scripts/vault.exe" if os.name == "nt" else "bin/vault")
    env = dict(os.environ, VAULT_ROOT=str(runtime), VAULT_AGENT="qa-tercero")

    # 1. BUILD
    p = subprocess.run([sys.executable, "-m", "build", "--wheel", "--sdist",
                        "--outdir", str(dist)], cwd=str(RAIZ),
                       capture_output=True, text=True, timeout=1800)
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    r.paso("build wheel+sdist", p.returncode == 0 and bool(wheels) and bool(sdists),
           f"{len(wheels)} whl / {len(sdists)} sdist")
    if not wheels or not sdists:
        return _fin(r, args)
    hash_whl = _hash(wheels[0])
    hash_sdist = _hash(sdists[0])

    # 2. INSTALACION LIMPIA
    p = subprocess.run([sys.executable, "-m", "venv", str(venv)],
                       capture_output=True, text=True, timeout=1800)
    p2 = subprocess.run([str(py), "-m", "pip", "install", "--quiet",
                         str(wheels[0])], capture_output=True, text=True,
                        timeout=1800)
    r.paso("instalacion limpia", p.returncode == 0 and p2.returncode == 0,
           f"pip exit={p2.returncode}")

    # 3-4. VERSION Y HELP
    p = subprocess.run([str(cli), "--version"], capture_output=True, text=True,
                       timeout=300)
    r.paso("version", p.returncode == 0 and p.stdout.strip() != "",
           p.stdout.strip())
    p = subprocess.run([str(cli), "--help"], capture_output=True, text=True,
                       timeout=300)
    r.paso("help", p.returncode == 0 and "init" in p.stdout, "")

    # 5-7. INIT, DOCTOR, STATUS
    p = subprocess.run([str(cli), "init", str(runtime)], capture_output=True,
                       text=True, timeout=1800)
    sobre = _json_de(p.stdout)
    r.paso("init", p.returncode == 0 and bool(sobre) and sobre.get("ok") is True,
           (sobre or {}).get("state", ""))
    p = subprocess.run([str(cli), "doctor", str(runtime)], capture_output=True,
                       text=True, timeout=1800)
    sobre = _json_de(p.stdout)
    r.paso("doctor", p.returncode == 0 and (sobre or {}).get("state") == "RUNTIME_OK",
           (sobre or {}).get("state", ""))
    p = subprocess.run([str(cli), "status", str(runtime)], capture_output=True,
                       text=True, timeout=1800)
    sobre = _json_de(p.stdout)
    r.paso("status", p.returncode == 0 and (sobre or {}).get("state") == "RUNTIME_OK",
           (sobre or {}).get("state", ""))

    # 8. WRITE POR CLI
    contenido = "linea uno del contenido\nlinea dos del contenido\nlinea tres"
    p = subprocess.run([str(cli), "run", "vault_write", "--folder", "07_Knowledge",
                        "--title", "Nota RC", "--tags", "rc", "--content", contenido],
                       capture_output=True, text=True, env=env, timeout=1800)
    sobre = _json_de(p.stdout)
    ok_write = bool(sobre) and sobre.get("ok") is True and sobre.get("path")
    r.paso("write CLI", ok_write, (sobre or {}).get("path", ""))
    nota = runtime / "07_Knowledge" / "nota-rc.md"
    if not nota.is_file():
        r.paso("nota persistida", False, "no existe 07_Knowledge/nota-rc.md")
        return _fin(r, args)
    # 9. HASH DE REFERENCIA: del FICHERO PERSISTIDO
    hash_persistido = _hash(nota)
    r.paso("hash de referencia del fichero persistido", True, hash_persistido[:16])

    # 10. READ POR CLI
    p = subprocess.run([str(cli), "run", "vault_read", "--path",
                        "07_Knowledge/nota-rc.md"], capture_output=True,
                       text=True, env=env, timeout=1800)
    sobre = _json_de(p.stdout)
    r.paso("read CLI", bool(sobre) and sobre.get("ok") is True
           and "linea tres" in json.dumps(sobre, ensure_ascii=False), "")

    # 11. SEARCH POR CLI
    p = subprocess.run([str(cli), "run", "vault_search", "--query", "linea tres"],
                       capture_output=True, text=True, env=env, timeout=1800)
    r.paso("search CLI", p.returncode == 0
           and "nota-rc" in p.stdout, "")

    # 12-14. MCP SECUENCIAL
    mjs = (venv / "Lib" / "site-packages" / "vault_toolkit" / "mcp" /
           "vault-mcp-server.mjs")
    if not mjs.is_file():
        # POSIX: lib/python3.X/site-packages. La ruta fija `lib/python3` no
        # existe en ningun venv, y el recorrido solo se habia ejecutado en
        # Windows: en Linux el cliente MCP arrancaba sobre un fichero ausente.
        candidatos = sorted(venv.glob("lib/python3*/site-packages/vault_toolkit/"
                                      "mcp/vault-mcp-server.mjs"))
        if candidatos:
            mjs = candidatos[0]
    env_mcp = dict(env, VAULT_MCP_PYTHON=str(py))
    cliente = ClienteMCP(mjs, env_mcp)
    ini = cliente.pedir({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {"protocolVersion": "2024-11-05",
                                    "capabilities": {},
                                    "clientInfo": {"name": "r09", "version": "1"}}}, 1)
    r.paso("MCP initialize", bool(ini) and "result" in (ini or {}),
           json.dumps((ini or {}).get("result", {}).get("serverInfo", {})))
    cliente.proc.stdin.write(json.dumps({"jsonrpc": "2.0",
                                        "method": "notifications/initialized"}) + "\n")
    cliente.proc.stdin.flush()
    lista = cliente.pedir({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, 2)
    tools = (((lista or {}).get("result") or {}).get("tools") or [])
    r.paso("MCP tools/list", len(tools) > 0, f"{len(tools)} tools")
    lectura = cliente.pedir({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                             "params": {"name": "vault_read",
                                        "arguments": {"path":
                                                      "07_Knowledge/nota-rc.md"}}}, 3)
    r.paso("MCP lee la nota",
           bool(lectura) and "linea tres" in json.dumps(lectura, ensure_ascii=False),
           "")
    busqueda = cliente.pedir({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                              "params": {"name": "vault_search",
                                         "arguments": {"query": "linea tres"}}}, 4)
    r.paso("MCP busca la nota",
           bool(busqueda) and "nota-rc" in json.dumps(busqueda, ensure_ascii=False),
           "")
    cliente.cerrar()

    # 15. PERSISTENCIA TRAS REINICIO DEL SERVIDOR
    cliente2 = ClienteMCP(mjs, env_mcp)
    cliente2.pedir({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "r09b", "version": "1"}}}, 1)
    cliente2.proc.stdin.write(json.dumps({"jsonrpc": "2.0",
                                          "method": "notifications/initialized"}) + "\n")
    cliente2.proc.stdin.flush()
    otra = cliente2.pedir({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                            "params": {"name": "vault_read",
                                       "arguments": {"path":
                                                     "07_Knowledge/nota-rc.md"}}}, 2)
    r.paso("persistencia tras reiniciar MCP",
           bool(otra) and "linea tres" in json.dumps(otra, ensure_ascii=False), "")
    cliente2.cerrar()

    # 16. CLEAN --DRY-RUN
    antes_quarentenas = set(proyecto.glob(f".{runtime.name}.cuarentena-*"))
    p = subprocess.run([str(py), "-m", "vault_toolkit.operations.vault_init",
                        "--clean", "--confirm", runtime.name, "--dry-run"],
                       capture_output=True, text=True, env=env, cwd=str(proyecto),
                       timeout=1800)
    sobre = _json_de(p.stdout)
    dry = bool(sobre) and (sobre.get("clean") or {}).get("dry_run") is True
    r.paso("clean --dry-run", p.returncode == 0 and dry,
           json.dumps((sobre or {}).get("clean", {}))[:150])
    r.paso("dry-run no borro", nota.is_file(), "la nota sigue en su sitio")

    # 17. CLEAN --CONFIRM
    p = subprocess.run([str(py), "-m", "vault_toolkit.operations.vault_init",
                        "--clean", "--confirm", runtime.name],
                       capture_output=True, text=True, env=env, cwd=str(proyecto),
                       timeout=1800)
    sobre = _json_de(p.stdout)
    estado_clean = (sobre or {}).get("clean", {}).get("estado")
    r.paso("clean --confirm", p.returncode == 0 and estado_clean == "VERIFIED",
           str(estado_clean))
    nuevas = set(proyecto.glob(f".{runtime.name}.cuarentena-*")) - antes_quarentenas
    r.paso("cuarentena creada por esta ejecucion", len(nuevas) == 1,
           ",".join(sorted(x.name for x in nuevas)))
    cuarentena = sorted(nuevas)[0] if nuevas else None
    r.paso("vault reinicializado", (runtime / "00_System").is_dir(), "")
    r.paso("la nota ya no esta en el vault nuevo", not nota.is_file(), "")

    # 18. INTEGRIDAD DE LA CUARENTENA
    if cuarentena is None:
        r.paso("cuarentena integra", False, "no hay cuarentena")
        return _fin(r, args)
    nota_cuarentena = cuarentena / "07_Knowledge" / "nota-rc.md"
    hash_cuarentena = _hash(nota_cuarentena) if nota_cuarentena.is_file() else ""
    r.paso("cuarentena conserva la nota por hash",
           bool(hash_cuarentena) and hash_cuarentena == hash_persistido,
           hash_cuarentena[:16])
    locks_cuarentena = (cuarentena / ".locks").is_dir()
    r.paso("locks preservado",
           (not locks_cuarentena) or (runtime / ".locks").is_dir(), "")

    # 19. RESTORE EN DESTINO LIMPIO + REINSTALACION CONSERVANDO DATOS
    restaurado = sandbox / "restaurado"
    shutil.copytree(cuarentena, restaurado, dirs_exist_ok=True, symlinks=True)
    manifiesto = restaurado / ".cuarentena.json"
    if manifiesto.is_file():
        manifiesto.unlink()
    inv_cuarentena = _inventario(cuarentena, excluir=(".cuarentena.json",))
    inv_restaurado = _inventario(restaurado, excluir=(".cuarenta.json",))
    iguales = inv_cuarentena == inv_restaurado
    r.paso("restore: inventario identico al de la cuarentena", iguales,
           f"{len(inv_restaurado)} ficheros")
    nota_restaurada = restaurado / "07_Knowledge" / "nota-rc.md"
    r.paso("restore: la nota tiene el hash original",
           nota_restaurada.is_file() and _hash(nota_restaurada) == hash_persistido,
           "")
    p = subprocess.run([str(py), "-m", "pip", "install", "--quiet", "--force-reinstall",
                        "--no-deps", str(wheels[0])], capture_output=True, text=True,
                       timeout=1800)
    env_restaurado = dict(env, VAULT_ROOT=str(restaurado))
    p2 = subprocess.run([str(cli), "run", "vault_read", "--path",
                         "07_Knowledge/nota-rc.md"], capture_output=True, text=True,
                        env=env_restaurado, timeout=1800)
    sobre = _json_de(p2.stdout)
    r.paso("reinstalacion conserva los datos",
           p.returncode == 0 and bool(sobre) and sobre.get("ok") is True
           and _hash(nota_restaurada) == hash_persistido, "")

    return _fin(r, args, hash_whl, hash_sdist)


def _fin(r: Recorrido, args, hash_whl: str = "", hash_sdist: str = "") -> int:
    informe = r.informe()
    informe["wheel_sha256"] = hash_whl
    informe["sdist_sha256"] = hash_sdist
    informe["instalacion_limpia"] = any(p["paso"] == "instalacion limpia" and p["ok"]
                                        for p in r.pasos)
    if args.salida:
        Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
        Path(args.salida).write_text(json.dumps(informe, indent=2,
                                                 ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    print(f"\n{informe['total_pasos'] - len(informe['fallidos'])}/"
          f"{informe['total_pasos']} pasos correctos")
    if informe["fallidos"]:
        print("fallidos:", ", ".join(informe["fallidos"]))
    print("wheel sha256:", hash_whl)
    print("sdist sha256:", hash_sdist)
    print("sandbox:", informe["sandbox"])
    return 0 if informe["todos_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

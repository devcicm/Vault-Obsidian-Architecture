"""QA-RC-05 · recorrido de tercero desde la wheel instalada, con --clean.

Todo en directorios descartables. La wheel se reconstruye desde el checkout
ACTUAL y se instala en un venv limpio; el runtime nace fuera del checkout.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DIST = RAIZ / "dist" / "rc"
VENV = Path(os.environ["TEMP"]) / "opencode" / "r07-venv"
CONSUM = Path(os.environ["TEMP"]) / "opencode" / "r07-consumidor"
RT = CONSUM / "mi-vault"

PASOS = []


def paso(nombre, ok, detalle=""):
    PASOS.append((nombre, bool(ok), detalle))
    print(("OK  " if ok else "FALLO"), nombre, detalle[:120])


def main():
    py = VENV / "Scripts" / "python.exe"
    # BUILD
    if DIST.exists():
        import shutil
        shutil.rmtree(DIST)
    r = subprocess.run([sys.executable, "-m", "build", "--wheel", "--sdist",
                        "--outdir", str(DIST)], cwd=str(RAIZ),
                       capture_output=True, text=True)
    paso("build wheel+sdist", r.returncode == 0)
    whl = next(DIST.glob("*.whl"))
    sdist = next(DIST.glob("*.tar.gz"))
    h_whl = hashlib.sha256(whl.read_bytes()).hexdigest()
    h_sdist = hashlib.sha256(sdist.read_bytes()).hexdigest()
    print("whl:", whl.name, h_whl[:16], "| sdist:", sdist.name, h_sdist[:16])

    # INSTALACION LIMPIA
    import shutil as _sh
    if VENV.exists():
        _sh.rmtree(VENV)
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    py = VENV / "Scripts" / "python.exe"
    cli = VENV / "Scripts" / "vault.exe"
    subprocess.run([str(py), "-m", "pip", "install", "--quiet", str(whl)],
                   check=True)
    paso("instalacion limpia", True)

    # VERSION / HELP
    v = subprocess.run([str(cli), "--version"], capture_output=True, text=True)
    paso("version", v.returncode == 0, v.stdout.strip())

    # INIT
    if RT.exists():
        _sh.rmtree(RT)
    CONSUM.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(cli), "init", str(RT)], capture_output=True,
                       text=True)
    paso("init", r.returncode == 0 and '"INIT_CREATED"' in r.stdout)
    r = subprocess.run([str(cli), "doctor", str(RT)], capture_output=True,
                       text=True)
    paso("doctor", r.returncode == 0 and '"RUNTIME_OK"' in r.stdout)

    # WRITE / READ POR CLI
    env = dict(os.environ, VAULT_ROOT=str(RT), VAULT_AGENT="qa-tercero")
    contenido = "linea uno del contenido\nlinea dos del contenido\nlinea tres"
    r = subprocess.run([str(cli), "run", "vault_write", "--folder",
                        "07_Knowledge", "--title", "Nota RC", "--tags", "rc",
                        "--content", contenido], capture_output=True,
                       text=True, env=env)
    paso("write CLI", '"ok": true' in r.stdout.lower(), r.stdout[:120])
    r = subprocess.run([str(cli), "run", "vault_read", "--path",
                        "07_Knowledge/nota-rc.md"], capture_output=True,
                       text=True, env=env)
    paso("read CLI", '"ok": true' in r.stdout.lower()
         and "linea tres" in r.stdout)

    # --CLEAN DRY-RUN (desde la WHEEL, no desde scripts/): no borra
    limpiar = [str(py), "-m", "vault_toolkit.operations.vault_init",
               "--clean", "--confirm", RT.name, "--dry-run"]
    r = subprocess.run(limpiar, capture_output=True, text=True, env=env,
                       cwd=str(CONSUM))
    plan_ok = '"dry_run": true' in r.stdout or "dry_run" in r.stdout
    paso("clean --dry-run (wheel)", r.returncode == 0 and plan_ok, r.stdout[:150])
    paso("dry-run no borro", (RT / "07_Knowledge" / "nota-rc.md").exists())

    # --CLEAN CON CONFIRMACION: cuarentena + vault nuevo
    r = subprocess.run([str(py), "-m",
                        "vault_toolkit.operations.vault_init", "--clean",
                        "--confirm", RT.name], capture_output=True, text=True,
                       env=env, cwd=str(CONSUM))
    ok_clean = '"ok": true' in r.stdout and '"VERIFIED"' in r.stdout
    paso("clean --confirm (wheel)", ok_clean, r.stdout[:200])
    cuarentenas = list(CONSUM.glob(f".{RT.name}.cuarentena-*"))
    paso("cuarentena creada", len(cuarentenas) == 1,
         str(cuarentenas[0]) if cuarentenas else "")
    if cuarentenas:
        cuarentena = cuarentenas[0]
        nota = cuarentena / "07_Knowledge" / "nota-rc.md"
        igual = nota.exists() and hashlib.sha256(
            nota.read_bytes()).hexdigest() == hashlib.sha256(
            (contenido + "\n").encode("utf-8")).hexdigest()
        paso("cuarentena conserva la nota por hash", igual)
    paso("vault reinicializado", (RT / "00_System").is_dir())
    paso("locks preservado (si existia)", (not cuarentenas or not (cuarentenas[0] / ".locks").exists()) or (RT / ".locks").is_dir())

    # RESTORE desde la cuarentena manual (recuperacion verificable)
    if cuarentenas:
        _sh.copytree(cuarentena, RT, dirs_exist_ok=True)
        manifest = RT / ".cuarentena.json"
        if manifest.exists():
            manifest.unlink()
        paso("restore manual desde cuarentena",
             (RT / "07_Knowledge" / "nota-rc.md").exists())
        r = subprocess.run([str(cli), "run", "vault_read", "--path",
                            "07_Knowledge/nota-rc.md"],
                           capture_output=True, text=True, env=env)
        paso("nota restaurada legible por CLI", '"ok": true' in r.stdout.lower())

    # MCP: inicializar + tools + leer la nota
    mcpjs = VENV / "Lib" / "site-packages" / "vault_toolkit" / "mcp" / \
        "vault-mcp-server.mjs"
    envmcp = dict(env, VAULT_MCP_PYTHON=str(py))
    peticiones = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "r07", "version": "1"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "vault_read",
                    "arguments": {"path": "07_Knowledge/nota-rc.md"}}},
    ]
    entrada = "\n".join(json.dumps(x) for x in peticiones) + "\n"
    r = subprocess.run(["node", str(mcpjs)], input=entrada,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=envmcp, timeout=300)
    respuestas = {}
    for linea in r.stdout.splitlines():
        if linea.strip().startswith("{"):
            try:
                dato = json.loads(linea)
                if "id" in dato:
                    respuestas[dato["id"]] = dato
            except ValueError:
                pass
    tools = ((respuestas.get(2) or {}).get("result") or {}).get("tools") or []
    texto = json.dumps(respuestas.get(3) or {}, ensure_ascii=False)
    paso("MCP initialize", "serverInfo" in json.dumps(respuestas.get(1) or {}))
    paso("MCP tools/list", len(tools) > 0, f"{len(tools)} tools")
    paso("MCP lee la nota", "linea tres" in texto or "linea tres" in texto.replace("\\n", "\n"))

    print("\nRESUMEN")
    fallos = [p for p in PASOS if not p[1]]
    for nombre, ok, detalle in PASOS:
        print(("OK  " if ok else "FALLO"), nombre)
    print(f"\n{len(PASOS) - len(fallos)}/{len(PASOS)} pasos correctos")
    print("whl_sha256:", h_whl)
    print("sdist_sha256:", h_sdist)
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())

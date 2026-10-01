"""El servidor MCP viaja en la wheel y funciona sin checkout (P3, v40.34).

Hasta aquí el único camino para levantarlo era clonar el repo: el `.mjs`
resolvía `scripts/` como `../../scripts` desde su propio directorio, y en una
instalación eso no existe — las tools viven en `vault_toolkit/_impl/`. La
promesa `mcp_requiere_checkout` de `vault_produccion` lo declaraba descubierto.

Estos tests reproducen el diseño instalado en `tmp_path` (la misma forma que
deja la wheel: `vault_toolkit/mcp/` junto a `vault_toolkit/_impl/`) y hablan
con el servidor por stdio, que es el criterio del consumidor (AP-44). La
instalación real en un venv limpio la ejerce `tests/clean_install_gate.py`.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
MCP = RAIZ / "mcp" / "nodejs"
FICHEROS_DEL_SERVIDOR = ("vault-mcp-server.mjs", "tools-catalog.json", "env-table.json")

requiere_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="el servidor MCP necesita Node en el PATH"
)


def _instalacion(destino: Path, *, sin=()) -> Path:
    """`site-packages` mínimo con la forma de la wheel. Devuelve el `.mjs`."""
    fuera = set(json.loads(
        (RAIZ / "empaquetado" / "fuera-de-la-wheel.json").read_text(encoding="utf-8")
    )["modulos"]) | set(sin)
    basura = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(RAIZ / "vault", destino / "vault", ignore=basura)
    shutil.copytree(RAIZ / "vault_toolkit", destino / "vault_toolkit", ignore=basura)
    impl = destino / "vault_toolkit" / "_impl"
    impl.mkdir()
    for f in (RAIZ / "scripts").glob("*.py"):
        if f.stem not in fuera:
            shutil.copy2(f, impl / f.name)
    mcp = destino / "vault_toolkit" / "mcp"
    mcp.mkdir()
    for nombre in FICHEROS_DEL_SERVIDOR:
        shutil.copy2(MCP / nombre, mcp / nombre)
    return mcp / "vault-mcp-server.mjs"


def _vault(destino: Path) -> Path:
    destino.mkdir(parents=True)
    for carpeta in ("00_System", "01_Projects", "99_Index"):
        (destino / carpeta).mkdir()
    return destino


def _entorno(site: Path, **extra) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("VAULT_ROOT", "PYTHONPATH")}
    env.update({"PYTHONPATH": str(site), "VAULT_MCP_PYTHON": sys.executable,
                "PYTHONIOENCODING": "utf-8"})
    env.update(extra)
    return env


def _sesion(servidor: Path, cwd: Path, env: dict, llamadas) -> tuple:
    """Envía initialize + las llamadas y cierra stdin: el servidor espera a
    las operaciones pendientes antes de salir. Devuelve (rc, respuestas, stderr)."""
    mensajes = [
        {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    ]
    for i, (metodo, params) in enumerate(llamadas, start=1):
        mensajes.append({"jsonrpc": "2.0", "id": i, "method": metodo, "params": params})
    r = subprocess.run(
        ["node", str(servidor)], input="".join(json.dumps(m) + "\n" for m in mensajes),
        cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=300,
    )
    respuestas = {}
    for linea in r.stdout.splitlines():
        try:
            m = json.loads(linea)
        except ValueError:
            continue
        if "id" in m:
            respuestas[m["id"]] = m
    return r.returncode, respuestas, r.stderr


@requiere_node
def test_instalado_el_servidor_lanza_las_tools_desde_impl(tmp_path):
    site = tmp_path / "site"
    servidor = _instalacion(site)
    vault = _vault(tmp_path / "vault")
    rc, resp, err = _sesion(servidor, vault, _entorno(site, VAULT_ROOT=str(vault)), [
        ("tools/list", {}),
        ("tools/call", {"name": "vault_query_parse", "arguments": {"query": "notas de la api"}}),
    ])
    assert rc == 0, err[-2000:]
    nombres = {t["name"] for t in resp[1]["result"]["tools"]}
    assert "vault_query_parse" in nombres and "vault_write" in nombres
    texto = resp[2]["result"]["content"][0]["text"]
    payload = json.loads(texto)
    assert payload.get("ok") is True, texto[:2000]
    # AP-36: nada se escribe dentro de la instalación.
    assert not (site / "vault-sandbox").exists()
    assert not list(site.rglob("*.jsonl"))


@requiere_node
def test_instalado_el_handshake_responde_por_stdio(tmp_path):
    """Sin respuesta a `initialize` ningún cliente MCP llega a pedir tools.

    Medido en v40.34 con la wheel instalada: en stdio, `handleInitialize`
    asignaba a un `clientInfo` que nunca se declaró —`ReferenceError` en un
    módulo ES— y el servidor no contestaba al primer mensaje. `_sesion`
    enviaba `initialize` en cada test pero ninguno miraba su respuesta.
    """
    site = tmp_path / "site"
    servidor = _instalacion(site)
    vault = _vault(tmp_path / "vault")
    rc, resp, err = _sesion(servidor, vault, _entorno(site, VAULT_ROOT=str(vault)), [])
    assert rc == 0, err[-2000:]
    assert "error" not in resp.get(0, {}), resp.get(0)
    assert resp.get(0, {}).get("result", {}).get("serverInfo"), err[-2000:]


@requiere_node
def test_instalado_una_tool_sin_script_no_se_ofrece(tmp_path):
    """Lo que no viaja en la wheel no sale en `tools/list` ni se ejecuta."""
    site = tmp_path / "site"
    servidor = _instalacion(site, sin=("vault_query_parse",))
    vault = _vault(tmp_path / "vault")
    rc, resp, err = _sesion(servidor, vault, _entorno(site, VAULT_ROOT=str(vault)), [
        ("tools/list", {}),
        ("tools/call", {"name": "vault_query_parse", "arguments": {"query": "x"}}),
    ])
    assert rc == 0, err[-2000:]
    assert "vault_query_parse" not in {t["name"] for t in resp[1]["result"]["tools"]}
    assert resp[2]["result"].get("isError") is True
    assert "vault_query_parse" in err  # se avisa de qué falta, no se calla


@requiere_node
def test_instalado_sin_vault_no_cae_dentro_de_la_instalacion(tmp_path):
    site = tmp_path / "site"
    servidor = _instalacion(site)
    vacio = tmp_path / "vacio"
    vacio.mkdir()
    rc, _, err = _sesion(servidor, vacio, _entorno(site), [("tools/list", {})])
    assert rc != 0
    assert "VAULT_ROOT" in err
    assert not (site / "vault-sandbox").exists()
    assert not (site / "vault_toolkit" / "vault-sandbox").exists()


@requiere_node
def test_instalado_el_cwd_del_cliente_vale_como_vault(tmp_path):
    site = tmp_path / "site"
    servidor = _instalacion(site)
    vault = _vault(tmp_path / "vault")
    rc, resp, err = _sesion(servidor, vault, _entorno(site), [("tools/list", {})])
    assert rc == 0, err[-2000:]
    assert resp[1]["result"]["tools"]


def _mcp_path(site_o_none, cwd: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    if site_o_none is not None:
        env["PYTHONPATH"] = str(site_o_none)
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run(
        [sys.executable, "-c", "import sys; from vault.product_cli import main; "
         "sys.exit(main(['mcp-path']))"],
        cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_mcp_path_apunta_al_servidor_instalado(tmp_path):
    site = tmp_path / "site"
    servidor = _instalacion(site)
    d = _mcp_path(site, tmp_path)
    assert Path(d["server"]).resolve() == servidor.resolve()
    assert d["config"]["command"] == "node"
    assert d["config"]["args"] == [d["server"]]
    assert d["config"]["env"]["VAULT_MCP_PYTHON"] == sys.executable
    assert "VAULT_ROOT" in d["config"]["env"]


def test_mcp_path_en_el_checkout_apunta_al_del_repo():
    d = _mcp_path(None, RAIZ)
    assert Path(d["server"]).resolve() == (MCP / "vault-mcp-server.mjs").resolve()


def test_la_wheel_declara_el_servidor_como_package_data():
    tomllib = pytest.importorskip("tomllib")
    st = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]
    assert st["package-dir"]["vault_toolkit.mcp"] == "mcp/nodejs"
    assert "vault_toolkit.mcp" in st["packages"]
    assert sorted(st["package-data"]["vault_toolkit.mcp"]) == sorted(FICHEROS_DEL_SERVIDOR)

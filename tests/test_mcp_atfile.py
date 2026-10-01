"""AP-36 — por MCP, `@file:<ruta>` no lee el disco de quien instala esto.

`@file:` es una comodidad de la CLI: quien la escribe lee su propio disco.
Medido en v40.34 por MCP, la ruta la elegía el agente y la leía el proceso
hijo: `vault_write` con `content: "@file:<cualquier fichero>"` copiaba ese
fichero a una nota del vault —y al índice de búsqueda— con `ok: true`, sin
pasar por el pre-vuelo anti-poison de `vault_ingest`. El catálogo lo
anunciaba en la descripción de `content`.

Se comprueba con el criterio del consumidor (AP-44): sesión JSON-RPC real.
"""

import json
import shutil
from pathlib import Path

import pytest

from test_mcp_runner import SesionMCP, _init_vault

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOGO = REPO_ROOT / "mcp" / "nodejs" / "tools-catalog.json"
SECRETO = "FUERA-DEL-VAULT"
AUTOR = json.dumps({"agent": "pytest"})

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="el servidor MCP necesita Node en el PATH"
)


@pytest.fixture(scope="module")
def entorno(tmp_path_factory):
    base = tmp_path_factory.mktemp("mcpatfile")
    vault = _init_vault(base / "vault")
    (vault / "07_Knowledge").mkdir(exist_ok=True)
    secreto = base / "secreto.txt"
    secreto.write_text(
        "\n".join(f"{SECRETO} línea {i} de un fichero que no es del vault" for i in range(4)),
        encoding="utf-8",
    )
    sesion = SesionMCP(vault)
    yield vault, secreto, sesion
    sesion.cerrar()


def _envelope(respuesta) -> dict:
    return json.loads(respuesta["result"]["content"][0]["text"])


def _sin_secreto(vault: Path) -> None:
    for f in vault.rglob("*"):
        if f.is_file() and f.suffix in (".md", ".json"):
            assert SECRETO not in f.read_text(encoding="utf-8", errors="replace"), f


@pytest.mark.parametrize("prefijo", ["@file:", "  @file:"])
def test_content_con_arroba_file_no_lee_el_disco(entorno, prefijo):
    vault, secreto, sesion = entorno
    env = _envelope(sesion.llamar("vault_write", {
        "folder": "07_Knowledge", "title": "fuga", "tags": ["demo"],
        "content": f"{prefijo}{secreto}", "author": AUTOR,
    }))
    assert env["ok"] is False and env["error_code"] == "INVALID_ARGS", env
    assert "@file:" in env["message"]
    _sin_secreto(vault)


def test_un_elemento_de_lista_con_arroba_file_tambien_se_rechaza(entorno):
    _, secreto, sesion = entorno
    env = _envelope(sesion.llamar("vault_write", {
        "folder": "07_Knowledge", "title": "fuga2", "content": "x\ny\nz",
        "tags": ["demo", f"@file:{secreto}"],
    }))
    assert env["ok"] is False and env["error_code"] == "INVALID_ARGS", env


def test_el_catalogo_no_anuncia_arroba_file_por_mcp():
    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    tools = catalogo["tools"] if isinstance(catalogo, dict) and "tools" in catalogo else catalogo
    for nombre, tool in (tools.items() if isinstance(tools, dict) else ((t["name"], t) for t in tools)):
        for clave, prop in (tool.get("inputSchema", {}).get("properties", {}) or {}).items():
            descripcion = prop.get("description", "")
            if "@file:" in descripcion:
                assert "CLI" in descripcion, f"{nombre}.{clave}: {descripcion}"

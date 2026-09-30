"""AP-40 en la dirección inversa — el servidor MCP no acepta lo que no publica.

AP-40 nació para que el catálogo no publicara params que la CLI rechaza. Medido
en v40.34 desde el otro lado, el servidor no miraba el catálogo al recibir una
llamada: convertía **cualquier** clave en `--clave`, publicada o no. Tres
consecuencias, todas desde un agente con una sesión abierta:

1. `root` no se publicaba por MCP para varias tools, pero se aceptaba igual: un
   `vault_graph_fix` con `root` y `apply` escribía en la carpeta que el agente
   nombrara, no en el vault de la sesión.
2. Las tools con `exposed_via_mcp: false` (`vault_norms`, `vault_foreign_check`)
   no salían en `tools/list` y sí se ejecutaban en `tools/call`.
3. Un valor que empezaba por `-` se leía como flag: `tags: ["--x"]` o un
   `content` que empezara por `--` cambiaban la línea de órdenes del hijo.

Y el esquema publicaba todo como `string`, así que un cliente que validaba
contra él no podía mandar `tags` como lista.

Se comprueba con el criterio del consumidor (AP-44): sesión JSON-RPC real.
"""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from test_mcp_runner import SesionMCP, _init_vault

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOGO = REPO_ROOT / "mcp" / "nodejs" / "tools-catalog.json"
#: El `contentGate` del servidor pide al menos tres líneas y diez palabras.
CUERPO = "\n".join(f"Línea {i} de una nota con cuerpo suficiente." for i in range(4))
AUTOR = json.dumps({"agent": "pytest"})

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="el servidor MCP necesita Node en el PATH"
)


@pytest.fixture(scope="module")
def vault(tmp_path_factory):
    v = _init_vault(tmp_path_factory.mktemp("mcpargs") / "vault")
    (v / "07_Knowledge").mkdir(exist_ok=True)
    return v


@pytest.fixture(scope="module")
def sesion(vault):
    s = SesionMCP(vault)
    yield s
    s.cerrar()


def _envelope(respuesta) -> dict:
    return json.loads(respuesta["result"]["content"][0]["text"])


def _nota(vault: Path, titulo_slug: str) -> Path:
    candidatas = list((vault / "07_Knowledge").glob(f"{titulo_slug}*.md"))
    assert len(candidatas) == 1, candidatas
    return candidatas[0]


def _frontmatter(ruta: Path) -> dict:
    texto = ruta.read_text(encoding="utf-8")
    return yaml.safe_load(texto.split("---", 2)[1])


def test_ap40_una_clave_no_publicada_no_llega_al_hijo(sesion, tmp_path):
    ajena = tmp_path / "ajena"
    (ajena / "07_Knowledge").mkdir(parents=True)
    (ajena / "07_Knowledge" / "n.md").write_text("[[[[rota]]\n", encoding="utf-8")
    antes = sorted(p.relative_to(ajena) for p in ajena.rglob("*"))

    env = _envelope(sesion.llamar("vault_graph_fix", {"root": str(ajena), "apply": True}))

    assert env["ok"] is False and env["error_code"] == "INVALID_ARGS", env
    assert "root" in env["message"]
    assert sorted(p.relative_to(ajena) for p in ajena.rglob("*")) == antes


def test_una_tool_no_expuesta_no_se_ejecuta(sesion):
    env = _envelope(sesion.llamar("vault_norms", {}))
    assert env["error_code"] == "tool_not_found", env


def test_un_booleano_que_no_lo_es_se_rechaza(sesion):
    env = _envelope(sesion.llamar("vault_graph_fix", {"apply": "quizas"}))
    assert env["error_code"] == "INVALID_ARGS", env


def test_un_enum_fuera_de_rango_se_rechaza(sesion):
    env = _envelope(sesion.llamar("vault_graph_fix", {"only": "todo"}))
    assert env["error_code"] == "INVALID_ARGS", env
    assert "brackets" in env["message"]


def test_un_obligatorio_ausente_se_rechaza_sin_ejecutar(sesion):
    env = _envelope(sesion.llamar("vault_read", {}))
    assert env["error_code"] == "INVALID_ARGS", env
    assert "path" in env["message"]


def test_un_elemento_de_lista_con_guion_no_se_lee_como_flag(sesion):
    env = _envelope(sesion.llamar("vault_write", {
        "folder": "07_Knowledge", "title": "Inyectada", "content": "x",
        "tags": ["api", "--meta-file"],
    }))
    assert env["error_code"] == "INVALID_ARGS", env


def test_las_tags_como_lista_llegan_como_dos_tags(sesion, vault):
    env = _envelope(sesion.llamar("vault_write", {
        "folder": "07_Knowledge", "title": "Dos tags",
        "content": CUERPO,
        "tags": ["api", "demo"], "meta": AUTOR,
    }))
    assert env["ok"] is True, env
    tags = _frontmatter(_nota(vault, "dos-tags"))["tags"]
    assert "api" in tags and "demo" in tags


def test_un_valor_que_empieza_por_guiones_es_un_valor(sesion, vault):
    env = _envelope(sesion.llamar("vault_write", {
        "folder": "07_Knowledge", "title": "Guiones",
        # Sin espacios a propósito: argparse ya trata como valor un argumento
        # con guion inicial que contiene un espacio, y eso taparía el defecto.
        "content": "\n".join(["--help"] + [f"--palabra-{i}" for i in range(12)]),
        "tags": ["demo"], "meta": AUTOR,
    }))
    assert env["ok"] is True, env
    assert "--help" in _nota(vault, "guiones").read_text(encoding="utf-8")


def test_ap40_el_esquema_publica_el_tipo_real_y_se_cierra():
    """Lado Python: lo que el servidor valida es lo que el catálogo publica."""
    tools = json.loads(CATALOGO.read_text(encoding="utf-8"))["tools"]
    tipos = set()
    for nombre, entrada in tools.items():
        schema = entrada.get("inputSchema") or {}
        assert schema.get("additionalProperties") is False, nombre
        props = schema.get("properties", {})
        assert not {"root", "vault-root", "vault_root"} & set(props), nombre
        tipos |= {p["type"] for p in props.values()}
    assert {"boolean", "array"} <= tipos
    assert tools["vault_write"]["inputSchema"]["properties"]["tags"]["type"] == "array"

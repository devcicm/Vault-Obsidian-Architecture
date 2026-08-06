"""AP-48 — una tool publicada tiene una implementación, no dos.

El servidor MCP resolvía nueve tools con backend nativo en Node. Siete de ellas
tenían además script Python del mismo nombre, así que cuál se ejecutaba dependía
de por dónde entrase el llamante: la suite y `vault_smoke` ejercitaban el `.py`,
el agente real recibía el JS, y las dos cosas estaban verdes.

Lo que estos tests fijan es la parte que no se ve leyendo el código: que el
envelope que **sale por MCP** cubre el contrato publicado, y que el side effect
declarado ocurre de verdad. `vault_graph` es el caso que motivó la norma —
`ok: true` sin un solo `writeFile`, o sea el índice desfasado (AP-47) servido
por el único camino que un agente usa.
"""

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
SERVIDOR = REPO_ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs"
sys.path.insert(0, str(SCRIPTS))

from vault_mcp_catalog import check_contracts  # noqa: E402
from vault_norms import NORM_CATALOG  # noqa: E402


def _js_native() -> list:
    m = re.search(
        r"const JS_NATIVE_TOOLS = new Set\(\[(.*?)\]\)",
        SERVIDOR.read_text(encoding="utf-8"), re.S,
    )
    assert m, "JS_NATIVE_TOOLS dejó de ser legible: el guard de AP-48 mide sobre esto"
    return sorted(set(re.findall(r'"(vault_[a-z0-9_]+)"', m.group(1))))


# ── La norma ──────────────────────────────────────────────────────────────────

def test_la_norma_existe_y_tiene_enforcement_real():
    norma = next((n for n in NORM_CATALOG if n["code"] == "AP-48"), None)
    assert norma, "AP-48 desapareció del catálogo"
    assert norma["enforcement"] in {"guard", "audit", "guard+audit", "recommended"}


# ── El guard ──────────────────────────────────────────────────────────────────

def test_ninguna_nativa_tiene_script_python():
    """El invariante, comprobado sobre el fichero que se ejecuta."""
    con_script = [t for t in _js_native() if (SCRIPTS / f"{t}.py").is_file()]
    assert not con_script, (
        f"tools con backend nativo y script a la vez: {con_script}. "
        f"Dos implementaciones bajo un nombre y un contrato (AP-48)."
    )


def test_check_contracts_reporta_la_implementacion_paralela():
    """La puerta lo dice, no solo este test."""
    r = check_contracts()
    assert r["ok"], [p for p in r["problems"]]
    assert r["js_native"], "el guard dejó de encontrar la lista de nativas"


def test_el_guard_caza_una_reincidencia(tmp_path, monkeypatch):
    """Si alguien devuelve `vault_graph` al backend nativo, la puerta falla.

    Se comprueba contra un servidor de mentira en vez de editar el real: lo que
    se está probando es el guard, y un guard que solo se ejerce cuando el repo
    está roto no se ejerce nunca.
    """
    import vault_mcp_catalog as vmc

    falso = tmp_path / "mcp" / "nodejs"
    falso.mkdir(parents=True)
    (falso / "vault-mcp-server.mjs").write_text(
        'const JS_NATIVE_TOOLS = new Set([\n  "vault_graph", "vault_backup_base64",\n]);\n',
        encoding="utf-8",
    )
    # `check_contracts` deriva la ruta del servidor de la del propio módulo.
    monkeypatch.setattr(vmc, "__file__", str(tmp_path / "scripts" / "vault_mcp_catalog.py"))
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "vault_graph.py").write_text("# stub\n", encoding="utf-8")
    (tmp_path / "scripts" / "README.md").write_text(
        (SCRIPTS / "README.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    r = vmc.check_contracts(str(REPO_ROOT / "vault-sandbox" / "00_System" / "tool-spec.json"))
    paralelas = [p for p in r["problems"] if p["kind"] == "implementacion_paralela"]
    assert paralelas and "vault_graph" in paralelas[0]["detail"], r["problems"]
    assert r["ok"] is False


# ── El comportamiento, por el camino del agente ───────────────────────────────

@pytest.fixture(scope="module")
def sesion():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mr", Path(__file__).resolve().parent / "test_mcp_runner.py"
    )
    mr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mr)
    s = mr.SesionMCP(REPO_ROOT / "vault-sandbox")
    yield s
    s.cerrar()


def _envelope(sesion, tool, args):
    return json.loads(sesion.llamar(tool, args)["result"]["content"][0]["text"])


def test_vault_graph_por_mcp_escribe_el_grafo():
    """El defecto que motivó la norma, comprobado por efecto y no por envelope.

    El backend nativo devolvía `ok: true`, `totalNodes` y `totalEdges` sin tocar
    el disco. Un agente lo leía como «grafo regenerado» y seguía trabajando
    sobre un índice viejo.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mr", Path(__file__).resolve().parent / "test_mcp_runner.py"
    )
    mr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mr)

    vault = REPO_ROOT / "vault-sandbox"
    grafo = vault / "99_Index" / "graph.json"
    antes = grafo.stat().st_mtime_ns if grafo.exists() else None

    s = mr.SesionMCP(vault)
    try:
        env = json.loads(s.llamar("vault_graph", {})["result"]["content"][0]["text"])
    finally:
        s.cerrar()

    assert env.get("savedTo"), f"vault_graph por MCP no declara dónde escribió: {sorted(env)}"
    assert grafo.exists() and grafo.stat().st_mtime_ns != antes, (
        "vault_graph por MCP devolvió ok sin tocar 99_Index/graph.json"
    )


@pytest.mark.parametrize("tool,args", [
    ("vault_search", {"query": "vault"}),
    ("vault_graph_inspect", {}),
])
def test_el_envelope_de_mcp_cubre_su_contrato(sesion, tool, args):
    """Criterio del consumidor (AP-44): se mide lo que sale por MCP.

    Los `declared_returns` son la unión sobre todos los modos de la tool, así
    que un campo condicionado a otra invocación puede faltar legítimamente. Lo
    que no puede es faltar **todo**, que es lo que pasaba: los envelopes nativos
    no compartían un solo campo con el contrato.
    """
    contratos = json.loads(
        (REPO_ROOT / "vault-sandbox" / "00_System" / "tool-spec.json")
        .read_text(encoding="utf-8")
    )["tools"]
    declarados = set(contratos[tool]["declared_returns"]) - {
        "error", "error_code", "message"
    }
    envelope = _envelope(sesion, tool, args)
    faltan = sorted(declarados - set(envelope))
    assert not faltan, (
        f"{tool} por MCP no devuelve {faltan}; su contrato declara "
        f"{sorted(declarados)} y el envelope trae {sorted(envelope)}"
    )

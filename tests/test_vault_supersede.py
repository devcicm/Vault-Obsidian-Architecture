"""`vault_supersede` — anota `superseded_by:` en una nota existente sin tocar su cuerpo.

Medido el 2026-10-07 al sanar una copia de /ans: el procedimiento de sanación
pide anotar la sustituida de un par AP-17, y ninguna tool podía hacerlo:
`vault_write` reescribe el cuerpo y su `--meta` no admite la clave. Hubo que
editar la copia a mano. Se ejecuta por subprocess con `VAULT_ROOT` y
`VAULT_STRICT_ROOT=1`, como la ve un consumidor.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

CUERPO = "\n# Guía MCP\n\nCuerpo con [[enlace]] y `codigo`.\n\n- uno\n- dos\n"


def _ejecutar(raiz: Path, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_supersede.py"), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="system"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=300,
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


def _nota(raiz: Path, rel: str, fm: str) -> Path:
    p = raiz / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(f"---\n{fm}\n---\n{CUERPO}".encode("utf-8"))
    return p


def _fm(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8").split("---", 2)[1])


@pytest.fixture
def raiz(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge", "10_Migrated", "99_Index"):
        (raiz / seccion).mkdir(parents=True)
    _nota(raiz, "07_Knowledge/mcp-agent-guide.md", "title: Mcp Agent Guide\nstatus: draft")
    return raiz


def test_por_defecto_mide_y_no_escribe(raiz):
    gemela = _nota(raiz, "10_Migrated/MCP_AGENT_GUIDE.md", "title: Mcp Agent Guide")
    antes = gemela.read_bytes()
    r = _ejecutar(raiz, "--path", "10_Migrated/MCP_AGENT_GUIDE.md", "--by", "mcp-agent-guide")
    assert r["ok"] and r["written"] is False and r["action"] == "check", r
    assert r["superseded_by"] == "[[mcp-agent-guide]]"
    assert gemela.read_bytes() == antes


def test_apply_anota_y_el_cuerpo_queda_byte_a_byte(raiz):
    gemela = _nota(raiz, "10_Migrated/MCP_AGENT_GUIDE.md",
                   "title: Mcp Agent Guide\ntags: [mcp, guia]")
    r = _ejecutar(raiz, "--path", "10_Migrated/MCP_AGENT_GUIDE.md",
                  "--by", "[[mcp-agent-guide]]", "--apply")
    assert r["ok"] and r["written"] is True, r
    assert r["canonical"] == "07_Knowledge/mcp-agent-guide.md"
    fm = _fm(gemela)  # criterio del consumidor: yaml.safe_load (AP-44)
    assert fm["superseded_by"] == "[[mcp-agent-guide]]"
    assert fm["title"] == "Mcp Agent Guide" and fm["tags"] == ["mcp", "guia"]
    antes = "\n" + CUERPO  # lo que sigue al `---` de cierre en la nota original
    assert gemela.read_text(encoding="utf-8").split("---", 2)[2] == antes


def test_el_par_sale_de_la_deuda_ap17_del_audit(raiz):
    """La tool y el audit leen la anotación igual: lo que una escribe, el otro lo salda."""
    gemela = _nota(raiz, "10_Migrated/MCP_AGENT_GUIDE.md", "title: Mcp Agent Guide")
    assert _ejecutar(raiz, "--path", "10_Migrated/MCP_AGENT_GUIDE.md",
                     "--by", "mcp-agent-guide", "--apply")["written"] is True
    sys.path.insert(0, str(SCRIPTS))
    import vault_audit
    import vault_io
    vault_io.set_vault_root(raiz)
    resueltos: list = []
    pares = vault_audit._detect_canonical_shadow(
        [raiz / "07_Knowledge/mcp-agent-guide.md", gemela], resueltos=resueltos)
    assert pares == [] and len(resueltos) == 1


def test_la_misma_anotacion_otra_vez_no_escribe(raiz):
    _nota(raiz, "10_Migrated/MCP_AGENT_GUIDE.md",
          'title: Mcp Agent Guide\nsuperseded_by: "[[mcp-agent-guide]]"')
    r = _ejecutar(raiz, "--path", "10_Migrated/MCP_AGENT_GUIDE.md",
                  "--by", "mcp-agent-guide", "--apply")
    assert r["ok"] and r["written"] is False and r["already"] is True, r


def test_otra_decision_ya_tomada_no_se_pisa_sin_replace(raiz):
    _nota(raiz, "07_Knowledge/otra.md", "title: Otra")
    gemela = _nota(raiz, "10_Migrated/MCP_AGENT_GUIDE.md",
                   'title: Mcp Agent Guide\nsuperseded_by: "[[otra]]"')
    r = _ejecutar(raiz, "--path", "10_Migrated/MCP_AGENT_GUIDE.md",
                  "--by", "mcp-agent-guide", "--apply")
    assert r["ok"] is False and r["error_code"] == "INVALID_VALUE", r
    assert "--replace" in r["recovery"]["hint"]
    assert _fm(gemela)["superseded_by"] == "[[otra]]"
    r = _ejecutar(raiz, "--path", "10_Migrated/MCP_AGENT_GUIDE.md",
                  "--by", "mcp-agent-guide", "--apply", "--replace")
    assert r["written"] is True and r["previous"] == "[[otra]]", r
    assert _fm(gemela)["superseded_by"] == "[[mcp-agent-guide]]"


@pytest.mark.parametrize("by,codigo", [
    ("no-existe", "NOTE_NOT_FOUND"),
    ("Mcp Agent Guide", "NOTE_NOT_FOUND"),   # un title: no resuelve (AP-44)
    ("MCP_AGENT_GUIDE", "INVALID_VALUE"),    # la nota a sí misma
])
def test_un_destino_que_no_es_otra_nota_se_rechaza_sin_escribir(raiz, by, codigo):
    gemela = _nota(raiz, "10_Migrated/MCP_AGENT_GUIDE.md", "title: Mcp Agent Guide")
    antes = gemela.read_bytes()
    r = _ejecutar(raiz, "--path", "10_Migrated/MCP_AGENT_GUIDE.md", "--by", by, "--apply")
    assert r["ok"] is False and r["error_code"] == codigo, r
    assert gemela.read_bytes() == antes


def test_un_destino_ambiguo_pide_la_carpeta(raiz):
    _nota(raiz, "10_Migrated/mcp-agent-guide.md", "title: Copia")
    _nota(raiz, "10_Migrated/MCP_AGENT_GUIDE.md", "title: Mcp Agent Guide")
    r = _ejecutar(raiz, "--path", "10_Migrated/MCP_AGENT_GUIDE.md",
                  "--by", "mcp-agent-guide", "--apply")
    assert r["ok"] is False and r["error_code"] == "INVALID_VALUE", r
    assert sorted(r["candidates"]) == ["07_Knowledge/mcp-agent-guide.md",
                                       "10_Migrated/mcp-agent-guide.md"]
    r = _ejecutar(raiz, "--path", "10_Migrated/MCP_AGENT_GUIDE.md",
                  "--by", "07_Knowledge/mcp-agent-guide", "--apply")
    assert r["written"] is True, r
    # El enlace que escribe es el más corto que resuelve a una sola nota.
    assert r["superseded_by"] == "[[07_Knowledge/mcp-agent-guide]]"


def test_un_ciclo_se_rechaza(raiz):
    _nota(raiz, "07_Knowledge/mcp-agent-guide.md",
          'title: Mcp Agent Guide\nsuperseded_by: "[[MCP_AGENT_GUIDE]]"')
    _nota(raiz, "10_Migrated/MCP_AGENT_GUIDE.md", "title: Mcp Agent Guide")
    r = _ejecutar(raiz, "--path", "10_Migrated/MCP_AGENT_GUIDE.md",
                  "--by", "mcp-agent-guide", "--apply")
    # INVALID_VALUE y no CIRCULAR_WIKILINK: la recuperación de ese manda a
    # vault_graph_fix, que rompe ciclos de enlaces del cuerpo y no deshace esta
    # decisión. Una pista que no lleva a salir es peor que ninguna.
    assert r["ok"] is False and r["error_code"] == "INVALID_VALUE", r
    assert "ciclo" in r["recovery"]["hint"]


def test_fuera_del_vault_se_rechaza(raiz):
    r = _ejecutar(raiz, "--path", "../fuera.md", "--by", "mcp-agent-guide", "--apply")
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH", r

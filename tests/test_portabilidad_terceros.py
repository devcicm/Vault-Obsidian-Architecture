"""The toolkit runs off this machine and for third parties (S5, QA-PORT-*).

Measured 2026-11-17 by the portability audit (wheel on python:3.12-slim, paths
with a space and `ñ`, MCP stdio on node 22):

- QA-PORT-02 / QA-PORT-04: the encoding trace and the security-scan notes wrote
  the absolute path of the person's machine into the vault (`C:\\Users\\<user>\\...`),
  so a vault shared with someone else carried the author's identity.
- QA-PORT-05: recovery hints said `python scripts/<tool>.py`, which an installed
  wheel does not have; `vault.kernel.registry.comando_de_tool` renders the form
  that runs where the code runs.
- QA-PORT-06: the MCP orchestrator spawned `["python", ...]`; Debian and Ubuntu
  ship no `python`, only `python3`.
- QA-PORT-07 / QA-PORT-08: the shell installers called bare `pip`/`python`
  (PEP 668 refuses system pip; without `python` the check reported FAIL) and
  the Python installer linked the server without its executable bit.
- QA-PORT-09: `vault mcp-path` answered `ok: true` for a vault that does not
  exist and for a machine without Node.
- QA-PORT-12: the MCP server hard-coded the Obsidian REST API URL.

The static guards are scoped to what can be checked without a second machine:
argv[0] literals in the `vault/` modules the wheel ships, `localhost` URLs in
the `.mjs`, and the `scripts/` hints of the modules fixed here (a general rule
over every string in `vault/` would flag docstrings and maintenance-only tools).
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

import pytest

from apoyo import ROOT, correr_python, correr_tool, entorno

import vault_grafo_import
import vault_io


def _texto(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _formas_de(ruta: Path) -> set:
    """Every spelling of an absolute path a tool could have written."""
    formas = set()
    for p in (ruta, ruta.resolve()):
        formas |= {str(p), p.as_posix(), json.dumps(str(p))[1:-1]}
    return {f.lower() for f in formas}


def _sin_rutas_de(texto: str, *rutas: Path) -> list:
    bajo = texto.lower()
    return sorted(f for r in rutas for f in _formas_de(r) if f in bajo)


# ── QA-PORT-02: the encoding trace stores vault-relative POSIX paths ────────


def test_la_traza_de_encoding_no_publica_la_ruta_de_la_maquina(tmp_path):
    vault = tmp_path / "mi vault ñ"
    vault.mkdir()
    r = correr_tool("vault_init", "--no-audit", vault=vault)
    assert r.codigo == 0 and r.envelope["ok"], r.stderr[-1500:]

    traza = vault / "00_System" / ".tool-trace.json"
    entradas = json.loads(_texto(traza))
    arreglos = [e for e in entradas if e.get("category") == "encoding_fix"]
    assert arreglos, "vault_init no longer logs encoding fixes: the probe is stale"
    for e in arreglos:
        assert not Path(e["path"]).is_absolute() and "\\" not in e["path"], e
        assert (vault / e["path"]).is_file(), e
    assert "01_Projects/00-01_projects-primer.md" in {e["path"] for e in arreglos}
    assert _sin_rutas_de(json.dumps(arreglos, ensure_ascii=False), vault, tmp_path) == []


# ── QA-PORT-04: the security scan stores paths relative to what it scanned ──


def test_el_escaneo_de_seguridad_no_publica_la_ruta_de_la_maquina(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    codigo = tmp_path / "repo ajeno" / "src"
    (codigo / "pkg").mkdir(parents=True)
    (codigo / "pkg" / "sucio.py").write_text(
        "import hashlib\nhuella = hashlib.md5(b'x')\n", encoding="utf-8")

    r = correr_tool("vault_security_scan", "--path", codigo, "--project", "", vault=vault)
    env = r.envelope
    assert r.codigo == 0 and env["ok"], r.stderr[-1500:]
    assert env["totalFindings"] >= 1, env
    assert {f["file"] for f in env["findings"]} == {"pkg/sucio.py"}, env["findings"]
    assert env["savedToVault"], env
    for guardada in env["savedToVault"]:
        assert "\\" not in guardada, guardada
        nota = vault / guardada
        assert nota.is_file(), guardada
        texto = _texto(nota)
        assert "`pkg/sucio.py:2`" in texto, texto
        assert _sin_rutas_de(texto, codigo, tmp_path) == [], guardada
    assert _sin_rutas_de(r.stdout, codigo, tmp_path) == []


# ── QA-PORT-05: hints go through `comando_de_tool` ──────────────────────────


@pytest.fixture
def vault_vacio(tmp_path):
    vault = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge"):
        (vault / seccion).mkdir(parents=True)
    vault_io.set_vault_root(vault)
    return vault


@pytest.fixture
def instalado(monkeypatch):
    """The wheel layout as `comando_de_tool` sees it (tools in `_impl/`)."""
    # A sibling of the real program directory: only its name changes, so every
    # other lookup derived from its parent (norms, catalogs) still resolves.
    monkeypatch.setattr(vault_grafo_import, "DIRECTORIO",
                        vault_grafo_import.DIRECTORIO.with_name("_impl"))


def test_subgraph_sin_grafo_da_la_pista_que_corre_instalada(vault_vacio, instalado):
    import vault_subgraph

    r = vault_subgraph.vault_subgraph(["x"])
    assert r["ok"] is False and r["error_code"] == "GRAPH_MISSING", r
    assert r["hint"] == "vault run vault_graph", r


def test_subgraph_sin_grafo_en_el_checkout_sigue_dando_el_script(tmp_path):
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    r = correr_tool("vault_subgraph", "--seeds", "x", vault=vault)
    assert r.envelope["error_code"] == "GRAPH_MISSING", r.envelope
    assert r.envelope["hint"] == "python scripts/vault_graph.py", r.envelope


def test_completar_manda_a_heal_con_la_forma_instalada(vault_vacio, instalado):
    import vault_frontmatter_completar

    rota = vault_vacio / "07_Knowledge" / "rota.md"
    roto = "---\ntitle: Overview: demo\n---\n\ncuerpo\n"
    rota.write_text(roto, encoding="utf-8")
    r = vault_frontmatter_completar.completar(apply=False)
    assert r["skipped"] == [{"path": "07_Knowledge/rota.md", "cause": "frontmatter_ilegible",
                             "hint": "vault run vault_frontmatter_heal --apply"}], r
    assert _texto(rota) == roto


#: Shipped modules whose hints were hand-written `python scripts/...` (QA-PORT-05).
#: `vault/autoria/voz.py` is fixed by its own unit (W4).
CON_PISTAS = ("vault/consulta/subgraph.py", "vault/grafo/refresco.py",
              "vault/autoria/frontmatter_completar.py")


@pytest.mark.parametrize("relativa", CON_PISTAS)
def test_las_pistas_no_escriben_la_forma_del_checkout_a_mano(relativa):
    arbol = ast.parse(_texto(ROOT / relativa))
    docstrings = {id(n.body[0].value) for n in ast.walk(arbol)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
                  and n.body and isinstance(n.body[0], ast.Expr)}
    a_mano = [n.lineno for n in ast.walk(arbol)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)
              and id(n) not in docstrings
              and re.search(r"python3? scripts/", n.value)]
    assert a_mano == [], relativa


# ── QA-PORT-06: no bare `python` as argv[0] in shipped code ─────────────────

INTERPRETES = {"python", "python3", "py"}


def _argv_con_interprete_literal(arbol: ast.AST) -> list:
    """Line numbers of list/tuple literals whose first item is an interpreter name."""
    lineas = []
    for n in ast.walk(arbol):
        if (isinstance(n, (ast.List, ast.Tuple)) and n.elts
                and isinstance(n.elts[0], ast.Constant)
                and isinstance(n.elts[0].value, str)
                and n.elts[0].value.lower() in INTERPRETES):
            lineas.append(n.lineno)
    return lineas


def _modulos_de_la_wheel():
    """`vault/` minus the subpackages the wheel leaves out (maintenance lanes)."""
    fuera = json.loads(_texto(ROOT / "empaquetado" / "fuera-de-la-wheel.json"))["subpaquetes"]
    excluidas = [ROOT.joinpath(*sub.split(".")) for sub in fuera]
    for fuente in sorted((ROOT / "vault").rglob("*.py")):
        if not any(c in fuente.parents for c in excluidas):
            yield fuente


def test_el_codigo_instalado_no_lanza_un_python_del_path():
    hallazgos = {}
    for fuente in _modulos_de_la_wheel():
        lineas = _argv_con_interprete_literal(ast.parse(_texto(fuente)))
        if lineas:
            hallazgos[fuente.relative_to(ROOT).as_posix()] = lineas
    assert hallazgos == {}, "use sys.executable, as vault/product_cli.py does"


def test_el_guard_de_interprete_muerde():
    assert _argv_con_interprete_literal(ast.parse('run(["python", "x.py"])')) == [1]
    assert _argv_con_interprete_literal(ast.parse("run([sys.executable, 'x.py'])")) == []


# ── QA-PORT-12: the Obsidian REST API URL comes from the env registry ───────

SERVIDOR = ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs"


def test_el_mjs_no_fija_urls_de_localhost():
    from vault.kernel.entorno import VARIABLES

    codigo = "\n".join(l for l in _texto(SERVIDOR).splitlines()
                       if not l.lstrip().startswith(("//", "*", "/*")))
    assert re.findall(r"https?://localhost:\d+", codigo) == []
    assert 'process.env.VAULT_OBSIDIAN_API_URL || envDefault("VAULT_OBSIDIAN_API_URL")' in codigo
    assert VARIABLES["VAULT_OBSIDIAN_API_URL"].default == "http://localhost:27124"


# ── QA-PORT-15: published examples do not carry a machine path ──────────────


@pytest.mark.parametrize("relativa", ("mcp/PLAN.md", "mcp/nodejs/vault-mcp-server.mjs"))
def test_los_ejemplos_del_servidor_no_llevan_rutas_de_windows(relativa):
    assert re.findall(r"--vault\s+\"?[A-Za-z]:[/\\]", _texto(ROOT / relativa)) == []


# ── QA-PORT-08: shell installers name their interpreter ────────────────────

INSTALADORES = ("install.sh", "install-mcp.sh", "uninstall.sh", "uninstall-mcp.sh")


@pytest.mark.parametrize("nombre", INSTALADORES)
def test_los_instaladores_shell_no_llaman_a_pip_ni_python_a_secas(nombre):
    ordenes = [l for l in _texto(ROOT / nombre).splitlines()
               if l.strip() and not l.lstrip().startswith(("#", "echo"))]
    desnudas = [l for l in ordenes
                if re.search(r"(^|[;&|(]\s*|\bthen\s+|\bdo\s+)(pip3?|python3?)\s", l.strip())]
    assert desnudas == [], nombre


def test_install_sh_dice_que_hacer_con_un_python_gestionado_por_el_sistema():
    texto = _texto(ROOT / "install.sh")
    assert '"${PYTHON:-python3}"' in texto or 'PYTHON="${PYTHON:-python3}"' in texto
    assert "EXTERNALLY-MANAGED" in texto and "venv" in texto


# ── QA-PORT-07: the Python installer leaves the server executable ──────────


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink and mode bits")
def test_install_mcp_deja_el_servidor_ejecutable(tmp_path, monkeypatch):
    import vault.install as instalador

    repo = tmp_path / "repo"
    servidor = repo / "mcp" / "nodejs" / "vault-mcp-server.mjs"
    servidor.parent.mkdir(parents=True)
    servidor.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    servidor.chmod(0o644)
    destino = tmp_path / "bin" / "vault-mcp"
    monkeypatch.setattr(instalador, "REPO_ROOT", repo)
    monkeypatch.setattr(instalador, "_destino_mcp", lambda: destino)

    assert instalador._install_mcp() == 0
    assert destino.is_symlink() and destino.resolve() == servidor.resolve()
    modo = stat.S_IMODE(servidor.stat().st_mode)
    assert modo & 0o111 == 0o111, oct(modo)
    assert modo & 0o644 == 0o644, oct(modo)


# ── QA-PORT-09: `vault mcp-path` does not hand out a config that cannot start ─


def _mcp_path(*argv, **extra):
    env = entorno(quitar=("VAULT_ROOT", "VAULT_STRICT_ROOT"), **extra)
    p = correr_python("-m", "vault", "mcp-path", *argv, env=env)
    salida = p.stdout.strip() or p.stderr.strip()
    return p.returncode, json.loads(salida[salida.index("{"):])


def test_mcp_path_rechaza_un_vault_que_no_existe(tmp_path):
    rc, d = _mcp_path("--root", tmp_path / "no-existe")
    assert rc != 0 and d["ok"] is False, d
    assert d["error_code"] == "VAULT_NOT_FOUND" and d["state"] == "RUNTIME_MISSING", d
    assert "config" not in d


def test_mcp_path_con_un_vault_que_existe_sigue_dando_la_config(tmp_path):
    rc, d = _mcp_path("--root", tmp_path)
    assert rc == 0 and d["ok"] is True, d
    assert d["config"]["env"]["VAULT_ROOT"] == str(tmp_path.resolve())
    assert d["config"]["command"] == "node"
    assert d["config"]["env"]["VAULT_MCP_PYTHON"] == d["python"]
    if shutil.which("node"):
        assert "warnings" not in d, d


def test_mcp_path_avisa_si_node_no_esta(tmp_path):
    vacio = tmp_path / "bin-vacio"
    vacio.mkdir()
    rc, d = _mcp_path("--root", tmp_path, PATH=str(vacio))
    assert rc == 0 and d["ok"] is True, d
    assert d["config"]["command"] == "node"
    assert any("Node" in w and "18" in w for w in d.get("warnings", [])), d

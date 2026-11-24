r"""AP-36 — `vault run` exempts only the params the catalog declares external.

BF-01 (brownfield onboarding, 2026-11-19): `vault run vault_onboard --project x
--path /abs/repo --dry-run`, the usage the vault-onboard skill documents, came
back PREFLIGHT_REJECTED (`absolute_path` in `path`). The CLI pre-flight applied
AP-36 to every argument whose NAME looks like a path, but some tools read (or,
like `vault_code_tag`, tag) code OUTSIDE the vault by design: the repository to
onboard, the code to scan, the file to ingest.

The registry decides, not the name: `scripts/vault_mcp_catalog.py` declares
`"ruta": "externa"` on those params, the generated catalog publishes it as
`x-ruta: externa` and the pre-flight reads it from the tool fragment. Every
other path argument keeps AP-36; `@file:` keeps AP-36 on every param; the
anti-poison and invisible-character checks still apply to external params.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from apoyo import ROOT, Corrida, correr_python

import vault_mcp_catalog as catalogo
from vault.gobernanza.base import CLAVE_RUTA, RUTA_EXTERNA
from vault.kernel.indices_structural import es_argumento_de_ruta

#: The params allowed to receive a path outside the vault. Pinned here on
#: purpose: relaxing AP-36 for one more param is a security decision that must
#: show up as a diff of this set, with its evidence in the catalog.
EXTERNAS_ESPERADAS = {
    ("vault_audit", "path"),
    ("vault_code_module", "scan-path"),
    ("vault_code_query", "scan-path"),
    ("vault_code_review", "files"),
    ("vault_code_review", "path"),
    ("vault_code_sync", "scan-dir"),
    ("vault_code_tag", "file"),
    ("vault_drift_detect", "path"),
    ("vault_flow_save", "scan-path"),
    ("vault_ingest", "file"),
    ("vault_migrate_docs", "source_path"),
    ("vault_onboard", "path"),
    ("vault_pattern_list", "scan-path"),
    ("vault_pattern_save", "scan-path"),
    ("vault_project", "path"),
    ("vault_security_scan", "path"),
}

CATALOGOS_GENERADOS = (
    ROOT / "mcp" / "nodejs" / "tools-catalog.json",
    ROOT / "vault" / "meta_toolkit" / "tools-catalog.json",
)


@pytest.fixture
def runtime(tmp_path):
    rt = tmp_path / "rt"
    p = correr_python("-m", "vault", "init", rt)
    assert p.returncode == 0, p.stderr[-1500:]
    return rt


@pytest.fixture
def repo_fuera(tmp_path):
    """A code repository outside the vault, with no git history."""
    repo = tmp_path / "repo-fuera"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n\nA demo project.\n", encoding="utf-8")
    (repo / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    return repo


def _huella(carpeta: Path, patron: str = "*") -> dict:
    return {
        str(f.relative_to(carpeta)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted(carpeta.rglob(patron)) if f.is_file()
    }


def _vault_run(rt: Path, tool: str, *argv) -> Corrida:
    p = correr_python("-m", "vault", "run", tool, *argv, vault=rt)
    # A pre-flight rejection is printed on stderr; a tool's envelope on stdout.
    return Corrida(p.returncode, p.stdout if "{" in p.stdout else p.stderr, p.stderr)


def _clases(env: dict) -> set:
    return {f.get("kind") for f in env.get("findings", [])}


# ── External params: accepted ────────────────────────────────────────────────

def test_onboard_con_ruta_absoluta_del_repo_pasa_el_preflight(runtime, repo_fuera):
    antes_repo, antes_vault = _huella(repo_fuera), _huella(runtime, "*.md")
    r = _vault_run(runtime, "vault_onboard", "--project", "x",
                   "--path", repo_fuera.resolve(), "--dry-run", "--no-git")
    env = r.envelope
    assert env.get("error_code") != "PREFLIGHT_REJECTED", env
    assert r.codigo == 0 and env["ok"] is True and env["tool"] == "vault_onboard", env
    assert env.get("dry_run") is True, env
    # Read-only on the repository, and a dry run writes no note in the vault
    # (the tool trace and voice counter are telemetry every run updates).
    assert _huella(repo_fuera) == antes_repo
    assert _huella(runtime, "*.md") == antes_vault


def test_onboard_con_ruta_relativa_al_padre_pasa_el_preflight(runtime, repo_fuera):
    """`..` on an external param is a location on the user's disk, not an escape."""
    r = correr_python("-m", "vault", "run", "vault_onboard", "--project", "x",
                      "--path", f"../{repo_fuera.name}", "--dry-run", "--no-git",
                      vault=runtime, cwd=runtime)
    env = Corrida(r.returncode, r.stdout if "{" in r.stdout else r.stderr, r.stderr).envelope
    assert env.get("error_code") != "PREFLIGHT_REJECTED", env
    assert r.returncode == 0 and env["ok"] is True, env


def test_drift_detect_con_ruta_absoluta_pasa_el_preflight(runtime, repo_fuera):
    antes = _huella(repo_fuera)
    r = _vault_run(runtime, "vault_drift_detect", "--project", "x",
                   "--path", repo_fuera.resolve())
    env = r.envelope
    assert env.get("error_code") != "PREFLIGHT_REJECTED", env
    assert env.get("tool") == "vault_drift_detect", env
    assert _huella(repo_fuera) == antes


# ── Everything else: AP-36 unchanged ─────────────────────────────────────────

@pytest.mark.parametrize("ruta", ["C:/x.md", "/etc/passwd"])
def test_param_relativo_al_vault_con_ruta_absoluta_sigue_rechazado(runtime, ruta):
    antes = _huella(runtime)
    r = _vault_run(runtime, "vault_read", "--path", ruta)
    env = r.envelope
    assert r.codigo != 0 and env.get("error_code") == "PREFLIGHT_REJECTED", env
    assert env["blocked"] is True and env["phase"] == "pre-flight", env
    assert _clases(env) == {"absolute_path"}, env
    assert _huella(runtime) == antes


def test_param_relativo_al_vault_con_traversal_sigue_rechazado(runtime):
    r = _vault_run(runtime, "vault_read", "--path", "../fuera.md")
    env = r.envelope
    assert r.codigo != 0 and env.get("error_code") == "PREFLIGHT_REJECTED", env
    assert _clases(env) == {"parent_traversal"}, env


def test_el_mismo_nombre_en_otra_tool_sigue_rechazado(runtime, repo_fuera):
    """The exemption is per tool: `path` of `vault_diff` is a note, not a repo."""
    r = _vault_run(runtime, "vault_diff", "--path", repo_fuera.resolve())
    env = r.envelope
    assert env.get("error_code") == "PREFLIGHT_REJECTED", env
    assert _clases(env) == {"absolute_path"}, env


def test_file_prefijo_en_param_externo_sigue_rechazado(runtime, repo_fuera):
    secreto = repo_fuera / "README.md"
    r = _vault_run(runtime, "vault_onboard", "--project", "x",
                   "--path", f"@file:{secreto.resolve()}", "--dry-run")
    env = r.envelope
    assert env.get("error_code") == "PREFLIGHT_REJECTED", env
    assert _clases(env) == {"absolute_path"}, env


def test_anti_poison_sigue_en_param_externo(runtime, repo_fuera):
    r = _vault_run(runtime, "vault_onboard", "--project", "x",
                   "--path", f"{repo_fuera.resolve()}/vault://otro/", "--dry-run")
    env = r.envelope
    assert env.get("error_code") == "PREFLIGHT_REJECTED", env
    assert _clases(env) == {"pattern_1_in_path"}, env


def test_caracteres_invisibles_siguen_en_param_externo(runtime, repo_fuera):
    r = _vault_run(runtime, "vault_onboard", "--project", "x",
                   "--path", f"{repo_fuera.resolve()}{chr(0x1f)}", "--dry-run")
    env = r.envelope
    assert env.get("error_code") == "PREFLIGHT_REJECTED", env
    assert _clases(env) == {"invisible_chars"}, env


# ── The declaration: one source, both surfaces ──────────────────────────────

def _declaradas() -> set:
    return {
        (nombre, param)
        for nombre, tool in catalogo.TOOLS_CATALOG.items()
        for param, info in (tool.get("params") or {}).items()
        if isinstance(info, dict) and "ruta" in info
    }


def test_las_externas_declaradas_son_las_esperadas():
    assert _declaradas() == EXTERNAS_ESPERADAS
    for nombre, param in EXTERNAS_ESPERADAS:
        assert catalogo.TOOLS_CATALOG[nombre]["params"][param]["ruta"] == RUTA_EXTERNA


@pytest.mark.parametrize("nombre,param", sorted(EXTERNAS_ESPERADAS))
def test_cada_externa_nombra_un_flag_real_del_script(nombre, param):
    reales = catalogo.argparse_params(catalogo.TOOLS_CATALOG[nombre]["script"])
    assert param in reales, f"{nombre}: --{param} no está en su argparse ({sorted(reales)})"
    # Only a name the pre-flight treats as a path needs (or may get) the exemption.
    assert es_argumento_de_ruta(param), param


@pytest.mark.parametrize("ruta", CATALOGOS_GENERADOS, ids=lambda p: p.parent.name)
def test_los_catalogos_generados_publican_la_misma_declaracion(ruta):
    """The MCP server and `vault run` read the same published marker."""
    tools = json.loads(ruta.read_text(encoding="utf-8"))["tools"]
    publicadas = {
        (nombre, param)
        for nombre, entrada in tools.items()
        for param, prop in ((entrada.get("inputSchema") or {}).get("properties") or {}).items()
        if CLAVE_RUTA in prop
    }
    assert publicadas == EXTERNAS_ESPERADAS
    for nombre, param in publicadas:
        assert tools[nombre]["inputSchema"]["properties"][param][CLAVE_RUTA] == RUTA_EXTERNA

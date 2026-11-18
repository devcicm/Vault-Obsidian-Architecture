"""Flow QA (2026-11-17): a published recovery, followed literally, fixes its cause.

Each test reproduces a flow the flow QA found broken on a fresh vault, follows
the `recovery` of the envelope as an agent would, and re-runs the original
command:

- QA-FL-03: `FOLDER_NOT_FOUND` published `vault_standard_upgrade --check`,
  which is read-only; and a typo in a folder or a scan path got the same code,
  whose recovery cannot fix a typo.
- QA-FL-04: a malformed `--desde-pack` file got `JSON_PARSE_ERROR`, whose
  recovery rebuilt indexes that have nothing to do with the user's file.
- QA-FL-11: `vault_says.next` named repo maintenance scripts that an installed
  product refuses to run.
- QA-FL-12: a `vault_fix_all` step that timed out or could not start was
  reported as `SERVICE_UNAVAILABLE`, recovered by starting the token counter.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict

import pytest

from apoyo import correr_tool

_SECCION = "21_QA"


@pytest.fixture(scope="module")
def _vault_base(tmp_path_factory) -> Path:
    vault = tmp_path_factory.mktemp("flujo") / "vault"
    vault.mkdir()
    assert correr_tool("vault_init", vault=vault).envelope["ok"]
    assert correr_tool("vault_project", "--add", "demo", vault=vault).envelope["ok"]
    return vault


@pytest.fixture
def vault(_vault_base, tmp_path) -> Path:
    copia = tmp_path / "vault"
    shutil.copytree(_vault_base, copia)
    return copia


def _notas(vault: Path) -> Dict[str, bytes]:
    return {p.relative_to(vault).as_posix(): p.read_bytes()
            for p in vault.rglob("*.md") if ".git" not in p.parts}


def _seguir(recovery: dict, vault: Path):
    assert recovery["action"] == "run_tool", recovery
    return correr_tool(recovery["tool"], *recovery["args"], vault=vault)


# ── QA-FL-03 ──────────────────────────────────────────────────────────────────

def test_fl03_seccion_ausente_la_recuperacion_la_crea_sin_tocar_notas(vault):
    shutil.rmtree(vault / _SECCION)
    antes = _notas(vault)

    error = correr_tool("vault_validate", "--check", "structure", vault=vault)
    assert error.codigo == 1
    assert error.envelope["error_code"] == "FOLDER_NOT_FOUND", error.envelope
    recovery = error.envelope["recovery"]
    assert "--check" not in recovery["args"], recovery

    seguida = _seguir(recovery, vault)
    assert seguida.codigo == 0 and seguida.envelope["ok"], seguida.envelope
    assert (vault / _SECCION).is_dir()
    assert _SECCION in seguida.envelope["folders_created"]
    # Only folders were created: every note is byte for byte what it was.
    assert _notas(vault) == antes

    otra = correr_tool("vault_validate", "--check", "structure", vault=vault)
    assert otra.codigo == 0 and otra.envelope["ok"], otra.envelope


def test_fl03_upgrade_check_no_dice_al_dia_si_faltan_secciones(vault):
    shutil.rmtree(vault / _SECCION)

    r = correr_tool("vault_standard_upgrade", "--check", vault=vault)
    assert r.codigo == 0 and r.envelope["ok"], r.envelope
    assert _SECCION in r.envelope["folders_to_create"]
    assert "No migrations needed" not in r.envelope["message"], r.envelope["message"]
    assert _SECCION in r.envelope["message"], r.envelope["message"]
    # --check reports and writes nothing.
    assert not (vault / _SECCION).exists()
    assert r.envelope["folders_created"] == []


def test_fl03_upgrade_que_crea_secciones_lo_dice(vault):
    shutil.rmtree(vault / _SECCION)

    r = correr_tool("vault_standard_upgrade", vault=vault)
    assert r.codigo == 0 and r.envelope["ok"], r.envelope
    assert _SECCION in r.envelope["folders_created"]
    assert "No migrations needed" not in r.envelope["message"], r.envelope["message"]
    assert _SECCION in r.envelope["message"], r.envelope["message"]


def test_fl03_upgrade_al_dia_conserva_su_mensaje(vault):
    r = correr_tool("vault_standard_upgrade", "--check", vault=vault)
    assert r.codigo == 0 and r.envelope["ok"], r.envelope
    assert r.envelope["folders_to_create"] == []
    assert "No migrations needed" in r.envelope["message"], r.envelope["message"]


def test_fl03_search_con_carpeta_mal_escrita_pide_corregir_el_argumento(vault):
    antes = _notas(vault)
    r = correr_tool("vault_search", "--query", "x", "--folder", "07_Knowlege", vault=vault)
    assert r.codigo == 1
    assert r.envelope["error_code"] == "UNKNOWN_SECTION", r.envelope
    assert r.envelope["recovery"]["action"] == "fix_input", r.envelope["recovery"]
    assert "07_Knowledge" in r.envelope["valid"]
    assert r.envelope["results"] == []
    assert _notas(vault) == antes


def test_fl03_search_en_seccion_del_estandar_ausente_sigue_siendo_folder_not_found(vault):
    shutil.rmtree(vault / _SECCION)
    r = correr_tool("vault_search", "--query", "x", "--folder", _SECCION, vault=vault)
    assert r.codigo == 1
    assert r.envelope["error_code"] == "FOLDER_NOT_FOUND", r.envelope

    assert _seguir(r.envelope["recovery"], vault).envelope["ok"]
    otra = correr_tool("vault_search", "--query", "x", "--folder", _SECCION, vault=vault)
    assert otra.codigo == 0 and otra.envelope["ok"], otra.envelope


def test_fl03_search_en_carpeta_existente_sigue_buscando(vault):
    r = correr_tool("vault_search", "--query", "primer", "--folder", "07_Knowledge", vault=vault)
    assert r.codigo == 0 and r.envelope["ok"], r.envelope


def test_fl03_code_module_scan_path_inexistente_pide_corregir_el_argumento(vault, tmp_path):
    antes = _notas(vault)
    r = correr_tool("vault_code_module", "--project", "demo",
                    "--scan-path", tmp_path / "nope", vault=vault)
    assert r.codigo == 1
    assert r.envelope["error_code"] == "SOURCE_NOT_FOUND", r.envelope
    assert r.envelope["recovery"]["action"] == "fix_input", r.envelope["recovery"]
    assert _notas(vault) == antes


def test_fl03_knowledge_save_scan_path_inexistente_pide_corregir_el_argumento(vault, tmp_path):
    antes = _notas(vault)
    r = correr_tool("vault_knowledge_save", "--category", "concept",
                    "--scan-path", tmp_path / "nope", vault=vault)
    assert r.codigo == 1
    assert r.envelope["error_code"] == "SOURCE_NOT_FOUND", r.envelope
    assert r.envelope["recovery"]["action"] == "fix_input", r.envelope["recovery"]
    assert _notas(vault) == antes


def test_fl03_section_index_subcarpeta_inexistente_pide_corregir_el_argumento(vault):
    antes = _notas(vault)
    r = correr_tool("vault_section_index", "--folder", "07_Knowledge/nope", vault=vault)
    assert r.codigo == 1
    assert r.envelope["error_code"] == "UNKNOWN_SECTION", r.envelope
    assert r.envelope["recovery"]["action"] == "fix_input", r.envelope["recovery"]
    assert _notas(vault) == antes


def test_fl03_section_index_de_seccion_ausente_se_recupera(vault):
    shutil.rmtree(vault / _SECCION)
    r = correr_tool("vault_section_index", "--folder", _SECCION, vault=vault)
    assert r.codigo == 1
    assert r.envelope["error_code"] == "FOLDER_NOT_FOUND", r.envelope

    assert _seguir(r.envelope["recovery"], vault).envelope["ok"]
    otra = correr_tool("vault_section_index", "--folder", _SECCION, vault=vault)
    assert otra.codigo == 0 and otra.envelope["ok"], otra.envelope
    assert (vault / _SECCION / "index.md").is_file()


# ── QA-FL-04 ──────────────────────────────────────────────────────────────────

def test_fl04_pack_malformado_pide_corregir_el_fichero(vault, tmp_path):
    pack = tmp_path / "p.json"
    pack.write_text("{bad", encoding="utf-8")
    antes = _notas(vault)

    r = correr_tool("vault_ingest", "--desde-pack", pack, "--section", "07_Knowledge",
                    "--text", "Texto de prueba suficientemente largo para una nota. " * 4,
                    vault=vault)
    assert r.codigo == 1
    assert r.envelope["error_code"] == "INVALID_INPUT", r.envelope
    assert r.envelope["recovery"]["action"] == "fix_input", r.envelope["recovery"]
    assert "--desde-pack" in r.envelope["message"]
    assert _notas(vault) == antes


def test_fl04_json_parse_error_no_promete_reindexar():
    """No emitter of JSON_PARSE_ERROR reads an index `vault_reindex` rebuilds."""
    from vault.kernel.errores import ERROR_CATALOG

    recovery = ERROR_CATALOG["JSON_PARSE_ERROR"]["recovery"]
    assert recovery.get("tool") != "vault_reindex", recovery
    assert recovery["action"] == "manual", recovery


# ── QA-FL-11 ──────────────────────────────────────────────────────────────────

_NORMA = {"code": "AP-21", "name": "Path-anchored wiki-links", "severity": "high",
          "tools_enforcing": ["vault_write"], "signal": "s", "prevention": "p"}


def _voz(**kw):
    from vault.autoria import voz

    return voz.speak("vault_write", {"ok": True}, catalog=[_NORMA],
                     severity_order={"high": 0}, runtime_root=None,
                     voice_mode="1", rotation=lambda: 0, **kw)


def test_fl11_instalado_no_nombra_scripts_del_repo(monkeypatch, tmp_path):
    """Installed, tools run from `vault_toolkit/_impl/` (simulated as
    `test_nota_de_comandos` does): `vault run` refuses maintenance tools."""
    import vault_grafo_import

    monkeypatch.setattr(vault_grafo_import, "DIRECTORIO", tmp_path / "_impl")
    for payload in ({"ok": True}, {"ok": False, "norm_code": "AP-21"}):
        from vault.autoria import voz

        bloque = voz.speak("vault_write", payload, catalog=[_NORMA],
                           severity_order={"high": 0}, runtime_root=None,
                           voice_mode="1", rotation=lambda: 0)
        assert bloque is not None and bloque["message"]
        assert "next" not in bloque, bloque


def test_fl11_en_el_checkout_conserva_el_siguiente_paso():
    bloque = _voz()
    assert bloque["next"] == "python scripts/vault_voice.py --tool vault_write"


def test_fl11_envelope_de_la_cli_en_el_checkout_conserva_next(vault):
    r = correr_tool("vault_validate", "--check", "structure", vault=vault)
    assert r.envelope["vault_says"]["next"] == (
        "python scripts/vault_voice.py --tool vault_validate"), r.envelope


# ── QA-FL-12 ──────────────────────────────────────────────────────────────────

def _paso_con(monkeypatch, fallo: BaseException) -> dict:
    import vault_fix_all

    def _falla(*_a, **_k):
        raise fallo

    monkeypatch.setattr(vault_fix_all, "ejecutar", _falla)
    return vault_fix_all._ejecutar_paso(vault_fix_all.PASOS[0], 1)


def test_fl12_paso_que_excede_el_timeout_es_tool_timeout(monkeypatch):
    r = _paso_con(monkeypatch, subprocess.TimeoutExpired(["x"], 180))
    assert r["ok"] is False and r["error_code"] == "TOOL_TIMEOUT", r
    assert r["recovery"]["action"] == "retry", r["recovery"]
    assert r["paso"] == 1 and r["nombre"]


def test_fl12_paso_que_no_arranca_es_tool_execution_failed(monkeypatch):
    r = _paso_con(monkeypatch, OSError("no such interpreter"))
    assert r["ok"] is False and r["error_code"] == "TOOL_EXECUTION_FAILED", r
    assert "vault_token_counter" not in str(r["recovery"]), r["recovery"]
    assert "MCP" not in r["recovery"]["hint"], r["recovery"]
    assert r["paso"] == 1 and r["nombre"]

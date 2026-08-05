"""AP-42 — ninguna tool se publica sin haberse ejecutado nunca.

`--help` demuestra que el argparse se construye. Nada más. La primera medición
de este smoke encontró 41 de 87 tools cuyo ejemplo documentado no llegaba a
emitir un JSON con `ok`: 36 porque el ejemplo usaba flags que la CLI rechaza
—AP-40 trasladado a la documentación— y el resto por contrato de salida.

El barrido completo tarda minutos y vive en CI (`vault_smoke --strict`). Estos
tests verifican la maquinaria que lo hace fiable: que la invocación se derive
bien del catálogo, que la baseline no pueda crecer, y que ninguna exención sea
silenciosa.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_smoke as smoke  # noqa: E402
from vault_mcp_catalog import TOOLS_CATALOG  # noqa: E402
from vault_norms import NORM_CATALOG  # noqa: E402


# ── La invocación se deriva del ejemplo documentado ──────────────────────────

def test_la_invocacion_sale_del_ejemplo_del_catalogo():
    argv = smoke.invocation("vault_search")
    assert argv[1].endswith("vault_search.py")
    assert "--query" in argv


def test_las_comillas_del_ejemplo_no_llegan_al_argumento():
    """`--query "circuit breaker"` es un solo argumento, sin comillas dentro."""
    argv = smoke.invocation("vault_search")
    assert "circuit breaker" in argv
    assert not any(a.startswith('"') for a in argv)


def test_a_una_tool_con_modo_json_se_le_pide_json():
    """Su modo por defecto es texto para una persona; el contrato es el JSON."""
    assert "--json" in smoke.invocation("vault_move")
    assert "--json" not in smoke.invocation("vault_search")


def test_toda_tool_del_catalogo_tiene_invocacion_derivable():
    sin_invocacion = [
        t for t, e in TOOLS_CATALOG.items()
        if e.get("script") and (SCRIPTS / e["script"]).is_file()
        and t not in smoke.SIN_SMOKE and smoke.invocation(t) is None
    ]
    assert sin_invocacion == []


def test_las_exenciones_estan_declaradas_con_motivo():
    assert smoke.SIN_SMOKE, "una exención sin declarar es una tool que nadie ejecuta"
    assert all(isinstance(v, str) and v for v in smoke.SIN_SMOKE.values())


def test_una_tool_exenta_no_se_ejecuta_pero_se_reporta():
    r = smoke.run_one("vault_token_service")
    assert r["ok"] and "no retorna" in r["skipped"]


# ── El contrato que se exige ─────────────────────────────────────────────────

def test_una_tool_real_pasa_el_smoke():
    r = smoke.smoke(["vault_norms"])
    assert r["ok"], r["failures"]
    assert r["passing"] == 1


def test_un_ok_false_bien_formado_aprueba():
    """Lo que se persigue es el fallo mudo, no el rechazo educado."""
    r = smoke.run_one("vault_read")
    assert r["ok"], r
    assert "tool_ok" in r


def test_el_smoke_no_toca_el_vault_de_pruebas():
    """Cada tool corre contra una copia: un ejemplo con escritura no contamina."""
    antes = sorted(p.name for p in (ROOT / "vault-sandbox" / "07_Knowledge").glob("*.md"))
    smoke.run_one("vault_write")
    assert sorted(p.name for p in (ROOT / "vault-sandbox" / "07_Knowledge").glob("*.md")) == antes


# ── La baseline solo puede encoger ───────────────────────────────────────────

def test_la_baseline_esta_saldada():
    """Quedó en 0 en v39: esto es un guard duro, no una deuda congelada."""
    assert smoke.load_baseline() == []


def test_freeze_rechaza_una_baseline_que_crece(monkeypatch):
    monkeypatch.setattr(smoke, "smoke", lambda *a, **k: {
        "failures": [{"tool": "vault_x"}, {"tool": "vault_y"}], "new_offenders": ["vault_x"]})
    monkeypatch.setattr(smoke, "load_baseline", lambda: [])
    r = smoke.freeze()
    assert not r["ok"] and "no puede crecer" in r["error"]


def test_un_fallo_nuevo_hace_que_strict_falle(monkeypatch):
    monkeypatch.setattr(smoke, "run_one", lambda t: {"tool": t, "ok": False, "problem": "sin salida"})
    monkeypatch.setattr(smoke, "load_baseline", lambda: [])
    r = smoke.smoke(["vault_write"])
    assert not r["ok"] and r["new_offenders"] == ["vault_write"]


def test_una_deuda_saldada_se_reporta_como_tal(monkeypatch):
    monkeypatch.setattr(smoke, "run_one", lambda t: {"tool": t, "ok": True})
    monkeypatch.setattr(smoke, "load_baseline", lambda: ["vault_write"])
    r = smoke.smoke(["vault_write"])
    assert r["ok"] and r["resolved"] == ["vault_write"]


# ── El audit y la norma ──────────────────────────────────────────────────────

def test_el_audit_reporta_la_deuda_congelada(tmp_path, monkeypatch):
    import vault_norms as vn

    root = tmp_path / "v"
    for sec in ("00_System", "01_Projects", "99_Index"):
        (root / sec).mkdir(parents=True)
    (root / "01_Projects" / "index.md").write_text("---\ntitle: idx\n---\n# idx\n", encoding="utf-8")
    monkeypatch.setattr(smoke, "load_baseline", lambda: ["vault_x"])
    r = vn.vault_norms_audit(root)
    assert "AP-42" in r["by_norm"]
    assert any("vault_x" in v["detail"] for v in r["violations"] if v["norm"] == "AP-42")


def test_ap42_esta_en_el_catalogo():
    norma = next((n for n in NORM_CATALOG if n["code"] == "AP-42"), None)
    assert norma is not None
    assert norma["enforcement"] == "guard+audit"
    assert any(t.startswith("vault_smoke") for t in norma["tools_enforcing"])


def test_vault_smoke_esta_en_el_catalogo_de_tools():
    assert "vault_smoke" in TOOLS_CATALOG


def test_la_baseline_en_disco_declara_su_norma():
    datos = json.loads((SCRIPTS / "smoke-baseline.json").read_text(encoding="utf-8"))
    assert datos["norm"] == "AP-42"

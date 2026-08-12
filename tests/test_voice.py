"""AP-43 — el vault le habla al agente en el punto de uso.

El catálogo de normas estaba completo y era invisible: el agente lo descubría
al incumplirlo, y solo si la norma era una de las que previenen. Estos tests
verifican las dos mitades de la norma — que la voz dice lo correcto, y que
llega de verdad al agente por el camino que todas las tools ya recorren.

El test que importa es `test_una_tool_real_devuelve_vault_says`: sin él, esta
capa sería otro registro que nadie consume, que es el fallo que la norma nombra.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_voice as voz  # noqa: E402
from vault_norms import NORM_CATALOG  # noqa: E402


@pytest.fixture(autouse=True)
def voz_encendida(monkeypatch):
    monkeypatch.delenv("VAULT_VOICE", raising=False)
    voz.norms_for_tool.cache_clear()


# ── Qué normas gobiernan una tool ────────────────────────────────────────────

def test_una_tool_de_escritura_tiene_normas_que_la_gobiernan():
    codigos = [n["code"] for n in voz.norms_for_tool("vault_write")]
    assert "AP-11" in codigos and "AP-41" in codigos


def test_las_que_la_tool_aplica_van_antes_que_las_que_solo_detectan():
    normas = voz.norms_for_tool("vault_write")
    aplican = [n["code"] for n in normas if voz._menciona(n["tools_enforcing"], "vault_write")]
    assert [n["code"] for n in normas][: len(aplican)] == aplican


def test_el_catalogo_guarda_la_tool_con_flags_y_aun_asi_se_reconoce():
    """`tools_detecting` guarda 'vault_norms --audit', no 'vault_norms'."""
    assert voz._menciona(["vault_norms --audit"], "vault_norms")
    assert not voz._menciona(["vault_norms_extra"], "vault_norms")


def test_una_tool_que_no_gobierna_nada_no_inventa_normas():
    assert voz.norms_for_tool("tool_que_no_existe") == []
    assert voz.speak("tool_que_no_existe", {"ok": True}) is None


# ── Qué dice, según lo que acaba de pasar ────────────────────────────────────

def test_cuando_una_norma_frena_la_llamada_la_voz_nombra_esa_norma():
    d = voz.speak("vault_write", {"ok": False, "norm_code": "AP-41"})
    assert d["moment"] == "blocked" and d["focus"] == "AP-41"
    assert "AP-41" in d["message"]
    assert d["next"] == "python scripts/vault_norms.py --explain AP-41"


def test_cuando_hubo_escritura_la_voz_dice_cuanto_cambio():
    d = voz.speak("vault_write", {"ok": True}, {"written": 4})
    assert d["moment"] == "wrote"
    assert "4 notas" in d["message"]
    assert d["next"] == "python scripts/vault_norms.py --audit"


def test_una_sola_nota_no_se_anuncia_en_plural():
    assert "1 nota en disco" in voz.speak("vault_write", {"ok": True}, {"written": 1})["message"]


def test_una_lectura_no_se_anuncia_como_cambio():
    d = voz.speak("vault_write", {"ok": True}, {"written": 0})
    assert d["moment"] == "read" and "Nada cambió" in d["message"]


def test_el_foco_rota_para_que_el_refuerzo_no_sea_ruido_fijo(monkeypatch):
    """Repetir siempre la misma norma la vuelve invisible a la segunda semana."""
    focos = set()
    for i in range(6):
        monkeypatch.setattr(voz, "_rotacion", lambda i=i: i)
        focos.add(voz.speak("vault_write", {"ok": True})["focus"])
    assert len(focos) > 1


def test_el_contador_de_rotacion_nunca_es_fatal(monkeypatch):
    monkeypatch.setattr(voz, "get_vault_root", None, raising=False)
    assert isinstance(voz._rotacion(), int)


# ── Control por entorno ──────────────────────────────────────────────────────

def test_se_puede_silenciar(monkeypatch):
    monkeypatch.setenv("VAULT_VOICE", "0")
    assert voz.speak("vault_write", {"ok": True}) is None


def test_el_modo_verbose_entrega_el_catalogo_completo(monkeypatch):
    monkeypatch.setenv("VAULT_VOICE", "verbose")
    d = voz.speak("vault_write", {"ok": True})
    assert len(d["detail"]) == len(d["norms"])
    assert all("prevention" in n for n in d["detail"])


# ── Que llegue de verdad al agente ───────────────────────────────────────────

def test_una_tool_real_devuelve_vault_says(tmp_path):
    """El test que impide que esto sea otro registro que nadie consume."""
    vault = tmp_path / "vault-voz"
    for sec in ("00_System", "07_Knowledge", "99_Index"):
        (vault / sec).mkdir(parents=True)
    env = dict(os.environ)
    env.update({"VAULT_ROOT": str(vault), "VAULT_AGENT": "pytest-ap43",
                "PYTHONIOENCODING": "utf-8"})
    env.pop("VAULT_VOICE", None)
    cuerpo = (
        "## Contexto\nUna nota con tres lineas reales de contenido suficiente.\n\n"
        "## Detalle\nSuficiente para pasar el guard AP-11 sin problemas de longitud.\n\n"
        "## Cierre\nFin del documento de prueba de refuerzo.\n"
    )
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_write.py"), "--folder", "07_Knowledge",
         "--title", "Nota voz", "--tags", "test", "--content", cuerpo],
        capture_output=True, text=True, env=env, encoding="utf-8",
    )
    salida = json.loads(proc.stdout.strip().splitlines()[-1])
    assert salida["ok"], salida
    dice = salida["vault_says"]
    assert dice["moment"] == "wrote", "el ledger AP-37 es thread-local: hay que leerlo en el hilo de la tool"
    assert dice["focus"] in {n["code"] for n in NORM_CATALOG}


def test_el_enganche_vive_en_el_punto_por_el_que_pasan_todas_las_tools():
    """Si esto se mueve a las tools una a una, la cobertura se degrada en silencio."""
    fuente = (SCRIPTS / "vault_errors.py").read_text(encoding="utf-8")
    assert "_inject_voice" in fuente
    assert "_inject_voice(data, tool_name, writes)" in fuente


def test_un_fallo_de_la_voz_no_puede_romper_una_tool(monkeypatch):
    import vault_errors as ve

    monkeypatch.setattr(voz, "speak", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    datos = {"ok": True, "tool": "vault_write"}
    ve._inject_voice(datos, "vault_write", {"written": 1})
    assert "vault_says" not in datos and datos["ok"] is True


# ── Cobertura: la norma que nadie pronuncia ─────────────────────────────────

def test_ninguna_norma_del_catalogo_es_muda():
    """Muda y descubierta no son lo mismo, y desde v40.11 no se cuentan igual.

    Una norma con `cobertura_descubierta` no la pronuncia ninguna tool porque
    ninguna la mide, y eso está escrito con su motivo en el catálogo. Exigir que
    lo pronunciado cubra el catálogo entero obligaría a inventarle un detector
    o a callar el hueco — las dos peores salidas.
    """
    r = voz.coverage()
    assert r["ok"], f"normas que ninguna tool pronuncia: {r['silent']}"
    assert r["norms_total"] == len(NORM_CATALOG)
    assert r["norms_spoken"] + len(r["uncovered_declared"]) == len(NORM_CATALOG)


def test_toda_norma_no_pronunciada_declara_por_escrito_por_que():
    """El freno de la excepción: no vale declararse descubierta sin motivo."""
    for codigo in voz.coverage()["uncovered_declared"]:
        norma = next(n for n in NORM_CATALOG if n["code"] == codigo)
        assert norma["cobertura_descubierta"].strip(), codigo


def test_el_audit_reporta_una_norma_muda(tmp_path, monkeypatch):
    import vault_norms as vn

    root = tmp_path / "v"
    for sec in ("00_System", "01_Projects", "99_Index"):
        (root / sec).mkdir(parents=True)
    (root / "01_Projects" / "index.md").write_text("---\ntitle: idx\n---\n# idx\n", encoding="utf-8")
    monkeypatch.setattr(voz, "coverage", lambda: {"silent": ["AP-99"]})
    r = vn.vault_norms_audit(root)
    assert "AP-43" in r["by_norm"]
    assert any("AP-99" in v["detail"] for v in r["violations"] if v["norm"] == "AP-43")


# ── La norma existe con enforcement real ─────────────────────────────────────

def test_ap43_esta_en_el_catalogo():
    norma = next((n for n in NORM_CATALOG if n["code"] == "AP-43"), None)
    assert norma is not None
    assert norma["enforcement"] == "guard+audit"
    assert "vault_voice" in norma["tools_enforcing"]


def test_vault_voice_esta_en_el_catalogo_de_tools():
    from vault_mcp_catalog import TOOLS_CATALOG

    assert "vault_voice" in TOOLS_CATALOG

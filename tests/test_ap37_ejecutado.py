"""AP-37 medido ejecutando: `vault_noop_audit --ejecutado`.

El modo estático mira `declared_returns`; un contrato que declara
`fixes_applied` y un envelope que no lo emite pasan igual. Medido el
2026-10-16 sobre los ejemplos de las tools con side effects: dos escribían
sin decirlo (`vault_delta --snapshot`, `vault_graph_fix --apply`, saldados en
a0fdb0c y 9985e24). El banco ejecuta el ejemplo documentado sobre una copia
desechable —la de `vault_smoke`, no una segunda— y compara el árbol.
"""

import sys
import textwrap
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RAIZ / "scripts"), str(RAIZ)]

import vault_noop_audit  # noqa: E402
import vault_smoke  # noqa: E402

_CALLA = textwrap.dedent("""
    import json, os, pathlib
    raiz = pathlib.Path(os.environ["VAULT_ROOT"])
    (raiz / "07_Knowledge" / "escrita.md").write_text("x", encoding="utf-8")
    (raiz / "00_System" / ".tool-trace.json").write_text("[]", encoding="utf-8")
    print(json.dumps({"ok": True}))
""")
_DICE = _CALLA.replace('{"ok": True}', '{"ok": True, "written": 1}')
_LEE = textwrap.dedent("""
    import json
    print(json.dumps({"ok": True}))
""")


@pytest.fixture
def banco(tmp_path, monkeypatch):
    """Sandbox mínimo y tres tools falsas que el smoke sabe invocar."""
    sandbox = tmp_path / "sandbox"
    (sandbox / "00_System").mkdir(parents=True)
    (sandbox / "07_Knowledge").mkdir()
    (sandbox / "07_Knowledge" / "nota.md").write_text("---\ntitle: N\n---\n", encoding="utf-8")
    monkeypatch.setattr(vault_smoke, "SANDBOX", sandbox)
    scripts = {}
    for nombre, codigo in (("calla", _CALLA), ("dice", _DICE), ("lee", _LEE)):
        ruta = tmp_path / f"{nombre}.py"
        ruta.write_text(codigo, encoding="utf-8")
        scripts[nombre] = [sys.executable, str(ruta)]
    monkeypatch.setattr(vault_smoke, "invocation", lambda tool: scripts.get(tool))
    monkeypatch.setattr(vault_smoke, "invocations",
                        lambda tool: [scripts[tool]] if tool in scripts else [])
    # El sandbox mínimo no tiene la estructura que pide `vault_project --add`:
    # las tools falsas no necesitan proyecto.
    monkeypatch.setattr(vault_noop_audit, "PROYECTO_DEL_EJEMPLO", None)
    return {nombre: {"side_effects": True} for nombre in scripts}


def test_ap37_ejecutado_ve_la_tool_que_escribe_y_calla(banco):
    r = vault_noop_audit.ejecutado(banco)
    assert r["ok"] is False, r
    assert [o["tool"] for o in r["ofensores"]] == ["calla"], r
    assert r["ofensores"][0]["cambiadas"] == ["07_Knowledge/escrita.md"], r
    assert r["medidas"] == ["dice"] and r["sin_escritura"] == ["lee"], r


def test_ap37_ejecutado_la_traza_no_cuenta_como_trabajo(banco, monkeypatch):
    monkeypatch.setattr(vault_noop_audit, "SIN_ESCRITURA_DECLARADA", {"lee": "solo lee"})
    r = vault_noop_audit.ejecutado({"lee": banco["lee"], "dice": banco["dice"]})
    assert r["ok"] is True and r["ofensores"] == [], r


def test_ap37_ejecutado_sin_nada_medido_no_sale_verde(banco):
    # AP-60: un universo vacío no es un verde.
    r = vault_noop_audit.ejecutado({"lee": banco["lee"]})
    assert r["ok"] is False and r["medidas"] == [], r
    r = vault_noop_audit.ejecutado({"otra": {"side_effects": True}})
    assert r["ok"] is False and r["sin_invocacion"][0]["tool"] == "otra", r


def test_ap37_ejecutado_ejecuta_cada_linea_del_ejemplo(banco, monkeypatch):
    """2026-10-17: el banco ejecutaba solo la primera línea del `example`, que
    casi siempre es la de lectura (`--list`, `--check`, el dry-run), y 73 de
    92 salían `sin_escritura`. La de escritura suele ser la segunda."""
    lineas = {"dos": [vault_smoke.invocation("lee"), vault_smoke.invocation("dice")]}
    monkeypatch.setattr(vault_smoke, "invocations", lambda tool: lineas.get(tool, []))
    r = vault_noop_audit.ejecutado({"dos": {"side_effects": True}})
    assert r["medidas"] == ["dos"] and r["ok"] is True, r


def test_ap37_ejecutado_una_linea_que_calla_basta_para_ofender(banco, monkeypatch):
    lineas = {"mixta": [vault_smoke.invocation("dice"), vault_smoke.invocation("calla")]}
    monkeypatch.setattr(vault_smoke, "invocations", lambda tool: lineas.get(tool, []))
    r = vault_noop_audit.ejecutado({"mixta": {"side_effects": True}})
    assert [o["tool"] for o in r["ofensores"]] == ["mixta"] and r["ok"] is False, r


def test_invocations_devuelve_cada_linea_documentada():
    lineas = vault_smoke.invocations("vault_fix_brackets")
    assert len(lineas) == 3
    assert lineas[0] == vault_smoke.invocation("vault_fix_brackets")
    assert "--apply" in lineas[1] and "--path" in lineas[2]


def test_el_banco_prepara_el_proyecto_y_los_ficheros_del_ejemplo():
    """Con el sandbox tal cual, 26 ejemplos daban `PROJECT_NOT_FOUND` —`mi-api`
    no está dado de alta— y 13 no encontraban la nota o el fichero que citan.
    Un `ok: false` sin escribir no es una medida de AP-37."""
    r = vault_noop_audit.ejecutado({t: {"side_effects": True}
                                    for t in ("vault_bug_save", "vault_quarantine")})
    assert r["medidas"] == ["vault_bug_save", "vault_quarantine"], r


def test_el_banco_no_ejecuta_las_tools_que_escriben_en_el_repo(monkeypatch):
    """La primera ronda que ejecutó todas las líneas (2026-10-17) corrió el
    `--freeze` y el `--fix` del meta-toolkit y reescribió tres baselines,
    `AGENTS.md` y `docs/BLUEPRINT.md` del checkout. Esas tools escriben en el
    repo, no en el vault: el banco las publica aparte y no las toca."""
    def no_se_ejecuta(*a, **k):
        raise AssertionError(f"el banco ejecutó {a}")

    monkeypatch.setattr(vault_smoke, "run_one", no_se_ejecuta)
    monkeypatch.setattr(vault_noop_audit, "PROYECTO_DEL_EJEMPLO", None)
    del_estandar = ("vault_blame_audit", "vault_doc_counts", "vault_blueprint")
    r = vault_noop_audit.ejecutado({t: {"side_effects": True} for t in del_estandar})
    assert r["fuera_del_vault"] == sorted(del_estandar), r
    assert r["ok"] is False and r["medidas"] == [], r


def test_el_banco_da_al_escaner_codigo_con_un_hallazgo():
    """`vault_security_scan --path "src/"` solo escribe si encuentra algo: con
    el directorio de trabajo vacío daba FILE_NOT_FOUND y el banco la contaba
    `sin_escritura`. El ejemplo presupone código que escanear."""
    r = vault_noop_audit.ejecutado({"vault_security_scan": {"side_effects": True}})
    assert r["medidas"] == ["vault_security_scan"], r


def test_una_tool_que_no_escribe_sin_motivo_declarado_no_sale_verde(banco, monkeypatch):
    """2026-10-17: 13 tools con side effects no escribieron en el banco, cada
    una por un motivo distinto y medido (dry-run, sin backup, solo lectura…).
    Publicadas como lista suelta, una tool nueva cuyo ejemplo no escribe se
    sumaba a ella sin que nadie preguntara por qué."""
    monkeypatch.setattr(vault_noop_audit, "SIN_ESCRITURA_DECLARADA", {})
    r = vault_noop_audit.ejecutado({"lee": banco["lee"], "dice": banco["dice"]})
    assert r["ok"] is False and r["sin_escritura_sin_motivo"] == ["lee"], r
    monkeypatch.setattr(vault_noop_audit, "SIN_ESCRITURA_DECLARADA", {"lee": "solo lee"})
    r = vault_noop_audit.ejecutado({"lee": banco["lee"], "dice": banco["dice"]})
    assert r["ok"] is True and r["sin_escritura_declarada"] == {"lee": "solo lee"}, r


def test_una_declaracion_de_que_no_escribe_que_ya_no_es_cierta_falla(banco, monkeypatch):
    monkeypatch.setattr(vault_noop_audit, "SIN_ESCRITURA_DECLARADA",
                        {"lee": "solo lee", "dice": "no escribe"})
    r = vault_noop_audit.ejecutado({"lee": banco["lee"], "dice": banco["dice"]})
    assert r["ok"] is False and r["declaradas_que_escriben"] == ["dice"], r


def test_lo_declarado_sin_escritura_son_tools_vivas_con_side_effects():
    import vault_mcp_catalog

    for tool, motivo in vault_noop_audit.SIN_ESCRITURA_DECLARADA.items():
        assert vault_mcp_catalog.TOOLS_CATALOG[tool].get("side_effects"), tool
        assert len(motivo) > 20, (tool, motivo)

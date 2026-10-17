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
    return {nombre: {"side_effects": True} for nombre in scripts}


def test_ap37_ejecutado_ve_la_tool_que_escribe_y_calla(banco):
    r = vault_noop_audit.ejecutado(banco)
    assert r["ok"] is False, r
    assert [o["tool"] for o in r["ofensores"]] == ["calla"], r
    assert r["ofensores"][0]["cambiadas"] == ["07_Knowledge/escrita.md"], r
    assert r["medidas"] == ["dice"] and r["sin_escritura"] == ["lee"], r


def test_ap37_ejecutado_la_traza_no_cuenta_como_trabajo(banco):
    r = vault_noop_audit.ejecutado({"lee": banco["lee"], "dice": banco["dice"]})
    assert r["ok"] is True and r["ofensores"] == [], r


def test_ap37_ejecutado_sin_nada_medido_no_sale_verde(banco):
    # AP-60: un universo vacío no es un verde.
    r = vault_noop_audit.ejecutado({"lee": banco["lee"]})
    assert r["ok"] is False and r["medidas"] == [], r
    r = vault_noop_audit.ejecutado({"otra": {"side_effects": True}})
    assert r["ok"] is False and r["sin_invocacion"][0]["tool"] == "otra", r

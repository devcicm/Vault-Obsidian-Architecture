"""El smoke ahora contrasta el envelope contra el contrato, no solo contra `ok`.

`vault_smoke` comprobaba que la salida fuese un JSON con `ok`, que es
literalmente la señal que AP-37 declara insuficiente. Para las 41 tools del
catálogo que no aparecen en ningún test, ese `ok` era **toda** la verificación
que existía.

Medido sobre las 91 tools al añadir `contract_gap`, salieron dos huecos y los dos
eran defectos de verdad: `vault_sdd_init` mezclaba el informe humano y el
envelope en el mismo stdout —su salida no era JSON parseable— y
`vault_change_log` declaraba solo `id`, el campo del modo de escritura, así que
el modo de consulta no tenía contrato. Por eso es puerta dura y no baseline.

Estos tests ejercen la regla, no el barrido: correr las 91 tools son minutos.
"""

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _smoke():
    spec = importlib.util.spec_from_file_location(
        "vault_smoke", REPO_ROOT / "scripts" / "vault_smoke.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def vs():
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    return _smoke()


def test_un_envelope_que_no_cubre_nada_de_su_contrato_es_hueco(vs, monkeypatch):
    monkeypatch.setattr(vs, "_contrato_de", lambda t: {"path", "total"})
    hueco = vs.contract_gap({"tool": "x", "returned": ["ok", "tool"]})
    assert hueco is not None
    assert hueco["problem"] == "el envelope no cubre ningún campo de su contrato"


def test_cubrir_un_solo_campo_basta(vs, monkeypatch):
    """`declared_returns` es la unión de todos los modos; el smoke corre uno.

    Exigir el contrato entero marcaría como incumplimiento el caso normal de una
    tool con varios modos, que es justo lo que le pasa a `vault_change_log`.
    """
    monkeypatch.setattr(vs, "_contrato_de", lambda t: {"path", "total"})
    assert vs.contract_gap({"tool": "x", "returned": ["ok", "total"]}) is None


def test_los_campos_de_error_no_cuentan_como_contrato(vs, monkeypatch):
    """Una tool sana no devuelve `error`: cubrirlo no demuestra nada."""
    monkeypatch.setattr(vs, "_contrato_de", lambda t: {"error", "message"})
    assert vs.contract_gap({"tool": "x", "returned": ["ok"]}) is None


def test_una_tool_saltada_no_se_juzga(vs):
    assert vs.contract_gap({"tool": "x", "ok": True, "skipped": "runtime node"}) is None


def test_sin_contrato_no_hay_hueco(vs, monkeypatch):
    monkeypatch.setattr(vs, "_contrato_de", lambda t: set())
    assert vs.contract_gap({"tool": "x", "returned": ["ok"]}) is None


def test_el_hueco_de_contrato_tumba_el_smoke(vs, monkeypatch):
    """Puerta dura: un hueco pone `ok: false` aunque ninguna tool falle."""
    monkeypatch.setattr(vs, "TOOLS_CATALOG", {"x": {}})
    monkeypatch.setattr(vs, "run_one", lambda t: {
        "tool": t, "ok": True, "tool_ok": True, "returned": ["ok", "tool"]})
    monkeypatch.setattr(vs, "_contrato_de", lambda t: {"path"})
    r = vs.smoke()
    assert r["ok"] is False
    assert r["failing"] == 0, "no falla ninguna tool: lo que falla es el contrato"
    assert r["contract_gaps_total"] == 1


def test_los_dos_huecos_medidos_estan_cerrados(vs):
    """Las dos tools que motivaron la regla, contrastadas de verdad.

    No se afirma sobre el resultado que dio el barrido: se vuelven a ejecutar.
    """
    for tool in ("vault_sdd_init", "vault_change_log"):
        r = vs.run_one(tool)
        assert r["ok"], r
        if r.get("skipped"):
            pytest.skip(f"{tool}: {r['skipped']}")
        assert vs.contract_gap(r) is None, vs.contract_gap(r)


def test_el_stdout_del_sdd_init_es_json_y_nada_mas():
    """La prosa de progreso va a stderr; stdout lo lee una tool."""
    import os
    import subprocess

    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "VAULT_TOOL_TIMEOUT": "1800"}
    proc = subprocess.run(
        ["python", str(REPO_ROOT / "scripts" / "vault_sdd_init.py"), "--dry-run"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(REPO_ROOT / "scripts"), timeout=600,
    )
    datos = json.loads(proc.stdout)
    assert datos["ok"] is True and datos["dry_run"] is True
    assert "vault-sdd-init" in proc.stderr, "el informe humano no debe desaparecer"

"""Tests de `vault_toolkit_audit` — verificación funcional del toolkit.

La ejecución real contra el catálogo se paga en las olas de la auditoría (cada
línea cuesta una copia del sandbox); aquí se prueba el instrumental con
entradas sintéticas y `run_one` falsificado. El repo real entra solo para las
sanidades que no dependen del estado del working tree.
"""

from __future__ import annotations

import sys
import json
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import vault_toolkit_audit as tka  # noqa: E402


def _entrada() -> dict:
    lineas = ["python vault_x.py --tool vault_write", "python vault_x.py --list"]
    return {
        # Un script que DE VERDAD existe (C0 lo comprueba contra el disco).
        "script": "vault_test_scope.py",
        "purpose": "guarda notas",
        "side_effects": ["01_Projects/note.md"],
        "example": "\n".join(lineas),
    }


# ———————————————————————————————————————————————————————— c1 ——————————————————

def test_c1_declara_side_effects_y_solo_mira():
    res = tka.c1_cobertura(
        "vault_x",
        {"script": "vault_x.py", "side_effects": ["01_Projects/n.md"]},
        ["python vault_x.py --list", "python vault_x.py --check"])
    assert res["estado"] == "DEFECTO"
    assert "solo lectura" in res["motivo"]


def test_c1_con_lineas_utiles_aprueba():
    res = tka.c1_cobertura(
        "vault_x",
        {"script": "vault_x.py", "side_effects": ["01_Projects/n.md"]},
        ["python vault_x.py --tool vault_write"])
    assert res["estado"] == "OK"


def test_c1_sin_side_effects_solo_mira_es_mejora():
    res = tka.c1_cobertura(
        "vault_x", {"script": "vault_x.py", "side_effects": []},
        ["python vault_x.py --list"])
    assert res["estado"] == "MEJORA"


def test_c1_con_dry_run_cuenta_como_util():
    res = tka.c1_cobertura(
        "vault_x",
        {"script": "vault_x.py", "side_effects": ["01_Projects/n.md"]},
        ["python vault_x.py --dry-run"])
    assert res["estado"] == "OK"


def test_c1_sin_example_no_es_defecto_de_c1():
    res = tka.c1_cobertura("vault_x", {"side_effects": ["n.md"]}, [])
    assert res["estado"] == "OK"  # lo declara C0, no C1


# ——————————————————————————————————————————————————— veredicto ————————————————

def test_el_veredicto_toma_la_maxima_severidad():
    chequeos = {
        "c0": {"estado": "OK"},
        "c2": {"estado": "MEJORA", "motivo": "solo mira"},
        "c5": {"estado": "DEFECTO", "motivo": "revienta"},
    }
    veredicto, motivos = tka._veredicto_de(chequeos)
    assert veredicto == "DEFECTO"
    assert "c5: revienta" in motivos


def test_el_veredicto_ok_no_lleva_motivos():
    veredicto, motivos = tka._veredicto_de(
        {"c0": {"estado": "OK"}, "c2": {"estado": "OK"}})
    assert veredicto == "OK"
    assert motivos == []


def test_no_verificable_gana_a_mejora():
    veredicto, motivos = tka._veredicto_de(
        {"c0": {"estado": "NO-VERIFICABLE", "motivo": "runtime node"},
         "c2": {"estado": "MEJORA", "motivo": "solo mira"}})
    assert veredicto == "NO-VERIFICABLE"
    assert "c0: runtime node" in motivos


# ———————————————————————————————————————————— auditar con el smoke falso ——————

def _smoke_sano(monkeypatch):
    import vault_smoke

    def run_one(tool, arbol=False, argv=None):
        resultado = {"tool": tool, "ok": True, "tool_ok": True,
                     "exit_code": 0, "returned": ["ok", "created"]}
        if arbol:
            resultado["cambiadas"] = []
        return resultado

    monkeypatch.setattr(vault_smoke, "invocations",
                        lambda tool: [[sys.executable, "f", "--tool", "n"]])
    monkeypatch.setattr(vault_smoke, "run_one", run_one)
    monkeypatch.setattr(vault_smoke, "contract_gap", lambda resultado: None)


def test_auditar_completo_con_run_one_sano(monkeypatch):
    _smoke_sano(monkeypatch)

    resultado = tka.auditar("vault_x", _entrada(), gid=35,
                            capacidad="gobernanza_del_estandar")
    assert resultado["veredicto"] == "OK"
    assert resultado["grupo_id"] == 35
    assert resultado["capacidad"] == "gobernanza_del_estandar"
    assert resultado["c1"]["estado"] == "OK"
    assert resultado["c2"]["estado"] == "OK"
    assert not resultado["c3"]["declarada"]  # el contrato de la falsa no declara idempotencia


def test_auditar_envelope_ok_con_exit_1_es_defecto(monkeypatch):
    import vault_smoke

    def run_one(tool, arbol=False, argv=None):
        resultado = {"tool": tool, "ok": True, "tool_ok": True,
                     "exit_code": 1, "returned": ["ok"]}
        if arbol:
            resultado["cambiadas"] = []
        return resultado

    monkeypatch.setattr(vault_smoke, "invocations",
                        lambda tool: [[sys.executable, "f", "--hace", "algo"]])
    monkeypatch.setattr(vault_smoke, "run_one", run_one)
    monkeypatch.setattr(vault_smoke, "contract_gap", lambda resultado: None)

    resultado = tka.auditar("vault_x", _entrada(), gid=35, capacidad="gobernanza")
    perdidas = resultado["c2"]["perdidas"]
    assert any("exit" in p for p in perdidas)


def test_auditar_gap_de_contrato_es_defecto(monkeypatch):
    import vault_smoke

    def run_one(tool, arbol=False, argv=None):
        resultado = {"tool": tool, "ok": True, "tool_ok": True,
                     "exit_code": 0, "returned": ["ok", "diferentes"]}
        if arbol:
            resultado["cambiadas"] = []
        return resultado

    monkeypatch.setattr(vault_smoke, "invocations",
                        lambda tool: [[sys.executable, "f", "--x"]])
    monkeypatch.setattr(vault_smoke, "run_one", run_one)
    # Un gap real: el contrato declara cosas y el envelope no devuelve ninguna.
    slack = {
        "tool": "vault_x",
        "problem": "el envelope no cubre ningún campo de su contrato",
        "declared": ["created", "updated"],
        "returned": ["nada"],
    }
    monkeypatch.setattr(vault_smoke, "contract_gap", lambda resultado: slack)

    resultado = tka.auditar("vault_x", _entrada(), gid=35, capacidad="gobernanza")
    assert resultado["c2"]["estado"] == "DEFECTO"
    perdidas = resultado["c2"]["perdidas"]
    assert any("contrato" in p for p in perdidas)


def test_auditar_runtime_node_es_no_verificable():
    resultado = tka.auditar("vault_js", {"runtime": "node"},
                            gid=1, capacidad="escritura_a_gobernanza")
    assert resultado["c0"]["estado"] == "NO-VERIFICABLE"
    assert resultado["veredicto"] == "NO-VERIFICABLE"


# ——————————————————————————————————————————————————— baseline ——————————————————

def test_freeze_niega_la_deuda_nueva():
    with pytest.raises(tka.DeudaNueva) as excinfo:
        tka.congelar({"vault_x"}, admitir=False,
                     baseline={"norm": "AP-42", "note": "", "failing": [], "objetivo": {}})
    assert excinfo.value.lista == ["vault_x"]


def test_freeze_con_admision_la_estrena_y_la_lista(tmp_path, monkeypatch):
    bàn = tmp_path / "toolkit-audit-baseline.json"
    monkeypatch.setattr(tka, "BASELINE_PATH", bàn)
    deuda_nueva = tka.congelar(
        {"vault_x", "vault_y"}, admitir=True,
        baseline={"norm": "AP-42", "note": "", "failing": ["vault_y"], "objetivo": {}})
    assert deuda_nueva == ["vault_x"]
    datos = json.loads(bàn.read_text(encoding="utf-8"))
    assert datos["failing"] == ["vault_x", "vault_y"]
    # La escritura la hizo el dueño canónico y el compromiso viajó con ella.
    assert datos["objetivo"]["tamano"] == 0
    assert datos["objetivo"]["fecha_limite"]
    assert datos["note"]


def test_load_baseline_corrupta_estrena_no_calla(tmp_path, monkeypatch):
    bàn = tmp_path / "toolkit-audit-baseline.json"
    bàn.write_text("{no soy json", encoding="utf-8")
    monkeypatch.setattr(tka, "BASELINE_PATH", bàn)
    with pytest.raises(ValueError):
        tka.load_baseline()


def test_load_baseline_fuera_de_forma_estrena(tmp_path, monkeypatch):
    bàn = tmp_path / "toolkit-audit-baseline.json"
    bàn.write_text('{"failing": "no-lista"}', encoding="utf-8")
    monkeypatch.setattr(tka, "BASELINE_PATH", bàn)
    with pytest.raises(ValueError):
        tka.load_baseline()


# ————————————————————————————————————————————————— doc derivado ————————————————

def test_doc_actualizado_lectura_sin_archivos(tmp_path, monkeypatch):
    monkeypatch.setattr(tka, "DOC_PATH", tmp_path / "doc.md")
    monkeypatch.setattr(tka, "LAST_RUN_PATH", tmp_path / "last.json")
    assert tka.doc_actualizado() is False


def test_doc_actualizado_stale_se_detecta(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    last = tmp_path / "last.json"
    doc.write_text("v", encoding="utf-8")
    time.sleep(0.05)  # la granularidad del mtime de NTFS no obliga a mirar bien
    last.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(tka, "DOC_PATH", doc)
    monkeypatch.setattr(tka, "LAST_RUN_PATH", last)
    monkeypatch.setattr(tka, "BASELINE_PATH", tmp_path / "baseline-inexistente.json")
    # last es más nuevo que doc → para el doc derivado, desfase honesto.
    assert tka.doc_actualizado() is False
    # re-escrita del doc tras el last → fresco
    time.sleep(0.05)
    doc.write_text("v2", encoding="utf-8")
    assert tka.doc_actualizado() is True


def test_doc_renderiza_incluyendo_deuda():
    cache = {
        "timestamp": "2026-10-20T00:00:00Z",
        "resumen": {"OK": 1, "DEFECTO": 1},
        "results": [
            {"tool": "vault_a", "grupo_id": 35, "capacidad": "c",
             "veredicto": "OK", "motivos": []},
            {"tool": "vault_b", "grupo_id": 30, "capacidad": "x",
             "veredicto": "DEFECTO", "motivos": ["c2: ejemplo"]},
        ],
        "deuda_congelada": ["vault_b"],
    }
    texto = tka._doc_de(cache)
    assert "| vault_b | 30" in texto
    assert "c2: ejemplo" in texto
    assert "Deuda congelada" in texto


# ————————————————————————————————————————————————— clasificación ——————————————

def test_seleccionar_tools_desconocida_sale_con_envelope(capsys):
    class Args:
        todo = False
        tools = "vault_doceana"
        grupo = None
    with pytest.raises(SystemExit):
        tka._seleccionar(Args())
    salida = capsys.readouterr().out
    assert "TOOL_NOT_IN_SPEC" in salida
    assert "vault_doceana" in salida


def test_sanidad_gana_y_capacidad_convergen_sobre_el_catalogo_real():
    gid, cap = tka.gid_y_capacidad()
    assert gid.get("vault_gate") == 35
    assert cap.get("vault_gate") == "gobernanza_del_estandar"

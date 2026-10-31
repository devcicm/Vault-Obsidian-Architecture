"""El registro de carriles no promete pasos que no existen ni deja puertas fuera.

`vault.meta_toolkit.carriles` es un dato que lee una persona y la CI: si un
paso nombra un script borrado o un flag que su argparse no declara, el carril
falla justo cuando alguien lo corre. Se comprueba leyendo el código, sin
ejecutar nada: el carril `dev` existe para que comprobarlo sea barato.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import vault_gate  # noqa: E402
from vault.meta_toolkit import carriles  # noqa: E402

_ALIAS = re.compile(r"El dueño vive en `([^`]+\.py)`")

PASOS = [(nombre, i, paso) for nombre, c in carriles.CARRILES.items()
         for i, paso in enumerate(c["pasos"]) if paso["argv"]]


def _scripts_del_paso(argv) -> list:
    """El script que el paso ejecuta, o el de `-m <módulo>`."""
    if argv[0] == "-m":
        return []
    script = REPO / argv[0]
    rutas = [script]
    if script.exists():
        alias = _ALIAS.search(script.read_text(encoding="utf-8"))
        if alias:
            rutas.append(REPO / alias.group(1))
    return rutas


def _flags_declarados(rutas) -> set:
    flags = set()
    for ruta in rutas:
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                    and nodo.func.attr == "add_argument"):
                flags |= {a.value for a in nodo.args
                          if isinstance(a, ast.Constant) and isinstance(a.value, str)}
    return flags


@pytest.mark.parametrize("nombre,i,paso", PASOS, ids=[f"{n}-{i}" for n, i, _ in PASOS])
def test_cada_paso_ejecuta_un_script_que_existe_con_flags_declarados(nombre, i, paso):
    rutas = _scripts_del_paso(paso["argv"])
    if not rutas:
        return
    assert rutas[0].exists(), f"{nombre}[{i}]: {rutas[0]} no existe"
    pedidos = {a for a in paso["argv"][1:] if a.startswith("--")}
    faltan = pedidos - _flags_declarados(rutas)
    assert not faltan, f"{nombre}[{i}]: {sorted(faltan)} no los declara su argparse"


def test_cada_nivel_que_nombra_un_carril_lo_entiende_el_gate():
    for nombre, c in carriles.CARRILES.items():
        for nivel in vault_gate._niveles_del_carril(c):
            assert nivel in vault_gate.SELECCIONES, (nombre, nivel)


def test_dev_y_merge_juntos_no_dejan_ninguna_puerta_fuera():
    """Lo que `dev` se salta lo exige `merge`: el carril barato no rebaja al caro."""
    cubiertas = {p["id"]
                 for nombre in ("dev", "merge")
                 for nivel in vault_gate._niveles_del_carril(carriles.CARRILES[nombre])
                 for p in vault_gate.seleccion(nivel)}
    assert cubiertas == {p["id"] for p in vault_gate.PUERTAS}


def test_dev_no_corre_las_puertas_que_ejecutan_el_producto():
    niveles = vault_gate._niveles_del_carril(carriles.CARRILES["dev"])
    ids = {p["id"] for n in niveles for p in vault_gate.seleccion(n)}
    assert ids and not ids & {"toolkit_audit", "noop"}


def test_merge_corre_la_suite_entera_con_los_workers_del_registro():
    argvs = [p["argv"] for p in carriles.CARRILES["merge"]["pasos"]]
    assert carriles.SUITE_COMPLETA in argvs
    suite = carriles.SUITE_COMPLETA
    assert "tests/" in suite and suite[suite.index("-n") + 1] == str(carriles.WORKERS)
    assert "auto" not in suite


def test_release_exige_merge_y_declara_lo_que_falta_cablear():
    release = carriles.CARRILES["release"]
    assert release["requiere"] == "merge"
    for paso in release["pasos"]:
        if paso.get("cableado") is False:
            assert paso.get("deuda"), paso["que"]


def test_solo_dev_tiene_presupuesto_en_segundos():
    """Los demás remiten a su medida: una cifra escrita a mano envejecería (AP-47)."""
    for nombre, c in carriles.CARRILES.items():
        if c["presupuesto_s"] is None:
            assert c.get("presupuesto"), nombre
    assert carriles.CARRILES["dev"]["presupuesto_s"] == 120


def test_el_doc_publicado_esta_al_dia():
    assert vault_gate.check_doc()["lanes_drift"] is None, "python scripts/vault_gate.py --fix-doc"


def test_editar_a_mano_los_carriles_los_pone_en_rojo(tmp_path, monkeypatch):
    (tmp_path / "AGENTS.md").write_text(vault_gate.checklist(), encoding="utf-8")
    monkeypatch.setattr(vault_gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(vault_gate, "_docstring", lambda s: "Resumen.\n\nPorque sí.")
    vault_gate.fix_doc()
    destino = tmp_path / vault_gate.CARRILES_DOC
    destino.write_text(destino.read_text(encoding="utf-8").replace("≤ 120 s", "≤ 600 s"),
                       encoding="utf-8")

    r = vault_gate.check_doc()
    assert r["ok"] is False and r["lanes_drift"] == "carriles_desactualizados"
    assert vault_gate.fix_doc()["lanes_changed"] is True
    assert vault_gate.check_doc()["ok"] is True

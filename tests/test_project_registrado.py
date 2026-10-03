"""AP-63 — todo `--project` pasa por el registro antes de llegar a la tool.

Dos cosas. La primera, el comportamiento de `vault_project.proyecto_registrado`:
un alias llega a la tool como su slug, un nombre que no resuelve no llega y
sale como `PROJECT_NOT_FOUND` con el nombre de la tool que llamó, y la cadena
vacía —el «sin proyecto» de las opcionales— pasa tal cual.

La segunda es el guard: un `add_argument("--project")` sin
`type=proyecto_registrado(...)` es una tool que acepta texto libre y escribe
lo que le den en `project:` o en `01_Projects/<valor>/`. `PENDIENTES` es la
deuda que había al estrenar el guard y **solo encoge**: una tool que se
convierte y sigue en la lista hace fallar el test, igual que una nueva que
no está en ella.
"""

import argparse
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402
import vault_project  # noqa: E402

#: Las que no deben resolver, con el motivo. No es deuda: es el diseño.
EXENTAS = {
    # Es quien funda el proyecto a partir de un repositorio: exigirle que ya
    # exista sería pedirle el resultado como entrada.
    "vault_onboard": "crea el proyecto",
}

#: Sitios sin `type=proyecto_registrado` al estrenar el guard, por módulo.
#: Solo encoge: se convierten por lotes y cada lote quita sus líneas.
PENDIENTES = {
    "vault_ai_decision": 1,
    "vault_audit": 1,
    "vault_bibliography_save": 1,
    "vault_bug_save": 1,
    "vault_change_log": 1,
    "vault_code_map": 1,
    "vault_code_module": 1,
    "vault_code_query": 1,
    "vault_code_relation": 1,
    "vault_code_sync": 1,
    "vault_delta": 1,
    "vault_diagram_export": 1,
    "vault_diagram_save": 1,
    "vault_drift_detect": 1,
    "vault_env_matrix": 1,
    "vault_env_save": 1,
    "vault_flow_save": 1,
    "vault_graph_merge": 1,
    "vault_incident_save": 1,
    "vault_infra_map": 1,
    "vault_infra_save": 1,
    "vault_knowledge_get": 1,
    "vault_knowledge_save": 1,
    "vault_log_error": 1,
    "vault_mcp": 2,
    "vault_mermaid_check": 1,
    "vault_migrate_docs": 1,
    "vault_ncr_save": 1,
    "vault_pattern_list": 1,
    "vault_pattern_save": 1,
    "vault_privacy_save": 1,
    "vault_project_overview": 1,
    "vault_project_status": 1,
    "vault_qa_save": 1,
    "vault_relation_add": 1,
    "vault_release_save": 1,
    "vault_requirement_save": 1,
    "vault_risk_save": 1,
    "vault_runbook_save": 1,
    "vault_security_scan": 1,
    "vault_slo_save": 1,
    "vault_test_save": 1,
    "vault_timeline": 1,
}


def _es_proyecto_registrado(nodo: ast.AST) -> bool:
    return (
        isinstance(nodo, ast.Call)
        and isinstance(nodo.func, (ast.Name, ast.Attribute))
        and (getattr(nodo.func, "id", None) or getattr(nodo.func, "attr", None))
        == "proyecto_registrado"
    )


def _sitios_sin_resolver() -> dict:
    """Módulo -> número de `add_argument("--project", ...)` sin el `type=`."""
    sin = {}
    for fichero in sorted(SCRIPTS.glob("*.py")):
        arbol = ast.parse(fichero.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "add_argument"
                and nodo.args
                and isinstance(nodo.args[0], ast.Constant)
                and nodo.args[0].value == "--project"
            ):
                continue
            tipo = next((k.value for k in nodo.keywords if k.arg == "type"), None)
            if tipo is None or not _es_proyecto_registrado(tipo):
                sin[fichero.stem] = sin.get(fichero.stem, 0) + 1
    return sin


def test_ap63_ningun_project_nuevo_sin_resolver():
    sin = _sitios_sin_resolver()
    for modulo in EXENTAS:
        sin.pop(modulo, None)
    nuevos = {m: n for m, n in sin.items() if n > PENDIENTES.get(m, 0)}
    assert not nuevos, (
        f"--project sin type=proyecto_registrado(...) fuera de la deuda declarada: "
        f"{nuevos}. AP-63: el nombre de un proyecto es identidad, no texto libre."
    )


def test_ap63_la_deuda_de_project_solo_encoge():
    sin = _sitios_sin_resolver()
    saldados = {m: n for m, n in PENDIENTES.items() if sin.get(m, 0) < n}
    assert not saldados, (
        f"Estos sitios ya resuelven y siguen en PENDIENTES: {saldados}. "
        "Quitarlos de la lista es parte del cambio que los convirtió."
    )


@pytest.fixture
def registro(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    ficha = raiz / "01_Projects" / "mi-api" / "project.md"
    ficha.parent.mkdir(parents=True)
    ficha.write_text(
        "---\ntitle: Mi API\ntype: project\nproject: mi-api\naliases:\n- Mi API\n---\n",
        encoding="utf-8",
    )
    anterior = vault_io.get_vault_root()
    vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(anterior)


def _parser():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="", type=vault_project.proyecto_registrado("vault_x"))
    return ap


def test_ap63_un_alias_llega_a_la_tool_como_su_slug(registro):
    assert _parser().parse_args(["--project", "Mi API"]).project == "mi-api"
    assert _parser().parse_args(["--project", "mi-api"]).project == "mi-api"


def test_ap63_la_cadena_vacia_es_sin_proyecto(registro):
    assert _parser().parse_args([]).project == ""


def test_ap63_un_nombre_libre_no_llega_a_la_tool(registro, capsys):
    with pytest.raises(SystemExit) as salida:
        _parser().parse_args(["--project", "mi-apii"])
    assert salida.value.code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is False and envelope["tool"] == "vault_x"
    assert envelope["error_code"] == "PROJECT_NOT_FOUND"
    assert envelope["sugerencias"] == ["mi-api"]
    assert not (registro / "01_Projects" / "mi-apii").exists()

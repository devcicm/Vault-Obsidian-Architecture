"""AP-63 — todo `--project` pasa por el registro antes de llegar a la tool.

Dos cosas. La primera, el comportamiento de `vault_errors.proyecto_registrado`:
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
import vault_errors  # noqa: E402

#: Las que no deben resolver, con el motivo. No es deuda: es el diseño.
EXENTAS = {
    # Es quien funda el proyecto a partir de un repositorio: exigirle que ya
    # exista sería pedirle el resultado como entrada.
    "vault_onboard": "crea el proyecto",
}

#: Sitios sin `type=proyecto_registrado` al estrenar el guard, por módulo.
#: Solo encoge: se convierten por lotes y cada lote quita sus líneas.
PENDIENTES: dict = {
    # Las 43 de `scripts/` se saldaron en v40.34, y los dos entry modules de
    # `vault/autoria/` al bajar `MAPA_DE_FALLOS` al núcleo. No se reponen.
}


def _es_proyecto_registrado(nodo: ast.AST) -> bool:
    return (
        isinstance(nodo, ast.Call)
        and isinstance(nodo.func, (ast.Name, ast.Attribute))
        and (getattr(nodo.func, "id", None) or getattr(nodo.func, "attr", None))
        == "proyecto_registrado"
    )


def _modulo(fichero: Path) -> str:
    """`scripts/` por su nombre, como siempre; `vault/` por su ruta."""
    if fichero.parent == SCRIPTS:
        return fichero.stem
    return fichero.relative_to(ROOT).with_suffix("").as_posix()


def _sitios_sin_resolver() -> dict:
    """Módulo -> número de `add_argument("--project", ...)` sin el `type=`.

    Mide `scripts/` y también `vault/`: el paquete instalable tiene entry
    modules propios, y un guard que solo mira `scripts/` dejaría fuera justo
    lo que se instala."""
    sin = {}
    ficheros = sorted(SCRIPTS.glob("*.py")) + sorted(
        f for f in (ROOT / "vault").rglob("*.py") if "__pycache__" not in f.parts)
    for fichero in ficheros:
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
                m = _modulo(fichero)
                sin[m] = sin.get(m, 0) + 1
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
    ap.add_argument("--project", default="", type=vault_errors.proyecto_registrado("vault_x"))
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


def _decision(raiz, proyecto):
    import os
    import subprocess

    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_ai_decision.py"), "--project", proyecto,
         "--title", "Usar colas", "--decision_type", "architectural",
         "--description", "Se usan colas.", "--rationale", "Desacoplan."],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=120,
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return proceso.returncode, json.loads(salida[salida.index("{"):])


def test_ap63_una_tool_real_escribe_el_slug_y_no_la_errata(registro):
    """El criterio de aceptación de P2, de punta a punta por la CLI."""
    import yaml

    codigo, r = _decision(registro, "Mi API")
    assert codigo == 0 and r["ok"], r
    nota = registro / r["path"]
    fm = yaml.safe_load(nota.read_text(encoding="utf-8").split("---")[1])
    assert fm["project"] == "mi-api", fm

    antes = sorted(p.relative_to(registro) for p in registro.rglob("*") if p.is_file())
    codigo, r = _decision(registro, "mi-apii")
    assert codigo == 1 and r["error_code"] == "PROJECT_NOT_FOUND", r
    assert r["tool"] == "vault_ai_decision" and r["sugerencias"] == ["mi-api"]
    despues = sorted(p.relative_to(registro) for p in registro.rglob("*") if p.is_file())
    assert despues == antes, set(despues) - set(antes)


@pytest.mark.parametrize("script, argv", [
    ("vault_project_overview", []),
    ("vault_project_status", ["--status", "en_desarrollo", "--summary", "x"]),
])
def test_ap63_las_tools_de_proyecto_no_fundan_carpetas_fantasma(registro, script, argv):
    """Las dos creaban `01_Projects/<lo que llegase>/` en la primera llamada:
    eran la forma por la que un typo se volvía un proyecto. Ahora fundarlo es
    `vault_project --add` y nada más."""
    import os
    import subprocess

    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / f"{script}.py"), "--project", "Otra Cosa", *argv],
        env=dict(os.environ, VAULT_ROOT=str(registro), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=120,
    )
    r = json.loads(proceso.stdout[proceso.stdout.index("{"):])
    assert proceso.returncode == 1 and r["error_code"] == "PROJECT_NOT_FOUND", r
    assert sorted(p.name for p in (registro / "01_Projects").iterdir()) == ["mi-api"]


def test_ap63_la_fabrica_vive_junto_a_emit_fallo_y_la_tool_la_reexporta():
    """Vivió en `vault_project` (Autoría); cada tool de otro contexto que la
    importaba de allí abría un cruce. Vive en `vault_errors`, que todas esas
    tools ya importaban, y `vault_project` la reexporta sin derogarla."""
    import vault_project
    from vault.autoria import proyectos as viejo
    from vault.kernel import proyectos as dueno

    assert vault_project.proyecto_registrado is vault_errors.proyecto_registrado
    assert viejo is dueno


@pytest.mark.parametrize("modulo, argv", [
    ("vault.autoria.knowledge_save",
     ["--category", "concepts", "--title", "T", "--content", "c"]),
    ("vault.autoria.knowledge_get", ["--query", "t"]),
])
def test_ap63_los_entry_modules_instalados_resuelven(registro, modulo, argv, capsys):
    """El código instalado no importa `scripts/`; resuelve con la fábrica y la
    tabla del núcleo. `--root` va detrás de `--project` a propósito: el
    registro sale de él aunque argparse aún no lo haya leído."""
    import importlib

    main = importlib.import_module(modulo).main
    with pytest.raises(SystemExit) as salida:
        main(["--project", "mi-apii", *argv, "--root", str(registro)])
    assert salida.value.code == 1
    r = json.loads(capsys.readouterr().out)
    assert r["error_code"] == "PROJECT_NOT_FOUND" and r["sugerencias"] == ["mi-api"], r
    assert r["tool"] == modulo.replace("vault.autoria.", "vault_")
    assert sorted(p.name for p in (registro / "01_Projects").iterdir()) == ["mi-api"]


def test_ap63_la_traduccion_de_fallos_tiene_un_solo_dueno():
    from vault.kernel import errores

    assert vault_errors.MAPA_DE_FALLOS is errores.MAPA_DE_FALLOS

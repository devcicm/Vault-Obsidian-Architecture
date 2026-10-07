"""Todo paquete de terceros que la suite importa está declarado en `pyproject.toml`.

`test_esquema_por_version` mide los JSON Schema de `schemas/` con `jsonschema`,
que es lo que usaría un consumidor sin Python del estándar (AP-44). Pero
`jsonschema` no estaba en ninguna lista de dependencias, y el test lo cargaba
con `importorskip`: en una máquina sin él —la CI instala `.[dev]` y nada más—
el contrato de los esquemas se daba por medido sin que nadie lo midiera. Un
test que se salta en silencio cuando falta lo que necesita es un verde falso.

Aquí la lista no se escribe: sale de los imports de `tests/` y se compara con
lo que declaran `dependencies`, el extra `dev` y `build-system.requires`.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Nombre de import → nombre de distribución, solo donde difieren.
_DISTRIBUCION = {"yaml": "pyyaml"}


def _locales():
    nombres = {p.stem for p in (REPO_ROOT / "scripts").glob("*.py")}
    nombres |= {p.stem for p in (REPO_ROOT / "tests").rglob("*.py")}
    nombres |= {p.name for p in REPO_ROOT.iterdir() if p.is_dir()}
    nombres |= {p.stem for p in REPO_ROOT.glob("*.py")}
    return nombres


def _importados_por_la_suite():
    locales = _locales()
    terceros = {}
    for fichero in (REPO_ROOT / "tests").rglob("*.py"):
        arbol = ast.parse(fichero.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                modulos = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
                modulos = [nodo.module]
            elif (isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "importorskip"
                  and nodo.args and isinstance(nodo.args[0], ast.Constant)):
                modulos = [nodo.args[0].value]
            else:
                continue
            for modulo in modulos:
                raiz = modulo.split(".")[0]
                if raiz in sys.stdlib_module_names or raiz in locales or raiz == "tomllib":
                    continue
                terceros.setdefault(raiz, fichero.name)
    return terceros


def _declarados():
    tomllib = pytest.importorskip("tomllib")
    datos = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requisitos = list(datos["project"].get("dependencies", []))
    requisitos += datos["project"].get("optional-dependencies", {}).get("dev", [])
    requisitos += datos.get("build-system", {}).get("requires", [])
    return {re.split(r"[<>=!~\[; ]", r, maxsplit=1)[0].strip().lower() for r in requisitos}


@pytest.mark.skipif(sys.version_info < (3, 10), reason="sys.stdlib_module_names es de 3.10")
def test_todo_paquete_que_importa_la_suite_esta_declarado():
    declarados = _declarados()
    faltan = {m: f for m, f in _importados_por_la_suite().items()
              if _DISTRIBUCION.get(m, m).lower() not in declarados}
    assert not faltan, f"importados por la suite sin declarar en pyproject.toml: {faltan}"


def test_el_contrato_de_los_esquemas_no_se_salta_si_falta_jsonschema():
    """Declarada la dependencia, su ausencia es un fallo de instalación, no un skip."""
    texto = (REPO_ROOT / "tests" / "test_esquema_por_version.py").read_text(encoding="utf-8")
    assert 'importorskip("jsonschema")' not in texto

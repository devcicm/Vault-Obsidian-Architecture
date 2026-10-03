"""AP-63, P3 — un solo criterio para «esto es del proyecto».

Cada lector decidía a su manera si una entrada era de un proyecto: `==`
exacto, `.lower() ==` o **subcadena**. Con la subcadena, `--project api`
devolvía lo de `mi-api` y `--project ans` cualquier ruta que contuviera
«ans». Tres criterios para una identidad es AP-57; el dueño es
`vault.kernel.proyectos.pertenencia`, y el guard de abajo hace fallar una
comparación propia nueva.
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.kernel.proyectos import Proyecto, Registro, pertenencia  # noqa: E402

#: El dueño del criterio: aquí sí se compara.
DUENO = ROOT / "vault" / "kernel" / "proyectos.py"


def _registro():
    return Registro({
        "mi-api": Proyecto("mi-api", aliases=("Mi API", "comun")),
        "api": Proyecto("api"),
        "otra": Proyecto("otra", aliases=("comun",)),
    })


def test_ap63_pertenencia_acepta_slug_alias_y_variantes():
    es_del = pertenencia(_registro(), "Mi API")
    assert [es_del(v) for v in ("mi-api", "Mi API", "mi_api", "MI-API")] == [True] * 4


def test_ap63_pertenencia_no_es_subcadena():
    assert pertenencia(_registro(), "api")("mi-api") is False
    assert pertenencia(_registro(), "mi-api")("api") is False


def test_ap63_un_alias_ambiguo_no_se_atribuye_a_nadie():
    assert pertenencia(_registro(), "mi-api")("comun") is False
    assert pertenencia(_registro(), "otra")("comun") is False


def test_ap63_sin_registro_compara_por_la_clave_propia():
    es_del = pertenencia(Registro(), "Demo")
    assert es_del("demo") and not es_del("demo-x") and not es_del(None)


def _comparaciones_propias(raiz: Path = ROOT):
    """`Compare` que decide pertenencia a un proyecto fuera del dueño."""

    def toca_proyecto(nodo: ast.AST) -> bool:
        for n in ast.walk(nodo):
            if isinstance(n, ast.Name) and n.id in ("project", "project_lower"):
                return True
            if (isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "get"
                    and n.args and isinstance(n.args[0], ast.Constant)
                    and n.args[0].value == "project"):
                return True
        return False

    sitios = []
    for zona in ("scripts", "vault"):
        for ruta in sorted((raiz / zona).rglob("*.py")):
            if "__pycache__" in ruta.parts or "_archived" in ruta.parts or ruta == DUENO:
                continue
            for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
                if not isinstance(nodo, ast.Compare):
                    continue
                if not all(isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn))
                           for op in nodo.ops):
                    continue
                lados = [nodo.left, *nodo.comparators]
                # Los dos lados hablan de proyecto: es decidir si uno es el otro.
                # `"project" in data` o `project == ""` no lo son.
                ambos = sum(toca_proyecto(l) for l in lados) >= 2
                # `project.lower() in <texto>`: la subcadena, sobre lo que sea.
                # `project in data` (clave de un dict) no lleva `.lower()`.
                subcadena = (
                    isinstance(nodo.ops[0], (ast.In, ast.NotIn))
                    and toca_proyecto(nodo.left)
                    and any(getattr(getattr(n, "func", None), "attr", "") == "lower"
                            for n in ast.walk(nodo.left))
                )
                if ambos or subcadena:
                    sitios.append(f"{ruta.relative_to(raiz).as_posix()}:{nodo.lineno}")
    return sitios


def test_ap63_ningun_lector_decide_la_pertenencia_por_su_cuenta():
    assert _comparaciones_propias() == []


def test_ap63_el_guard_ve_las_tres_formas(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "vault").mkdir()
    (tmp_path / "scripts" / "vault_x.py").write_text(
        "a = [d for d in xs if d.get('project') == project]\n"
        "b = [d for d in xs if d.get('project', '').lower() == project.lower()]\n"
        "c = [e for e in xs if project.lower() in e.get('path', '').lower()]\n"
        "ok = 'project' in data and project == ''\n",
        encoding="utf-8",
    )
    assert len(_comparaciones_propias(tmp_path)) == 3


def _cli(vault: Path, script: str, *args: str) -> dict:
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        env=dict(os.environ, VAULT_ROOT=str(vault), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=180,
    )
    return json.loads(p.stdout[p.stdout.index("{"):])


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    for slug, alias in (("mi-api", "Mi API"), ("api", None)):
        args = ["--add", slug] + (["--alias", alias] if alias else [])
        assert _cli(vault, "vault_project.py", *args)["ok"]
    return vault


def test_ap63_change_log_no_filtra_por_subcadena(tmp_path):
    vault = _vault(tmp_path)
    for ruta in ("01_Projects/mi-api/status.md", "01_Projects/api/status.md"):
        assert _cli(vault, "vault_change_log.py", "--action", "created",
                    "--path", ruta, "--reason", "prueba")["ok"]
    r = _cli(vault, "vault_change_log.py", "--query", "--project", "api")
    assert [e["path"] for e in r["entries"]] == ["01_Projects/api/status.md"], r


def test_ap63_un_valor_anterior_al_registro_sigue_siendo_del_proyecto(tmp_path):
    """Un índice escrito antes de AP-63 guarda `project: Mi API`; el lector
    recibe ya el slug y antes no lo encontraba con su `==`."""
    vault = _vault(tmp_path)
    indice = vault / "05_Patterns" / "index.json"
    indice.parent.mkdir(parents=True)
    indice.write_text(json.dumps({"patterns": [
        {"title": "Reintentos", "project": "Mi API", "type": "design"},
        {"title": "Colas", "project": "api", "type": "design"},
    ]}), encoding="utf-8")
    r = _cli(vault, "vault_pattern_list.py", "--project", "mi-api")
    assert r["ok"], r
    assert [p["title"] for p in r["patterns"]] == ["Reintentos"], r

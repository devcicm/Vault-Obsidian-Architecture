"""AP-52 — `recovery` es un objeto, también cuando el sitio trae su pista.

Medido en v40.34: nueve sitios del grupo 35 hacían `env = emit_error(…)` y
luego `env["recovery"] = "elige uno"`. La llamada cumplía el contrato y la
línea siguiente lo deshacía: el envelope salía con `recovery` en cadena, sin
`action`, y el consumidor que decide por `recovery.action` no tenía por dónde.
El guard de AP-52 mira la llamada, no lo que se hace con su resultado.

La pista del sitio no se pierde: viaja en `recovery.hint` vía `pista=`.
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from vault.kernel.errores import ERROR_CATALOG, problemas_de_forma  # noqa: E402


def recovery_en_cadena(raiz: Path = RAIZ):
    """`algo["recovery"] = <texto>`: pisa el objeto que puso el catálogo."""
    sitios = []
    for zona in ("scripts", "vault", "cli", "vault_toolkit"):
        for ruta in sorted((raiz / zona).rglob("*.py")):
            if "__pycache__" in ruta.parts or "_archived" in ruta.parts:
                continue
            for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
                if not isinstance(nodo, ast.Assign):
                    continue
                texto = isinstance(nodo.value, ast.JoinedStr) or (
                    isinstance(nodo.value, ast.Constant) and isinstance(nodo.value.value, str))
                for t in nodo.targets:
                    if (texto and isinstance(t, ast.Subscript)
                            and isinstance(t.slice, ast.Constant)
                            and t.slice.value == "recovery"):
                        sitios.append(f"{ruta.relative_to(raiz).as_posix()}:{nodo.lineno}")
    return sitios


def test_ningun_sitio_pisa_recovery_con_texto():
    assert recovery_en_cadena() == []


def test_el_detector_ve_la_forma_que_persigue(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "vault_x.py").write_text(
        "env['recovery'] = 'elige uno'\n"
        "env['recovery'] = f'usa {x}'\n"
        "env['recovery'] = {**env['recovery'], 'hint': 'ok'}\n",
        encoding="utf-8",
    )
    assert recovery_en_cadena(tmp_path) == ["scripts/vault_x.py:1", "scripts/vault_x.py:2"]


def test_la_pista_va_a_hint_y_la_accion_sale_del_catalogo():
    from vault_errors import emit_error

    env = emit_error("vault_x", "CONFLICTING_ARGS", "choque", pista="elige uno")
    assert problemas_de_forma(env) == []
    assert env["recovery"]["hint"] == "elige uno"
    assert env["recovery"]["action"] == ERROR_CATALOG["CONFLICTING_ARGS"]["recovery"]["action"]
    assert ERROR_CATALOG["CONFLICTING_ARGS"]["recovery"]["hint"] != "elige uno"


@pytest.mark.parametrize("tool,argv", [
    ("vault_ciclos", ["--freeze", "--check"]),
    ("vault_criterios", ["--freeze", "--check"]),
    ("vault_excepcion_declarada", ["--freeze", "--check"]),
    ("vault_frontmatter_heal", ["--apply", "--check"]),
    ("vault_fuente_unica", ["--freeze", "--check"]),
    ("vault_kernel", ["--freeze", "--check"]),
    ("vault_produccion", ["--guia", "--check"]),
    ("vault_recursos", ["--freeze", "--check"]),
])
def test_argumentos_en_conflicto_salen_en_forma(tool, argv):
    """Con la salida real del proceso: el criterio del consumidor (AP-44)."""
    p = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / f"{tool}.py"), *argv],
        env=dict(os.environ, PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(RAIZ), timeout=300,
    )
    env = json.loads(p.stdout[p.stdout.index("{"):])
    assert env["error_code"] == "CONFLICTING_ARGS", env
    assert problemas_de_forma(env) == [], env
    assert env["recovery"]["hint"] == "elige uno"


def test_modulo_inexistente_en_kernel_trace_sale_en_forma():
    import vault_kernel

    env = vault_kernel.trace("no_existe_este_modulo")
    assert problemas_de_forma(env) == [], env
    assert "stem" in env["recovery"]["hint"]

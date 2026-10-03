"""AP-63, P5 — una sesión atada a un proyecto no escribe en otro.

`VAULT_PROJECT` + `VAULT_PROJECT_LOCK=1`: todo `--project` pasa por la
fábrica `proyectos.proyecto_registrado`, y con el candado puesto un nombre que
resuelve a otro proyecto sale con `PROJECT_LOCKED` antes de que la tool cree
nada. `vault mcp-path --project` emite esa configuración con el slug ya
resuelto por Python; el servidor solo copia el entorno.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.kernel import proyectos  # noqa: E402
from vault.kernel.fallos import FalloDeDominio  # noqa: E402


def _cli(vault: Path, script: str, *args: str, **entorno: str):
    env = dict(os.environ, VAULT_ROOT=str(vault), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    env.pop("VAULT_PROJECT", None)
    env.pop("VAULT_PROJECT_LOCK", None)
    env.update(entorno)
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args], env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=180,
    )
    return p.returncode, json.loads(p.stdout[p.stdout.index("{"):])


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    (v / "00_System").mkdir(parents=True)
    assert _cli(v, "vault_project.py", "--add", "mi-api", "--alias", "Pasarela")[1]["ok"]
    assert _cli(v, "vault_project.py", "--add", "otra")[1]["ok"]
    return v


def _registro():
    return proyectos.Registro({
        "mi-api": proyectos.Proyecto("mi-api", aliases=("Pasarela",)),
        "otra": proyectos.Proyecto("otra"),
    })


def test_ap63_sin_candado_vault_project_no_restringe():
    assert proyectos.proyecto_de_sesion(_registro(), {"VAULT_PROJECT": "mi-api"}) is None
    proyectos.comprobar_sesion(_registro(), "otra", {"VAULT_PROJECT": "mi-api"})


def test_ap63_el_candado_resuelve_el_proyecto_de_sesion_por_alias():
    entorno = {"VAULT_PROJECT": "Pasarela", "VAULT_PROJECT_LOCK": "1"}
    assert proyectos.proyecto_de_sesion(_registro(), entorno) == "mi-api"
    proyectos.comprobar_sesion(_registro(), "mi-api", entorno)
    with pytest.raises(FalloDeDominio) as e:
        proyectos.comprobar_sesion(_registro(), "otra", entorno)
    assert e.value.causa == "PROYECTO_FUERA_DE_SESION"
    assert e.value.datos["session_project"] == "mi-api"


def test_ap63_candado_sin_proyecto_cierra_en_vez_de_abrir():
    with pytest.raises(FalloDeDominio) as e:
        proyectos.comprobar_sesion(_registro(), "mi-api", {"VAULT_PROJECT_LOCK": "1"})
    assert e.value.causa == "PROYECTO_FUERA_DE_SESION"


def test_ap63_una_tool_con_candado_no_escribe_en_otro_proyecto(vault):
    candado = {"VAULT_PROJECT": "mi-api", "VAULT_PROJECT_LOCK": "1"}
    notas = lambda: sorted(p.relative_to(vault).as_posix() for p in vault.rglob("*.md"))  # noqa: E731
    antes = notas()
    args = ("--title", "Reinicio", "--trigger", "caida", "--category", "deploy", "--steps", '["parar", "arrancar"]')
    codigo, r = _cli(vault, "vault_runbook_save.py", "--project", "otra", *args, **candado)
    assert codigo == 1 and r["error_code"] == "PROJECT_LOCKED", r
    assert r["session_project"] == "mi-api" and r["project"] == "otra"
    # Solo la traza del fallo, dentro de 00_System/: ninguna nota.
    assert notas() == antes

    # El proyecto de la sesión, por alias, sí pasa.
    codigo, r = _cli(vault, "vault_runbook_save.py", "--project", "Pasarela", *args, **candado)
    assert r.get("error_code") != "PROJECT_LOCKED", r


def _mcp_path(*args: str) -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("VAULT_ROOT", None)
    p = subprocess.run(
        [sys.executable, "-c",
         "import sys; from vault.product_cli import main; sys.exit(main(sys.argv[1:]))",
         "mcp-path", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=env, timeout=120,
    )
    salida = p.stdout or p.stderr  # los errores de la CLI de producto van a stderr
    return json.loads(salida[salida.index("{"):])


def test_ap63_mcp_path_ata_la_sesion_con_el_slug_resuelto(vault):
    d = _mcp_path("--root", str(vault), "--project", "Pasarela")
    assert d["ok"] and d["project"] == "mi-api", d
    assert d["project_resolved_from"] == "alias"
    env = d["config"]["env"]
    assert env["VAULT_PROJECT"] == "mi-api" and env["VAULT_PROJECT_LOCK"] == "1"
    assert env["VAULT_ROOT"] == str(vault.resolve())


def test_ap63_mcp_path_no_inventa_el_proyecto(vault):
    d = _mcp_path("--root", str(vault), "--project", "fantasma")
    assert d["ok"] is False and d["error_code"] == "PROJECT_NOT_FOUND", d
    d = _mcp_path("--project", "mi-api")
    assert d["ok"] is False and d["error_code"] == "MISSING_REQUIRED_ARG", d

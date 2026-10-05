"""AP-36 — un `VAULT_ROOT` que no existe no siembra un vault fantasma.

Medido en v40.34 con `VAULT_ROOT=%V%` (variable de Windows sin expandir, que
un cliente MCP pasa tal cual): `vault_write` devolvía `ok: true` y creaba
`00_System/`, `99_Index/`, `19_Audits/` y la nota en `<cwd>/%V%`. El propio
repo acumulaba un `scripts/%V%/` así. Una raíz explícita que no existe es un
error de configuración, no una orden de crearla: `vault_init` ya lo rechaza.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CUERPO = "uno dos tres cuatro cinco seis\nsiete ocho nueve diez once\ndoce trece catorce"


def _ejecutar(cwd: Path, raiz: str, script: str, *argv: str) -> dict:
    entorno = {k: v for k, v in os.environ.items()
               if k not in ("VAULT_PERMISSIVE_ROOT", "VAULT_STRICT_ROOT")}
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *argv],
        env=dict(entorno, VAULT_ROOT=raiz, PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


def test_ap36_vault_root_sin_expandir_no_crea_nada(tmp_path):
    env = _ejecutar(
        tmp_path, "%V%", "vault_write.py", "--folder", "07_Knowledge",
        "--title", "Hola", "--content", CUERPO, "--tags", "t",
        "--meta", json.dumps({"agent": "pytest"}),
    )
    assert env["ok"] is False, env
    assert list(tmp_path.iterdir()) == []


def test_ap36_vault_root_absoluto_inexistente_no_se_crea(tmp_path):
    raiz = tmp_path / "no-existe"
    env = _ejecutar(
        tmp_path, str(raiz), "vault_write.py", "--folder", "07_Knowledge",
        "--title", "Hola", "--content", CUERPO, "--tags", "t",
        "--meta", json.dumps({"agent": "pytest"}),
    )
    assert env["ok"] is False, env
    assert not raiz.exists()



def test_ap36_la_pista_del_rechazo_habla_de_la_variable_y_no_de_99_index(tmp_path):
    """La pista genérica de VAULT_NOT_FOUND manda a crear `99_Index/`, que con
    una VAULT_ROOT que apunta a nada no arregla nada (QA 2026-10-04)."""
    env = _ejecutar(tmp_path, str(tmp_path / "no-existe"), "vault_init.py", "--json")
    assert env["error_code"] == "VAULT_NOT_FOUND"
    pista = env["recovery"]["hint"]
    assert "99_Index" not in pista
    assert "VAULT_ROOT" in pista and "vault init" in pista

def test_una_raiz_que_existe_sigue_escribiendo(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge"):
        (raiz / seccion).mkdir(parents=True)
    env = _ejecutar(
        tmp_path, str(raiz), "vault_write.py", "--folder", "07_Knowledge",
        "--title", "Hola", "--content", CUERPO, "--tags", "t",
        "--meta", json.dumps({"agent": "pytest"}),
    )
    assert env["ok"] is True, env
    assert (raiz / "07_Knowledge" / "Hola.md").is_file()


def test_el_origen_se_declara_de_baja_confianza(tmp_path):
    codigo = (
        "import vault_raiz as r;"
        "print(r.vault_root_origin(), r.vault_root_is_confident())"
    )
    proceso = subprocess.run(
        [sys.executable, "-c", codigo],
        env=dict(os.environ, VAULT_ROOT=str(tmp_path / "no-existe")),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS),
    )
    assert proceso.stdout.split() == ["env_inexistente", "False"], proceso.stderr


def test_el_origen_se_reevalua_si_el_directorio_aparece_o_hay_override(tmp_path):
    """El origen se fija al importar; un fixture o una sesión larga que crea
    el directorio después, o que fija el vault con set_vault_root(), no puede
    quedarse bloqueado por lo que se vio en el import."""
    raiz = tmp_path / "tarde"
    otro = tmp_path / "otro"
    otro.mkdir()
    codigo = (
        "import sys, vault_raiz as r;"
        "antes = (r.vault_root_origin(), r.vault_root_is_confident());"
        f"r.set_vault_root(r'{otro}');"
        "con_override = (r.vault_root_origin(), r.vault_root_is_confident());"
        "r.reset_vault_root();"
        f"__import__('pathlib').Path(r'{raiz}').mkdir();"
        "despues = (r.vault_root_origin(), r.vault_root_is_confident());"
        "print(antes, con_override, despues)"
    )
    proceso = subprocess.run(
        [sys.executable, "-c", codigo],
        env=dict(os.environ, VAULT_ROOT=str(raiz)),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS),
    )
    assert proceso.stdout.strip() == (
        "('env_inexistente', False) ('explicit_override', True) ('env', True)"
    ), proceso.stderr

"""`vault_section` — declarar, listar y retirar secciones propias (CN-02).

`vault_registry` lee y valida `00_System/secciones.json`; esta tool es la única
que lo escribe. Se ejecuta por subprocess con `VAULT_ROOT` y
`VAULT_STRICT_ROOT=1`, como la ve un consumidor, contra un vault de `tmp_path`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_registry as reg  # noqa: E402


def _ejecutar(raiz: Path, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_section.py"), *argv, "--json"],
        env=dict(
            os.environ,
            VAULT_ROOT=str(raiz),
            VAULT_STRICT_ROOT="1",
            PYTHONIOENCODING="utf-8",
            VAULT_AGENT="system",
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(SCRIPTS),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.fixture
def raiz(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / seccion).mkdir(parents=True)
    return raiz


def _registro(raiz: Path) -> dict:
    return json.loads((raiz / reg.SECCIONES_PROPIAS_RUTA).read_text(encoding="utf-8"))


def test_add_declara_la_seccion_y_crea_la_carpeta(raiz):
    r = _ejecutar(raiz, "--add", "22_Scripts", "--documentacion", "referencia",
                  "--description", "scripts de despliegue")
    assert r["ok"] and r["written"] == 1 and r["folder"] == "22_Scripts"
    assert (raiz / "22_Scripts").is_dir()
    entrada = _registro(raiz)["secciones"][0]
    assert entrada == {"folder": "22_Scripts", "documentacion": "referencia",
                       "description": "scripts de despliegue", "status": "activa"}
    assert "22_Scripts" in reg.secciones_del_vault(raiz)


def test_add_conserva_una_carpeta_que_ya_existe(raiz):
    (raiz / "22_Scripts").mkdir()
    (raiz / "22_Scripts" / "deploy.md").write_text("x\n", encoding="utf-8")
    r = _ejecutar(raiz, "--add", "22_Scripts", "--documentacion", "guia")
    assert r["ok"] and r["created_folder"] is False
    assert (raiz / "22_Scripts" / "deploy.md").read_text(encoding="utf-8") == "x\n"


@pytest.mark.parametrize("argv,codigo", [
    (["--add", "scripts", "--documentacion", "guia"], "INVALID_FOLDER"),
    (["--add", "07_Otra", "--documentacion", "guia"], "INVALID_FOLDER"),
    (["--add", "22_X", "--documentacion", "manual"], "INVALID_VALUE"),
    (["--add", "22_X"], "MISSING_REQUIRED_ARG"),
    (["--retire", "23_Nada"], "UNKNOWN_SECTION"),
    (["--retire", "07_Knowledge"], "INVALID_FOLDER"),
])
def test_entradas_invalidas_no_escriben_nada(raiz, argv, codigo):
    r = _ejecutar(raiz, *argv)
    assert r["ok"] is False and r["error_code"] == codigo
    assert not (raiz / reg.SECCIONES_PROPIAS_RUTA).exists()
    assert not (raiz / "22_X").exists()


def test_add_rechaza_un_numero_o_nombre_ya_declarado(raiz):
    _ejecutar(raiz, "--add", "22_Scripts", "--documentacion", "guia")
    antes = _registro(raiz)
    r = _ejecutar(raiz, "--add", "22_Otra", "--documentacion", "guia")
    assert r["ok"] is False and r["error_code"] == "INVALID_FOLDER"
    assert _registro(raiz) == antes


def test_retire_no_borra_nada_y_anota_el_reemplazo(raiz):
    _ejecutar(raiz, "--add", "22_Viejo", "--documentacion", "guia")
    _ejecutar(raiz, "--add", "23_Nuevo", "--documentacion", "guia")
    (raiz / "22_Viejo" / "nota.md").write_text("x\n", encoding="utf-8")
    r = _ejecutar(raiz, "--retire", "22_Viejo", "--superseded-by", "23_Nuevo")
    assert r["ok"] and r["written"] == 1
    viejo = [s for s in _registro(raiz)["secciones"] if s["folder"] == "22_Viejo"][0]
    assert viejo["status"] == "retirada" and viejo["superseded_by"] == "23_Nuevo"
    assert (raiz / "22_Viejo" / "nota.md").exists()
    assert "22_Viejo" in reg.secciones_del_vault(raiz)


def test_retire_con_reemplazo_desconocido_no_escribe(raiz):
    _ejecutar(raiz, "--add", "22_Viejo", "--documentacion", "guia")
    antes = _registro(raiz)
    r = _ejecutar(raiz, "--retire", "22_Viejo", "--superseded-by", "40_Nada")
    assert r["ok"] is False and r["error_code"] == "UNKNOWN_SECTION"
    assert _registro(raiz) == antes


def test_list_publica_propias_y_carpetas_sin_seccion(raiz):
    _ejecutar(raiz, "--add", "22_Scripts", "--documentacion", "referencia")
    (raiz / "scripts").mkdir()
    (raiz / ".obsidian").mkdir()
    r = _ejecutar(raiz, "--list")
    assert r["ok"] and r["written"] == 0
    assert r["standard"] == len(reg.ORDERED_SECTIONS)
    assert [s["folder"] for s in r["sections"]] == ["22_Scripts"]
    assert r["sections"][0]["exists"] is True
    assert r["folders_without_section"] == ["scripts"]
    assert r["free_range"] == list(reg.NUMEROS_PROPIOS)


def test_un_registro_roto_falla_en_voz_alta_y_no_se_reescribe(raiz):
    destino = raiz / reg.SECCIONES_PROPIAS_RUTA
    destino.write_text("{roto", encoding="utf-8")
    for argv in (["--list"], ["--add", "22_X", "--documentacion", "guia"]):
        r = _ejecutar(raiz, *argv)
        assert r["ok"] is False and r["error_code"] == "DATA_FILE_CORRUPT"
    assert destino.read_text(encoding="utf-8") == "{roto"

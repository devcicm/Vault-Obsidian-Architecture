"""O8: el presupuesto de las tools que recorren el vault entero.

Medido en un vault ajeno real de 15.785 ficheros: el presupuesto genérico de
60 s existe para detectar una tool COLGADA, no para acotar trabajo legítimo —
el init moría a mitad de escritura dejando índices y sello. La cura vive en el
dueño (`vault_errors.PRESUPUESTO_DE_VAULT = max(VAULT_TOOL_TIMEOUT, 3600)`) y
la comparten las tools que recorren el vault entero; `vault_entorno
--limites` publica el registro con su help para que el presupuesto no se
descubra leyendo once ficheros.
"""

import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_errors  # noqa: E402


def _presupuesto_de(monkeypatch, defecto, script):
    visto = {}

    def wrap_main_falso(fn, tool_name, timeout=None):
        visto["timeout"] = timeout
        return 0

    monkeypatch.setattr(vault_errors, "wrap_main", wrap_main_falso)
    monkeypatch.setattr(vault_errors, "TOOL_TIMEOUT_SECONDS", defecto)
    with pytest.raises(SystemExit):
        runpy.run_path(str(SCRIPTS / script), run_name="__main__")
    return visto["timeout"]


def test_init_y_reindex_comparten_el_fondo(monkeypatch):
    assert _presupuesto_de(monkeypatch, 60, "vault_init.py") == 3600
    assert _presupuesto_de(monkeypatch, 60, "vault_reindex.py") == 3600


def test_un_limite_exportado_mayor_sigue_mandando(monkeypatch):
    assert _presupuesto_de(monkeypatch, 7200, "vault_init.py") == 7200


def test_audit_y_quality_heredan_el_fondo(monkeypatch):
    assert _presupuesto_de(monkeypatch, 60, "vault_audit.py") == 3600
    assert _presupuesto_de(monkeypatch, 60, "vault_quality_check.py") == 3600


def test_la_derivacion_vive_en_el_dueno_y_se_resuelve_al_llamarse(monkeypatch):
    """AP-49: función, no constante — un límite exportado después manda."""
    monkeypatch.setattr(vault_errors, "TOOL_TIMEOUT_SECONDS", 60)
    assert vault_errors.presupuesto_de_vault() == 3600
    monkeypatch.setattr(vault_errors, "TOOL_TIMEOUT_SECONDS", 7200)
    assert vault_errors.presupuesto_de_vault() == 7200


def test_las_tools_de_vault_entero_usan_el_presupuesto(monkeypatch):
    """Cada tool que recorre el vault entero pide el presupuesto del dueño.

    Se comprueba EJECUTANDO la tool (con `wrap_main` falsificado, que es lo
    que hace el precedente de `vault_reindex`) y no leyendo su código: un test
    que lee el script por ruta se queda mirando una copia y no lo que corre
    (la regla del alias).
    """
    for script in ("vault_audit.py", "vault_quality_check.py", "vault_graph.py",
                   "vault_master_index.py", "vault_merge.py",
                   "vault_frontmatter_heal.py"):
        assert _presupuesto_de(monkeypatch, 60, script) == 3600, script


def test_el_presupuesto_esta_documentado_en_el_entorno():
    """`vault_entorno --limites` publica el registro con help: el presupuesto
    no se descubre leyendo once ficheros (la lección del vault de 15.785)."""
    import vault_entorno

    assert "VAULT_TOOL_TIMEOUT" in vault_entorno.VARIABLES
    v = vault_entorno.VARIABLES["VAULT_TOOL_TIMEOUT"]
    assert v.default == 60
    assert v.tipo == "entero"


def test_el_cli_filtra_y_publica_el_presupuesto(tmp_path):
    """El comando: `--filtro` acota, `--json` es consumible, y un filtro sin
    coincidencias sale con 1."""
    env = {k: v for k, v in os.environ.items() if k != "VAULT_TOOL_TIMEOUT"}
    env["PYTHONIOENCODING"] = "utf-8"
    cli = SCRIPTS / "vault_entorno.py"

    p = subprocess.run(
        [sys.executable, str(cli), "--json", "--filtro", "TOOL_TIMEOUT"],
        capture_output=True, text=True, env=env, encoding="utf-8",
        errors="replace", timeout=120)
    filas = json.loads(p.stdout)
    por_nombre = {f["variable"]: f for f in filas}
    assert "VAULT_TOOL_TIMEOUT" in por_nombre
    assert por_nombre["VAULT_TOOL_TIMEOUT"]["default"] == 60
    assert por_nombre["VAULT_TOOL_TIMEOUT"]["valor_actual"] == 60
    assert por_nombre["VAULT_TOOL_TIMEOUT"]["contexto"] == "kernel"

    p = subprocess.run([sys.executable, str(cli), "--filtro", "inexistente-xyz"],
                       capture_output=True, text=True, env=env,
                       encoding="utf-8", errors="replace", timeout=120)
    assert p.returncode == 1
    assert "sin variables" in p.stdout

    p = subprocess.run([sys.executable, str(cli), "--limites"],
                       capture_output=True, text=True, env=env,
                       encoding="utf-8", errors="replace", timeout=120)
    assert p.returncode == 0
    assert "VAULT_TOOL_TIMEOUT" in p.stdout
    assert "VAULT_SMOKE_TIMEOUT" in p.stdout

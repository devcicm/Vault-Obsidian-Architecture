"""El contrato que no miente (v41.15).

Tres cosas que la auditoria del repo encontro midiendo, no leyendo:

1. `vault --version` decia **41.12** con el estandar en 41.15: el metadata de
   una instalacion editable se congela en el momento de instalar, y la CLI lo
   leia sin mirar el codigo que se estaba ejecutando.
2. `vault_move` imprimia **prosa** («Movido: …», «Error: …») salvo que se
   pasara `--json`, mientras el resto de las tools imprimen el envelope
   siempre: un consumidor que parsea stdout se llevaba texto donde el
   contrato publica un envelope (AP-40).
3. Dos tools **declaraban un side effect falso**: `vault_test_save` annonces
   `01_Projects/{project}/tests/` y escribe en `15_Tests/{test_type}/`;
   `vault_bibliography_save` annonce `07_Knowledge/bibliography/` y escribe
   en `12_Bibliography/`. Y `vault_code_sync` no decia que `--fix` escribe
   DENTRO de los ficheros del proyecto (fuera del vault): un side effect sin
   declarar no se puede revisar (AP-36).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))


def test_la_version_de_la_cli_no_es_menor_que_la_del_codigo():
    """La CLI dice la version del toolkit que corre, no la de la instalacion."""
    import vault_version
    from vault.product_cli import toolkit_version

    assert toolkit_version() == vault_version.CURRENT_VERSION.lstrip("v"), (
        f"la CLI dice {toolkit_version()} y el codigo va en "
        f"{vault_version.CURRENT_VERSION}: el metadata de la instalacion esta "
        "congelado y el codigo que corre es la verdad")


def test_vault_move_con_json_responde_un_envelope(tmp_path):
    """Es lo que pasa siempre el MCP: con `--json`, la salida es envelope.

    La salida dual ES el contrato publicado y lo fija
    `tests/test_move_salida_json.py`: con `--json` envelope (el servidor),
    sin `--json` prosa (el humano). La auditoria de la tanda 3 lo habia
    leido como defecto y no lo era: aqui queda medido en su lado maquina.
    """
    raiz = tmp_path / "v"
    for carpeta in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / carpeta).mkdir(parents=True)
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_AGENT="test",
               VAULT_VOICE="0", PYTHONIOENCODING="utf-8")
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_move.py"),
         "--json", "--from", "07_Knowledge/no-existe.md", "--to", "07_Knowledge/otra.md"],
        capture_output=True, text=True, env=env, encoding="utf-8", errors="replace",
        timeout=300)
    salida = r.stdout.strip()
    assert salida.startswith("{"), f"sin envelope: {salida[:200]}"
    env_error = json.loads(salida)
    assert env_error["ok"] is False and env_error["error_code"]

def test_los_side_effects_declarados_no_contradicen_las_secciones():
    """Un side effect que nombra una seccion tiene que ser en esa seccion."""
    import vault_mcp_catalog as mc

    esperado = {
        # (tool, seccion que declara, seccion donde escribe)
        "vault_test_save": ("15_Tests",),
        "vault_bibliography_save": ("12_Bibliography",),
    }
    for tool, (seccion,) in esperado.items():
        declarados = " ".join(mc.TOOLS_CATALOG[tool].get("side_effects") or [])
        assert seccion in declarados, (
            f"{tool} declara «{declarados}» y escribe en {seccion}")


def test_el_fix_que_escribe_fuera_del_vault_se_declara():
    """`vault_code_sync --fix` escribe en los ficheros del proyecto: fuera del
    vault (AP-36). Un side effect sin declarar no se puede revisar."""
    import vault_mcp_catalog as mc

    declarados = " ".join(mc.TOOLS_CATALOG["vault_code_sync"].get("side_effects") or [])
    assert "--fix" in declarados, declarados
    assert "FUERA del vault" in declarados, declarados

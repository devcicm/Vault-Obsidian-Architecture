"""`--init` / `--target` solo aceptan versiones del registro (AP-51).

Medido el 2026-10-04: `vault_init --target <ruta>` —confundiendo la versión con
el vault de destino— respondía `ok: true`, pasaba la ruta a
`vault_standard_upgrade --init` y esta la escribía como `applied_version` en
`standard-version.json`. Desde ahí `_version_index` devuelve -1 y ninguna
migración vuelve a aplicarse, sin un solo error visible.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_init  # noqa: E402
import vault_io  # noqa: E402
import vault_standard_upgrade as upgrade  # noqa: E402
from vault_version import CURRENT_VERSION  # noqa: E402


@pytest.mark.parametrize("v", [CURRENT_VERSION, "v40", "v21", "v38.1"])
def test_las_versiones_del_registro_se_aceptan(v):
    assert upgrade.version_conocida(v)


@pytest.mark.parametrize(
    "v", ["C:/x/vault", "/tmp/vault", "v99", "latest", "40.34", "v40.34.1", "", None]
)
def test_lo_que_no_es_una_version_se_rechaza(v):
    assert not upgrade.version_conocida(v)


@pytest.fixture
def vault_vacio(tmp_path):
    previo = vault_io.get_vault_root()
    vault_io.set_vault_root(tmp_path)
    yield tmp_path
    vault_io.set_vault_root(previo)


def test_init_con_una_ruta_no_escribe_la_version(vault_vacio):
    r = upgrade.vault_standard_upgrade(init_version="C:/x/vault")
    assert r["ok"] is False and r["error_code"] == "INVALID_INPUT"
    assert not (vault_vacio / "00_System" / "standard-version.json").exists()


def test_vault_init_rechaza_la_ruta_antes_de_crear_nada(vault_vacio):
    r = vault_init.vault_init(target_version="C:/x/vault", run_audit=False)
    assert r["ok"] is False and r["error_code"] == "INVALID_INPUT"
    # 00_System puede existir: ahí deja emit_error su traza (AP-36).
    creadas = [p.name for p in vault_vacio.iterdir() if p.name != "00_System"]
    assert creadas == [], f"vault_init creó carpetas con un --target inválido: {creadas}"
    version = vault_vacio / "00_System" / "standard-version.json"
    assert not version.exists()


def test_init_con_una_version_valida_la_escribe(vault_vacio):
    r = upgrade.vault_standard_upgrade(init_version=CURRENT_VERSION)
    assert r["ok"] is True
    datos = json.loads(
        (vault_vacio / "00_System" / "standard-version.json").read_text(encoding="utf-8")
    )
    assert datos["applied_version"] == CURRENT_VERSION

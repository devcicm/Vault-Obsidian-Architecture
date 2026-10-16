"""Un solo criterio de instantánea para no puntuar ni auditar copias (AP-57).

Auditoría del 2026-10-15: `vault_audit` y `vault_quality_check` decidían con
`skip in str(ruta)` sobre su propia lista. Faltaba `.trash/` en las dos, y el
`in` sobre la cadena saltaba una nota legítima que nombrara la carpeta.
El dueño es `vault_io.is_snapshot_path`.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit  # noqa: E402
import vault_io  # noqa: E402
import vault_quality_check  # noqa: E402

MODULOS = [vault_audit, vault_quality_check]


@pytest.mark.parametrize("modulo", MODULOS, ids=lambda m: m.__name__)
@pytest.mark.parametrize("rel", [".trash/tirada.md", "vault-backups/x/n.md", ".history/n.md"])
def test_una_instantanea_no_se_mide(tmp_path, modulo, rel):
    vault_io.set_vault_root(tmp_path)
    assert modulo._is_skipped(tmp_path / rel)


@pytest.mark.parametrize("modulo", MODULOS, ids=lambda m: m.__name__)
def test_una_nota_que_nombra_la_carpeta_si_se_mide(tmp_path, modulo):
    vault_io.set_vault_root(tmp_path)
    assert not modulo._is_skipped(tmp_path / "07_Knowledge" / "como-usar-vault-backups.md")

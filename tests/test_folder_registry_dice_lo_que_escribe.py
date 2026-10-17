"""AP-37 — `vault_folder_registry` dice cuánto escribió.

Medido el 2026-10-17 con `vault_noop_audit --ejecutado`: `--scan` reescribe el
registro de carpetas (como mínimo `detected_at`) y respondía con
`new_folders`/`total_folders`, ninguno indicador de trabajo; `--add` añadía la
entrada y respondía solo con `folder`. `tool-spec.json` declara `total`, y la
tool no lo emitía.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_folder_registry  # noqa: E402
from vault_noop_audit import WORK_INDICATORS  # noqa: E402


def _vault(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "11_Code" / "tests").mkdir(parents=True)
    return raiz


def test_scan_dice_que_escribio_y_cuantas_anadio(tmp_path):
    raiz = _vault(tmp_path)
    r = vault_folder_registry.scan_and_update(root=raiz)
    assert r["ok"] and set(r) & WORK_INDICATORS, r
    assert r["written"] is True and r["added"] == r["new_folders"] == 1, r
    assert r["total"] == r["total_folders"], r
    otra = vault_folder_registry.scan_and_update(root=raiz)
    assert otra["added"] == 0 and otra["written"] is True, otra


def test_add_dice_que_anadio(tmp_path):
    raiz = _vault(tmp_path)
    r = vault_folder_registry.add_folder("11_Code/tests", root=raiz)
    assert r["ok"] and r["added"] == 1, r

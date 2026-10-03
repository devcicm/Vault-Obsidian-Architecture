"""vault_quality_dashboard lee el índice de calidad de quien lo publica.

`_quality_index()` se lo pedía a `RepositorioAutoria`, que no tiene
`indice_calidad`: desde 90c3fe6 cada ejecución levantaba AttributeError, el
`wrap_main` lo convertía en UNEXPECTED_ERROR y ningún test ejecutaba la tool.
El índice lo escribe Gobernanza (`vault_quality_check`), así que se lee de
`RepositorioGobernanza`.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))


@pytest.fixture
def vault(tmp_path):
    import vault_io

    root = tmp_path / "v"
    (root / "00_System").mkdir(parents=True)
    vault_io.set_vault_root(root)
    return root


def test_dashboard_sin_indice_no_revienta(vault):
    import vault_quality_dashboard as qd

    r = qd.vault_quality_dashboard(check_only=True)
    assert r["ok"] and "Sin datos" in r["content"]


def test_dashboard_lee_el_indice_que_publica_gobernanza(vault):
    import vault_quality_dashboard as qd
    from vault.gobernanza.repositorio import RepositorioGobernanza
    from vault.kernel import construir

    indice = RepositorioGobernanza(construir(vault)).indice_calidad
    indice.write_text(json.dumps({
        "overall_dq_score": 0.812, "total_notes": 4, "notes_below_07": 1,
        "generated_at": "2026-10-02T00:00:00.000Z",
    }), encoding="utf-8")
    r = qd.vault_quality_dashboard()
    assert r["ok"], r
    texto = (vault / r["path"]).read_text(encoding="utf-8")
    assert "0.812" in texto and "| Total notas | 4 |" in texto

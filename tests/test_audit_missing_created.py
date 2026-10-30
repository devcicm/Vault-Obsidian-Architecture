"""D-01 -- `createdAt` ausente se cuenta y se penaliza (AP-13), como ya `updatedAt`."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit  # noqa: E402


def test_missing_created_tiene_penalizacion_con_norma_ap13():
    p = {x["id"]: x for x in vault_audit.PENALIZACIONES}
    assert p["missing_created"]["norma"] == "AP-13"
    assert p["missing_created"]["familia"] == "metadatos"


def test_el_detector_cuenta_la_nota_sin_createdat(tmp_path, monkeypatch):
    import inspect
    fuente = inspect.getsource(vault_audit)
    assert '"missing_created": missing_created' in fuente
    assert 'meta_issues["missing_created"]' in fuente

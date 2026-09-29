"""`vault_doc_staleness`: mide el vault resuelto y regenera desde su registro.

Hasta aquí la carpeta estaba congelada en ``vault-sandbox/`` desde ``__file__``
(AP-49) y la pista de arreglo era una segunda lista escrita a mano que ya
omitía un artefacto. En la CI la puerta salía roja porque la sesión de pytest
que hacía el bootstrap del sandbox lo limpiaba al terminar, y nada sabía
regenerarlo.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import vault_doc_staleness as staleness  # noqa: E402  (conftest pone scripts/ en sys.path)


def _ejecutar(raiz: Path, script: str, *argv: str):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="system"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), timeout=600,
    )


def _vault_sin_contrato(tmp_path) -> Path:
    raiz = tmp_path / "vault"
    raiz.mkdir()
    r = _ejecutar(raiz, "vault_init.py", "--no-audit")
    assert r.returncode == 0, r.stdout + r.stderr
    return raiz


@pytest.fixture
def vault(tmp_path):
    """Como lo monta `sandbox_fixture.bootstrap`: `tool-spec.json` es contrato
    versionado —entrada de `vault_compact_contracts`—, no un derivado."""
    raiz = _vault_sin_contrato(tmp_path)
    (raiz / "00_System" / "tool-spec.json").write_bytes(
        (ROOT / "vault-sandbox" / "00_System" / "tool-spec.json").read_bytes())
    return raiz


def test_todo_productor_declarado_existe():
    for fname, productor in staleness.ARTIFACTS.items():
        if productor is not None:
            assert (SCRIPTS / productor[0]).is_file(), fname


def test_la_pista_fix_sale_del_registro():
    fix = staleness._fix()
    for productor in staleness.ARTIFACTS.values():
        if productor is not None:
            assert "python scripts/" + " ".join(productor) in fix


def test_mide_el_vault_resuelto_y_no_el_sandbox(vault):
    """Un vault recién creado no tiene los derivados: el informe tiene que decirlo."""
    r = _ejecutar(vault, "vault_doc_staleness.py", "--check", "--strict")
    informe = json.loads(r.stdout)
    assert r.returncode == 1
    assert informe["missing"] > 0
    assert "standard-version.json" in informe["present_files"]


def test_regenerar_deja_el_vault_en_siete_de_siete(vault):
    r = _ejecutar(vault, "vault_doc_staleness.py", "--regenerar")
    informe = json.loads(r.stdout)
    assert r.returncode == 0, informe
    assert informe["ok"] is True
    assert informe["present"] == informe["total"] == len(staleness.ARTIFACTS)
    assert informe["regenerated"] > 0
    assert not informe["producers_failed"]
    for fname in staleness.ARTIFACTS:
        assert (vault / "00_System" / fname).is_file(), fname


def test_un_productor_que_falla_no_se_da_por_regenerado(tmp_path):
    """Sin el contrato, `vault_compact_contracts` no puede producir: AP-37."""
    raiz = _vault_sin_contrato(tmp_path)
    r = _ejecutar(raiz, "vault_doc_staleness.py", "--regenerar")
    informe = json.loads(r.stdout)
    assert r.returncode == 1
    assert informe["ok"] is False
    assert ["vault_compact_contracts.py"] in [f["argv"] for f in informe["producers_failed"]]
    assert "tool-contracts.json" in [m["file"] for m in informe["missing_files"]]


def test_sin_productor_se_reporta_y_no_se_inventa(vault):
    (vault / "00_System" / "standard-version.json").unlink()
    r = _ejecutar(vault, "vault_doc_staleness.py", "--regenerar")
    informe = json.loads(r.stdout)
    assert r.returncode == 1
    assert informe["without_producer"] == ["standard-version.json"]
    assert not (vault / "00_System" / "standard-version.json").exists()

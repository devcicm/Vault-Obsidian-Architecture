"""Tests de idempotencia de vault_ncr_save, corredor consciente del hardware y mapa de conteos."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from apoyo import ROOT

import vault_io
import vault_ncr_save
from vault.meta_toolkit.estandar import corredor_suite


def test_vault_ncr_save_es_idempotente_en_dos_corridas_consecutivas(tmp_path):
    raiz = tmp_path / "vault"
    for c in ("00_System", "01_Projects/mi-api", "02_Observability/quality", "99_Index"):
        (raiz / c).mkdir(parents=True, exist_ok=True)
    prev = vault_io.set_vault_root(raiz)
    try:
        vault_io.write_ledger_reset()
        r1 = vault_ncr_save.vault_ncr_save(
            project="mi-api",
            title="Missing validation",
            severity="major",
            detected_by="audit",
        )
        assert r1.get("ok"), r1
        assert r1.get("written", 0) >= 1, r1
        nota = raiz / r1["path"]
        sha1 = hashlib.sha256(nota.read_bytes()).hexdigest()

        vault_io.write_ledger_reset()
        r2 = vault_ncr_save.vault_ncr_save(
            project="mi-api",
            title="Missing validation",
            severity="major",
            detected_by="audit",
        )
        assert r2.get("ok"), r2
        sha2 = hashlib.sha256(nota.read_bytes()).hexdigest()
        assert sha1 == sha2, "la segunda corrida reescribio la nota NCR rompiendo idempotencia"
        assert r2.get("written") == 0, r2
    finally:
        vault_io.set_vault_root(prev)


def test_corredor_suite_adapta_workers_a_pentium_y_windows_16_hilos():
    p2 = corredor_suite.plan_hardware(cpus=2, sistema="Windows", modo="completa")
    assert p2["workers"] == 2
    assert p2["dist"] == "worksteal"
    assert "Amdahl" in p2["nota_hardware"]

    p4 = corredor_suite.plan_hardware(cpus=4, sistema="Windows", modo="completa")
    assert p4["workers"] == 3

    p16_win = corredor_suite.plan_hardware(cpus=16, sistema="Windows", modo="completa")
    assert p16_win["workers"] == 8
    assert "--dist=worksteal" in p16_win["command"]

    p16_lin = corredor_suite.plan_hardware(cpus=16, sistema="Linux", modo="rapida")
    assert p16_lin["workers"] == 12
    assert "-m" in p16_lin["command"] and "not slow" in p16_lin["command"]

    with pytest.raises(ValueError):
        corredor_suite.plan_hardware(modo="bloque", bloque="inexistente")


def test_mapa_de_conteos_existe_con_propiedad_y_registro():
    from vault.kernel import registry

    mapa = ROOT / "docs" / "MAPA-CONTEOS-Y-REGISTROS.md"
    assert mapa.is_file()
    cabeza = mapa.read_text(encoding="utf-8")[:300]
    assert "propiedad: CARLOS IVAN CM" in cabeza
    assert "MAPA-CONTEOS-Y-REGISTROS.md" in registry.DOCS_DEL_REPO

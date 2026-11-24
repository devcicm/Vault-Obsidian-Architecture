"""Fase I: blindaje de deuda tecnica viva y guards ciegos.

Fija el contrato verificable de cada correccion de deuda:
1. `RepositorioGobernanza.leer_movimientos_con_estado` aisla un `move-log.json`
   legado corrupto (AP-51: expone `legado_roto`) sin perder los movimientos
   vigentes (`moved_at`) de `.change-log.jsonl`, y `leer_movimientos` devuelve
   esos movimientos vigentes sin abortar.
2. `vault_preferences._escribir_adapter` cae a creacion exclusiva `O_CREAT|O_EXCL`
   cuando `os.link` falla con `EPERM`/`ENOTSUP`, sin pisar ficheros existentes
   cuando `force=False`.
3. `vault.kernel.normativa.contrato_nota._estados_de_tool` falla con `ValueError`
   descriptivo en vez de `StopIteration` si falta la entrada del registro.
4. `vault.kernel.normativa.audit_catalog` no mantiene comentarios obsoletos con
   cifra manual `22 penalizaciones ... 285` divergente del registro vivo.
5. `vault_doc_counts` vigila cobertura ISO (`iso_coverage`) y puertas de calidad
   (`gates_total`) contra sus registros canonicos (`FRAMEWORK_REGISTRIES` y `PUERTAS`).
"""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path

import pytest

from vault.gobernanza.repositorio import RepositorioGobernanza
from vault.kernel import construir
from vault.kernel.normativa import audit_catalog, contrato_nota

import vault_doc_counts
import vault_io
import vault_preferences


def test_leer_movimientos_aisla_move_log_legado_corrupto_y_conserva_jsonl(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    congelada = raiz / "00_System" / "move-log.json"
    congelada.write_text("{corrupto", encoding="utf-8")

    jsonl = raiz / "00_System" / ".change-log.jsonl"
    entrada = {
        "id": "chg-1",
        "action": "moved",
        "path": "07_Knowledge/vieja.md",
        "new_path": "07_Knowledge/nueva.md",
        "moved_at": "2026-11-23T20:00:00+00:00",
        "agent": "vault_move",
    }
    jsonl.write_text(f"{json.dumps(entrada)}\n", encoding="utf-8")

    repo = RepositorioGobernanza(construir(raiz))
    lectura = repo.leer_movimientos_con_estado(congelada)
    assert lectura.legado_roto is not None
    assert len(lectura.movimientos) == 1
    assert lectura.movimientos[0]["from"] == "07_Knowledge/vieja.md"
    assert lectura.movimientos[0]["to"] == "07_Knowledge/nueva.md"

    # leer_movimientos tambien devuelve los movimientos vigentes sin caerse
    movs = repo.leer_movimientos(congelada)
    assert len(movs) == 1
    assert movs[0]["to"] == "07_Knowledge/nueva.md"


def test_escribir_adapter_cae_a_creacion_exclusiva_si_os_link_no_esta_soportado(tmp_path, monkeypatch):
    destino = tmp_path / "AGENTS.md"

    def _link_no_soportado(_src, _dst):
        raise OSError(errno.ENOTSUP, "hard links not supported")

    monkeypatch.setattr(os, "link", _link_no_soportado)

    escrito = vault_preferences._escribir_adapter(destino, "# Reglas\n\nTexto limpio.\n", force=False)
    assert escrito is True
    assert destino.read_text(encoding="utf-8") == "# Reglas\n\nTexto limpio.\n"

    # Segunda llamada con force=False NO sobrescribe aunque os.link no este soportado
    segundo = vault_preferences._escribir_adapter(destino, "# Otro\n", force=False)
    assert segundo is False
    assert destino.read_text(encoding="utf-8") == "# Reglas\n\nTexto limpio.\n"


def test_contrato_nota_estados_de_tool_falla_con_value_error_claro():
    assert "draft" in contrato_nota._estados_de_tool(
        contrato_nota.LIFECYCLE_REGISTRY, "vault_requirement_save"
    )
    with pytest.raises(ValueError, match="vault_inexistente"):
        contrato_nota._estados_de_tool(contrato_nota.LIFECYCLE_REGISTRY, "vault_inexistente")


def test_audit_catalog_no_afirma_cifra_obsoleta_22_penalizaciones():
    fuente = Path(audit_catalog.__file__).read_text(encoding="utf-8")
    assert "resta 22 penalizaciones independientes cuyos" not in fuente
    assert len(audit_catalog.PENALIZACIONES) >= 24


def test_doc_counts_vigila_iso_coverage_y_gates_total():
    ids = {f["id"] for f in vault_doc_counts.COUNTED_FACTS}
    assert "iso_coverage" in ids
    assert "gates_total" in ids
    assert vault_doc_counts.count_iso_coverage() >= 31
    assert vault_doc_counts.count_gates_total() >= 29

"""ISO/IEC 20000-1: change and capacity records through existing owners.

A release written by `vault_release_save` is the change record (§8.5.1) and may
declare its change class and approver; capacity (§8.4.3) is recorded as SLOs
of type `throughput` and `saturation`. The service catalogue (§8.2.4) has no
owner and stays a declared gap.
"""

import pytest
import yaml

from apoyo import correr_tool
from vault.kernel.normativa import procesos_iso as pi
from vault_slo_save import SLO_TYPES


@pytest.fixture(scope="module")
def vault(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("iso20000")
    assert correr_tool("vault_init", vault=raiz).codigo == 0
    assert correr_tool("vault_project", "--add", "demo", vault=raiz).codigo == 0
    return raiz


def _frontmatter(ruta):
    return yaml.safe_load(ruta.read_text(encoding="utf-8").split("---")[1])


def test_iso_20000_clause_map_names_change_capacity_and_catalogue():
    por = {e["clausula"]: e for e in pi.SERVICIO_20000}
    assert por["§8.5.1"]["tools"] == ["vault_release_save"]
    assert por["§8.4.3"]["tools"] == ["vault_slo_save"]
    assert por["§8.2.4"]["tools"] == [] and por["§8.2.4"]["hueco"].strip()
    # Capacity is the SLO vocabulary the owner already declares.
    assert {"throughput", "saturation"} <= set(SLO_TYPES)
    assert pi.CLASES_DE_CAMBIO == ("standard", "normal", "emergency")


def test_iso_20000_release_records_change_class_and_approver(vault):
    r = correr_tool("vault_release_save", "--project", "demo", "--version", "2.0.0",
                    "--change_class", "emergency", "--change_approver", "CAB semanal",
                    vault=vault)
    assert r.codigo == 0
    e = r.envelope
    assert e["ok"] is True
    assert e["change_class"] == "emergency" and e["change_approver"] == "CAB semanal"
    nota = vault / e["path"]
    fm = _frontmatter(nota)
    assert fm["change_class"] == "emergency" and fm["change_approver"] == "CAB semanal"
    texto = nota.read_text(encoding="utf-8")
    assert "| **Clase de cambio** | emergency |" in texto
    assert "| **Cambio aprobado por** | CAB semanal |" in texto


def test_iso_20000_unknown_change_class_is_rejected_and_writes_nothing(vault):
    antes = sorted(p.name for p in (vault / "08_Runbooks" / "deploy").glob("*.md"))
    r = correr_tool("vault_release_save", "--project", "demo", "--version", "3.0.0",
                    "--change_class", "urgent", vault=vault)
    assert r.codigo == 2 and "invalid choice: 'urgent'" in r.stderr
    assert sorted(p.name for p in (vault / "08_Runbooks" / "deploy").glob("*.md")) == antes


def test_iso_20000_release_without_change_fields_is_unchanged(vault):
    """Previous behavior: no new key in the envelope, frontmatter or table."""
    r = correr_tool("vault_release_save", "--project", "demo", "--version", "1.0.0",
                    vault=vault)
    assert r.codigo == 0
    assert "change_class" not in r.envelope and "change_approver" not in r.envelope
    nota = vault / r.envelope["path"]
    fm = _frontmatter(nota)
    assert "change_class" not in fm and "change_approver" not in fm
    texto = nota.read_text(encoding="utf-8")
    assert "Clase de cambio" not in texto
    assert "| **ISO process** | ISO/IEC/IEEE 12207:2017 §6.3.5 · §6.4.10 |\n\n## Cambios incluidos" in texto

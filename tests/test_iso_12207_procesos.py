"""ISO/IEC/IEEE 12207: every life-cycle process maps to a tool or a reason.

`vault.kernel.normativa.procesos_iso.PROCESOS_12207` is the registry: each
process of 12207:2017 clause 6 names the tools that record its evidence, or is
declared `fuera` with the reason. `vault_audit --procesos-iso` publishes the
map read-only.
"""

import pytest

from apoyo import SCRIPTS, correr_tool
from vault.kernel.ledger import FICHEROS_AMBIENTALES
from vault.kernel.normativa import procesos_iso as pi

#: The 30 processes of ISO/IEC/IEEE 12207:2017 §6, in the standard's order.
IDS_12207 = [
    "6.1.1", "6.1.2",
    "6.2.1", "6.2.2", "6.2.3", "6.2.4", "6.2.5", "6.2.6",
    "6.3.1", "6.3.2", "6.3.3", "6.3.4", "6.3.5", "6.3.6", "6.3.7", "6.3.8",
    "6.4.1", "6.4.2", "6.4.3", "6.4.4", "6.4.5", "6.4.6", "6.4.7",
    "6.4.8", "6.4.9", "6.4.10", "6.4.11", "6.4.12", "6.4.13", "6.4.14",
]


def _ficheros(raiz):
    """The vault's files and mtimes, minus the ambient files every run touches."""
    return sorted(
        (rel, p.stat().st_mtime_ns)
        for p in raiz.rglob("*") if p.is_file()
        for rel in [p.relative_to(raiz).as_posix()] if rel not in FICHEROS_AMBIENTALES
    )


@pytest.fixture(scope="module")
def vault(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("iso12207")
    assert correr_tool("vault_init", vault=raiz).codigo == 0
    return raiz


def test_iso_12207_registry_lists_every_process_of_clause_6():
    assert [p["id"] for p in pi.PROCESOS_12207] == IDS_12207
    for p in pi.PROCESOS_12207:
        assert p["grupo"] in pi.GRUPOS_12207, p["id"]
        assert p["proceso"].strip(), p["id"]
        # Either a tool records it, or it is declared out of reach with a reason.
        assert bool(p["tools"]) != bool(str(p.get("fuera") or "").strip()), p["id"]


def test_iso_12207_requested_technical_processes_have_a_recorder():
    por_id = {p["id"]: p for p in pi.PROCESOS_12207}
    assert "vault_requirement_save" in por_id["6.4.3"]["tools"]
    assert "vault_test_save" in por_id["6.4.9"]["tools"]
    assert "vault_release_save" in por_id["6.4.10"]["tools"]
    assert "vault_risk_save" in por_id["6.3.4"]["tools"]
    assert por_id["6.4.14"]["fuera"], "disposal stays out: records are never destroyed"


def test_iso_12207_registries_name_only_existing_tools():
    r = pi.comprobar_registros(SCRIPTS)
    assert r == {"ok": True, "tools_inexistentes": [], "sin_motivo": []}


def test_iso_12207_check_fails_when_a_tool_disappears(tmp_path):
    (tmp_path / "vault_audit.py").write_text("", encoding="utf-8")
    r = pi.comprobar_registros(tmp_path)
    assert r["ok"] is False
    assert {"registro": "procesos_12207", "id": "6.3.4", "tool": "vault_risk_save"} in r["tools_inexistentes"]
    assert not any(x["tool"] == "vault_audit" for x in r["tools_inexistentes"])


def test_iso_12207_check_fails_when_a_gap_has_no_reason(monkeypatch):
    falsos = ({"id": "6.9.9", "grupo": "tecnico", "proceso": "X", "tools": []},)
    monkeypatch.setitem(pi.REGISTROS, "procesos_12207", (falsos, "id", "fuera"))
    r = pi.comprobar_registros(SCRIPTS)
    assert r["ok"] is False
    assert r["sin_motivo"] == [{"registro": "procesos_12207", "id": "6.9.9"}]


def test_iso_12207_audit_report_is_read_only(vault):
    antes = _ficheros(vault)
    r = correr_tool("vault_audit", "--procesos-iso", vault=vault)
    assert r.codigo == 0
    e = r.envelope
    assert e["ok"] is True and e["mode"] == "procesos_iso"
    p = e["procesos_12207"]
    con = sum(1 for x in pi.PROCESOS_12207 if x["tools"])
    assert (p["total"], p["con_registro"], p["sin_registro"]) == (30, con, 30 - con)
    assert [x["id"] for x in p["entradas"]] == IDS_12207
    assert all(x["capacidad"] is None for x in p["entradas"]) and p["evaluados"] == 0
    assert sum(g["total"] for g in p["por_grupo"].values()) == 30
    assert e["evaluaciones"] == 0 and e["evaluaciones_invalidas"] == []
    assert f"12207: {con}/30" in e["summary"]
    assert _ficheros(vault) == antes


def test_iso_12207_report_rejects_scoping_options(vault):
    r = correr_tool("vault_audit", "--procesos-iso", "--path", str(vault), vault=vault)
    assert r.codigo == 1
    assert r.envelope["ok"] is False and r.envelope["error_code"] == "CONFLICTING_ARGS"
    assert "--path" in r.envelope["message"]


def test_iso_12207_plain_audit_keeps_its_previous_envelope(vault):
    """Previous behavior: without the flag, vault_audit runs the health audit."""
    r = correr_tool("vault_audit", vault=vault)
    assert r.codigo == 0
    assert "healthScore" in r.envelope
    assert "procesos_12207" not in r.envelope and r.envelope.get("mode") != "procesos_iso"

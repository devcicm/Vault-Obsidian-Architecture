"""ISO/IEC/IEEE 90003: ISO 9001 applied to software, clause by clause.

`procesos_iso.CLAUSULAS_90003` maps each ISO 9001:2015 clause, as 90003 applies
it to software, to the tool that executes it or to the declared gap.
Organizational clauses (leadership, management review) stay gaps (S4).
"""

from apoyo import correr_tool
from vault.kernel.normativa import procesos_iso as pi
from vault_fundamentals_catalog import ISO_COVERAGE


def _por_clausula():
    return {e["clausula"]: e for e in pi.CLAUSULAS_90003}


def test_iso_90003_maps_the_requested_9001_clauses_to_executors():
    por = _por_clausula()
    esperado = {
        "§7.5": "vault_write",
        "§8.1": "vault_release_save",
        "§8.2": "vault_requirement_save",
        "§8.3": "vault_arquitectura_en",
        "§8.5.2": "vault_drift_detect",
        "§8.6": "vault_release_save",
        "§8.7": "vault_ncr_save",
        "§9.1": "vault_quality_check",
        "§9.2": "vault_audit",
        "§10.2": "vault_ncr_save",
    }
    for clausula, tool in esperado.items():
        assert tool in por[clausula]["tools"], clausula


def test_iso_90003_organizational_clauses_are_declared_gaps():
    por = _por_clausula()
    for clausula in ("§5", "§9.3"):
        assert por[clausula]["tools"] == [], clausula
        assert "organización" in por[clausula]["hueco"], clausula
    for e in pi.CLAUSULAS_90003:
        assert e["tools"] or e["hueco"].strip(), e["clausula"]


def test_iso_90003_agrees_with_the_9001_entry():
    """The 9001 clauses the registry already claims are executed by the same tools."""
    iso9001 = next(e for e in ISO_COVERAGE if e["id"] == "ISO-9001")
    por = _por_clausula()
    assert set(por["§9.2"]["tools"]) | set(por["§10.2"]["tools"]) <= set(iso9001["tools"])


def test_iso_90003_and_33000_entries_name_registry_tools():
    """The ISO_COVERAGE entries cite tools the clause/process registries use."""
    por_id = {e["id"]: e for e in ISO_COVERAGE}
    de_90003 = {t for e in pi.CLAUSULAS_90003 for t in e["tools"]}
    assert set(por_id["ISO-90003"]["tools"]) <= de_90003
    assert por_id["ISO-90003"]["cobertura"] == "parcial"
    assert "§9.3" in por_id["ISO-90003"]["hueco"]
    assert set(por_id["ISO-33000"]["tools"]) == {"vault_write", "vault_audit"}
    assert "15504" in por_id["ISO-33000"]["norm"]
    assert "ISO-15504" not in por_id, "15504 is named inside the 33000 entry, not duplicated"


def test_iso_90003_report_publishes_the_clause_map(tmp_path):
    assert correr_tool("vault_init", vault=tmp_path).codigo == 0
    r = correr_tool("vault_audit", "--procesos-iso", vault=tmp_path)
    assert r.codigo == 0
    m = r.envelope["clausulas_90003"]
    assert [e["clausula"] for e in m["entradas"]] == [e["clausula"] for e in pi.CLAUSULAS_90003]
    con = sum(1 for e in pi.CLAUSULAS_90003 if e["tools"])
    assert (m["total"], m["con_registro"]) == (len(pi.CLAUSULAS_90003), con)
    s = r.envelope["servicio_20000"]
    assert s["total"] == len(pi.SERVICIO_20000)

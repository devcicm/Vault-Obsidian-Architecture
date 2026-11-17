"""AP-71: a concept many notes mention and no note owns (Karpathy's lint).

The "LLM Wiki" lint looks for "important concepts mentioned without their own
page". The detector is in `vault_audit`, with the entity rule of the kernel
owner (`vault.kernel.normativa.conceptos`) and Obsidian's resolution: a page
answers by file name or `aliases:`, never by `title:` (AP-44).
"""

from pathlib import Path

from apoyo import escribir_nota

CUERPO = "La {n} usa Raft Consensus para elegir líder; el MCP lo expone.\n"


def _vault(tmp_path: Path, notas: int = 3) -> Path:
    import vault_io

    raiz = tmp_path / "v"
    for sec in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / sec).mkdir(parents=True)
    for i in range(notas):
        escribir_nota(raiz, f"07_Knowledge/nota-{i}.md",
                      {"title": f"Nota {i}", "type": "knowledge"},
                      f"# Nota {i}\n\n" + CUERPO.format(n=f"nota {i}"))
    vault_io.set_vault_root(raiz)
    return raiz


def _sin_pagina(resultado) -> dict:
    return {c["term"]: c for c in resultado.get("conceptsWithoutPage", [])}


def test_ap71_un_termino_en_tres_notas_sin_pagina_se_reporta(tmp_path):
    _vault(tmp_path)
    import vault_audit

    r = vault_audit.vault_audit()

    hallazgos = _sin_pagina(r)
    assert "Raft Consensus" in hallazgos, r.get("conceptsWithoutPage")
    assert hallazgos["Raft Consensus"]["notes"] == 3
    acciones = [a for a in r.get("nextActions", []) if a.get("norm") == "AP-71"]
    assert any("Raft Consensus" in a["description"] for a in acciones), r.get("nextActions")
    assert all(a["category"] == "concept_without_page" for a in acciones)


def test_ap71_por_debajo_del_umbral_no_se_reporta(tmp_path):
    _vault(tmp_path, notas=2)
    import vault_audit

    assert "Raft Consensus" not in _sin_pagina(vault_audit.vault_audit())


def test_ap71_una_nota_con_ese_nombre_de_fichero_es_su_pagina(tmp_path):
    raiz = _vault(tmp_path)
    escribir_nota(raiz, "07_Knowledge/raft-consensus.md",
                  {"title": "Consenso", "type": "knowledge"}, "# Consenso\n\nRaft.\n")
    import vault_audit

    assert "Raft Consensus" not in _sin_pagina(vault_audit.vault_audit())


def test_ap71_un_alias_es_su_pagina_y_el_titulo_no(tmp_path):
    raiz = _vault(tmp_path)
    escribir_nota(raiz, "07_Knowledge/mcp.md",
                  {"title": "Raft Consensus", "aliases": ["Model Context Protocol", "MCP"],
                   "type": "knowledge"}, "# MCP\n\nProtocolo.\n")
    import vault_audit

    hallazgos = _sin_pagina(vault_audit.vault_audit())
    assert "MCP" not in hallazgos  # file name and alias resolve it
    assert "Raft Consensus" in hallazgos  # a title does not (AP-44)


def test_ap71_lo_que_esta_en_un_bloque_de_codigo_no_cuenta(tmp_path):
    raiz = _vault(tmp_path, notas=0)
    for i in range(3):
        escribir_nota(raiz, f"07_Knowledge/c-{i}.md", {"title": f"C {i}", "type": "knowledge"},
                      f"# C {i}\n\n```\nGrafo Distribuido Ejemplo\n```\n")
    import vault_audit

    assert "Grafo Distribuido Ejemplo" not in _sin_pagina(vault_audit.vault_audit())


def test_ap71_una_sigla_que_solo_es_un_nombre_de_fichero_no_cuenta(tmp_path):
    """Found in the rule-7 contrast (scrap_* corpora, 2026-11-16): `AGENTS`
    came out as a concept because `AGENTS.md` matches the acronym pattern.
    A file name is a path, not a concept."""
    raiz = _vault(tmp_path, notas=0)
    for i in range(3):
        escribir_nota(raiz, f"07_Knowledge/f-{i}.md", {"title": f"F {i}", "type": "knowledge"},
                      f"# F {i}\n\nLee AGENTS.md antes de tocar nada.\n")
    import vault_audit

    assert "AGENTS" not in _sin_pagina(vault_audit.vault_audit())


def test_ap71_el_catalogo_la_declara_como_audit():
    import vault_norms_catalog

    norma = vault_norms_catalog.norma_por_codigo("AP-71")
    assert norma and norma["enforcement"] == "audit"
    assert "vault_audit" in norma["tools_detecting"]


def test_audit_refresh_dq_declares_and_emits_its_work_indicator():
    """OPEN-01: the writing mode declares its side effect and the envelope shows the work."""
    import vault_smoke
    from vault_mcp_catalog import TOOLS_CATALOG
    from vault_noop_audit import WORK_INDICATORS
    from apoyo import SCRIPTS

    assert TOOLS_CATALOG["vault_audit"]["side_effects"], "the --refresh-dq write must be declared"
    r = vault_smoke.run_one("vault_audit", arbol=True, argv=[
        vault_smoke.sys.executable, str(SCRIPTS / "vault_audit.py"), "--refresh-dq"])
    assert r.get("tool_ok") is True, r
    assert "change_log" in r["returned"] and "change_log" in WORK_INDICATORS
    assert any(p.startswith("00_System/") and "change-log" in p for p in r["cambiadas"]), r["cambiadas"]

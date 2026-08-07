"""Tests para vault_norms --audit y el guard CN-02 de vault_section_index."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from vault_norms import NORM_CATALOG, STATUS_VOCAB, vault_norms_audit


def _make_vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault-test"
    for sec in ("00_System", "01_Projects", "03_Decisions", "99_Index"):
        (root / sec).mkdir(parents=True)
    # AP-36 exige index.md en secciones de contenido presentes
    for sec in ("01_Projects", "03_Decisions"):
        (root / sec / "index.md").write_text(
            "---\ntitle: idx\n---\n# idx\n", encoding="utf-8"
        )
    return root


def _note(path: Path, fm: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{fm}\n---\n{body}", encoding="utf-8")


def test_no_manual_enforcement_left():
    assert not [n["code"] for n in NORM_CATALOG if n["enforcement"] == "manual"]


def test_status_vocab_unified():
    # El vocabulario unificado v38 incluye ambos ciclos (CN-03 + spec §status)
    assert {"draft", "verified", "planned", "stub"} <= STATUS_VOCAB


def _sync_index(root: Path) -> None:
    """Deja `search-index.json` reflejando lo que hay en disco (AP-47).

    `_make_vault` monta el vault a mano y nunca escribió índice, así que un vault
    "limpio" para el resto de normas estaba, para AP-47, sin buscador. No es un
    falso positivo: un vault con notas y sin índice es exactamente lo que la norma
    describe. Se sincroniza con el enumerador de `vault_reindex` —no con uno
    propio— para no medir con un criterio distinto del que arregla (AP-44).
    """
    import json

    from vault_reindex import _notas_en_disco

    (root / "99_Index").mkdir(parents=True, exist_ok=True)
    (root / "99_Index" / "search-index.json").write_text(
        json.dumps(
            {
                "notes": [
                    {"path": str(p.relative_to(root)).replace("\\", "/")}
                    for p in _notas_en_disco(root)
                ]
            }
        ),
        encoding="utf-8",
    )


def test_audit_clean_vault(tmp_path):
    root = _make_vault(tmp_path)
    _note(root / "01_Projects" / "demo.md", "title: Demo\nstatus: implemented", "# Demo\nok")
    _sync_index(root)
    result = vault_norms_audit(root)
    assert result["ok"] and result["total_violations"] == 0


def test_audit_detects_root_file_ap15(tmp_path):
    root = _make_vault(tmp_path)
    (root / "suelto.md").write_text("x", encoding="utf-8")
    result = vault_norms_audit(root)
    assert "AP-15" in result["by_norm"]


def test_audit_detects_adhoc_folder_cn02(tmp_path):
    root = _make_vault(tmp_path)
    (root / "MiCarpeta").mkdir()
    result = vault_norms_audit(root)
    assert "CN-02" in result["by_norm"]


def test_audit_detects_bad_status_cn03(tmp_path):
    root = _make_vault(tmp_path)
    _note(root / "01_Projects" / "n.md", "title: N\nstatus: fresh", "# N\nx")
    result = vault_norms_audit(root)
    assert "CN-03" in result["by_norm"]


def test_audit_detects_incomplete_adr_ap07(tmp_path):
    root = _make_vault(tmp_path)
    _note(root / "03_Decisions" / "adr-009-x.md", "title: ADR-009\nstatus: implemented", "# ADR\nsin secciones")
    result = vault_norms_audit(root)
    assert "AP-07" in result["by_norm"]


def test_audit_adr_stub_exempt_ap07(tmp_path):
    root = _make_vault(tmp_path)
    _note(root / "03_Decisions" / "adr-010-x.md", "title: ADR-010\nstatus: stub", "# ADR stub")
    result = vault_norms_audit(root)
    assert "AP-07" not in result["by_norm"]


def test_audit_detects_runbook_out_of_place_ap09(tmp_path):
    root = _make_vault(tmp_path)
    _note(root / "01_Projects" / "rb.md", "title: RB\ntype: runbook\nstatus: implemented", "# RB\nx")
    result = vault_norms_audit(root)
    assert "AP-09" in result["by_norm"]


def test_audit_bom_frontmatter_parsed(tmp_path):
    # Regresión: BOM de Windows no debe ocultar el frontmatter (falso AP-07/CN-03)
    root = _make_vault(tmp_path)
    p = root / "03_Decisions" / "adr-001-bom.md"
    p.write_text(
        "﻿---\ntitle: ADR BOM\nstatus: implemented\n---\n# ADR\n"
        "## Context\nx\n## Decision\ny\n## Consequences\nz\n",
        encoding="utf-8",
    )
    result = vault_norms_audit(root)
    assert "AP-07" not in result["by_norm"]


def test_section_index_rejects_root_and_adhoc():
    from vault_section_index import vault_section_index

    assert vault_section_index("")["error"] == "invalid_folder"
    assert vault_section_index(".")["error"] == "invalid_folder"
    assert vault_section_index("carpeta-adhoc")["error"] == "invalid_folder"


def test_ap36_detects_bak_in_section(tmp_path):
    root = _make_vault(tmp_path)
    _note(root / "01_Projects" / "index.md", "title: idx", "# idx")
    (root / "01_Projects" / "nota.md.bak").write_text("x", encoding="utf-8")
    result = vault_norms_audit(root)
    assert any(v["norm"] == "AP-36" and ".bak" in v["path"] for v in result["violations"])


def test_ap36_detects_section_without_index(tmp_path):
    root = _make_vault(tmp_path)
    (root / "01_Projects" / "index.md").unlink()
    _note(root / "01_Projects" / "demo.md", "title: D\nstatus: implemented", "# D\nx")
    result = vault_norms_audit(root)
    assert any(v["norm"] == "AP-36" and v["path"] == "01_Projects/" for v in result["violations"])


def test_ap36_detects_sibling_pollution(tmp_path):
    root = _make_vault(tmp_path)
    _note(root / "01_Projects" / "index.md", "title: idx", "# idx")
    (tmp_path / "vault-backups").mkdir()
    result = vault_norms_audit(root)
    assert any(v["norm"] == "AP-36" and "vault-backups" in v["path"] for v in result["violations"])


def test_backup_root_inside_vault(tmp_path):
    """AP-36: los backups cuelgan del vault, y no se copian a sí mismos.

    Lo mismo que antes, comprobado donde ahora vive: la constante congelada de
    `vault_backup` desapareció al migrar el contexto (era AP-49) y la raíz sale
    del vault inyectado.
    """
    from vault.durabilidad.repositorio import RepositorioDurabilidad
    from vault.durabilidad.snapshot import NO_COPIAR
    from vault.kernel import construir

    assert RepositorioDurabilidad(construir(tmp_path)).raiz_backups == \
        (tmp_path / "vault-backups").resolve()
    assert "vault-backups" in NO_COPIAR


def test_stub_dir_in_maintenance_section():
    import vault_graph_fix

    assert vault_graph_fix._STUBS_DIR == "02_Observability/maintenance/stubs"


def test_trace_follows_set_vault_root(tmp_path):
    # AP-36: con set_vault_root, la observabilidad escribe en el vault objetivo
    import vault_io
    from vault_errors_trace import log_trace, trace_file

    target = tmp_path / "vault-x"
    (target / "00_System").mkdir(parents=True)
    try:
        vault_io.set_vault_root(target)
        assert trace_file() == target / "00_System" / ".tool-trace.json"
        log_trace({"tool": "test", "ok": True})
        assert (target / "00_System" / ".tool-trace.json").exists()
    finally:
        vault_io.reset_vault_root()


def test_section_index_table_separates_link_and_title(tmp_path, monkeypatch):
    # El wikilink va SIN alias; el título vive en su propia columna. Un alias
    # largo en la celda confunde a agentes y genera notas en blanco.
    import vault_section_index as vsi

    content = vsi._build_index_content(
        "13_Flows",
        [{"path": "13_Flows/mi-flujo.md", "title": "Mi Flujo — Título/largo", "type": "flow", "updatedAt": "2026-07-12"}],
        "2026-07-12T00:00:00.000Z",
        subdirs=None,
    )
    assert "| [[mi-flujo]] | Mi Flujo — Título/largo | flow |" in content
    assert "[[mi-flujo|" not in content


def test_heal_indexes_fixes_legacy_alias(tmp_path):
    import vault_io
    from vault_section_index import heal_indexes

    root = _make_vault(tmp_path)
    _note(root / "01_Projects" / "demo.md", "title: Demo\nstatus: implemented", "# Demo")
    (root / "01_Projects" / "index.md").write_text(
        "# idx\n\n| Nota | Tipo |\n|---|---|\n| [[demo|Demo — x/y]] | note |\n",
        encoding="utf-8",
    )
    try:
        vault_io.set_vault_root(root)
        result = heal_indexes(root)
        assert result["healed_count"] >= 1
        healed_text = (root / "01_Projects" / "index.md").read_text(encoding="utf-8")
        assert "[[demo|" not in healed_text
        # Idempotencia: segunda pasada no cura nada
        assert heal_indexes(root)["healed_count"] == 0
    finally:
        vault_io.reset_vault_root()


def test_audit_detects_legacy_alias_index(tmp_path):
    root = _make_vault(tmp_path)
    (root / "01_Projects" / "index.md").write_text(
        "# idx\n\n| [[nota|Alias — largo]] | tipo |\n", encoding="utf-8"
    )
    result = vault_norms_audit(root)
    assert any("alias" in v["detail"] for v in result["violations"] if v["norm"] == "AP-36")


def test_manual_index_write_self_heals(tmp_path):
    import vault_io
    from vault_io import atomic_write_text

    root = _make_vault(tmp_path)
    _note(root / "01_Projects" / "demo.md", "title: Demo\nstatus: implemented", "# Demo")
    try:
        vault_io.set_vault_root(root)
        idx = root / "01_Projects" / "index.md"
        atomic_write_text(idx, "# x\n\n| [[demo|Demo — y]] | note |\n")
        text = idx.read_text(encoding="utf-8")
        assert "[[demo|" not in text and "[[demo]]" in text
    finally:
        vault_io.reset_vault_root()

"""AP-52, the meaning half: following a published recovery fixes its cause.

`test_recovery_ejecutable.py` proves that every recovery parses. That is
necessary, not sufficient: `INDEX_NOT_FOUND` publishes `vault_reindex --graph`,
which rebuilds `search-index.json` and `graph.json` and nothing else. Measured
on 2026-11-17 against a copy of a real vault, three emitters of that code name
an artefact that reindex never produces, so an agent obeying `recovery` got the
same error back:

- `vault_pattern_list`: `05_Patterns/index.json` is written only by
  `vault_pattern_save` (same class as `vault_tags` and `tag-registry.json`).
- `vault_doc_sync --fix`: the README index table is hand-maintained structure;
  nothing regenerates a missing or split table.
- `vault_migrate_rollback`: an empty or malformed migration report is fixed by
  reading the report, not by rebuilding indexes.

The recovery `action` is the catalog's per code (`vault.kernel.errores`), so
the last two now emit `PARSE_FAILED` (`fix_input`: the input document lost the
documented structure) instead of overriding the action of `INDEX_NOT_FOUND`.
"""
import json
from pathlib import Path

from apoyo import SCRIPTS, correr_tool


def _cli(vault: Path, script: str, *args: str) -> dict:
    return correr_tool(script, *args, vault=vault, cwd=SCRIPTS).envelope


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    assert _cli(vault, "vault_project.py", "--add", "mi-api")["ok"]
    return vault


def _concreto(args, valores):
    return [valores.get(a, a) for a in args]


def test_ap52_pattern_list_sin_indice_recupera_con_quien_lo_escribe(tmp_path):
    vault = _vault(tmp_path)
    (vault / "05_Patterns").mkdir()

    error = _cli(vault, "vault_pattern_list.py")
    assert error["ok"] is False and error["error_code"] == "INDEX_NOT_FOUND", error
    recovery = error["recovery"]
    assert recovery["action"] == "run_tool", recovery
    assert recovery["tool"] == "vault_pattern_save", recovery

    # Obeying the recovery literally (placeholders filled in) clears the error.
    args = _concreto(recovery["args"], {
        "<project>": "mi-api", "<name>": "Reintentos", "<type>": "design",
        "<status>": "planificado"})
    assert _cli(vault, "vault_pattern_save.py", *args)["ok"]
    listado = _cli(vault, "vault_pattern_list.py")
    assert listado["ok"], listado


def test_ap52_doc_sync_sin_tabla_de_indice_pide_corregir_el_readme(tmp_path, monkeypatch):
    import vault_doc_sync

    readme = tmp_path / "README.md"
    readme.write_text("# Scripts\n\nSin tabla de índice.\n", encoding="utf-8")
    monkeypatch.setattr(vault_doc_sync, "README", readme)

    r = vault_doc_sync.fix()
    assert r["error_code"] == "PARSE_FAILED", r
    assert r["recovery"]["action"] == "fix_input", r["recovery"]
    assert "vault_reindex" not in json.dumps(r["recovery"]), r["recovery"]
    assert readme.read_text(encoding="utf-8") == "# Scripts\n\nSin tabla de índice.\n"


def test_ap52_rollback_con_informe_vacio_pide_revisar_el_informe(tmp_path):
    vault = _vault(tmp_path)
    informe = vault / "10_Migrated" / "_report-vacio.md"
    informe.parent.mkdir(parents=True)
    informe.write_text("# Informe\n\nSin secciones.\n", encoding="utf-8")

    r = _cli(vault, "vault_migrate_rollback.py", "--report_path", "10_Migrated/_report-vacio.md")
    assert r["ok"] is False and r["error_code"] == "PARSE_FAILED", r
    assert r["recovery"]["action"] == "fix_input", r["recovery"]
    assert "vault_reindex" not in json.dumps(r["recovery"]), r["recovery"]

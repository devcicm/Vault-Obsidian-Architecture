"""El sandbox de pruebas se reconstruye sin estado local oculto."""

from pathlib import Path

from sandbox_fixture import DERIVED_FILES, bootstrap, clean, ready


def test_el_fixture_nace_desde_cero_en_una_raiz_ajena(tmp_path):
    target = tmp_path / "vault-sandbox"
    assert not target.exists()
    bootstrap(target)
    assert ready(target)
    assert (target / "00_System" / "vault-commands.md").is_file()
    assert (target / "03_Decisions" / "adr-001-mcp-transport.md").is_file()
    assert all((target / "00_System" / name).is_file() for name in DERIVED_FILES)
    clean(target, preserve_contract=False)
    assert not target.exists()

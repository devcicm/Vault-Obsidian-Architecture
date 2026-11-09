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


def test_un_sandbox_de_una_siembra_anterior_no_se_da_por_listo(tmp_path):
    """Medido el 2026-10-01: un `vault-sandbox/` viejo, con su `adr-001` y sin
    las notas `mcp-transport-*`, pasaba `ready()` y la suite medía restos."""
    target = tmp_path / "vault-sandbox"
    bootstrap(target)
    assert ready(target)

    viejo = target / "03_Decisions" / "adr-001-mcp-transport.md"
    viejo.write_text("---\ntitle: ADR-001 de otra siembra\n---\n", encoding="utf-8")
    assert not ready(target), "un adr-001 con otro contenido no es la semilla"

    bootstrap(target)
    (target / "03_Decisions" / "mcp-transport-provenance.md").unlink()
    assert not ready(target), "falta una nota de la semilla"
    clean(target, preserve_contract=False)

def test_la_limpieza_no_borra_el_contrato_rastreado(tmp_path):
    """El contrato vive en el sandbox **y esta versionado** (`.gitignore` lo
    publica a proposito). Que la limpieza se lo llevara convertia un fallo
    del bootstrap en un repo con un fichero rastreado borrado: medido el
    2026-11-09 en una revision independiente — dos intentos de prueba
    abortaron y el contrato hubo que restaurarlo desde HEAD.
    """
    import sandbox_fixture

    objetivo = tmp_path / "vault-sandbox"
    (objetivo / "00_System").mkdir(parents=True)
    contrato = objetivo / "00_System" / "tool-spec.json"
    contrato.write_bytes(b'{"tools": {}}')
    (objetivo / "00_System" / "otro.json").write_bytes(b"{}")
    (objetivo / "nota.md").write_bytes(b"nota")

    sandbox_fixture.clean(objetivo, preserve_contract=True)

    assert contrato.is_file(), "la limpieza se llevo el contrato versionado"
    assert contrato.read_bytes() == b'{"tools": {}}'
    # Lo demas si se limpia: es estado de ejecucion.
    assert not (objetivo / "00_System" / "otro.json").exists()
    assert not (objetivo / "nota.md").exists()

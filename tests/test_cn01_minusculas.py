"""CN-01: `vault_write` deriva el nombre en minúsculas, sin duplicar notas viejas.

Medido el 2026-10-01 con la wheel: `vault_write` con el título «Decision
transporte MCP» escribía `Decision-transporte-MCP.md`. CN-01 —enforcement
`guard`, y ese guard es este `slugify`— exige minúsculas, y ninguna tool audita
después los nombres ya escritos: lo que aquí no se normaliza no lo corrige nadie.

Pasar a minúsculas tiene un precio en vaults que ya existen: en un sistema de
ficheros sensible a mayúsculas, actualizar una nota escrita antes del cambio
crearía una segunda nota en minúsculas al lado de la vieja (AP-02). Por eso la
nota heredada que solo difiere en mayúsculas se actualiza en su sitio, con su
nombre y su identidad.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

CUERPO = (
    "Una nota con contenido suficiente para pasar la puerta de calidad.\n"
    "Segunda linea real del cuerpo con varias palabras.\n"
    "Tercera linea real del cuerpo con varias palabras.\n"
)


def _vault(tmp_path, monkeypatch):
    import vault_io

    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setenv("VAULT_AGENT", "prueba")
    vault_io.set_vault_root(tmp_path)
    (tmp_path / "03_Decisions").mkdir(parents=True)
    return tmp_path / "03_Decisions"


def _notas(carpeta: Path):
    return sorted(p.name for p in carpeta.glob("*.md") if p.name != "index.md")


def test_el_nombre_derivado_va_en_minusculas(tmp_path, monkeypatch):
    import vault_write

    carpeta = _vault(tmp_path, monkeypatch)
    r = vault_write.vault_write(folder="03_Decisions", title="Decision transporte MCP",
                                content=CUERPO, tags=["prueba"])
    assert r["ok"], r
    assert _notas(carpeta) == ["decision-transporte-mcp.md"]
    # El contrato de `sanitize_filename` se conserva: lo inválido sigue fuera.
    assert vault_write.slugify('ADR-001 Auth: "Decision"?') == "adr-001-auth-decision"


def test_la_nota_heredada_en_mayusculas_se_actualiza_en_su_sitio(tmp_path, monkeypatch):
    import vault_write

    carpeta = _vault(tmp_path, monkeypatch)
    heredada = carpeta / "Decision-transporte-MCP.md"
    heredada.write_text(
        "---\ntitle: Decision transporte MCP\nid: id-heredado\n"
        "createdAt: 2026-01-01T00:00:00.000Z\nagent: prueba\ntags: [prueba]\n---\n\n"
        + CUERPO, encoding="utf-8")

    r = vault_write.vault_write(folder="03_Decisions", title="Decision transporte MCP",
                                content=CUERPO + "Cuarta linea nueva.\n", tags=["prueba"])
    assert r["ok"], r
    assert _notas(carpeta) == ["Decision-transporte-MCP.md"], "duplicó la nota heredada"
    texto = heredada.read_text(encoding="utf-8")
    assert "Cuarta linea nueva." in texto
    assert "id: id-heredado" in texto, "la actualización perdió la identidad"

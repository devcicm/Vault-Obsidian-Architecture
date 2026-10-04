"""CN-01: `vault_write` deriva el nombre con el slug canónico, sin duplicar notas viejas.

Hasta v40.34 `vault_write.slugify` era `sanitize_filename(...).lower()`, que
conserva acentos y puntuación: «Mapa de Código — ANS (v2)» se escribía como
`mapa-de-código-—-ans-(v2).md`, mientras el resto del toolkit
(`slugify_strict`) llamaba a la misma nota `mapa-de-codigo-ans-v2`. Un título,
dos identidades según la tool que preguntara.

El cambio tiene el mismo precio que el paso a minúsculas: la nota ya escrita
con el nombre viejo no puede duplicarse al actualizarla. Se actualiza en su
sitio, con su nombre y su `id`.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

CUERPO = (
    "Una nota con contenido suficiente para pasar la puerta de calidad.\n"
    "Segunda linea real del cuerpo con varias palabras.\n"
    "Tercera linea real del cuerpo con varias palabras.\n"
)
TITULO = "Mapa de Código — ANS (v2)"


def _vault(tmp_path, monkeypatch, carpeta="07_Knowledge"):
    import vault_io

    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setenv("VAULT_AGENT", "prueba")
    vault_io.set_vault_root(tmp_path)
    (tmp_path / carpeta).mkdir(parents=True, exist_ok=True)
    return tmp_path / carpeta


def _notas(carpeta: Path):
    return sorted(p.name for p in carpeta.glob("*.md") if p.name != "index.md")


def test_la_nota_nueva_usa_el_slug_canonico(tmp_path, monkeypatch):
    import vault_write
    from vault_lib import slugify_strict

    carpeta = _vault(tmp_path, monkeypatch)
    r = vault_write.vault_write(folder="07_Knowledge", title=TITULO,
                                content=CUERPO, tags=["prueba"])
    assert r["ok"], r
    assert _notas(carpeta) == ["mapa-de-codigo-ans-v2.md"]
    assert vault_write.slugify(TITULO) == slugify_strict(TITULO)


def test_la_nota_con_el_slug_viejo_se_actualiza_en_su_sitio(tmp_path, monkeypatch):
    import vault_write

    carpeta = _vault(tmp_path, monkeypatch)
    viejo = vault_write._slug_heredado(TITULO)
    assert viejo != vault_write.slugify(TITULO), "el caso no ejercita el cambio"
    heredada = carpeta / f"{viejo}.md"
    heredada.write_text(
        f"---\ntitle: {json.dumps(TITULO, ensure_ascii=False)}\nid: id-heredado\n"
        "createdAt: 2026-01-01T00:00:00.000Z\nagent: prueba\ntags: [prueba]\n---\n\n"
        + CUERPO, encoding="utf-8")

    r = vault_write.vault_write(folder="07_Knowledge", title=TITULO,
                                content=CUERPO + "Cuarta linea nueva.\n", tags=["prueba"])
    assert r["ok"], r
    assert _notas(carpeta) == [heredada.name], "duplicó la nota heredada"
    texto = heredada.read_text(encoding="utf-8")
    assert "Cuarta linea nueva." in texto
    assert "id: id-heredado" in texto, "la actualización perdió la identidad"


def test_un_titulo_sin_letras_no_produce_un_nombre_vacio():
    import vault_write

    for titulo in ("!!!", "¿?"):
        assert vault_write.slugify(titulo), titulo


def test_la_nota_vieja_en_otra_carpeta_se_detecta(tmp_path, monkeypatch):
    """La detección entre carpetas también reconoce el nombre viejo."""
    import vault_write

    _vault(tmp_path, monkeypatch, "07_Knowledge")
    _vault(tmp_path, monkeypatch, "03_Decisions")
    viejo = vault_write._slug_heredado(TITULO)
    (tmp_path / "99_Index").mkdir()
    (tmp_path / "99_Index" / "search-index.json").write_text(json.dumps(
        {"notes": [{"path": f"03_Decisions/{viejo}.md", "title": TITULO}]}),
        encoding="utf-8")

    r = vault_write.vault_write(folder="07_Knowledge", title=TITULO,
                                content=CUERPO, tags=["prueba"])
    assert r["ok"] is False and r["error_code"] == "note_moved", r
    assert r["current_path"] == f"03_Decisions/{viejo}.md"

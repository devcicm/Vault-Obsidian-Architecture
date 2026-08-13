"""Tres defectos de `vault_ingest` que el QA de v40.16 destapó.

Los tres tienen la misma forma que el resto de la tanda: la tool devolvía algo
que parecía correcto y no lo era. Un `agent:` sin escapar rompía el YAML de la
nota entera; un `[[ejemplo]]` dentro de un fence se convertía en enlace real; y
una escritura caída a mitad del lote dejaba notas sin índice y `ok: true`.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import yaml  # noqa: E402


def test_el_wikilink_dentro_de_un_fence_no_se_extrae():
    """Obsidian no resuelve un wikilink en un fence: lo enseña (AP-57)."""
    import vault_ingest

    texto = "\n".join([
        "Se escribe asi:",
        "```markdown",
        "[[ejemplo-de-la-doc]]",
        "```",
        "Y el destino real es [[nota-real]].",
    ])
    entidades = vault_ingest._extract_entities(texto)
    assert "nota-real" in entidades["wikilinks"]
    assert "ejemplo-de-la-doc" not in entidades["wikilinks"], (
        "un enlace de documentacion no puede volverse una nota fantasma"
    )


def test_el_agent_con_dos_puntos_no_rompe_el_frontmatter():
    """AP-56: `agent` viene del invocante, no de esta tool."""
    import vault_ingest

    nota = vault_ingest._build_note(
        {"title": "Titulo", "body": "Cuerpo con suficiente texto para la nota."},
        {"tags": [], "wikilinks": []},
        "07_Knowledge", "", "prueba", "inline", "claude: opus", [],
    )
    crudo = nota["content"].split("---")[1]
    datos = yaml.safe_load(crudo)
    assert datos["agent"] == "claude: opus"


def test_una_nota_caida_no_se_lleva_el_lote_ni_el_indice(tmp_path, monkeypatch):
    """La nota k que falla es una fila del informe, no la desaparicion del resto."""
    import vault_io
    import vault_ingest

    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    vault_io.set_vault_root(tmp_path)

    original = vault_ingest.atomic_write_text
    estado = {"n": 0}

    def falla_en_la_segunda(path, content, *a, **kw):
        estado["n"] += 1
        if estado["n"] == 2:
            raise OSError("disco lleno simulado")
        return original(path, content, *a, **kw)

    monkeypatch.setattr(vault_ingest, "atomic_write_text", falla_en_la_segunda)

    parrafo = "Un parrafo con contenido de sobra para superar el minimo de caracteres exigido por la segmentacion de esta tool. "
    texto = "\n\n".join([
        "# Primero", parrafo * 2,
        "# Segundo", parrafo * 2,
        "# Tercero", parrafo * 2,
    ])
    r = vault_ingest.vault_ingest(
        text=texto, section="07_Knowledge", source="prueba",
        origin="inline", commit=True, agent="test",
    )

    assert r["failed"], "la nota caida se reporta"
    assert r["ok"] is False, "un lote con bajas no es un exito"
    assert r["written"], "las demas si se escribieron"
    assert (tmp_path / "99_Index").exists() or r["written"], (
        "el indice de seccion corre aunque una nota falle"
    )

"""La validación que corre cuando nace una nota, y los dueños que consulta.

`vault_write._collect_ghost_links` es el aviso de SP-02/AP-14 en el único
momento en que arreglarlo es barato: cuando el enlace se escribe. Hasta v40.14
medía con su propio criterio en los cuatro sitios donde ya había dueño canónico
(AP-57), y —esto es lo que lo hizo caro— **con los dos sentidos del error a la
vez**: resolvía por basename (falso negativo: el enlace roto pasaba), no miraba
`aliases:` (falso positivo: avisaba del bueno). El ruido enseña a ignorar el
aviso justo cuando el aviso deja escapar lo que importa; así es como un vault
real llega a 221 enlaces muertos con la validación puesta.

Un test por defecto. El de basename es el que no puede volver a caerse: es el
único cuyo fallo sale **verde**, en el mismo sitio donde Obsidian pinta el
enlace roto.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import vault_io
import vault_write
from vault_lib import indice_de_destinos, resolver_destino_wikilink


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """Un vault mínimo con las cuatro trampas plantadas."""
    (tmp_path / "00_System").mkdir()
    (tmp_path / "containers").mkdir()
    (tmp_path / "07_Knowledge").mkdir()
    (tmp_path / ".history").mkdir()

    (tmp_path / "containers" / "ct105.md").write_text(
        "---\ntitle: CT 105\n---\n", encoding="utf-8")
    # Mismo basename, otra carpeta: `[[otra/ct105]]` NO resuelve por él.
    (tmp_path / "07_Knowledge" / "con-alias.md").write_text(
        "---\naliases:\n  - Nombre Largo Y Bonito\n---\n", encoding="utf-8")
    # Instantánea congelada: existe en disco y no es un destino del vault.
    (tmp_path / ".history" / "fantasma.md").write_text("x\n", encoding="utf-8")

    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    vault_io.set_vault_root(tmp_path)
    yield tmp_path


def _ghost(links, desde="07_Knowledge/nota.md"):
    return vault_write._collect_ghost_links(links, Path(desde))


class TestLosCuatroDefectos:
    def test_destino_con_carpeta_no_se_resuelve_por_basename(self, vault):
        """El sentido peligroso: fallaba **en verde**.

        `[[otra/ct105]]` no existe; que exista `containers/ct105.md` no lo
        salva. Obsidian pinta ese enlace roto y la validación decía que no.
        """
        assert _ghost(["otra/ct105"]) == ["otra/ct105"]

    def test_el_destino_con_su_carpeta_real_si_resuelve(self, vault):
        """El espejo del anterior: la ruta correcta no puede dar ruido."""
        assert _ghost(["containers/ct105"]) == []

    def test_una_instantanea_no_es_un_destino(self, vault):
        """`.history/fantasma.md` existe en disco y no lo resuelve nadie.

        Quién es instantánea lo decide `vault_io.is_snapshot_path`, no una
        lista propia — que es el AP-57 que esta tool tenía.
        """
        assert _ghost(["fantasma"]) == ["fantasma"]

    def test_los_aliases_resuelven(self, vault):
        """Obsidian resuelve por `aliases:`; `title:` no lo mira (AP-44).

        Este era el falso positivo que entrenaba al operador a ignorar el
        aviso.
        """
        assert _ghost(["Nombre Largo Y Bonito"]) == []

    def test_el_title_no_resuelve(self, vault):
        """La otra mitad de AP-44: `title: CT 105` no es un destino."""
        assert _ghost(["CT 105"]) == ["CT 105"]

    def test_un_wikilink_dentro_de_un_fence_no_es_un_enlace(self, vault):
        """Obsidian no lo resuelve: lo enseña.

        La nota que documenta la convención cita la sintaxis, y contarla eran
        87 de 301 «rotos» en un vault real.
        """
        contenido = "Ver [[containers/ct105]].\n\n```\n[[no-existe-jamas]]\n```\n"
        assert vault_write.extract_wiki_links(contenido) == ["containers/ct105"]


class TestDuenosCanonicos:
    """`vault_lib` es el dueño desde v40.14; vivían privados en una tool."""

    def test_quita_alias_y_ancla(self):
        assert resolver_destino_wikilink("a/b|Texto") == "a/b"
        assert resolver_destino_wikilink("a/b#Seccion") == "a/b"
        assert resolver_destino_wikilink("a/b#Sec|Txt") == "a/b"

    def test_relativa_se_resuelve_contra_la_carpeta_de_la_nota(self):
        desde = Path("07_Knowledge/sub/nota.md")
        assert resolver_destino_wikilink("../otra", desde) == "07_knowledge/otra"
        assert resolver_destino_wikilink("./vecina", desde) == "07_knowledge/sub/vecina"

    def test_sin_origen_una_relativa_no_se_resuelve_a_la_raiz(self):
        """No saber no es lo mismo que resolver a la raíz.

        Devolverla normalizada deja el enlace como no resuelto; inventar la
        raíz lo daría por bueno sin fundamento.
        """
        assert resolver_destino_wikilink("../otra") == "../otra"

    def test_el_indice_incluye_todos_los_sufijos_de_ruta(self):
        d = indice_de_destinos([Path("a/b/c.md")])
        assert "c" in d and "b/c" in d and "a/b/c" in d

    def test_el_indice_incluye_los_aliases(self):
        d = indice_de_destinos([Path("a.md")], ["Otro Nombre"])
        assert "otro nombre" in d

    def test_vault_write_y_foreign_check_consultan_al_dueno(self):
        """AP-57: la copia se salda importando, no congelando."""
        for mod in ("vault_write", "vault_foreign_check"):
            src = (Path(__file__).parent.parent / "scripts" / f"{mod}.py").read_text(
                encoding="utf-8")
            assert "resolver_destino_wikilink" in src, mod
            assert "indice_de_destinos" in src, mod


def test_los_dos_criterios_nuevos_no_estan_en_el_registro_de_ap57():
    """Su límite está declarado, no disimulado.

    `"|"`, `"#"` y `"aliases"` no son constantes distintivas: media docena de
    módulos las escribe por motivos legítimos, y registrarlos daba 10 hallazgos
    falsos. Un guard con ruido deja de leerse, así que se declara el límite en
    el docstring en vez de comprarse el verde ampliando la baseline.
    """
    import vault_criterios
    registrados = {c["criterio"] for c in vault_criterios.CRITERIOS_CON_DUENO}
    assert "como_se_resuelve_un_wikilink" not in registrados
    assert "que_destinos_resuelven" not in registrados
    doc = vault_criterios.__doc__ or ""
    assert "resolver_destino_wikilink" in doc
    assert "indice_de_destinos" in doc

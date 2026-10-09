"""La cascada de índices no pisa un índice que no generó.

`vault_section_index` regeneraba sin condición el `index.md` de la sección y de
cada subcarpeta. En un vault preexistente eso borra el índice que alguien
escribió a mano; y en un sistema de ficheros que no distingue mayúsculas
(Windows, macOS) además renombra `INDEX.md` a `index.md`, porque el reemplazo
atómico crea el fichero con el nombre nuevo. El índice generado lleva la marca
`Generado automáticamente` desde v25 (767a84a): sin ella no es nuestro y se
conserva, y se informa como `indice_ajeno_preservado`.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402
import vault_section_index  # noqa: E402

A_MANO = "# Mi índice\n\nEscrito a mano, con contexto que ningún generador conoce.\n"


@pytest.fixture
def vault(tmp_path):
    previo = vault_io.get_vault_root()
    for rel in ("07_Knowledge/jwt.md", "07_Knowledge/temas/oauth.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("---\ntitle: x\n---\nx\n", encoding="utf-8")
    (tmp_path / "00_System").mkdir()
    vault_io.set_vault_root(tmp_path)
    yield tmp_path
    vault_io.set_vault_root(previo)


def _nombres(carpeta: Path):
    return sorted(p.name for p in carpeta.iterdir() if p.name.lower() == "index.md")


@pytest.mark.parametrize("nombre", ["index.md", "INDEX.md"])
def test_un_indice_escrito_a_mano_sobrevive_y_conserva_su_nombre(vault, nombre):
    propio = vault / "07_Knowledge" / nombre
    propio.write_text(A_MANO, encoding="utf-8")
    r = vault_section_index.vault_section_index("07_Knowledge")
    assert r["ok"] is True, r
    assert propio.read_text(encoding="utf-8") == A_MANO
    assert _nombres(vault / "07_Knowledge") == [nombre]
    assert "07_Knowledge/" + nombre in r["indice_ajeno_preservado"]


def test_el_de_una_subcarpeta_tambien(vault):
    propio = vault / "07_Knowledge" / "temas" / "INDEX.md"
    propio.write_text(A_MANO, encoding="utf-8")
    r = vault_section_index.vault_section_index("07_Knowledge")
    assert propio.read_text(encoding="utf-8") == A_MANO
    assert _nombres(vault / "07_Knowledge" / "temas") == ["INDEX.md"]
    assert "07_Knowledge/temas/INDEX.md" in r["indice_ajeno_preservado"]
    # El de la sección, que no existía, sí se genera.
    assert "Generado automáticamente" in (vault / "07_Knowledge" / "index.md").read_text(
        encoding="utf-8")


def test_un_indice_generado_se_sigue_regenerando(vault):
    vault_section_index.vault_section_index("07_Knowledge")
    (vault / "07_Knowledge" / "nueva.md").write_text("---\ntitle: n\n---\nn\n", encoding="utf-8")
    r = vault_section_index.vault_section_index("07_Knowledge")
    assert r["indice_ajeno_preservado"] == []
    assert "nueva" in (vault / "07_Knowledge" / "index.md").read_text(encoding="utf-8")

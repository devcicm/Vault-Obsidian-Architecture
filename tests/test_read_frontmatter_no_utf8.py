"""Una nota que no es UTF-8 no tumba a quien lee su frontmatter.

Síntoma real: dos notas binarias de un runtime de pytest dentro de
`vault-sandbox/` hicieron que `vault_audit` terminase en UNEXPECTED_ERROR
(`UnicodeDecodeError`), porque `vault_lib.read_frontmatter` capturaba solo
`OSError`, que es lo que `read_text` declara, y no lo que lanza de verdad un
fichero en ANSI/Latin-1 (AP-61). En Windows esas notas son frecuentes: es el
vault de un tercero, no un caso de laboratorio.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vault_lib import read_frontmatter  # noqa: E402


def test_nota_latin1_devuelve_vacio_en_vez_de_lanzar(tmp_path):
    """AP-61: la excepción que se captura es la que se lanza, no la declarada."""
    nota = tmp_path / "ansi.md"
    nota.write_bytes("---\ntitle: Migración\n---\n\ncuerpo\n".encode("latin-1"))
    assert read_frontmatter(nota) == {}


def test_nota_binaria_devuelve_vacio(tmp_path):
    nota = tmp_path / "binaria.md"
    nota.write_bytes(b"\x80\x82bytes no-utf8")
    assert read_frontmatter(nota) == {}


def test_nota_utf8_se_sigue_leyendo(tmp_path):
    nota = tmp_path / "ok.md"
    nota.write_text("---\ntitle: Migración\n---\n\ncuerpo\n", encoding="utf-8")
    assert read_frontmatter(nota) == {"title": "Migración"}

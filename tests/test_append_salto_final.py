"""Un append al final deja la nota terminada en un solo salto de línea.

Medido el 2026-10-05 con la wheel 40.35 sobre una copia de un vault real con
`end-of-file-fixer` en su pre-commit: `vault_append` dejaba `\n\n\n**fecha**
texto` sin salto final, así que cada append ensuciaba el commit siguiente con
un cambio que la tool no había pedido.
"""

import vault_append


def _vault(tmp_path, monkeypatch, texto):
    (tmp_path / "00_System").mkdir()
    nota = tmp_path / "nota.md"
    nota.write_bytes(texto.encode("utf-8"))
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setattr(vault_append, "get_vault_root", lambda: tmp_path)
    return nota


def test_append_al_final_termina_en_un_salto(tmp_path, monkeypatch):
    nota = _vault(tmp_path, monkeypatch, "---\nid: n\n---\n\n# N\n\ncuerpo\n")
    assert vault_append.vault_append("nota.md", "linea", timestamped=False)["ok"]
    assert nota.read_bytes().decode("utf-8") == "---\nid: n\n---\n\n# N\n\ncuerpo\n\nlinea\n"


def test_append_a_una_nota_sin_salto_final_tambien(tmp_path, monkeypatch):
    nota = _vault(tmp_path, monkeypatch, "cuerpo")
    assert vault_append.vault_append("nota.md", "linea", timestamped=False)["ok"]
    assert nota.read_bytes().decode("utf-8") == "cuerpo\n\nlinea\n"


def test_append_en_seccion_intermedia_no_cambia(tmp_path, monkeypatch):
    nota = _vault(tmp_path, monkeypatch, "# N\n\n## A\n\nuno\n\n## B\n\ndos\n")
    assert vault_append.vault_append("nota.md", "x", section="A", timestamped=False)["ok"]
    assert nota.read_bytes().decode("utf-8") == "# N\n\n## A\n\nuno\n\nx\n\n## B\n\ndos\n"

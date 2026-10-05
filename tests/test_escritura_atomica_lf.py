"""La escritura atómica deposita el texto tal cual, también en Windows.

`open(temp, "w")` sin `newline=` traduce cada `\n` a `\r\n` en Windows, así
que el `normalize_newlines` del saneado —que deja LF a propósito— se deshacía
en el último paso. Medido el 2026-10-05 en un vault real escrito desde Windows:
243 notas en CRLF, 369 en LF y 4 mezcladas, según qué tool tocó cada una por
última vez; y un `vault_append` reescribía en CRLF la nota entera para añadir
una línea. `vault init` y el fichero de versión ya escribían LF.
"""

from vault.kernel.escritura import escritura_atomica


def test_el_primitivo_no_traduce_saltos(tmp_path):
    destino = tmp_path / "nota.md"
    escritura_atomica(destino, "---\nid: n\n---\n\ncuerpo\n")
    assert destino.read_bytes() == b"---\nid: n\n---\n\ncuerpo\n"


def test_atomic_write_text_deja_lf(tmp_path, monkeypatch):
    import vault_io

    (tmp_path / "00_System").mkdir()
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    destino = tmp_path / "nota.md"
    vault_io.atomic_write_text(destino, "# N\r\n\r\ncuerpo\n")
    assert b"\r" not in destino.read_bytes()

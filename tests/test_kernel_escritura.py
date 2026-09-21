"""Caracterización ejecutable del primitive atómico package-owned."""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from vault.kernel import escritura


def test_escritura_normal_crea_padre_y_reemplaza_el_destino(tmp_path):
    target = tmp_path / "deep" / "note.md"
    target.parent.mkdir(parents=True)
    target.write_text("anterior", encoding="utf-8")

    result = escritura.escritura_atomica(target, "nueva\n")

    assert result is None
    assert target.read_text(encoding="utf-8") == "nueva\n"
    assert not list(target.parent.glob(".tmp.*"))


def test_escritura_crea_el_directorio_padre_si_falta(tmp_path):
    target = tmp_path / "missing" / "nested" / "note.md"
    escritura.escritura_atomica(target, "contenido")
    assert target.read_text(encoding="utf-8") == "contenido"


def test_encoding_y_newlines_se_delegan_a_open_sin_normalizacion(tmp_path):
    target = tmp_path / "nota.md"
    content = "café\r\nlínea dos\n"
    escritura.escritura_atomica(target, content, encoding="utf-8")
    # El primitive histórico abría en modo texto sin ``newline=``. En Windows
    # cada LF conserva la traducción estándar de ``open`` (incluido un CRLF de
    # entrada, que pasa a CRCRLF); no se normaliza contenido en este nivel.
    assert target.read_bytes() == content.replace("\n", os.linesep).encode("utf-8")


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, False), ("0", False), ("1", True), ("true", False)],
)
def test_vault_fsync_conserva_la_semantica_historica(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("VAULT_FSYNC", raising=False)
    else:
        monkeypatch.setenv("VAULT_FSYNC", value)
    assert escritura._fsync_enabled() is expected


def test_fsync_de_archivo_y_directorio_es_opt_in(monkeypatch, tmp_path):
    target = tmp_path / "note.md"
    calls: list[int] = []
    monkeypatch.setenv("VAULT_FSYNC", "1")
    monkeypatch.setattr(escritura.os, "fsync", lambda fd: calls.append(fd))
    escritura.escritura_atomica(target, "contenido")
    assert calls


def test_fallo_de_escritura_limpia_temporal_y_propagacion(monkeypatch, tmp_path):
    target = tmp_path / "note.md"

    def broken_write(temp: Path, _text: str, _encoding: str) -> None:
        temp.write_text("parcial", encoding="utf-8")
        raise OSError(errno.ENOSPC, "disk full")

    monkeypatch.setattr(escritura, "_escribir_temporal", broken_write)
    with pytest.raises(OSError) as caught:
        escritura.escritura_atomica(target, "contenido")
    assert caught.value.errno == errno.ENOSPC
    assert not list(tmp_path.glob(".tmp.*"))
    assert not target.exists()


def test_fallo_de_replace_limpia_temporal_y_propagacion(monkeypatch, tmp_path):
    target = tmp_path / "note.md"

    def broken_replace(_source: Path, _target: Path) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(escritura.os, "replace", broken_replace)
    with pytest.raises(PermissionError, match="denied"):
        escritura.escritura_atomica(target, "contenido")
    assert not list(tmp_path.glob(".tmp.*"))


def test_guardas_corren_antes_de_crear_el_directorio(tmp_path):
    target = tmp_path / "not-created" / "note.md"

    def reject(_path: Path, _text: str) -> None:
        raise ValueError("blocked")

    with pytest.raises(ValueError, match="blocked"):
        escritura.escritura_atomica(target, "contenido", guardas=(reject,))
    assert not target.parent.exists()

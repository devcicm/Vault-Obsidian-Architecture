"""Caracterización ejecutable del primitive atómico package-owned."""

from __future__ import annotations

import errno
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
    # No se normaliza contenido en este nivel: se deposita byte a byte.
    # Hasta 2026-10-05 se abría en modo texto sin ``newline=`` y en Windows
    # cada LF pasaba a CRLF (y un CRLF de entrada a CRCRLF), deshaciendo el LF
    # que el saneado fija. Ver ``test_escritura_atomica_lf``.
    assert target.read_bytes() == content.encode("utf-8")


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


def _comparticion(winerror: int = 5) -> PermissionError:
    """El `PermissionError` que da Windows cuando otro proceso tiene abierto el
    destino sin compartir el borrado. `winerror` se fija a mano para que el
    caso corra igual en POSIX."""
    exc = PermissionError(13, "Acceso denegado")
    exc.winerror = winerror
    return exc


def test_replace_reintenta_la_comparticion_transitoria_de_windows(monkeypatch, tmp_path):
    """r48, 2026-10-16: `test_appends_en_paralelo_llegan_todos` en rojo, uno de
    cada ~15 intentos fuera de la suite. Con un espía, ninguna apertura de la
    nota fuera del lock y ningún robo: quien la tenía abierta era ajeno al
    repo (antivirus, indexador) y el append devolvía PERMISSION_DENIED por un
    instante de compartición. `bloqueo.soltar` ya reintentaba lo mismo."""
    target = tmp_path / "note.md"
    target.write_text("anterior", encoding="utf-8")
    real = escritura.os.replace
    fallos = [_comparticion(5), _comparticion(32)]

    def ocupado(origen, destino):
        if fallos:
            raise fallos.pop(0)
        real(origen, destino)

    monkeypatch.setattr(escritura.os, "replace", ocupado)
    escritura.escritura_atomica(target, "nueva")
    assert target.read_text(encoding="utf-8") == "nueva"
    assert not fallos
    assert not list(tmp_path.glob(".tmp.*"))


def test_replace_se_rinde_si_la_comparticion_no_se_libera(monkeypatch, tmp_path):
    target = tmp_path / "note.md"
    monkeypatch.setattr(escritura, "PLAZO_DE_COMPARTICION", 0.05)

    def siempre(_origen, _destino):
        raise _comparticion()

    monkeypatch.setattr(escritura.os, "replace", siempre)
    with pytest.raises(PermissionError):
        escritura.escritura_atomica(target, "contenido")
    assert not list(tmp_path.glob(".tmp.*"))


def test_el_reintento_vuelve_a_comprobar_el_lock(monkeypatch, tmp_path):
    """Quien pierde el lock mientras espera no reemplaza: el fencing va antes
    de cada intento, no solo del primero."""
    target = tmp_path / "note.md"
    llamadas = []

    def comprobar(_path):
        llamadas.append(1)
        if len(llamadas) > 1:
            raise RuntimeError("lock perdido")

    monkeypatch.setattr(escritura, "comprobar_toma", comprobar)

    def ocupado(_origen, _destino):
        raise _comparticion()

    monkeypatch.setattr(escritura.os, "replace", ocupado)
    with pytest.raises(RuntimeError, match="lock perdido"):
        escritura.escritura_atomica(target, "contenido")
    assert not target.exists()
    assert not list(tmp_path.glob(".tmp.*"))


def test_guardas_corren_antes_de_crear_el_directorio(tmp_path):
    target = tmp_path / "not-created" / "note.md"

    def reject(_path: Path, _text: str) -> None:
        raise ValueError("blocked")

    with pytest.raises(ValueError, match="blocked"):
        escritura.escritura_atomica(target, "contenido", guardas=(reject,))
    assert not target.parent.exists()

"""Process helpers keep test subprocess contracts in one place."""

from pathlib import Path

from apoyo import correr_python, esperar_condicion, lanzar_python


def test_correr_python_tiene_modo_bytes_y_texto_utf8():
    bytes_result = correr_python(
        "-c", "import sys; sys.stdout.buffer.write(bytes([255]))", modo="bytes"
    )
    assert bytes_result.returncode == 0
    assert bytes_result.stdout == bytes([255])

    text_result = correr_python(
        "-c", "print('diagn\\u00f3stico')", modo="text"
    )
    assert text_result.returncode == 0
    assert text_result.stdout == "diagn\u00f3stico\n"


def test_lanzar_python_conserva_streams_heredados_y_acepta_overrides(tmp_path):
    marker = tmp_path / "started"
    child = lanzar_python(
        "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('ok')"
    )
    assert child.stdout is None and child.stderr is None
    assert child.wait(timeout=10) == 0
    assert marker.read_text(encoding="utf-8") == "ok"


def test_correr_python_conserva_el_orden_del_pythonpath_del_llamador(tmp_path):
    custom = tmp_path / "custom"
    custom.mkdir()
    (custom / "selected.py").write_text("VALUE = 'caller-first'\n", encoding="utf-8")
    result = correr_python(
        "-c", "import selected; print(selected.VALUE)",
        env={"PYTHONPATH": str(custom)}, cwd=tmp_path, modo="text",
    )
    assert result.returncode == 0
    assert result.stdout == "caller-first\n"


def test_esperar_condicion_es_acotado_y_no_requiere_sleep():
    assert esperar_condicion(lambda: True, timeout=0)
    assert not esperar_condicion(lambda: False, timeout=0)

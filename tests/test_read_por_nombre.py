"""O2 — `vault_read` resuelve por nombre con el criterio del consumidor.

El catálogo prometía «por ruta relativa o por título» y la tool solo aceptaba
rutas: un agente que pasaba el nombre recibía NOTE_NOT_FOUND. La resolución se
implementó con el criterio con el que Obsidian abre un enlace —stem y
`aliases:`, nunca `title:` (AP-44)— y su dueño es `vault_lib`, el mismo que
usan el write path y los índices.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from vault_io import reset_vault_root, set_vault_root  # noqa: E402


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    seccion = tmp_path / "07_Knowledge"
    seccion.mkdir(parents=True)
    (seccion / "mi-concepto.md").write_text(
        "---\ntitle: Un Título Cualquiera\naliases: [apodo-vivo]\n---\n\n"
        "# Un Título Cualquiera\n\ncuerpo\n", encoding="utf-8")
    set_vault_root(tmp_path)
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    yield tmp_path
    reset_vault_root()


def _lee(arg: str):
    import importlib

    modulo = importlib.import_module("vault_read")
    return modulo.vault_read(arg)


def test_por_stem_del_fichero(vault):
    r = _lee("mi-concepto")
    assert r["ok"] is True
    assert r["path"] == "07_Knowledge/mi-concepto.md"
    assert r["resolved_from"] == "mi-concepto"


def test_por_alias(vault):
    r = _lee("apodo-vivo")
    assert r["ok"] is True
    assert r["path"] == "07_Knowledge/mi-concepto.md"


def test_por_titulo_no_resuelve_como_obsidian(vault):
    """`title:` no es clave de resolución: el criterio es stem/aliases."""
    r = _lee("Un Título Cualquiera")
    assert r["ok"] is False and r["error_code"] == "NOTE_NOT_FOUND"


def test_la_ruta_directa_no_declara_resolucion(vault):
    r = _lee("07_Knowledge/mi-concepto.md")
    assert r["ok"] is True
    assert "resolved_from" not in r


def test_un_nombre_ambiguo_lista_los_candidatos(tmp_path, monkeypatch):
    (tmp_path / "07_Knowledge").mkdir()
    (tmp_path / "03_Decisions").mkdir()
    for carpeta in ("07_Knowledge", "03_Decisions"):
        (tmp_path / carpeta / "guia.md").write_text(
            f"---\ntitle: Guía {carpeta}\n---\n\n# Guía\n\n{carpeta}\n",
            encoding="utf-8")
    set_vault_root(tmp_path)
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    try:
        r = _lee("guia")
    finally:
        reset_vault_root()
    assert r["ok"] is False and r["error_code"] == "NOTE_NOT_FOUND"
    assert sorted(r.get("candidates") or []) == [
        "03_Decisions/guia.md", "07_Knowledge/guia.md"]

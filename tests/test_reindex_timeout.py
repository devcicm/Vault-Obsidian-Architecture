"""`vault_reindex` no muere por el límite genérico de 60 s.

Medido el 2026-10-05 en un vault real de 612 notas: el reindex tardaba ~56 s
y la primera ejecución murió en `TOOL_TIMEOUT` a mitad de escritura, dejando
el índice a medias y un lock huérfano. Recorre el vault entero, así que el
límite pensado para detectar una tool colgada no le sirve; sí debe seguir
mandando un `VAULT_TOOL_TIMEOUT` mayor exportado por quien lo necesita.
"""

import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_errors  # noqa: E402


def _limite_de_reindex(monkeypatch, defecto):
    visto = {}

    def wrap_main_falso(fn, tool_name, timeout=None):
        visto["timeout"] = timeout
        return 0

    monkeypatch.setattr(vault_errors, "wrap_main", wrap_main_falso)
    monkeypatch.setattr(vault_errors, "TOOL_TIMEOUT_SECONDS", defecto)
    with pytest.raises(SystemExit):
        runpy.run_path(str(SCRIPTS / "vault_reindex.py"), run_name="__main__")
    return visto["timeout"]


def test_reindex_no_usa_el_limite_generico(monkeypatch):
    assert _limite_de_reindex(monkeypatch, 60) >= 3600


def test_un_limite_exportado_mayor_sigue_mandando(monkeypatch):
    assert _limite_de_reindex(monkeypatch, 7200) == 7200

"""La `safe.directory` va acotada a la invocación, no global.

El MiniServer tiene el vault escrito por la cuenta del servicio MCP y
leído por la del dueño: git se negaba a operar sobre él («dubious
ownership»). La salida es la opción **acotada** —`-c safe.directory=<repo>`
en ese argv—, que vale solo para esa llamada. La alternativa, poner
`safe.directory=*` en la configuración global de la máquina, abriría
**todos** los repositorios de esa máquina: es una decisión del dueño, no
del toolkit.

Lo que estos tests fijan:

- la opción se añade al argv de la llamada, con la ruta **absoluta** del
  repositorio (la del `-C` si lo hay, y si no la del `cwd`);
- sin repositorio conocido no se inventa nada;
- **no se toca la configuración global**: la única llamada que sale es la
  del verbo pedido.
"""

from __future__ import annotations

from pathlib import Path

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

from vault.kernel.procesos_git import _safe_directory, ejecutar_git


def test_la_opcion_va_con_la_ruta_absoluta_del_repositorio():
    opcion = _safe_directory(["log", "--oneline"], str(REPO_ROOT))
    assert opcion[:1] == ["-c"], opcion
    assert opcion[1].startswith("safe.directory="), opcion
    assert str(REPO_ROOT).lower().replace("\\", "/") in opcion[1].lower().replace("\\", "/")


def test_el_guion_c_del_argv_manda_sobre_el_cwd():
    opcion = _safe_directory(["-C", "/otro/repo", "log"], str(REPO_ROOT))
    assert opcion[1].endswith("/otro/repo") or opcion[1].endswith("\\otro\\repo"), opcion


def test_sin_repositorio_no_se_inventa_la_opcion():
    assert _safe_directory(["log"], None) == []
    assert _safe_directory(["log"], "") == []


def test_la_llamada_lleva_la_opcion_y_no_toca_la_configuracion_global(monkeypatch):
    """Una sola llamada, con la opción; nada de `git config --global`."""
    llamadas = []

    class _Falso:
        returncode = 0
        stdout = ""
        stderr = ""

    def _run(argv, **kwargs):
        llamadas.append((list(argv), kwargs))
        return _Falso()

    import subprocess

    monkeypatch.setattr(subprocess, "run", _run)

    ejecutar_git(REPO_ROOT, ["log", "--oneline"])

    assert len(llamadas) == 1, llamadas
    argv = llamadas[0][0]
    assert argv[0] == "git"
    assert "-c" in argv, argv
    assert any(a.startswith("safe.directory=") for a in argv), argv
    assert not any("config" in a for a in argv), (
        "la configuración global no se toca: la opción es del argv")
    assert "log" in argv

"""`vault.ejecutor` — correr una tool en este intérprete.

Lo que se prueba aquí es el **comportamiento** en proceso: que la tool acepte
los argumentos, escriba donde debe y conteste lo mismo que por subproceso. El
**contrato CLI** —que el script publicado arranque y rechace lo malformado sin
traceback— se sigue comprobando por subproceso, una vez por tool.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from apoyo import escribir_nota
from vault.ejecutor import ejecutar
from vault.kernel.contexto import construir
from vault.kernel.ledger import write_report
from vault.kernel.raiz import get_vault_root


def _vault_de_prueba(tmp_path: Path) -> Path:
    """Un vault mínimo con la nota que `vault_append` va a tocar."""
    vault = tmp_path / "vault"
    (vault / "07_Knowledge").mkdir(parents=True)
    escribir_nota(vault, "07_Knowledge/log.md",
                  {"title": "log", "status": "draft"}, "# log\n")
    return vault


def test_una_tool_en_proceso_escribe_donde_debe_y_contesta_ok(tmp_path):
    vault = _vault_de_prueba(tmp_path)
    r = ejecutar(construir(vault),
                 ["vault_append.py", "--path", "07_Knowledge/log.md",
                  "--content", "hola", "--no-timestamp"])
    assert r.ok, r.texto + r.error
    assert "hola" in (vault / "07_Knowledge/log.md").read_text(encoding="utf-8")


def test_el_envelope_de_un_fallo_es_el_mismo_que_por_subproceso(tmp_path):
    """Los argumentos que faltan salen con el envelope del contrato, no con un texto."""
    from vault_errors import wrap_main

    vault = _vault_de_prueba(tmp_path)
    r = ejecutar(construir(vault), ["vault_append.py"], envoltorio=wrap_main)
    assert r.codigo == 2, r.texto
    assert r.envelope is not None
    assert r.envelope.get("error_code") == "INVALID_ARGS", r.envelope


def test_restaura_el_interpretero_como_lo_encontro(tmp_path):
    antes_argv = list(sys.argv)
    antes_cwd = os.getcwd()
    antes_agente = os.environ.get("VAULT_AGENT")

    vault = _vault_de_prueba(tmp_path)
    ejecutar(construir(vault),
             ["vault_append.py", "--path", "07_Knowledge/log.md",
              "--content", "hola", "--no-timestamp"],
             agente="otro-agente")

    assert sys.argv == antes_argv
    assert os.getcwd() == antes_cwd
    assert os.environ.get("VAULT_AGENT") == antes_agente


def test_restaura_la_raiz_aunque_la_tool_escriba(tmp_path):
    antes = get_vault_root()
    vault = _vault_de_prueba(tmp_path)
    ejecutar(construir(vault),
             ["vault_append.py", "--path", "07_Knowledge/log.md",
              "--content", "hola", "--no-timestamp"])
    assert get_vault_root() == antes


def test_el_ledger_del_llamador_no_cuenta_lo_que_escribio_la_tool(tmp_path):
    """El contador de escrituras es thread-local: el de la tool es el de su hilo."""
    vault = _vault_de_prueba(tmp_path)
    antes = write_report()
    ejecutar(construir(vault),
             ["vault_append.py", "--path", "07_Knowledge/log.md",
              "--content", "hola", "--no-timestamp"])
    assert write_report() == antes


class _ToolQueCambiaElDirectorio:
    """Una tool que se va de casa: el ejecutor la devuelve a su sitio."""

    def __init__(self, destino: Path) -> None:
        self.destino = destino

    def main(self) -> int:
        os.chdir(str(self.destino))
        return 0


def test_una_tool_que_cambia_el_directorio_no_lo_deja_cambiado(tmp_path):
    antes = os.getcwd()
    ejecutar(None, ["cambia.py"], modulo=_ToolQueCambiaElDirectorio(tmp_path))
    assert os.getcwd() == antes


class _ToolColgada:
    """Una tool que no termina: el timeout declara la llamada perdida."""

    def __init__(self) -> None:
        self.semaforo = threading.Event()

    def main(self) -> int:
        self.semaforo.wait(60)
        return 0


def test_el_timeout_declara_perdida_la_llamada():
    tool = _ToolColgada()
    try:
        r = ejecutar(None, ["colgada.py"], modulo=tool, timeout=0.2)
    finally:
        tool.semaforo.set()
    assert r.codigo == 1
    assert r.motivo is not None and "timeout" in r.motivo, r.motivo


def test_una_tool_que_no_existe_se_dice():
    """Una tool que no está es un error de quien la pidió: se levanta, no se tapa."""
    import pytest

    with pytest.raises(ModuleNotFoundError) as exc:
        ejecutar(None, ["no_existe_esta_tool.py"])
    assert "no_existe_esta_tool" in str(exc.value)


def test_la_raiz_llega_a_los_hijos_que_lanza_la_tool(tmp_path):
    """Los pasos de `vault_init` son subprocesos: heredan la raíz del entorno.

    Sin `VAULT_ROOT` en el entorno, el hijo autodetecta la raíz y escribe en
    otro vault: el que se inicializa en proceso salía sin índice maestro, sin
    grafo, sin hash-index y sin la versión del estándar. Medido el 2026-11-04
    al migrar `test_indice_no_se_regenera_dos_veces.py`.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    r = ejecutar(None, ["vault_init.py", "--no-audit"], raiz=vault)
    assert r.ok, r.texto[-400:] + r.error[-400:]
    for relativo in ("99_Index/index.md", "99_Index/graph.json",
                     "99_Index/hash-index.json", "00_System/standard-version.json"):
        assert (vault / relativo).is_file(), relativo

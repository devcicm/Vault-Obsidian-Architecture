"""La copia de un vault vivo ignora el estado de EJECUCION (locks).

Medido el 2026-10-27 en la CI (run 40464661392, Windows 3.10): la copia del
sandbox canonico arrastro `00_System/.locks` y fallo con `shutil.Error`
(WinError 3) porque otro worker retiro ese directorio a mitad de la copia. Es
la MISMA clase que el defecto R13-03b del backup (que ya ignoraba los locks):
la diferencia era que cada copia inventaba su patron —el test que fallo
ignoraba `*.lock` pero no `.locks/`.

Este test fija el criterio en UN sitio (`sandbox_fixture.copiar_vault`):
`.locks/` y `*.lock` no se copian; todo lo demas, si.
"""
import shutil
from pathlib import Path

import pytest

from sandbox_fixture import ESTADO_DE_EJECUCION, copiar_vault


def _vault_con_locks(destino: Path) -> Path:
    (destino / "00_System").mkdir(parents=True)
    (destino / "00_System" / ".locks").mkdir()
    (destino / "00_System" / ".locks" / "contador.txt.lock").write_text("x")
    (destino / "00_System" / ".tool-trace.json.lock").write_text("x")
    (destino / "00_System" / "tool-contracts.json").write_text("{}")
    (destino / "07_Knowledge").mkdir()
    (destino / "07_Knowledge" / "nota.md").write_text("# nota\n")
    return destino


def test_la_copia_no_arrastra_el_estado_de_ejecucion(tmp_path):
    origen = _vault_con_locks(tmp_path / "vivo")
    copia = copiar_vault(origen, tmp_path / "copia")
    assert not (copia / "00_System" / ".locks").exists(), "se copio el directorio .locks"
    assert not (copia / "00_System" / ".tool-trace.json.lock").exists(), \
        "se copio un fichero de lock"
    assert not list(copia.rglob("*.lock")), "quedo algun *.lock en la copia"


def test_la_copia_si_arrastra_el_contenido(tmp_path):
    """El ignore no puede ser tan ancho que se lleve contenido real."""
    origen = _vault_con_locks(tmp_path / "vivo")
    copia = copiar_vault(origen, tmp_path / "copia")
    assert (copia / "00_System" / "tool-contracts.json").is_file()
    assert (copia / "07_Knowledge" / "nota.md").is_file()


def test_el_conjunto_canonico_cubre_los_dos_patrones(tmp_path):
    """La regresion: `*.lock` sin `.locks` deja la carrera viva."""
    assert ".locks" in ESTADO_DE_EJECUCION
    assert "*.lock" in ESTADO_DE_EJECUCION
    patrones = shutil.ignore_patterns(*ESTADO_DE_EJECUCION)
    assert patrones("00_System", [".locks"]) == {".locks"}
    assert patrones("00_System", [".tool-trace.json.lock"]) == {".tool-trace.json.lock"}
    assert patrones("00_System", ["tool-contracts.json"]) == set()


def test_una_copia_con_locks_extra_que_se_retira_no_rompe(tmp_path):
    """La carrera concreta: el directorio desaparece durante la copia.

    Causa y remedio en una linea: `copytree` NO desciende en los nombres que
    el `ignore` excluye, asi que si `.locks` esta excluido, su retirada a
    mitad no puede affectar la copia (antes: `shutil.Error` con WinError 3).
    """
    patrones = shutil.ignore_patterns(*ESTADO_DE_EJECUCION)
    excluidos = patrones("00_System", [".locks", "tool-contracts.json",
                                       ".tool-trace.json.lock"])
    assert ".locks" in excluidos, "copytree descenderia en .locks: la carrera sigue viva"
    assert ".tool-trace.json.lock" in excluidos

    # Y la copia real termina sin tocar ese directorio.
    origen = _vault_con_locks(tmp_path / "vivo")
    destino = tmp_path / "copia"
    shutil.copytree(origen, destino,
                    ignore=shutil.ignore_patterns(*ESTADO_DE_EJECUCION))
    assert destino.is_dir()


def test_la_copia_acepta_patrones_extra(tmp_path):
    origen = _vault_con_locks(tmp_path / "vivo")
    (origen / "00_System" / ".tmp.abc").write_text("x")
    copia = copiar_vault(origen, tmp_path / "copia", ignore_extra=(".tmp.*",))
    assert not (copia / "00_System" / ".tmp.abc").exists()

"""4.2 — tras una terminación forzada, el vault está intacto y el temporal
huérfano se recoge **sin borrar nada cuya propiedad no se pueda demostrar**.

La escritura atómica es temporal→rename: si el proceso muere entre ambas,
el fichero destino conserva su contenido anterior y queda un temporal
`.tmp.<pid>.<8 hex>` en su carpeta. El contenido no se pierde; el temporal
sí es basura, y seAccumula.

Lo que se prueba aquí:

- el **destino queda intacto** (no hay medio fichero);
- el temporal de un **proceso muerto** se recoge;
- el temporal de un **proceso vivo** NO se toca: su escritura está en
  curso y ese fichero es suyo;
- un fichero que **no tiene nuestra forma** no se toca: aunque se llame
  «.tmp», sin la prueba de propiedad no se borra nada de nadie;
- el `--dry-run` **no borra**: dice lo que haría.

La propiedad se demuestra por dos cosas a la vez: el **nombre** tiene la
forma que esta casa le da a sus temporales, y el **pid** está muerto. Lo
que no cumple las dos se queda.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

from vault.kernel.escritura import (  # noqa: E402
    PATRON_TEMPORAL,
    limpiar_temporales,
    temporales_huerfanos,
)

PID_MUERTO = 999_999  # ningún proceso tiene ese identificador


def _temporal(carpeta: Path, pid: int) -> Path:
    ruta = carpeta / f".tmp.{pid}.a1b2c3d4"
    ruta.write_text("contenido a medias", encoding="utf-8")
    return ruta


def test_el_destino_queda_intinto_y_el_temporal_se_recoge(tmp_path):
    """El escenario: el proceso muere entre escribir el temporal y renombrar."""
    notas = tmp_path / "07_Knowledge"
    notas.mkdir()
    destino = notas / "nota.md"
    destino.write_text("contenido bueno", encoding="utf-8")
    temporal = _temporal(notas, PID_MUERTO)

    huerfanos = temporales_huerfanos(tmp_path)
    assert [h["path"] for h in huerfanos] == [str(temporal)], huerfanos

    informe = limpiar_temporales(tmp_path)
    assert informe["temporales_borrados"] == 1, informe
    assert not temporal.exists()
    # Y el fichero bueno sigue intacto: la escritura atómica no lo tocó.
    assert destino.read_text(encoding="utf-8") == "contenido bueno"


def test_el_temporal_de_un_proceso_vivo_no_se_toca(tmp_path):
    """Su escritura está en curso: ese temporal es suyo."""
    notas = tmp_path / "07_Knowledge"
    notas.mkdir()
    temporal = _temporal(notas, os.getpid())

    assert temporales_huerfanos(tmp_path) == []
    informe = limpiar_temporales(tmp_path)
    assert informe["temporales_borrados"] == 0, informe
    assert temporal.exists(), "se borró el temporal de un proceso vivo"


def test_un_fichero_que_no_tiene_nuestra_forma_no_se_toca(tmp_path):
    """Sin la forma, no hay prueba de propiedad: no se borra nada de nadie."""
    notas = tmp_path / "07_Knowledge"
    notas.mkdir()
    ajeno = notas / ".tmp.999999.txt"
    ajeno.write_text("no es nuestro", encoding="utf-8")
    otro = notas / "nota.tmp.1.x"
    otro.write_text("tampoco", encoding="utf-8")

    assert temporales_huerfanos(tmp_path) == []
    limpiar_temporales(tmp_path)
    assert ajeno.exists() and otro.exists()


def test_el_dry_run_no_borra(tmp_path):
    notas = tmp_path / "07_Knowledge"
    notas.mkdir()
    temporal = _temporal(notas, PID_MUERTO)

    informe = limpiar_temporales(tmp_path, dry_run=True)
    assert informe["dry_run"] is True
    assert informe["temporales_borrados"] == 1, informe
    assert temporal.exists(), "el dry-run borró de verdad"


def test_el_patron_es_exacto():
    """La forma es la prueba de propiedad: si se relaja, la prueba se pierde."""
    assert PATRON_TEMPORAL.match(".tmp.1234.a1b2c3d4")
    assert not PATRON_TEMPORAL.match(".tmp.1234.A1B2C3D4")  # hex en minúscula
    assert not PATRON_TEMPORAL.match(".tmp.abc.a1b2c3d4")
    assert not PATRON_TEMPORAL.match(".tmp.1234.a1b2c3d")     # longitud
    assert not PATRON_TEMPORAL.match("tmp.1234.a1b2c3d4")

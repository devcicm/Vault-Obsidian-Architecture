"""La D de ACID: declarada como decisión, no dejada como omisión.

`atomic_write_text` da **atomicidad** (temp + `os.replace`: nadie lee la nota a
medias) y `file_lock` da **aislamiento**. La **durabilidad** era la que faltaba:
cero `fsync` en todo el repo, así que entre el `replace` y el volcado real del
sistema de ficheros hay una ventana en la que un corte deja la nota truncada.

La decisión es no pagarla por defecto —el contenido de un vault es reconstruible,
y hay tools que escriben cientos de ficheros por pasada— y ofrecerla con
`VAULT_FSYNC=1`. Lo que estos tests fijan no es «se hace fsync», es que **la
elección sea una elección**: que exista la palanca, que el defecto sea el
documentado, y que activarla no cambie lo que se escribe.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import vault_io  # noqa: E402


@pytest.fixture(autouse=True)
def _sin_fsync_heredado(monkeypatch):
    """Ningún test hereda la palanca del entorno del que corre la suite."""
    monkeypatch.delenv("VAULT_FSYNC", raising=False)


def test_por_defecto_no_se_sincroniza(tmp_path, monkeypatch):
    """El defecto es el barato, y es el que la docstring declara."""
    llamadas = []
    monkeypatch.setattr(os, "fsync", lambda fd: llamadas.append(fd))
    vault_io.atomic_write_text(tmp_path / "n.md", "hola\n")
    assert llamadas == []


def test_con_la_palanca_se_sincroniza_el_temporal(tmp_path, monkeypatch):
    llamadas = []
    monkeypatch.setenv("VAULT_FSYNC", "1")
    monkeypatch.setattr(os, "fsync", lambda fd: llamadas.append(fd))
    vault_io.atomic_write_text(tmp_path / "n.md", "hola\n")
    assert llamadas, "VAULT_FSYNC=1 no llegó a sincronizar nada"


def test_solo_el_valor_exacto_activa(tmp_path, monkeypatch):
    """`VAULT_FSYNC=0` es alguien apagándolo, no encendiéndolo por estar puesto."""
    llamadas = []
    monkeypatch.setenv("VAULT_FSYNC", "0")
    monkeypatch.setattr(os, "fsync", lambda fd: llamadas.append(fd))
    vault_io.atomic_write_text(tmp_path / "n.md", "hola\n")
    assert llamadas == []


def test_sincronizar_no_cambia_lo_escrito(tmp_path, monkeypatch):
    """La palanca es de durabilidad, no de contenido: mismo byte a byte.

    Los nombres no son `sin.md` / `con.md` por casualidad: el primer intento usó
    `con.md` y el test se colgaba para siempre. `CON` es un **nombre de
    dispositivo reservado** de Windows, así que `con.md` no era un fichero —
    `exists()` daba `True`, `st_mode` era `S_IFCHR` y leerlo bloqueaba esperando
    entrada de consola. De ahí sale `_rechazar_nombre_reservado`.
    """
    contenido = "---\ntype: knowledge\n---\n\nCuerpo con acentos: ñ á →\n"
    vault_io.atomic_write_text(tmp_path / "plana.md", contenido)
    monkeypatch.setenv("VAULT_FSYNC", "1")
    vault_io.atomic_write_text(tmp_path / "durable.md", contenido)
    assert (tmp_path / "durable.md").read_bytes() == (
        tmp_path / "plana.md"
    ).read_bytes()


def test_el_json_hereda_la_palanca(tmp_path, monkeypatch):
    """`atomic_write_json` delega, así que no puede tener otra durabilidad.

    Los artefactos que más duelen al perderse —`search-index.json`, el registro
    de tags, el grafo— son JSON: si la palanca no les llegara, cubriría justo lo
    reconstruible y dejaría fuera lo caro (AP-05: dos criterios para lo mismo).
    """
    llamadas = []
    monkeypatch.setenv("VAULT_FSYNC", "1")
    monkeypatch.setattr(os, "fsync", lambda fd: llamadas.append(fd))
    vault_io.atomic_write_json(tmp_path / "d.json", {"a": 1})
    assert llamadas
    assert json.loads((tmp_path / "d.json").read_text(encoding="utf-8")) == {"a": 1}


def test_no_deja_temporales_al_terminar(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_FSYNC", "1")
    vault_io.atomic_write_text(tmp_path / "n.md", "hola\n")
    assert not list(tmp_path.glob(".tmp.*"))


@pytest.mark.parametrize("nombre", ["con.md", "CON.md", "Aux.md", "nul.md", "com1.md"])
def test_los_nombres_de_dispositivo_se_bloquean(tmp_path, nombre):
    """No es un fichero: `exists()` miente y leerlo cuelga al proceso.

    Se prefiere el error a la escritura porque el fallo alternativo no es
    perder la nota — es que quien la lea se quede esperando entrada de consola
    para siempre, sin traza ni excepción.
    """
    with pytest.raises(ValueError, match="reservado"):
        vault_io.atomic_write_text(tmp_path / nombre, "hola\n")


@pytest.mark.parametrize("nombre", ["console.md", "contrato.md", "auxiliar.md", "com.md"])
def test_los_nombres_que_solo_empiezan_igual_pasan(tmp_path, nombre):
    """Prohibir el prefijo en vez del nombre apagaría media sección."""
    vault_io.atomic_write_text(tmp_path / nombre, "hola\n")
    assert (tmp_path / nombre).read_text(encoding="utf-8") == "hola\n"


def test_la_decision_esta_escrita_donde_se_toma():
    """Una omisión y una decisión se ven igual en el código si nadie la escribe.

    Este test es la parte que evita que dentro de seis meses alguien «arregle»
    la falta de fsync sin saber que ya se decidió, o al revés: que la lea como
    olvido y la deje.
    """
    doc = vault_io._fsync_si_procede.__doc__ or ""
    assert "VAULT_FSYNC" in doc
    assert "atomicidad" in doc and "durabilidad" in doc

"""AP-20 — una lista de viñetas vacías no es contenido.

`vault_write` rechaza la nota cuyo texto pasa AP-11 con prosa suficiente pero
cuya lista es casi toda viñetas vacías: la forma de la nota promete un
contenido que no tiene. Se mide lo que queda en disco, no solo el envelope.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402
import vault_write  # noqa: E402

PROSA = ("La cola reintenta tres veces antes de descartar el mensaje.\n"
         "Cada intento queda registrado con su marca temporal.\n"
         "Los errores llegan al canal de observabilidad del equipo.\n")


@pytest.fixture
def vault_vacio(tmp_path):
    previo = vault_io.get_vault_root()
    (tmp_path / "07_Knowledge").mkdir()
    vault_io.set_vault_root(tmp_path)
    yield tmp_path
    vault_io.set_vault_root(previo)


def _escribir(lista):
    return vault_write.vault_write(folder="07_Knowledge", title="Reintentos",
                                   content=PROSA + "\n" + lista, tags=["demo"],
                                   meta={"agent": "probe"})


def _notas(vault):
    return [p.name for p in (vault / "07_Knowledge").glob("*.md") if p.name != "index.md"]


def test_ap20_una_lista_casi_vacia_se_rechaza_sin_escribir(vault_vacio):
    r = _escribir("- \n- [ ]\n-   \n- Primer reintento a los cinco segundos\n")
    assert r["ok"] is False and r["norm_code"] == "AP-20", r
    assert r["error_code"] == "content_empty_list"
    assert _notas(vault_vacio) == []


def test_ap20_una_lista_llena_pasa(vault_vacio):
    r = _escribir("- Primer reintento a los cinco segundos\n"
                  "- Segundo reintento al minuto\n- \n")
    assert r["ok"] is True, r
    assert _notas(vault_vacio) == ["reintentos.md"], "AP-20 no frena una lista con contenido"


def test_ap20_una_vineta_vacia_no_se_traga_la_linea_siguiente():
    r"""Hasta v40.35 el patrón era `^\s*[-*]\s*(.*)` en tres sitios: el `\s*`
    cruzaba el salto de línea y `- ` seguido de `- [ ]` daba una sola viñeta
    llena («- [ ]»). Tampoco son viñetas una negrita ni una regla horizontal."""
    from vault_norms_catalog import VINETA_VACIA, vinetas_de_lista

    assert vinetas_de_lista("- \n- [ ]\n-   \n- algo\n") == ["", "[ ]", "", "algo"]
    assert vinetas_de_lista("**Ruta:** x\n---\n*énfasis*\n") == []
    assert sum(v in VINETA_VACIA for v in vinetas_de_lista("- \n- [ ]\n- algo")) == 2, "AP-20"

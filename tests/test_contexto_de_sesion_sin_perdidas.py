"""El estado de sesión del vault no pierde actualizaciones entre instancias.

La nota de causa raíz «traceability-session-lifecycle-debt» (2026-11-07) y la
re-auditoría del vault (2026-11-09) reproducían lo mismo: dos instancias de
`VaultContext` creadas antes de que ninguna escribiera, cada una anotando un
cambio, dejaban en el fichero **solo la última** — el snapshot propio se
escribía entero, sin lock ni fusión.

La corrección (misma propuesta del paper): lock del fichero, **recargar
dentro del lock**, fusionar el evento y escribir atómico. Este test fija el
repro y la corrección.
"""

import json

import pytest

from vault_io import set_vault_root
from vault_mcp_context import VaultContext


@pytest.fixture
def raiz(tmp_path):
    previa = set_vault_root(tmp_path)
    yield tmp_path
    set_vault_root(previa)


def test_dos_instancias_obsoletas_no_se_pisan(raiz):
    """El repro del 2026-11-07: A y B leen a la vez; cada uno anota lo suyo.

    Antes: el fichero acababa con solo el cambio de B. Ahora los dos cambios
    quedan fusionados.
    """
    a = VaultContext(persist=True)
    b = VaultContext(persist=True)

    a.add_session_change("a.md", "write")
    b.add_session_change("b.md", "write")

    en_disco = json.loads(
        (raiz / "00_System" / "vault_context.json").read_text(encoding="utf-8"))
    rutas = [c["path"] for c in en_disco["session"]["changes"]]
    assert "a.md" in rutas and "b.md" in rutas, rutas
    # La vista en memoria de A queda obsoleta por diseño: quien escribió
    # después no puede haberla refrescado. Lo que garantiza el arreglo es el
    # FICHERO, que es lo que lee la siguiente sesión.


def test_dos_instancias_marcan_campos_distintos_y_ninguno_se_pierde(raiz):
    """Fusionar por campo: lo que A fija no borra lo que B fija en otro campo."""
    a = VaultContext(persist=True)
    b = VaultContext(persist=True)

    a.set_health_score(90)
    b.set_next_actions(["revisar el indice"])

    en_disco = json.loads(
        (raiz / "00_System" / "vault_context.json").read_text(encoding="utf-8"))
    assert en_disco["health_score"] == 90, en_disco
    assert en_disco["next_actions"] == ["revisar el indice"], en_disco


def test_la_lectura_toleran_un_fichero_corrupto(raiz):
    """Un fichero ilegible vuelve al default y una escritura posterior lo
    repara; no se propaga el estado roto."""
    (raiz / "00_System").mkdir(parents=True, exist_ok=True)
    (raiz / "00_System" / "vault_context.json").write_text(
        "{corrupto", encoding="utf-8")

    contexto = VaultContext(persist=True)
    contexto.add_session_change("c.md", "write")

    en_disco = json.loads(
        (raiz / "00_System" / "vault_context.json").read_text(encoding="utf-8"))
    rutas = [c["path"] for c in en_disco["session"]["changes"]]
    assert rutas == ["c.md"], rutas

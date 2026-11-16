"""Karpathy's schema layer (L3): the client adapter is derived from registries.

`vault_preferences --adapters` renders the AGENTS.md/CLAUDE.md a client loads.
The folder map, the naming rule and the line budget come from their owners
(`vault_registry.SECTION_DOCUMENTACION`, CN-01 in the norm catalog), never
from a list typed in the renderer. It stays delivery, not enforcement, and it
never overwrites a user's file without `--force`.
"""

from pathlib import Path

import pytest

import vault_io
import vault_preferences


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge", "17_Preferences"):
        (raiz / seccion).mkdir(parents=True)
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


def _adaptador(tmp_path) -> str:
    destino = tmp_path / "proyecto"
    destino.mkdir()
    res = vault_preferences.vault_preferences_adapters(str(destino))
    assert res.get("ok"), res
    return (destino / "AGENTS.md").read_text(encoding="utf-8")


def test_el_adaptador_publica_el_mapa_de_carpetas_del_registro(vault, tmp_path):
    from vault_registry import SECTION_DOCUMENTACION

    texto = _adaptador(tmp_path)

    assert "## Mapa de carpetas" in texto
    for carpeta, (clase, motivo) in SECTION_DOCUMENTACION.items():
        assert f"`{carpeta}` — {clase}: {motivo}" in texto, carpeta


def test_el_adaptador_publica_la_regla_de_nombres_cn01(vault, tmp_path):
    import vault_norms_catalog

    cn01 = vault_norms_catalog.norma_por_codigo("CN-01")
    texto = _adaptador(tmp_path)

    assert "## Nombres de fichero (CN-01)" in texto
    assert cn01["name"] in texto and cn01["prevention"] in texto


def test_el_adaptador_publica_los_pasos_del_protocolo_de_sesion(vault, tmp_path):
    from vault.kernel.protocolo_de_sesion import PROTOCOLO_DE_SESION

    texto = _adaptador(tmp_path)

    assert "## Protocolo de sesión" in texto
    for momento in PROTOCOLO_DE_SESION.values():
        assert f"**{momento['titulo']}**" in texto
        for paso in momento["pasos"]:
            assert f"`{paso['tool']}" in texto, paso["tool"]


def test_el_protocolo_vive_en_el_kernel_y_meta_toolkit_es_su_alias():
    import vault.kernel.protocolo_de_sesion as dueno
    import vault.meta_toolkit.protocolo_de_sesion as alias

    assert alias is dueno
    assert alias.PROTOCOLO_DE_SESION is dueno.PROTOCOLO_DE_SESION


def test_el_adaptador_respeta_su_presupuesto_de_lineas(vault, tmp_path):
    texto = _adaptador(tmp_path)

    assert len(texto.splitlines()) <= vault_preferences.LINEAS_MAXIMAS_ADAPTER
    assert f"{vault_preferences.LINEAS_MAXIMAS_ADAPTER} líneas" in texto


def test_el_adaptador_sigue_sin_pisar_un_fichero_del_usuario(vault, tmp_path):
    destino = tmp_path / "proyecto"
    destino.mkdir()
    (destino / "CLAUDE.md").write_bytes(b"propio\r\n")

    res = vault_preferences.vault_preferences_adapters(str(destino))

    assert res["ok"] and (destino / "CLAUDE.md").read_bytes() == b"propio\r\n"
    assert "Mapa de carpetas" in (destino / "AGENTS.md").read_text(encoding="utf-8")

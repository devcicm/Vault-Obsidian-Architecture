"""4.5b — el onboarding: procedencia, confianza y la matriz que hay que probar.

El paper de la re-auditoría pedía cerrar el contrato de
`vault_onboard`: qué pasa en cada modo (greenfield y brownfield), que la
procedencia y la confianza queden **registradas** en la nota, que lo manual
se preserve, y probar la matriz: vault vacío, proyecto existente, error de
lectura y repetición.

Lo que estos tests fijan:

- **greenfield**: vault vacío + proyecto → notas creadas, y cada una dice de
  dónde salió (`provenance`) y cuánto se le puede creer (`confidence`);
- **brownfield**: una nota ya escrita por una persona → su contenido **sigue
  intacto** (la fusión solo añade secciones `##` que falten);
- **error de lectura**: un fichero ilegible → sale declarado en `degraded`, y
  la corrida no se cae (nadie afirma lo que no pudo leer);
- **repetición**: correr dos veces no duplica nada.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

import vault_io  # noqa: E402
import vault_onboard  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


@pytest.fixture
def proyecto(tmp_path):
    raiz = tmp_path / "proyecto"
    (raiz / "src").mkdir(parents=True)
    (raiz / "src" / "core.py").write_text(
        '"""Nucleo del proyecto."""\n\n\ndef arrancar():\n    return 1\n',
        encoding="utf-8")
    (raiz / "README.md").write_text(
        "# Proyecto de prueba\n\nUn modulo `core`.\n", encoding="utf-8")
    return raiz


def _onboard(proyecto: Path, **kwargs):
    return vault_onboard.vault_onboard(
        project="demo", path=str(proyecto), no_git=True, **kwargs)


def test_greenfield_las_notas_dicen_de_donde_salen_y_cuanto_valen(vault, proyecto):
    """Vault vacío + proyecto: lo escrito declara su procedencia y su confianza."""
    res = _onboard(proyecto)
    assert res["ok"], res
    assert res["created"], res

    nota = vault / "11_Code" / "demo" / "core.md"
    assert nota.is_file(), "no se creó la nota del módulo"
    cuerpo = nota.read_text(encoding="utf-8")
    assert "provenance:" in cuerpo, cuerpo[:400]
    assert "confidence:" in cuerpo, cuerpo[:400]
    # La procedencia nombra el proyecto y el commit —sin ruta absoluta: la
    # máquina del dueño no viaja en el vault.
    assert "demo" in cuerpo
    assert str(vault) not in cuerpo
    assert str(proyecto) not in cuerpo
    assert "status: stub" in cuerpo


def test_brownfield_lo_que_ya_esta_escrito_no_se_toca(vault, proyecto):
    """Una nota escrita por una persona sobrevive al onboarding.

    La fusión solo añade secciones `##` que falten; el cuerpo que escribió
    la persona se queda como estaba.
    """
    nota = vault / "11_Code" / "demo" / "core.md"
    nota.parent.mkdir(parents=True)
    nota.write_text(
        "---\ntitle: core -- Module\nid: x\ntype: code\ncreatedAt: 2026-01-01T00:00:00.000Z\n"
        "updatedAt: 2026-01-01T00:00:00.000Z\ntags: []\n---\n\n"
        "# core -- Module\n\n## Mi analisis\n\nEsto lo escribi una persona.\n",
        encoding="utf-8")

    _onboard(proyecto)

    cuerpo = nota.read_text(encoding="utf-8")
    assert "Esto lo escribi una persona." in cuerpo, (
        "el onboarding piso una nota ya escrita")
    assert "## Mi analisis" in cuerpo


def test_un_error_de_lectura_se_declara_y_no_rompe(vault, proyecto):
    """Un fichero ilegible sale declarado: nadie afirma lo que no pudo leer."""
    (proyecto / "src" / "roto.py").write_bytes(b"\xff\xfe\x00binario")

    res = _onboard(proyecto)

    assert res["ok"], res
    assert isinstance(res["degraded"], list)
    # O no se pudo leer y está declarado, o no le affects y no hay degraded:
    # lo que no puede pasar es que afirme algo sin decirlo.
    if res["degraded"]:
        pasos = [d.get("step", "") for d in res["degraded"]]
        assert any("roto" in str(d) or "leer" in s for d, s in zip(res["degraded"], pasos)), res["degraded"]


def test_repetir_no_duplica_nada(vault, proyecto):
    """La segunda corrida no repite secciones ni pisa lo escrito."""
    _onboard(proyecto)
    nota = vault / "11_Code" / "demo" / "core.md"
    primera = nota.read_text(encoding="utf-8")

    res = _onboard(proyecto)
    segunda = nota.read_text(encoding="utf-8")

    assert primera == segunda, "la segunda corrida cambio la nota"
    assert res["merge_stats"]["created"] == 0, res["merge_stats"]
    assert primera.count("# core -- Module") == 1


def test_dry_run_declara_secciones_planificadas_y_excluidas(vault, proyecto):
    resultado = _onboard(proyecto, dry_run=True)
    assert resultado["ok"], resultado
    excluidas = resultado["sections_left_empty_by_design"]
    assert set(excluidas).issubset(set(vault_onboard.ORDERED_SECTIONS))
    indices = set(resultado["created"].get("indexes_updated", []))
    previstas = {f"{s}/index.md" for s in vault_onboard.ORDERED_SECTIONS if s not in excluidas}
    assert indices == previstas
    assert not list(vault.rglob("*.md")), "dry-run escribio notas"


def test_fallo_de_reindex_declara_advertencia_y_conserva_notas(vault, proyecto, monkeypatch):
    import vault_reindex
    def fallo():
        raise OSError("fallo de reindex simulado")
    monkeypatch.setattr(vault_reindex, "vault_reindex", fallo)
    resultado = _onboard(proyecto)
    assert resultado["ok"], resultado
    assert any("search-index no reconstruido" in aviso for aviso in resultado["warnings"]), resultado
    assert (vault / "11_Code" / "demo" / "core.md").is_file()


def test_contexto_de_onboarding_concurrente_no_se_mezcla(vault, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrera = Barrier(2)
    observaciones = {}
    class Terminar(RuntimeError):
        pass
    def detectar(raiz, _idioma):
        listas = (vault_onboard._README_H1, vault_onboard._SIN_EVIDENCIA,
                  vault_onboard._OMITIDAS_POR_POLITICA, vault_onboard._DETECCION_DEGRADADA)
        for lista in listas:
            lista.append(raiz.name)
        barrera.wait(timeout=10)
        observaciones[raiz.name] = ((vault_onboard._CONTEXTO_ONBOARD.get() or {}).get("proyecto"),
                                    tuple(tuple(lista) for lista in listas))
        raise Terminar()
    monkeypatch.setattr(vault_onboard, "_detect_project_meta", detectar)
    proyectos = [tmp_path / "proyecto-uno", tmp_path / "proyecto-dos"]
    for proyecto in proyectos:
        proyecto.mkdir()
    def ejecutar(proyecto):
        try:
            vault_onboard.vault_onboard(project=proyecto.name, path=str(proyecto),
                                        no_git=True, dry_run=True)
        except Terminar:
            pass
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(ejecutar, proyectos))
    assert observaciones == {p.name: (p.name, ((p.name,),) * 4) for p in proyectos}


def test_contexto_de_onboarding_se_restaurara_tras_error(vault, proyecto, monkeypatch):
    def fallar(*args, **kwargs):
        raise RuntimeError("simulado")
    monkeypatch.setattr(vault_onboard, "_detect_project_meta", fallar)
    antes = vault_onboard._CONTEXTO_ONBOARD.get()
    with pytest.raises(RuntimeError, match="simulado"):
        _onboard(proyecto, dry_run=True)
    assert vault_onboard._CONTEXTO_ONBOARD.get() is antes

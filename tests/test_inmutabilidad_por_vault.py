"""4.6 — inmutabilidad por vault: la mecánica existe, la política la declara
el dueño.

El paper de la re-auditoría (`per-vault-immutability-and-derived-index-policy-
2026-11-07`) pide separar las notas históricas de los índices derivados,
resolver la política **por identidad de vault**, y probar las prohibiciones y
las excepciones autorizadas.

Lo que se entrega aquí:

- **La política es del vault**, no del toolkit: `00_System/inmutable.json`
  declara qué secciones son histórico inmutable. El fichero ausente o vacío
  significa que nada es inmutable: la mecánica existe **sin cambiarle el
  comportamiento a nadie**.
- **Modificar** una nota de una sección declarada es un error con código
  (`IMMUTABLE_NOTE`); **crear** una nota nueva ahí sí se permite: el
  histórico crece, no se reescribe.
- Un fichero de política ilegible **no** convierte el vault en inmutable
  entero: ante la duda no se bloquea a nadie.

Lo que NO se hace aquí (y por qué): elegir las secciones. El registro del
estándar ya clasifica ocho secciones como `registro` —lo que ocurrió,
anotado cuando ocurrió—, y esa es la lista que el dueño puede copiar a su
declaración. La decisión de qué es histórico en **su** vault es suya.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

import vault_io  # noqa: E402
import vault_write  # noqa: E402
from vault.kernel.errores import ERROR_CATALOG  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "19_Audits", "07_Knowledge"):
        (raiz / seccion).mkdir(parents=True)
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


def _declarar(vault: Path, secciones):
    (vault / "00_System" / "inmutable.json").write_text(
        json.dumps({"secciones": secciones}), encoding="utf-8")


#: La valla de contenido (AP-11) exige ≥3 lineas y ≥10 palabras reales: un
#: texto de una linea no llega al camino que estos tests quieren probar.
LARGO = (
    "Linea uno con contenido suficiente para pasar la valla de contenido.\n"
    "Linea dos que anade contexto y completa el relato de la nota.\n"
    "Linea tres que cierra con la idea final del asunto tratado aqui.\n"
)


def test_sin_declaracion_nada_es_inmutable(vault):
    """El comportamiento de siempre: la mecánica no cambia a nadie."""
    assert vault_io.inmutables_declaradas(vault) == []
    nota = vault / "19_Audits" / "nota.md"
    nota.write_text("x", encoding="utf-8")
    assert vault_io.nota_es_inmutable(nota, vault) is None


def test_una_seccion_declarada_no_se_reescribe(vault):
    """La prohibición: una nota histórica no se modifica."""
    _declarar(vault, ["19_Audits"])
    nota = vault / "19_Audits" / "nota.md"
    nota.write_text("---\ntitle: nota\n---\n\nContenido original.\n", encoding="utf-8")

    assert vault_io.nota_es_inmutable(nota, vault) == "19_Audits"

    res = vault_write.vault_write(
        folder="19_Audits", title="nota", tags=["prueba"], meta={"agent": "opencode"}, content=f"{LARGO}\nContenido nuevo.\n")
    assert res.get("ok") is False, res
    assert res.get("error_code") == "IMMUTABLE_NOTE", res
    # Y lo importante: el fichero no cambió.
    assert "Contenido original." in nota.read_text(encoding="utf-8")


def test_una_nota_nueva_si_se_puede_escribir(vault):
    """La excepción autorizada: el histórico **crece**."""
    _declarar(vault, ["19_Audits"])
    res = vault_write.vault_write(
        folder="19_Audits", title="sucesora", tags=["prueba"], meta={"agent": "opencode"}, content=f"{LARGO}\nUn hallazgo nuevo.\n")
    assert res.get("ok"), res
    assert (vault / "19_Audits" / "sucesora.md").is_file()


def test_una_seccion_no_declarada_se_puede_modificar(vault):
    """La valla es por sección, no global."""
    _declarar(vault, ["19_Audits"])
    res = vault_write.vault_write(
        folder="07_Knowledge", title="nota", tags=["prueba"], meta={"agent": "opencode"}, content=f"{LARGO}\nSe puede tocar.\n")
    assert res.get("ok"), res


def test_un_fichero_de_politica_ilegible_no_convierte_en_todo_inmutable(vault):
    """Ante la duda, no se bloquea a nadie."""
    (vault / "00_System" / "inmutable.json").write_text("{esto no es json",
                                                        encoding="utf-8")
    assert vault_io.inmutables_declaradas(vault) == []
    res = vault_write.vault_write(
        folder="19_Audits", title="nota", tags=["prueba"], meta={"agent": "opencode"}, content=f"{LARGO}\nSe puede tocar.\n")
    assert res.get("ok"), res


def test_el_codigo_de_error_esta_en_el_catalogo():
    """Un error fuera del catálogo no lo puede leer un consumidor (AP-52)."""
    assert "IMMUTABLE_NOTE" in ERROR_CATALOG
    entrada = ERROR_CATALOG["IMMUTABLE_NOTE"]
    assert entrada["category"] == "governance"
    assert entrada["recovery"]["action"] in (
        "auto", "fix_input", "manual", "retry", "run_tool")

def test_un_vault_nace_sin_politica_declarada(tmp_path):
    """Un vault nuevo **no** declara la política de inmutabilidad.

    Un vault vacío no tiene nada que proteger: si `vault_init` declara
    las secciones como inmutables antes de que el onboarding las pueble,
    cada nota que el onboarding escribe recibe el veto (medido el
    2026-11-09: 45 fallos y 24 errores de preparación). La política la
    declara el dueño **después** de poblar el vault, cuando ya sabe qué
    secciones tienen contenido que vale la pena proteger.
    """
    import vault_init
    import vault_io

    raiz = tmp_path / "nuevo"
    raiz.mkdir()
    previa = vault_io.set_vault_root(raiz)
    try:
        vault_init.vault_init(run_audit=False)
    finally:
        vault_io.set_vault_root(previa)

    politica = raiz / "00_System" / "inmutable.json"
    assert not politica.is_file(), (
        "el vault nuevo declaró la política de inmutabilidad: eso impide "
        "que el onboarding pueble las secciones")
    # Y sin la política, todo es escribible.
    assert vault_io.inmutables_declaradas(raiz) == []


def test_el_init_respeta_la_politica_que_ya_tenia(tmp_path):
    """Si el dueño ya declaró su política, el init no la toca."""
    import vault_init

    raiz = tmp_path / "con-politica"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "00_System" / "inmutable.json").write_text(
        json.dumps({"secciones": ["19_Audits"]}), encoding="utf-8")
    previa = vault_io.set_vault_root(raiz)
    try:
        vault_init.vault_init(run_audit=False)
    finally:
        vault_io.set_vault_root(previa)

    declaradas = json.loads(
        (raiz / "00_System" / "inmutable.json").read_text(encoding="utf-8"))["secciones"]
    assert declaradas == ["19_Audits"], declaradas

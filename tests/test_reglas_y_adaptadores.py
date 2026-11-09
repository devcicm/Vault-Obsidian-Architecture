"""La política del vault: se persiste, se entrega y se aplica — por separado.

Propuestas `persistent-custom-rules-and-agent-integration` y
`multi-provider-vault-policy-adapters`. La distinción que fijan estos tests:

- **Persistencia:** la regla vive en el vault (`00_System/inmutable.json`,
  `00_System/reglas.json`, `17_Preferences/`).
- **Entrega:** un adaptador la lleva al fichero que cada cliente lee
  (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `copilot-instructions.md`).
- **Enforcing:** la frontera de mutación (`vault_write` / `vault_delete`).
  Un prompt no es un permiso, y un agente que no cargue el adaptador sigue
  sujeto a la misma política.

Y lo que se prueba aquí: que la regla **se aplica donde se muta** (borrado),
que un fichero ilegible **no** bloquea a nadie, y que el adaptador dice lo
que es y no se pisa sin permiso.
"""

from __future__ import annotations

import json

import pytest

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

import vault_delete
import vault_io
import vault_preferences
from vault.kernel.errores import ERROR_CATALOG


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "19_Audits", "07_Knowledge"):
        (raiz / seccion).mkdir(parents=True)
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


def _nota(vault, seccion, nombre):
    ruta = vault / seccion / nombre
    ruta.write_text(
        f"---\ntitle: {nombre}\n---\n\nContenido de la nota de prueba.\n",
        encoding="utf-8")
    return ruta


def _reglas(vault, datos):
    (vault / "00_System" / "reglas.json").write_text(json.dumps(datos),
                                                     encoding="utf-8")


def test_sin_reglas_no_se_prohibe_nada(vault):
    """Ante la duda no se bloquea a nadie."""
    nota = _nota(vault, "19_Audits", "nota.md")
    assert vault_io.reglas_declaradas(vault) == {"inmutable": [], "no_borrar": []}
    assert vault_io.nota_no_se_borra(nota, vault) is None


def test_no_borrar_se_aplica_en_la_frontera_de_mutacion(vault):
    """Persistir la regla no basta: se aplica donde se borra."""
    _reglas(vault, {"no_borrar": ["19_Audits"]})
    nota = _nota(vault, "19_Audits", "nota.md")

    res = vault_delete.vault_delete(
        "19_Audits/nota.md", "prueba de la valla", agent="opencode")

    assert res.get("ok") is False, res
    assert res.get("error_code") == "DELETE_FORBIDDEN", res
    assert nota.is_file(), "la nota se borro con la politica en contra"


def test_una_seccion_no_declarada_se_puede_borrar(vault):
    """La valla es por seccion, no global."""
    _reglas(vault, {"no_borrar": ["19_Audits"]})
    nota = _nota(vault, "07_Knowledge", "libre.md")

    res = vault_delete.vault_delete(
        "07_Knowledge/libre.md", "prueba de la valla", agent="opencode",
        trash_only=True)

    assert res.get("ok"), res
    assert not nota.exists(), "la nota no se movio a cuarentena"


def test_un_fichero_de_reglas_ilegible_no_prohibe_nada(vault):
    """Ante la duda, no se bloquea; y no se inventa una regla."""
    (vault / "00_System" / "reglas.json").write_text("{roto", encoding="utf-8")
    nota = _nota(vault, "19_Audits", "nota.md")
    assert vault_io.nota_no_se_borra(nota, vault) is None


def test_las_reglas_leen_tambien_la_politica_ya_publicada(vault):
    """`inmutable.json` no se mueve: se suma a las reglas."""
    (vault / "00_System" / "inmutable.json").write_text(
        json.dumps({"secciones": ["18_Bugs"]}), encoding="utf-8")
    _reglas(vault, {"no_borrar": ["19_Audits"]})
    declaradas = vault_io.reglas_declaradas(vault)
    assert "18_Bugs" in declaradas["inmutable"]
    assert "19_Audits" in declaradas["no_borrar"]


def test_el_codigo_de_error_esta_en_el_catalogo():
    assert "DELETE_FORBIDDEN" in ERROR_CATALOG
    assert ERROR_CATALOG["DELETE_FORBIDDEN"]["category"] == "governance"


def test_el_adaptador_dice_que_es_entrega_y_no_pisa(vault, tmp_path):
    """El fichero que lee un cliente no es la frontera de permisos."""
    destino = tmp_path / "proyecto"
    destino.mkdir()
    (destino / "AGENTS.md").write_text("mio", encoding="utf-8")

    res = vault_preferences.vault_preferences_adapters(str(destino))

    assert res.get("ok"), res
    estados = {a["adapter"]: a["estado"] for a in res["adapters"]}
    assert estados["AGENTS.md"] == "existente (no se toca)"
    assert (destino / "AGENTS.md").read_text(encoding="utf-8") == "mio"
    # Los demás sí se escriben, y dicen lo que son.
    claude = (destino / "CLAUDE.md").read_text(encoding="utf-8")
    assert "entrega" in claude and "no enforcing" in claude.lower()
    assert "frontera de mutación" in claude
    assert "Enforcing" not in claude or "no enforcing" in claude.lower()


def test_el_adaptador_publica_las_reglas_del_vault(vault, tmp_path):
    _reglas(vault, {"no_borrar": ["19_Audits"]})
    destino = tmp_path / "proyecto2"
    res = vault_preferences.vault_preferences_adapters(str(destino), force=True)
    assert res.get("ok"), res
    cuerpo = (destino / "GEMINI.md").read_text(encoding="utf-8")
    assert "19_Audits" in cuerpo, cuerpo[:400]
    assert "no se borra" in cuerpo

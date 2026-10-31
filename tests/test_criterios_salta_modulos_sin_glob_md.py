"""A-13 — `vault_criterios.medir` mira también el recorrido de notas por sufijo.

La precondición del literal (`medir`, «solo puede incumplirse donde se
clasifican notas») es el alcance real de la puerta AP-57. Hasta v41.25 dejaba un
falso negativo: el mismo criterio copiado —el fence a mano en vez de
`vault_lib.strip_code_blocks`— se veía en un módulo que recorre notas con
`glob("*.md")` y no en uno que las recorre con `p.suffix == ".md"`. Medido el
2026-10-30: 36 de 167 módulos entraban en la medida; con
`_recorre_notas_por_sufijo` entran 40 y no estrenan ninguna copia.

La entrada `criterios_salta_modulos_sin_glob_md` de
`vault_blueprint.DEUDA_DECLARADA` queda `saldada` y se sostiene en este test.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import vault_criterios as C  # noqa: E402

_COPIA = '''
from pathlib import Path


def enlaces(raiz):
    for nota in {recorrido}:
        partes = nota.read_text(encoding="utf-8").split("```")
        yield from partes[::2]
'''

#: Escribe un fence y compone un nombre `.md`, pero no clasifica notas: es la
#: forma de `vault_subgraph`, que admitir por el literal suelto daba por copia.
_ESCRITOR = '''
def diagrama(seed, nodos):
    if f"{seed}.md" in nodos:
        return ["```mermaid", "graph LR", "```"]
    return []
'''


def _medir(monkeypatch, tmp_path, fuente):
    modulo = tmp_path / "vault_copia_del_fence.py"
    modulo.write_text(fuente, encoding="utf-8")
    monkeypatch.setattr(C, "_modulos", lambda: [modulo])
    monkeypatch.setattr(C.vault_grafo_import, "fuente_de", lambda nombre: modulo)
    hallazgos = C.medir()
    return hallazgos, dict(C._ALCANCE)


def test_la_copia_se_ve_en_un_modulo_que_nombra_el_glob(monkeypatch, tmp_path):
    """El control: con `glob("*.md")` el detector ve la copia del fence."""
    fuente = _COPIA.format(recorrido='Path(raiz).rglob("*.md")')
    hallazgos, alcance = _medir(monkeypatch, tmp_path, fuente)
    assert alcance["medidos"] == ["vault_copia_del_fence"]
    assert [h["criterio"] for h in hallazgos] == ["que_es_codigo_y_no_enlace"]


@pytest.mark.parametrize("recorrido", [
    '(p for p in Path(raiz).rglob("*") if p.suffix == ".md")',
    '(p for p in Path(raiz).rglob("*") if p.name.endswith(".md"))',
    '(p for p in Path(raiz).rglob("*") if p.suffix in (".md", ".markdown"))',
])
def test_la_copia_se_ve_recorriendo_notas_por_sufijo(monkeypatch, tmp_path, recorrido):
    """La misma copia, recorriendo notas por sufijo: AP-57 ya la ve."""
    hallazgos, alcance = _medir(monkeypatch, tmp_path, _COPIA.format(recorrido=recorrido))
    assert alcance["medidos"] == ["vault_copia_del_fence"]
    assert [h["criterio"] for h in hallazgos] == ["que_es_codigo_y_no_enlace"]


def test_el_literal_md_suelto_no_mete_al_modulo_en_la_medida(monkeypatch, tmp_path):
    """Componer `f"{x}.md"` no es clasificar notas: se sigue saltando."""
    hallazgos, alcance = _medir(monkeypatch, tmp_path, _ESCRITOR)
    assert alcance["saltados"] == ["vault_copia_del_fence"]
    assert not hallazgos

"""A-13 — límite declarado: `vault_criterios.medir` no mira un módulo sin `"*.md"`.

La precondición del literal (`medir`, «solo puede incumplirse donde se
clasifican notas») es el alcance real de la puerta AP-57, y deja un falso
negativo que este test fija: el mismo criterio copiado —el fence a mano en vez
de `vault_lib.strip_code_blocks`— se ve en un módulo que recorre notas con
`glob("*.md")` y no en uno que las recorre con `.endswith(".md")`. Medido el
2026-10-30: 36 de 167 módulos entran en la medida.

Falla el día que el detector vea el segundo caso, para que
`vault_blueprint.DEUDA_DECLARADA` pase la entrada a `saldada`.
"""

import sys
from pathlib import Path

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


def _medir(monkeypatch, tmp_path, recorrido):
    modulo = tmp_path / "vault_copia_del_fence.py"
    modulo.write_text(_COPIA.format(recorrido=recorrido), encoding="utf-8")
    monkeypatch.setattr(C, "_modulos", lambda: [modulo])
    monkeypatch.setattr(C.vault_grafo_import, "fuente_de", lambda nombre: modulo)
    hallazgos = C.medir()
    return hallazgos, dict(C._ALCANCE)


def test_la_copia_se_ve_en_un_modulo_que_nombra_el_glob(monkeypatch, tmp_path):
    """El control: con `glob("*.md")` el detector ve la copia del fence."""
    hallazgos, alcance = _medir(monkeypatch, tmp_path, 'Path(raiz).rglob("*.md")')
    assert alcance["medidos"] == ["vault_copia_del_fence"]
    assert [h["criterio"] for h in hallazgos] == ["que_es_codigo_y_no_enlace"]


def test_limite_declarado_criterios_salta_modulos_sin_glob_md(monkeypatch, tmp_path):
    """La misma copia, recorriendo notas por sufijo: nadie la mira."""
    recorrido = '(p for p in Path(raiz).rglob("*") if p.suffix == ".md")'
    hallazgos, alcance = _medir(monkeypatch, tmp_path, recorrido)
    assert alcance["saltados"] == ["vault_copia_del_fence"]
    assert not hallazgos, "ya se ve la copia: salda la deuda A-13 en DEUDA_DECLARADA"

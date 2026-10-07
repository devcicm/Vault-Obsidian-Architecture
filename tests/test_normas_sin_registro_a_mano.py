"""Las secciones de norma del manifiesto no copian el registro que la norma cita.

Medido el 2026-10-07: la sección de CN-02 decía «NO duplicar esta lista» justo
debajo de la lista, con «Actualmente 19:» cuando `vault_registry` ya tenía 23.
`vault_doc_counts` no la vio porque «Actualmente N:» no es ninguno de sus
patrones, y añadir uno por cada redacción es perseguir la prosa. Lo que se
mide aquí es la copia misma: cuántas secciones del registro enumera la norma.
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from vault_norms_catalog import NORM_CATALOG  # noqa: E402
from vault_registry import ORDERED_SECTIONS  # noqa: E402

MANIFIESTO = ROOT / "vault-obsidian-architecture.md"

#: Nombrar una o dos secciones como ejemplo es prosa; a partir de aquí es copia.
MAXIMO_DE_EJEMPLOS = 3


def _seccion_de_norma(codigo: str) -> str:
    texto = MANIFIESTO.read_text(encoding="utf-8")
    inicio = re.search(rf"^### {re.escape(codigo)} — .*$", texto, re.M)
    assert inicio, f"{codigo} sin sección en el manifiesto"
    fin = re.search(r"^### ", texto[inicio.end():], re.M)
    return texto[inicio.start(): inicio.end() + (fin.start() if fin else len(texto))]


@pytest.mark.parametrize("codigo", ["CN-02", "AP-15"])
def test_la_norma_no_enumera_las_secciones_del_registro(codigo):
    cuerpo = _seccion_de_norma(codigo)
    nombradas = sorted(s for s in ORDERED_SECTIONS if s in cuerpo)
    assert len(nombradas) <= MAXIMO_DE_EJEMPLOS, (
        f"{codigo} copia {len(nombradas)} secciones del registro ({nombradas}); "
        "se consultan con vault_section --list o vault_registry.ORDERED_SECTIONS"
    )


@pytest.mark.parametrize("codigo", ["CN-02", "AP-15"])
def test_la_norma_no_escribe_a_mano_cuantas_secciones_hay(codigo):
    cuerpo = _seccion_de_norma(codigo)
    # En presente: «listaba 13 secciones obsoletas hasta v38.1» es historia.
    cifras = re.findall(
        r"[Aa]ctualmente\s+\d+|\b\d+\s+secciones\s+(?:estándar|del registro|canónicas)",
        cuerpo,
    )
    assert not cifras, f"{codigo} escribe la cifra del registro a mano: {cifras}"


def _entrada(codigo: str) -> dict:
    return next(n for n in NORM_CATALOG if n["code"] == codigo)


#: «00_System…11_Code» es una lista escrita como rango: envejece igual que la
#: lista entera, y en AP-15 lo hizo cuando el registro pasó de 11_Code.
_RANGO = re.compile(r"\d\d_[A-Za-z]+\s*(?:…|\.\.\.?)\s*`?\d\d_[A-Za-z]+")


@pytest.mark.parametrize("codigo", ["CN-02", "AP-15"])
def test_el_catalogo_no_escribe_el_registro_como_rango(codigo):
    n = _entrada(codigo)
    for campo in ("description", "signal", "prevention"):
        assert not _RANGO.search(n.get(campo, "")), (
            f"{codigo}.{campo} escribe las secciones como rango: {n[campo]!r}")
    cuerpo = _seccion_de_norma(codigo)
    assert not _RANGO.search(cuerpo), f"{codigo} escribe las secciones como rango"


def test_ap15_la_cumplen_las_tools_que_rechazan_la_raiz():
    """`motivo_de_destino_invalido` rechaza la raíz citando AP-15, y lo usan
    `vault_write` y `vault_move`; `vault_section_index` tiene su propio guard.
    Hasta v41.2 el catálogo decía `tools_enforcing: []`."""
    assert {"vault_write", "vault_move", "vault_section_index"} <= set(
        _entrada("AP-15")["tools_enforcing"])

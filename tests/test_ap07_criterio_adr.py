"""AP-07 — un solo criterio de «ADR completo», el que leen todos los detectores.

Medido el 2026-10-08: `vault_norms_scan` exigía a la vez «contexto» y
«context», «opciones» y «options», así que un ADR completo en castellano salía
siempre incompleto; y decidía por la subcadena `adr` en la ruta, así que
`07_Knowledge/padre.md` era un ADR. La auditoría decidía por `type` y pedía
otras secciones. Contra /ans (regla 7), los diez ADR reales tienen contexto,
decisión y consecuencias, y ocho de diez no tienen «Opciones»: por eso se
recomienda y no se exige.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402
from vault.kernel.contenido import (  # noqa: E402
    es_adr,
    plantilla_adr,
    secciones_adr_faltantes,
    secciones_adr_recomendadas_faltantes,
)

ADR_ES = (
    "# ADR-001 — Monolito\n\n## Contexto detectado\nUn equipo.\n\n"
    "## Decisión\nMonolito.\n\n## Consecuencias\nDespliegue único.\n"
)
ADR_EN = "# ADR\n\n## Context\nx\n\n## Decision\ny\n\n## Consequences\nz\n"


def test_ap07_un_adr_completo_en_castellano_o_en_ingles_no_falta_nada():
    assert secciones_adr_faltantes(ADR_ES) == []
    assert secciones_adr_faltantes(ADR_EN) == []


def test_ap07_las_faltantes_salen_en_orden_y_con_su_nombre():
    assert secciones_adr_faltantes("# ADR\n\n## Decision\nx\n") == ["Contexto", "Consecuencias"]
    # Una palabra en el cuerpo no es una sección: cuenta el encabezado.
    assert secciones_adr_faltantes("# ADR\nEl contexto y las consecuencias.\n") == [
        "Contexto", "Decisión", "Consecuencias"]


def test_ap07_opciones_se_recomienda_no_se_exige():
    assert secciones_adr_recomendadas_faltantes(ADR_ES) == ["Opciones"]
    assert secciones_adr_recomendadas_faltantes("## Alternativas evaluadas\n") == []


def test_ap07_la_plantilla_cumple_su_propio_criterio():
    assert secciones_adr_faltantes(plantilla_adr()) == []
    assert secciones_adr_recomendadas_faltantes(plantilla_adr()) == []


@pytest.mark.parametrize("rel,tipo,esperado", [
    ("03_Decisions/2026-05-03-adr-001.md", "adr", True),
    ("03_Decisions/adr-003.md", "decision", True),
    ("03_Decisions/adr-004.md", "", True),           # sin type no es la vía de escape
    ("03_Decisions/audit.md", "audit", False),       # declara un type ajeno
    ("03_Decisions/index.md", "", False),
    ("03_Decisions/00-03_decisions-primer.md", "primer", False),
    ("07_Knowledge/padre.md", "", False),            # «adr» en la ruta no decide
    ("07_Knowledge/adr-notes.md", "adr", False),     # fuera de la sección
])
def test_ap07_que_es_un_adr(rel, tipo, esperado):
    assert es_adr(rel, tipo) is esperado


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "v"
    for s in ("00_System", "03_Decisions", "07_Knowledge"):
        (raiz / s).mkdir(parents=True)
    previo = vault_io.get_vault_root()
    vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previo)


def _escribe(raiz, rel, fm, cuerpo):
    (raiz / rel).write_text(f"---\n{fm}\n---\n{cuerpo}", encoding="utf-8")


def _ap07(scan):
    return [n for n in scan["applicable_norms"] if n["code"] == "AP-07"]


def test_ap07_scan_no_marca_un_adr_completo_en_castellano(vault):
    import vault_norms
    _escribe(vault, "03_Decisions/adr-001.md", "title: ADR\ntype: adr\nstatus: accepted", ADR_ES)
    assert _ap07(vault_norms.vault_norms_scan("03_Decisions/adr-001.md")) == []


def test_ap07_scan_nombra_lo_que_falta(vault):
    import vault_norms
    _escribe(vault, "03_Decisions/adr-002.md", "title: ADR\ntype: adr", "# ADR\n\n## Decisión\nx\n")
    (ap07,) = _ap07(vault_norms.vault_norms_scan("03_Decisions/adr-002.md"))
    assert "Contexto" in ap07["reason"] and "Consecuencias" in ap07["reason"]


def test_ap07_scan_no_toma_una_ruta_con_adr_por_un_adr(vault):
    import vault_norms
    _escribe(vault, "07_Knowledge/padre.md", "title: Padre\ntype: concept", "# Padre\nuno\ndos\ntres\n")
    assert _ap07(vault_norms.vault_norms_scan("07_Knowledge/padre.md")) == []


def test_ap07_la_auditoria_usa_el_mismo_criterio(vault):
    """Un ADR en inglés con «Decision» sin tilde y uno castellano con
    «Contexto detectado»: los dos completos para la auditoría y para el scan.
    Uno sin consecuencias sale marcado en los dos con el mismo nombre."""
    import vault_norms
    from vault.gobernanza.auditoria_runtime import _ADR_TYPES, auditar_runtime
    from vault.kernel.contenido import TIPOS_ADR
    assert tuple(_ADR_TYPES) == tuple(TIPOS_ADR)
    fm = "title: ADR\ntype: adr\nstatus: accepted"
    _escribe(vault, "03_Decisions/adr-es.md", fm, ADR_ES)
    _escribe(vault, "03_Decisions/adr-en.md", fm, ADR_EN)
    _escribe(vault, "03_Decisions/adr-corto.md", fm, "# ADR\n\n## Contexto\nx\n\n## Decisión\ny\n")
    auditoria = {v["path"]: v["detail"] for v in auditar_runtime(vault)["violations"]
                 if v["norm"] == "AP-07"}
    assert set(auditoria) == {"03_Decisions/adr-corto.md"}, auditoria
    assert "Consecuencias" in auditoria["03_Decisions/adr-corto.md"]
    for rel in ("03_Decisions/adr-es.md", "03_Decisions/adr-en.md"):
        assert _ap07(vault_norms.vault_norms_scan(rel)) == [], rel
    (scan,) = _ap07(vault_norms.vault_norms_scan("03_Decisions/adr-corto.md"))
    assert "Consecuencias" in scan["reason"]

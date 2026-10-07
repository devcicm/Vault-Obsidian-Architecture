"""Cada sección declara qué clase de documento es (Diátaxis + registro + índice).

La metodología de documentación del estándar decía qué campos lleva una nota,
pero no qué *clase* de documento contiene cada sección: si un runbook es una
guía o una explicación lo decidía quien escribía. El registro lo declara una
vez por sección, con el motivo, y el SDD lo publica derivado de ahí.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_registry as reg  # noqa: E402
import vault_sdd_init  # noqa: E402


def test_toda_seccion_declara_su_clase_de_documento():
    assert list(reg.SECTION_DOCUMENTACION) == reg.ORDERED_SECTIONS


def test_la_clase_es_del_vocabulario_cerrado_y_lleva_motivo():
    for carpeta, (clase, motivo) in reg.SECTION_DOCUMENTACION.items():
        assert clase in reg.DOCUMENTACION_CLASES, carpeta
        assert motivo.strip(), carpeta


def test_diataxis_son_las_cuatro_clases_y_estan_en_el_vocabulario():
    assert reg.DIATAXIS == ("tutorial", "guia", "referencia", "explicacion")
    assert set(reg.DIATAXIS) <= set(reg.DOCUMENTACION_CLASES)


def test_una_subcarpeta_hereda_la_clase_y_lo_que_no_es_seccion_no_tiene():
    assert reg.section_documentacion("08_Runbooks") == "guia"
    assert reg.section_documentacion("08_Runbooks/deploy") == "guia"
    assert reg.section_documentacion("08_Runbooks\\deploy") == "guia"
    assert reg.section_documentacion("docs") == ""
    assert reg.section_documentacion("scripts/x") == ""


def test_el_sdd_publica_la_tabla_derivada_del_registro():
    texto = vault_sdd_init.generate_methodology(REPO_ROOT, {})
    assert "{TABLA_DOCUMENTACION}" not in texto
    for carpeta, (clase, motivo) in reg.SECTION_DOCUMENTACION.items():
        assert f"| `{carpeta}` | {reg.section_name(carpeta)} | {clase} | {motivo} |" in texto


def test_el_sdd_publica_el_hueco_en_vez_de_callarlo():
    """Ninguna sección es tutorial: el documento lo dice, no lo esconde."""
    usadas = {c for c, _ in reg.SECTION_DOCUMENTACION.values()}
    sin = [c for c in reg.DIATAXIS if c not in usadas]
    texto = vault_sdd_init.generate_methodology(REPO_ROOT, {})
    if sin:
        assert "Clases de Diátaxis sin ninguna sección: " + ", ".join(sin) in texto


def test_el_sdd_versionado_coincide_con_el_generador():
    """Con el mismo criterio del guard de SDD: saneado, sin marca temporal."""
    assert "06-documentation-methodology.md" not in \
        vault_sdd_init.sdd_desfase_de_contenido(REPO_ROOT)

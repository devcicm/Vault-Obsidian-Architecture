"""Qué carpetas de la raíz son legítimas sin ser secciones: una lista, no tres.

El síntoma fue que el propio estándar se reprobaba: `vault_sdd_init` escribe en
`docs/sdd/` —su `SDD_OUTPUT_DIR`— y el audit denunciaba `docs/` como CN-02.
El kernel ya sabía que `docs/` no es una sección, porque no le disparaba la
cascada de índices; el audit no se había enterado. Dos criterios para la misma
pregunta, escritos a mano en dos módulos: AP-05.

La lista vive ahora en `vault_registry.NON_SECTION_ROOT_FOLDERS` y los dos
consumidores la derivan.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vault_registry import NON_SECTION_ROOT_FOLDERS, SECTIONS  # noqa: E402


def test_el_audit_deriva_su_lista_del_registro():
    import vault_norms

    assert vault_norms._ROOT_ALLOWED == set(NON_SECTION_ROOT_FOLDERS)


def test_el_kernel_deriva_la_suya_del_mismo_registro():
    """Más las dos secciones canónicas que gestionan su propio índice."""
    import vault_io

    assert set(NON_SECTION_ROOT_FOLDERS) <= vault_io._SKIP_AUTO_INDEX
    assert vault_io._SKIP_AUTO_INDEX - set(NON_SECTION_ROOT_FOLDERS) == {
        "00_System",
        "99_Index",
    }


def test_la_salida_del_generador_de_sdd_no_viola_cn02():
    """Es la violación concreta que destapó la duplicación."""
    import vault_sdd_init

    raiz_del_sdd = vault_sdd_init.SDD_OUTPUT_DIR.split("/")[0]
    assert raiz_del_sdd in NON_SECTION_ROOT_FOLDERS


def test_ninguna_carpeta_permitida_es_ademas_una_seccion():
    """Si lo fuera, la sección quedaría sin índice y sin audit a la vez."""
    secciones = {s["folder"] for s in SECTIONS}
    assert not (secciones & set(NON_SECTION_ROOT_FOLDERS))


@pytest.mark.parametrize("carpeta", sorted(NON_SECTION_ROOT_FOLDERS))
def test_cada_entrada_dice_quien_la_escribe(carpeta):
    assert NON_SECTION_ROOT_FOLDERS[carpeta].strip()


def test_docs_en_la_raiz_ya_no_se_denuncia(tmp_path):
    import vault_norms

    for s in SECTIONS:
        (tmp_path / s["folder"]).mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "sdd").mkdir(parents=True)

    resultado = vault_norms.vault_norms_audit(tmp_path)
    cn02 = [v for v in resultado["violations"] if v["norm"] == "CN-02"]
    assert cn02 == [], cn02


def test_una_carpeta_de_verdad_ajena_si_se_denuncia(tmp_path):
    """La lista no puede volverse un colador: lo no declarado sigue fallando."""
    import vault_norms

    for s in SECTIONS:
        (tmp_path / s["folder"]).mkdir(parents=True, exist_ok=True)
    (tmp_path / "descargas").mkdir()

    resultado = vault_norms.vault_norms_audit(tmp_path)
    assert any(
        v["norm"] == "CN-02" and v["path"] == "descargas"
        for v in resultado["violations"]
    )

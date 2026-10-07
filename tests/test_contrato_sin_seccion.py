"""Un `.md` que no está en ninguna sección no es una nota de contenido.

Medido el 2026-10-07 en dos vaults ajenos (solo lectura): el `README.md` y el
`Home.md` de la raíz, y los `.md` de una carpeta que el registro no declara
(`scripts/`), salían como clase `contenido`. El contrato les exigía CIA,
`agent`, `type` y `status`, que son los campos de una nota **de una sección**:
la sensibilidad y el tipo los decide la sección en la que vive la nota
(`SECTION_TYPES`), y fuera de toda sección no hay quien los decida.

Desde v41 son clase `sin_seccion`: se les exige identidad y timestamps, lo
mismo que a una nota de sistema. Antes de v41 el validador no los distinguía
y los juzgaba como contenido; el contrato de esas versiones no se reescribe.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_contrato_nota as contrato  # noqa: E402
from vault_registry import es_de_seccion  # noqa: E402

IDENTIDAD = {"id": "x", "title": "x", "createdAt": "2026-10-07T00:00:00Z",
             "updatedAt": "2026-10-07T00:00:00Z"}


@pytest.mark.parametrize("rel", ["README.md", "Home.md", "scripts/x.md", "docs/guia.md"])
def test_fuera_de_las_secciones_la_clase_es_sin_seccion(rel):
    assert not es_de_seccion(rel)
    assert contrato.clase_de_nota(rel) == "sin_seccion"


@pytest.mark.parametrize("rel,clase", [
    ("07_Knowledge/jwt.md", "contenido"),
    ("07_Knowledge/sub/jwt.md", "contenido"),
    ("00_System/primer.md", "sistema"),
    ("99_Index/index.md", "derivada"),
    ("index.md", "derivada"),
])
def test_las_demas_clases_no_cambian(rel, clase):
    assert contrato.clase_de_nota(rel) == clase


def test_una_carpeta_con_nombre_de_seccion_no_basta_si_el_fichero_esta_en_la_raiz():
    """`07_Knowledge.md` en la raíz no es de la sección `07_Knowledge/`."""
    assert not es_de_seccion("07_Knowledge.md")


def test_se_le_exige_identidad_y_timestamps():
    assert contrato.faltantes(IDENTIDAD, "README.md") == []
    assert contrato.faltantes({}, "README.md") == list(contrato.campos_requeridos("00_System/x.md"))


def test_no_se_le_exige_cia_ni_type_ni_status():
    requeridos = set(contrato.campos_requeridos("README.md"))
    assert not requeridos & {"cia_integrity", "cia_availability", "cia_sensitivity",
                             "agent", "tags", "type", "status"}


@pytest.mark.parametrize("version", ["v25", "v37", "v40"])
def test_antes_de_v41_se_juzgaba_como_contenido(version):
    """La clase nueva no reescribe lo que el validador de entonces exigía."""
    assert contrato.faltantes({}, "README.md", version) == \
        contrato.faltantes({}, "07_Knowledge/x.md", version)
    assert "sin_seccion" not in contrato.contrato_de_version(version)["requeridos"]


def test_el_contrato_v41_publica_la_clase():
    c = contrato.contrato_de_version("v41")
    assert c["requeridos"]["sin_seccion"] == c["requeridos"]["sistema"]
    assert "sin_seccion" in contrato.esquema_json("v41")["$defs"]


def test_el_audit_no_le_pide_campos_de_contenido(tmp_path):
    import vault_audit as va
    import vault_io

    root = tmp_path / "v"
    (root / "00_System").mkdir(parents=True)
    (root / "README.md").write_text(
        "---\nid: readme\ntitle: README\ncreatedAt: 2026-10-07T00:00:00Z\n"
        "updatedAt: 2026-10-07T00:00:00Z\n---\n\n# README\n", encoding="utf-8")
    vault_io.set_vault_root(root)

    r = va._detect_missing_metadata([root / "README.md"])
    for lista in ("missing_cia", "missing_type", "missing_status", "missing_tags",
                  "missing_agent", "missing_contract"):
        assert not r[lista], (lista, r[lista])

"""El nombre de un proyecto es identidad: un solo slug, nunca dos ni ninguno.

Medido 2026-10-02 en un vault ajeno de 647 notas (regla 7, solo lectura):
`--project` libre había fundado los proyectos fantasma `mi-api`, `mi-proyecto`,
`demo` y `website-demo`, y la misma entidad aparecía como `Proyecto:` y
`PROJECT:`. En otro de 145 notas la identidad era solo la carpeta
`01_Projects/vcloud-saas/`, sin frontmatter que la declarase, y su
`index.md` era un índice generado — por eso la ficha es `project.md`.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import vault_errors  # noqa: E402
from vault.autoria import proyectos  # noqa: E402
from vault.kernel.fallos import FalloDeDominio  # noqa: E402
from vault.kernel.indices_structural import es_nombre_reservado  # noqa: E402


def _proyecto(raiz: Path, slug: str, ficha: str | None = None) -> None:
    carpeta = raiz / "01_Projects" / slug
    carpeta.mkdir(parents=True)
    if ficha is not None:
        (carpeta / "project.md").write_text(ficha, encoding="utf-8")


def test_la_ficha_no_es_un_nombre_reservado():
    # Si lo fuera, vault_section_index la regeneraría encima.
    assert not es_nombre_reservado(proyectos.FICHA)


def test_la_carpeta_sola_registra_el_slug(tmp_path):
    _proyecto(tmp_path, "vcloud-saas")
    (tmp_path / "01_Projects" / "vcloud-saas" / "index.md").write_text("# índice", encoding="utf-8")
    (tmp_path / "01_Projects" / ".locks").mkdir()
    registro = proyectos.leer_registro(tmp_path)
    assert sorted(registro.proyectos) == ["vcloud-saas"]
    assert registro.resolver("VCloud SaaS") == "vcloud-saas"


def test_los_alias_resuelven_al_slug(tmp_path):
    _proyecto(tmp_path, "ans", "---\ntitle: ANS\naliases: [Ans Core, ans-api]\n---\n")
    registro = proyectos.leer_registro(tmp_path)
    assert registro.resolver("ANS-API") == "ans"
    assert registro.proyectos["ans"].ficha == "01_Projects/ans/project.md"


def test_ap63_un_nombre_no_registrado_no_funda_un_proyecto(tmp_path):
    _proyecto(tmp_path, "mi-api-real")
    registro = proyectos.leer_registro(tmp_path)
    with pytest.raises(FalloDeDominio) as info:
        registro.resolver("mi-api")
    assert info.value.causa == "PROYECTO_NO_REGISTRADO"
    assert info.value.datos["sugerencias"] == ["mi-api-real"]
    assert not (tmp_path / "01_Projects" / "mi-api").exists()


def test_ap63_un_alias_reclamado_por_dos_no_elige_en_silencio(tmp_path):
    _proyecto(tmp_path, "alfa", "---\naliases: [core]\n---\n")
    _proyecto(tmp_path, "beta", "---\naliases: [Core]\n---\n")
    registro = proyectos.leer_registro(tmp_path)
    assert registro.ambiguedades() == {"core": ["alfa", "beta"]}
    with pytest.raises(FalloDeDominio) as info:
        registro.resolver("core")
    assert info.value.causa == "PROYECTO_AMBIGUO"
    assert info.value.datos["candidatos"] == ["alfa", "beta"]


def test_las_incidencias_se_publican_sin_corregirse(tmp_path):
    _proyecto(tmp_path, "Mi Proyecto")
    _proyecto(tmp_path, "gamma", "---\nproject: delta\n---\n")
    _proyecto(tmp_path, "rota", "---\ntitle: [sin cerrar\n---\n")
    registro = proyectos.leer_registro(tmp_path)
    tipos = sorted(i["kind"] for i in registro.incidencias)
    assert tipos == ["carpeta_no_canonica", "ficha_contradice_carpeta", "ficha_ilegible"]
    assert (tmp_path / "01_Projects" / "Mi Proyecto").is_dir()


def test_ap63_fantasmas_separa_lo_registrado_de_lo_que_no(tmp_path):
    _proyecto(tmp_path, "ans")
    hallazgos = proyectos.fantasmas(
        proyectos.leer_registro(tmp_path),
        {"ANS": ["a.md"], "demo": ["b.md", "c.md"]},
    )
    assert hallazgos == [{
        "project": "demo", "kind": "no_registrado",
        "candidates": [], "notes": ["b.md", "c.md"],
    }]


@pytest.mark.parametrize("causa,codigo", [
    ("PROYECTO_NO_REGISTRADO", "PROJECT_NOT_FOUND"),
    ("PROYECTO_AMBIGUO", "PROJECT_AMBIGUOUS"),
])
def test_la_tool_traduce_la_causa_al_catalogo(causa, codigo):
    envelope = vault_errors.emit_fallo(
        "vault_project", FalloDeDominio(causa, "x", project="p"),
    )
    assert envelope["error_code"] == codigo
    assert envelope["causa"] == causa
    assert envelope["project"] == "p"

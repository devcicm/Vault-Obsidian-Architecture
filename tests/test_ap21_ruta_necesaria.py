"""AP-21 precisado: la carpeta en un enlace vale si es lo que fija la identidad.

Medido el 2026-10-04 en un vault de consumidor con dos proyectos: cada uno
tiene `01_Projects/<slug>/overview.md`, y AP-21 prohibía `[[demo/overview]]`.
El único enlace posible era `[[overview]]`, que resuelve a dos notas — el
propio `resolver_wikilink` del núcleo lo clasifica como ambiguo. Obsidian
resuelve el sufijo de ruta y con su formato por defecto escribe él mismo
`[[demo/overview]]`. La regla pasa a ser la de Obsidian: el nombre si es
único, la ruta más corta si no; una ruta que no resuelve o que sobra sigue
siendo AP-21.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402
import vault_write  # noqa: E402
from vault_lib import destino_mas_corto, indice_de_nombres, ruta_necesaria  # noqa: E402

NOTAS = [
    "01_Projects/demo/overview.md",
    "01_Projects/billing/overview.md",
    "07_Knowledge/jwt.md",
]
CUERPO = (
    "Primera línea con contenido real para el gate.\n"
    "Segunda línea con contenido real para el gate.\n"
    "Tercera línea que enlaza {enlace} desde la nota.\n"
)


def test_criterio_ap21_ruta_necesaria():
    indice = indice_de_nombres(NOTAS)
    assert ruta_necesaria("demo/overview", None, indice)
    assert ruta_necesaria("01_Projects/billing/overview|Billing", None, indice)
    # Sobra: el nombre ya es único.
    assert not ruta_necesaria("07_Knowledge/jwt", None, indice)
    # No resuelve: el caso de ANS que originó AP-21.
    assert not ruta_necesaria("concepts/jwt", None, indice)
    assert not ruta_necesaria("otro/overview", None, indice)


def test_destino_mas_corto_es_el_de_obsidian():
    indice = indice_de_nombres(NOTAS)
    assert destino_mas_corto("07_Knowledge/jwt.md", indice) == "jwt"
    assert destino_mas_corto("01_Projects/demo/overview.md", indice) == "demo/overview"


@pytest.fixture
def vault(tmp_path):
    previo = vault_io.get_vault_root()
    for rel in NOTAS:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("---\ntitle: x\n---\nx\n", encoding="utf-8")
    vault_io.set_vault_root(tmp_path)
    yield tmp_path
    vault_io.set_vault_root(previo)


def _escribir(enlace, titulo):
    return vault_write.vault_write(
        folder="07_Knowledge", title=titulo, content=CUERPO.format(enlace=enlace),
        tags=["demo"], meta={"agent": "probe"},
    )


def test_vault_write_acepta_la_ruta_que_desambigua(vault):
    r = _escribir("[[demo/overview]]", "Enlace Desambiguado")
    assert r["ok"] is True, r


@pytest.mark.parametrize("enlace", ["[[07_Knowledge/jwt]]", "[[concepts/jwt]]"])
def test_vault_write_sigue_rechazando_la_ruta_que_sobra_o_no_resuelve(vault, enlace):
    r = _escribir(enlace, "Enlace Anclado")
    assert r["ok"] is False and "AP-21" in r["message"], r


def test_el_indice_enlaza_la_ruta_mas_corta_cuando_el_nombre_se_repite(vault):
    """Medido en el vault de consumidor: `01_Projects/index.md` listaba
    `[[overview]]` dos veces, una por proyecto, y las dos eran ambiguas."""
    import vault_section_index

    r = vault_section_index.vault_section_index("01_Projects")
    assert r["ok"] is True, r
    texto = (vault / "01_Projects" / "index.md").read_text(encoding="utf-8")
    assert "| [[demo/overview]] |" in texto
    assert "| [[billing/overview]] |" in texto
    assert "| [[overview]] |" not in texto
    # Y el nombre único sigue yendo por nombre.
    vault_section_index.vault_section_index("07_Knowledge")
    k = (vault / "07_Knowledge" / "index.md").read_text(encoding="utf-8")
    assert "| [[jwt]] |" in k


def test_los_detectores_de_ap21_usan_el_mismo_criterio(vault):
    """Si el índice escribe `[[demo/overview]]` y la auditoría lo marca como
    AP-21, el vault queda penalizado por lo que genera su propia tool."""
    import vault_graph_inspect
    import vault_norms

    nota = vault / "07_Knowledge" / "enlaces.md"
    nota.write_text(
        "---\ntitle: Enlaces\n---\n" + CUERPO.format(enlace="[[demo/overview]]")
        + "Y una que sobra: [[07_Knowledge/jwt]].\n",
        encoding="utf-8",
    )
    scan = vault_norms.vault_norms_scan("07_Knowledge/enlaces.md")
    ap21 = [n for n in scan["applicable_norms"] if n["code"] == "AP-21"]
    assert len(ap21) == 1 and "07_Knowledge/jwt" in ap21[0]["reason"], ap21
    assert "demo/overview" not in ap21[0]["reason"]

    body = nota.read_text(encoding="utf-8").split("---", 2)[2]
    errores = vault_graph_inspect._detect_wikilink_syntax_errors(
        {"07_Knowledge/enlaces.md": {"body": body, "aliases": []},
         **{rel: {"body": "", "aliases": []} for rel in NOTAS}}
    )
    anclados = [e["detail"] for e in errores if e["type"] == "path_anchored"]
    assert anclados == ["[[07_Knowledge/jwt]]"], anclados


def test_vault_audit_marca_el_nombre_que_resuelve_a_varias_notas(vault):
    """El otro lado de la regla: `[[overview]]` con dos proyectos no es un
    enlace roto, es ambiguo, y ningún detector lo veía. vault_audit lo
    reporta como AP-21 con la ruta más corta de cada candidato."""
    import vault_audit

    (vault / "07_Knowledge" / "enlaces.md").write_text(
        "---\ntitle: Enlaces\n---\n" + CUERPO.format(enlace="[[overview]] y [[jwt]]"),
        encoding="utf-8",
    )
    r = vault_audit.vault_audit()
    ambiguos = r["issues"]["ambiguousLinks"]
    assert len(ambiguos) == 1, ambiguos
    e = ambiguos[0]
    assert e["norm_code"] == "AP-21" and e["link"] == "overview"
    assert sorted(e["suggest"]) == ["billing/overview", "demo/overview"]
    pena = [x for x in r["penalties"] if x["id"] == "ambiguous_links"]
    assert pena and pena[0]["norm_code"] == "AP-21" and pena[0]["count"] == 1, pena

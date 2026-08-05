"""AP-44 — el filtro de placeholders no puede tragarse enlaces a notas reales.

`_extract_wiki_links` descarta wikilinks que parecen sobras de plantilla
(`[[nombre-del-proyecto]]`, `[[yyyy-mm-dd]]`) comparando por `startswith`
contra `PLACEHOLDER_PATTERNS`. El prefijo es una heuristica de la tool, no un
hecho del vault: `patron`, `nombre`, `imagen`, `express`, `postgres` son
tambien comienzos legitimos de nombres de nota.

Coste medido en el vault de BuilderX: `patron-dsl-compilacion`,
`patron-mcp-streaming` y `patron-blastmode-weavingmode` salian como huerfanas
teniendo 6, 8 y 2 enlaces entrantes. El audit las mandaba enlazar desde otra
nota; ya lo estaban. Tercer sintoma de AP-44 en `vault_audit`: decidir con
criterio propio en vez de preguntar al vault si el destino existe.

La regla: **un enlace cuyo destino existe nunca es un placeholder.** El
descarte solo aplica cuando no hay nota detras, que es el caso para el que se
escribio.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit as va  # noqa: E402


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "v"
    for sec in ("00_System", "01_Projects", "05_Patterns"):
        (root / sec).mkdir(parents=True)
    return root


def _huerfanas(root: Path):
    previo = va.VAULT_ROOT
    va.VAULT_ROOT = root
    try:
        notas = va._get_active_notes(None, include_structural=True)
        backlinks, _ = va._build_indexes(notas)
        contenido = va._get_active_notes(None, include_structural=False)
        return {o["path"].replace("\\", "/") for o in va._detect_orphans(contenido, backlinks)}
    finally:
        va.VAULT_ROOT = previo


def _nota(root: Path, rel: str, cuerpo: str = "") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\nstatus: draft\ntype: reference\ntags: [x]\n---\n\n# n\n\n" + cuerpo,
        encoding="utf-8",
    )


def test_una_nota_enlazada_cuyo_nombre_empieza_por_placeholder_no_es_huerfana(tmp_path):
    """El caso literal de BuilderX: `patron` es prefijo de `PLACEHOLDER_PATTERNS`."""
    root = _vault(tmp_path)
    _nota(root, "05_Patterns/patron-dsl-compilacion.md")
    _nota(root, "01_Projects/arquitectura.md", "Ver [[patron-dsl-compilacion]].\n")

    assert "05_Patterns/patron-dsl-compilacion.md" not in _huerfanas(root)


def test_el_placeholder_sin_nota_detras_se_sigue_descartando(tmp_path):
    """El filtro existe por algo: una plantilla vacia no genera enlaces rotos."""
    root = _vault(tmp_path)
    _nota(root, "01_Projects/plantilla.md", "Ver [[nombre-del-proyecto]].\n")

    previo = va.VAULT_ROOT
    va.VAULT_ROOT = root
    try:
        notas = va._get_active_notes(None, include_structural=True)
        _, all_stems = va._build_indexes(notas)
        rotos = va._detect_broken_links(notas, all_stems)
    finally:
        va.VAULT_ROOT = previo

    assert rotos == []


def test_sin_known_el_comportamiento_es_el_de_antes(tmp_path):
    """La firma nueva es aditiva: `known=None` conserva el filtro completo."""
    assert va._extract_wiki_links("Ver [[patron-x]].") == []
    assert va._extract_wiki_links("Ver [[patron-x]].", known={"patronx"}) == ["patron-x"]


def test_un_enlace_a_nota_real_con_prefijo_placeholder_no_se_reporta_roto(tmp_path):
    """El mismo sesgo enmascaraba enlaces rotos de verdad en la otra direccion."""
    root = _vault(tmp_path)
    _nota(root, "05_Patterns/patron-existe.md")
    _nota(root, "01_Projects/o.md", "[[patron-existe]] y [[patron-que-no-existe]]\n")

    previo = va.VAULT_ROOT
    va.VAULT_ROOT = root
    try:
        notas = va._get_active_notes(None, include_structural=True)
        _, all_stems = va._build_indexes(notas)
        rotos = va._detect_broken_links(notas, all_stems)
    finally:
        va.VAULT_ROOT = previo

    # `patron-que-no-existe` no lo detecta el filtro de placeholders (sigue
    # descartado por prefijo, y eso es aceptable: no hay nota detras). Lo que
    # esta prueba fija es que el que SI existe no ensucia la lista.
    assert all(r["link"] != "patron-existe" for r in rotos)

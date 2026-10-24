"""Propiedad de la documentación: todo doc vivo declara quién responde.

`<!-- propiedad: CARLOS IVAN CM · revisión: manual -->` en los primeros
renglones. Tres clases, cada una con su criterio:

- **derivado** — su productor es una tool y su deriva la vigila una puerta
  (`doc_staleness`, `servicio --check`, `doc_sync`): no necesita dueño,
  necesita generador, y lo tiene.
- **registro** — `auditorias/`, `archivo/`, `adr/`: inmutables por
  no-derogación; el ADR lleva además su `Responsable:` (AP-64, v41.21).
- **vivo** — lo demás: alguien tiene que mirarlo de vez en cuando, y este
  test es el que se acuerda.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")

DOCS = RAIZ / "docs"

DERIVADOS = {
    "docs/ARQUITECTURA.md", "docs/BLUEPRINT.md", "docs/PUERTAS.md",
    "docs/METRICAS.md", "docs/GOBIERNO.md", "docs/GUIA-DE-PRODUCCION.md",
    "docs/SKILLS.md",
}
REGISTROS = ("auditorias", "archivo", "adr", "sdd", "contrastes",
             "product/baseline-report.md")
SIN_TITULO_OK = {"docs/MAPA-MANIFIESTO.md"}  # empieza con la cabecera de propiedad


def es_derivado(rel: str) -> bool:
    if rel in DERIVADOS:
        return True
    return rel.startswith("docs/sdd/") or rel.startswith("docs/contrastes/")


REGISTROS_FICHERO = {"docs/product/baseline-report.md"}


def es_registro(rel: str) -> bool:
    if rel in REGISTROS_FICHERO:
        return True
    partes = rel.split("/")
    return bool(partes) and partes[1] in REGISTROS


def docs_de_docs() -> list[Path]:
    return sorted(p for p in DOCS.rglob("*.md") if "__pycache__" not in p.parts)


def test_todo_doc_vivo_declara_propiedad():
    sin = []
    for p in docs_de_docs():
        rel = p.relative_to(RAIZ).as_posix()
        if es_derivado(rel) or es_registro(rel):
            continue
        cabeza = p.read_text(encoding="utf-8", errors="replace")[:400]
        if "propiedad:" not in cabeza:
            sin.append(rel)
    assert not sin, (
        f"docs vivos sin cabecera de propiedad: {sin}. Un doc que nadie "
        "declara mantener es un doc que nadie mantiene. Se salda añadiendo "
        "<!-- propiedad: CARLOS IVAN CM · revisión: manual --> al principio "
        "(o reclasificándolo como derivado o registro, con el criterio "
        "escrito)."
    )


def test_la_cabecera_declara_dueno_y_revision():
    """`propiedad:` a secas no basta: el dueño tiene nombre y la revisión dice
    cómo se hace (manual, o con qué tool)."""
    for p in docs_de_docs():
        rel = p.relative_to(RAIZ).as_posix()
        cabeza = p.read_text(encoding="utf-8", errors="replace")[:400]
        if "propiedad:" not in cabeza:
            continue
        linea = next(l for l in cabeza.split("\n") if "propiedad:" in l)
        assert "CARLOS IVAN CM" in linea or "meta_toolkit" in linea, (rel, linea)
        assert "revisión:" in linea, (rel, linea)


def test_los_derivados_tienen_productor_y_no_cabecera():
    """Un derivado con cabecera de propiedad es la confusión de las dos clases:
    su dueño es la tool que lo genera, y la deriva la mira su puerta."""
    for rel in DERIVADOS:
        p = RAIZ / rel
        if not p.is_file():
            continue
        cabeza = p.read_text(encoding="utf-8", errors="replace")[:300]
        assert "propiedad:" not in cabeza, (
            f"{rel} es derivado: su dueño es {DERIVADOS[rel]}, no una persona"
        )


def test_los_adr_llevan_responsable_incluso_como_registro():
    """AP-64 aplicado al propio repo: los ADR son registros inmutables, pero
    la decisión que registran tiene dueño — y eso no se exemptúa con ellos."""
    for adr in sorted((DOCS / "adr").glob("*.md")):
        t = adr.read_text(encoding="utf-8", errors="replace")
        assert "Responsable:" in t, (
            f"{adr.name} declara una decisión sin responsable"
        )

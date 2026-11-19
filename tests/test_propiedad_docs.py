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

La cabecera admite además la fecha de la última revisión,
`<!-- propiedad: … · revisión: manual · revisado: AAAA-MM-DD -->` (Torti Code,
fase 4: dueño, fecha de revisión y una herramienta que avise). Vencerla no
falla: `test_docs_vivos_con_revision_vencida_son_lista_de_trabajo` la publica
como trabajo pendiente, con la aritmética de las normas.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")

DOCS = RAIZ / "docs"

DERIVADOS = {
    "docs/ARQUITECTURA.md", "docs/BLUEPRINT.md", "docs/PUERTAS.md",
    "docs/METRICAS.md", "docs/GOBIERNO.md", "docs/GUIA-DE-PRODUCCION.md",
    "docs/SKILLS.md", "docs/DISPONIBILIDAD-DE-TOOLS.md", "docs/ENTORNO.md",
    "docs/CARRILES.md",
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
            f"{rel} es derivado: su dueño es la tool que lo genera, no una persona"
        )


def test_los_adr_llevan_responsable_incluso_como_registro():
    """AP-64 aplicado al propio repo: los ADR son registros inmutables, pero
    la decisión que registran tiene dueño — y eso no se exemptúa con ellos."""
    for adr in sorted((DOCS / "adr").glob("*.md")):
        t = adr.read_text(encoding="utf-8", errors="replace")
        assert "Responsable:" in t, (
            f"{adr.name} declara una decisión sin responsable"
        )


# ── Revisión por fecha (Torti Code, fase 4) ─────────────────────────────────

import re  # noqa: E402
from datetime import date  # noqa: E402

RE_REVISADO = re.compile(r"revisado:\s*(\S+?)\s*(?:·|-->|$)")

#: Cada cuántos días se relee un doc vivo: la cadencia de una norma
#: `recommended`, la que solo orienta (`CADENCIA_POR_ENFORCEMENT`).
CADENCIA_DOCS_VIVOS = "recommended"


def _linea_de_propiedad(p: Path) -> str:
    cabeza = p.read_text(encoding="utf-8", errors="replace")[:400]
    return next((linea for linea in cabeza.splitlines() if "propiedad:" in linea), "")


def test_la_fecha_de_revision_de_la_cabecera_es_legible():
    """`revisado:` es opcional; si está, es una fecha y no es futura."""
    from vault_norms_catalog import estado_de_revision

    malas = []
    for p in docs_de_docs():
        m = RE_REVISADO.search(_linea_de_propiedad(p))
        if m:
            estado = estado_de_revision(m.group(1), 1, date.today())
            if "problema" in estado:
                malas.append((p.relative_to(RAIZ).as_posix(), estado["problema"]))
    assert not malas, malas


def test_la_cabecera_acepta_la_fecha_de_revision():
    """El caso que la cabecera nueva admite, medido en un doc que la lleva."""
    linea = _linea_de_propiedad(DOCS / "INSIGHTS.md")
    assert "revisión:" in linea and RE_REVISADO.search(linea), linea


def test_docs_vivos_con_revision_vencida_son_lista_de_trabajo(capsys):
    """No es una puerta: imprime qué docs vivos tocan revisar y por qué."""
    from vault_norms_catalog import CADENCIA_POR_ENFORCEMENT, estado_de_revision

    cadencia = CADENCIA_POR_ENFORCEMENT[CADENCIA_DOCS_VIVOS]
    vencidos, sin_fecha = [], []
    for p in docs_de_docs():
        rel = p.relative_to(RAIZ).as_posix()
        linea = _linea_de_propiedad(p)
        if not linea:
            continue
        m = RE_REVISADO.search(linea)
        if not m:
            sin_fecha.append(rel)
            continue
        estado = estado_de_revision(m.group(1), cadencia, date.today())
        if estado.get("vencida"):
            vencidos.append(f"{rel} (venció el {estado['vence_en']})")
    with capsys.disabled():
        print(f"\n[revisión de docs vivos] vencidos: {vencidos or 'ninguno'}; "
              f"sin fecha de revisión: {len(sin_fecha)}")
    assert all(" (venció el " in v for v in vencidos), vencidos


# ── AP-07 sobre los ADR del repo, y lo editado tras aceptarlos ─────────────

#: Un ADR aceptado se sustituye, no se reescribe. Los que se editaron después
#: de aceptarse lo declaran aquí con su motivo, en vez de reescribir su
#: historia: la edición ya ocurrió y borrarla sería otra reescritura.
ADR_EDITADOS_TRAS_ACEPTAR = {
    "docs/adr/0002-puente-scripts-impl.md": (
        "Lleva una línea «Estado del puente (2026-10-16)» y un «Addendum "
        "(v40.35)» añadidos tras su aceptación, antes de que el repo adoptara "
        "«se sustituye, no se reescribe» (2026-11-16). Se conservan como "
        "están; un cambio de decisión nuevo va en un ADR sucesor."),
}

#: Las marcas de una edición posterior a la aceptación que se pueden leer en
#: el propio documento, sin historia de git.
RE_EDICION_TRAS_ACEPTAR = re.compile(
    r"^(?:#{2,}\s*Addendum\b|- \*\*Estado del [^*]+\(\d{4}-\d{2}-\d{2}\)\*\*)",
    re.MULTILINE)


def _adrs():
    return sorted((DOCS / "adr").glob("[0-9][0-9][0-9][0-9]-*.md"))


def test_los_adr_del_repo_tienen_las_secciones_de_ap07():
    from vault.kernel.contenido import secciones_adr_faltantes

    faltas = {a.name: secciones_adr_faltantes(a.read_text(encoding="utf-8"))
              for a in _adrs()}
    assert _adrs() and not {k: v for k, v in faltas.items() if v}, faltas


def test_un_adr_editado_tras_aceptarse_lo_declara_con_su_motivo():
    editados = {a.relative_to(RAIZ).as_posix() for a in _adrs()
                if RE_EDICION_TRAS_ACEPTAR.search(a.read_text(encoding="utf-8"))}
    assert editados == set(ADR_EDITADOS_TRAS_ACEPTAR), (
        "un ADR aceptado se sustituye con uno nuevo; si ya se editó, se declara "
        f"en ADR_EDITADOS_TRAS_ACEPTAR con su motivo: {sorted(editados)}")
    assert all(m.strip() for m in ADR_EDITADOS_TRAS_ACEPTAR.values())


# ── Clase Diátaxis de cada doc del repo ─────────────────────────────────────

def test_todo_doc_de_docs_tiene_su_clase_registrada():
    from vault_registry import DOCS_DEL_REPO, DOCUMENTACION_CLASES

    en_disco = {p.name for p in DOCS.glob("*.md")}
    assert en_disco == set(DOCS_DEL_REPO), (
        f"sin clase: {sorted(en_disco - set(DOCS_DEL_REPO))}; "
        f"registrados sin fichero: {sorted(set(DOCS_DEL_REPO) - en_disco)}")
    for rel, (clase, motivo) in DOCS_DEL_REPO.items():
        assert clase in DOCUMENTACION_CLASES and motivo.strip(), rel


def test_cada_clase_diataxis_tiene_doc_o_hueco_declarado():
    from vault_registry import DIATAXIS, DOCS_DEL_REPO, HUECOS_DOCS_DEL_REPO

    con_doc = {clase for clase, _ in DOCS_DEL_REPO.values()}
    for clase in DIATAXIS:
        assert (clase in con_doc) != (clase in HUECOS_DOCS_DEL_REPO), clase


def test_el_tutorial_existe_y_lo_enlazan_el_indice_y_el_readme():
    """The gap was saldado by writing the document and removing the entry
    (producto-usable S2): the index and the README send a newcomer to it."""
    from vault_registry import DOCS_DEL_REPO, HUECOS_DOCS_DEL_REPO

    assert "tutorial" not in HUECOS_DOCS_DEL_REPO
    assert DOCS_DEL_REPO["TUTORIAL.md"][0] == "tutorial"
    assert "](TUTORIAL.md)" in (DOCS / "README.md").read_text(encoding="utf-8")
    assert "](./docs/TUTORIAL.md)" in (RAIZ / "README.md").read_text(encoding="utf-8")

"""AP-79: the audit measures how far each note goes from its lead to its detail.

A layered note opens with a self-sufficient lead (what it is, why it matters,
its state, where it comes from) and grows `## Contexto`, `## Detalle` and
`## Fuentes` with knowledge. The criterion belongs to the kernel owner
(`vault.kernel.contenido.profundidad_de_nota`); `vault_audit` only reads it:
an article without a lead is listed, an event record (a `registro` section)
may be short and is listed only without a lead and without any wikilink.
Informative: no row in `PENALIZACIONES`, so the health numbers never move.
"""

import pytest

from apoyo import correr_tool, escribir_nota

#: Two sentences and more than twenty real words: a self-sufficient lead.
LEAD = ("El servicio de cobros concilia cada pago con su factura antes del cierre "
        "diario del libro mayor. Importa porque un pago sin conciliar bloquea el "
        "informe fiscal mensual y lo mantiene el equipo de finanzas.")

ESCALONADA = f"""# Cobros

{LEAD}

## Contexto

Sustituye a la conciliación manual que se hacía en una hoja de cálculo.

## Fuentes

- [[nota-delgada]]
"""


def _vault(raiz):
    for seccion in ("00_System", "04_Sessions", "07_Knowledge", "99_Index"):
        (raiz / seccion).mkdir(parents=True)
    escribir_nota(raiz, "07_Knowledge/nota-delgada.md",
                  {"title": "Nota delgada", "type": "knowledge"},
                  "# Nota delgada\n\nUna línea corta.\n")
    escribir_nota(raiz, "07_Knowledge/cobros.md",
                  {"title": "Cobros", "type": "knowledge"}, ESCALONADA)
    escribir_nota(raiz, "04_Sessions/2026-11-19-enlazada.md",
                  {"title": "Sesión enlazada", "type": "session"},
                  "# Sesión enlazada\n\nSe revisó [[cobros]].\n")
    escribir_nota(raiz, "04_Sessions/2026-11-19-suelta.md",
                  {"title": "Sesión suelta", "type": "session"},
                  "# Sesión suelta\n\nSe revisó algo.\n")
    escribir_nota(raiz, "07_Knowledge/00-07_knowledge-primer.md",
                  {"title": "Primer", "type": "primer", "scaffold": True},
                  "# Primer\n\nAndamio.\n")
    escribir_nota(raiz, "07_Knowledge/plantilla.md",
                  {"title": "Plantilla", "type": "knowledge", "status": "template"},
                  "# Plantilla\n\nTexto.\n")
    return raiz


@pytest.fixture(scope="module")
def auditoria(tmp_path_factory):
    raiz = _vault(tmp_path_factory.mktemp("ap79") / "v")
    corrida = correr_tool("vault_audit", vault=raiz)
    assert corrida.codigo == 0, corrida.stderr[-1500:]
    return corrida.envelope


def _sin_lead(envelope):
    return {h["path"]: h for h in envelope["issues"]["notesWithoutLead"]}


def test_ap79_un_articulo_delgado_se_lista(auditoria):
    hallazgo = _sin_lead(auditoria)["07_Knowledge/nota-delgada.md"]
    assert hallazgo["norm_code"] == "AP-79"
    assert hallazgo["kind"] == "article"
    assert hallazgo["type"] == "knowledge"
    assert hallazgo["nivel"] == 0
    assert hallazgo["lead_words"] < 20


def test_ap79_un_articulo_con_lead_no_se_lista(auditoria):
    assert "07_Knowledge/cobros.md" not in _sin_lead(auditoria)
    profundidad = auditoria["notesDepth"]
    assert profundidad["norm"] == "AP-79"
    assert profundidad["byLevel"]["3"] == 1  # lead + Contexto + Fuentes


def test_ap79_un_registro_enlazado_no_se_lista_y_uno_suelto_si(auditoria):
    """AP-79: an event record may be short when it links to its parent note."""
    hallazgos = _sin_lead(auditoria)
    assert "04_Sessions/2026-11-19-enlazada.md" not in hallazgos
    suelta = hallazgos["04_Sessions/2026-11-19-suelta.md"]
    assert suelta["kind"] == "record"
    assert suelta["links"] == 0


def test_ap79_andamio_y_plantilla_quedan_fuera(auditoria):
    hallazgos = _sin_lead(auditoria)
    assert "07_Knowledge/00-07_knowledge-primer.md" not in hallazgos
    assert "07_Knowledge/plantilla.md" not in hallazgos
    # AP-79: four measured notes — two articles and two records.
    profundidad = auditoria["notesDepth"]
    assert profundidad["checked"] == 4
    assert sum(profundidad["byLevel"].values()) == 4


def test_ap79_recuentos_por_tipo_y_mediana(auditoria):
    profundidad = auditoria["notesDepth"]
    assert profundidad["articlesWithoutLead"] == 1  # AP-79
    assert profundidad["recordsWithoutLeadOrLink"] == 1
    assert profundidad["byType"]["knowledge"]["checked"] == 2
    assert profundidad["byType"]["knowledge"]["withoutLead"] == 1
    assert profundidad["byType"]["session"]["checked"] == 2
    assert profundidad["byType"]["session"]["withoutLead"] == 1
    assert profundidad["criterion"]["lead_min_sentences"] == 2
    assert profundidad["criterion"]["lead_min_words"] == 20
    assert isinstance(profundidad["medianLeadWords"], (int, float))
    assert auditoria["stats"]["notesWithoutLead"] == 2


def test_ap79_acciones_apuntan_al_comando_y_nombran_las_capas(auditoria):
    from vault_registry import comando_de_tool

    acciones = {a["path"]: a for a in auditoria["nextActions"] if a.get("norm") == "AP-79"}
    assert set(acciones) == {"07_Knowledge/nota-delgada.md",
                             "04_Sessions/2026-11-19-suelta.md"}
    delgada = acciones["07_Knowledge/nota-delgada.md"]
    assert delgada["category"] == "note_without_lead"
    assert delgada["command"] == comando_de_tool(
        "vault_write --folder 07_Knowledge --title 'Nota delgada' --content '...'")
    for capa in ("Contexto", "Detalle", "Fuentes"):
        assert capa in delgada["description"]
    assert "[[" in acciones["04_Sessions/2026-11-19-suelta.md"]["description"]


def test_ap79_las_acciones_tienen_tope(tmp_path):
    import vault_audit

    raiz = tmp_path / "v"
    for seccion in ("00_System", "07_Knowledge"):
        (raiz / seccion).mkdir(parents=True)
    total = vault_audit.MAX_ACCIONES_DE_PROFUNDIDAD + 3
    for i in range(total):
        escribir_nota(raiz, f"07_Knowledge/corta-{i}.md",
                      {"title": f"Corta {i}", "type": "knowledge"}, f"# Corta {i}\n\nPoco.\n")
    envelope = correr_tool("vault_audit", vault=raiz).envelope
    acciones = [a for a in envelope["nextActions"] if a.get("norm") == "AP-79"]
    assert len(acciones) == vault_audit.MAX_ACCIONES_DE_PROFUNDIDAD
    assert len(envelope["issues"]["notesWithoutLead"]) == total


def test_ap79_la_salud_no_cambia_con_el_detector(tmp_path, monkeypatch):
    """AP-79 is informative: healthScore, families and healthIndex stay identical."""
    import vault_audit
    import vault_io

    raiz = _vault(tmp_path / "v")
    previo = vault_io.set_vault_root(raiz)
    try:
        con = vault_audit.vault_audit()
        assert con["issues"]["notesWithoutLead"]
        monkeypatch.setattr(vault_audit, "_detect_profundidad",
                            lambda notas: ({"norm": "AP-79", "checked": 0}, []))
        sin = vault_audit.vault_audit()
    finally:
        vault_io.set_vault_root(previo)
    for campo in ("healthScore", "healthIndex", "healthProfile", "penalties", "summary"):
        assert con[campo] == sin[campo], campo

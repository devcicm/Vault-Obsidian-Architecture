"""The layered note (nota-escalonada S4): one kernel owner for the lead and the depth.

A note read by a human auditor or an external agent without context starts
with a lead that stands alone (what it is, why it matters, its state, where it
comes from), like a Wikipedia lead, and grows into `## Contexto`, `## Detalle`
and `## Fuentes`. The generators compose it and the audit measures it with the
same functions, so the note a tool writes is the note the audit accepts.
"""

from vault.kernel import contenido as c

LEAD = ("La cola de eventos usa NATS JetStream desde marzo de 2026. "
        "Reemplazo a Redis Streams porque el equipo necesitaba retencion por tiempo "
        "y reproceso de consumidores durables.")


def test_el_lead_es_el_parrafo_entre_el_titulo_y_la_primera_seccion():
    cuerpo = f"# Cola de eventos\n\n{LEAD}\n\n## Contexto\n\nAntes era Redis.\n"
    assert c.lead_de(cuerpo) == LEAD


def test_la_procedencia_en_cita_y_los_metadatos_no_son_lead():
    cuerpo = ("# Sesion\n\n> Stub generado por vault_onboard el 2026-11-19.\n\n"
              "**Periodo:** 2026-11-01 -> 2026-11-28\n\n## Cambios\n\n- uno\n")
    assert c.lead_de(cuerpo) == ""


def test_sin_titulo_el_lead_empieza_en_la_primera_linea():
    assert c.lead_de(f"{LEAD}\n\n## Detalle\n\nx\n") == LEAD


def test_la_profundidad_cuenta_lead_capas_y_enlaces():
    cuerpo = (f"# T\n\n{LEAD}\n\n## Contexto\n\nVer [[redis-streams]] y [[nats]].\n\n"
              "## Detalle\n\nTexto.\n\n## Fuentes\n\n- commit abc\n")
    p = c.profundidad_de_nota(cuerpo)
    assert p["tiene_lead"] is True and p["lead_oraciones"] == 2
    assert p["capas"] == ["Contexto", "Detalle", "Fuentes"]
    assert p["enlaces"] == 2 and p["nivel"] == 3


def test_un_lead_de_una_frase_corta_no_alcanza():
    p = c.profundidad_de_nota("# T\n\nUsamos NATS.\n\n## Detalle\n\nx y z\n")
    assert p["tiene_lead"] is False and p["nivel"] == 0


def test_las_capas_se_reconocen_sin_tildes_ni_mayusculas():
    p = c.profundidad_de_nota(f"# T\n\n{LEAD}\n\n## contexto\n\nx\n")
    assert p["capas"] == ["Contexto"] and p["nivel"] == 2


def test_el_compositor_escribe_titulo_lead_capas_y_lo_que_falta():
    nota = c.nota_escalonada("Cola de eventos", LEAD, contexto="Antes era Redis.",
                             fuentes="- commit abc", falta="la decision original del equipo")
    assert nota.startswith(f"# Cola de eventos\n\n{LEAD}")
    assert "## Contexto\n\nAntes era Redis." in nota and "## Fuentes\n\n- commit abc" in nota
    assert "## Detalle" not in nota  # a layer without content is not written (AP-45)
    assert "> _Pendiente: la decision original del equipo._" in nota
    p = c.profundidad_de_nota(nota)
    assert p["tiene_lead"] and p["capas"] == ["Contexto", "Fuentes"]


def test_lo_que_falta_no_cuenta_como_evidencia():
    """AP-45 is not weakened: the stub's missing-line is a pending marker."""
    nota = c.nota_escalonada("T", LEAD, falta="todo lo demas")
    assert "todo lo demas" not in c.cuerpo_sin_marcadores(nota)


def test_las_palabras_reales_son_las_del_content_gate():
    """One owner for the real-word count (AP-57): the gate and the measure agree."""
    assert c.palabras_reales("# Titulo\n- a uno, dos;\n| x | tres |") == ["Titulo", "uno", "dos", "tres"]

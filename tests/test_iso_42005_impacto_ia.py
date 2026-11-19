"""ISO/IEC 42005 — the full impact assessment per affected party (AP-78).

`vault_ai_decision --affected` records who a decision affects (AP-65). The
full assessment of ISO/IEC 42005 also records, for each affected party, how
likely the harm is, how severe it is and how it is mitigated. `--assessment`
carries that, on the likelihood and impact scales of `vault_risk_save`
(1-5, the same labels), validated by the tool; the note records it in its
"Evaluacion de Impacto" table and declares `evaluacion_por_afectado`. A
decision that does not use the new option is written exactly as before.

AP-78 is the audit work list: a high-impact decision whose affected parties
lack that assessment. Every test drives the CLI or the audit function and
reads what lands on disk.
"""

import json
from pathlib import Path

import pytest
import yaml

from apoyo import correr_tool, escribir_nota

import vault_io

DECISION = ("--decision_type", "process",
            "--description", "Colas con reintento acotado.",
            "--rationale", "No perder mensajes sin saturar al consumidor.")


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "v"
    for seccion in ("00_System", "01_Projects", "16_AI_Governance", "99_Index"):
        (raiz / seccion).mkdir(parents=True)
    assert correr_tool("vault_project", "--add", "demo", vault=raiz).envelope["ok"]
    return raiz


def _decidir(raiz, titulo, impacto, *extra):
    return correr_tool("vault_ai_decision", "--project", "demo", "--title", titulo,
                       "--impact_level", impacto, *DECISION, *extra, vault=raiz)


def _fm(raiz, rel):
    texto = (raiz / rel).read_text(encoding="utf-8")
    return yaml.safe_load(texto.split("---", 2)[1]), texto.split("---", 2)[2]


def _indice(raiz):
    datos = json.loads((raiz / "16_AI_Governance/.decisions-log.json").read_text(encoding="utf-8"))
    return datos["decisions"]


EVALUACION = [
    {"affected": "consumidores de la cola", "likelihood": 3, "impact": 4,
     "mitigation": "Reintento con backoff y alerta de latencia"},
    {"affected": "equipo de guardia", "likelihood": 2, "impact": 2,
     "mitigation": "Runbook de vaciado manual | revisado"},
]


# ── The tool records the assessment ──────────────────────────────────────────

def test_ap78_assessment_per_party_is_recorded_complete(vault):
    corrida = _decidir(vault, "Reintento evaluado", "high",
                       "--assessment", json.dumps(EVALUACION))
    sobre = corrida.envelope
    assert corrida.codigo == 0 and sobre["ok"] is True
    assert sobre["impact_assessment"] == "completa"
    assert sobre["evaluacion_por_afectado"] == "completa"
    assert "hint" not in sobre
    fm, cuerpo = _fm(vault, sobre["path"])
    assert fm["impact_assessment"] == "completa"
    assert fm["evaluacion_por_afectado"] == "completa"
    assert "| Afectado | Probabilidad | Severidad | Mitigación |" in cuerpo
    assert ("| consumidores de la cola | 3/5 Posible | 4/5 Mayor | "
            "Reintento con backoff y alerta de latencia |") in cuerpo
    # A pipe in the text cannot break the table.
    assert "| equipo de guardia | 2/5 Improbable | 2/5 Menor | " \
           "Runbook de vaciado manual \\| revisado |" in cuerpo
    entrada = next(d for d in _indice(vault) if d["relPath"] == sobre["path"])
    assert entrada["evaluacion_por_afectado"] == "completa"


def test_ap78_affected_without_assessment_is_partial_and_said(vault):
    corrida = _decidir(vault, "Reintento a medias", "critical",
                       "--affected", json.dumps(["consumidores de la cola", "auditoría"]),
                       "--assessment", json.dumps(EVALUACION[:1]))
    sobre = corrida.envelope
    assert corrida.codigo == 0 and sobre["evaluacion_por_afectado"] == "parcial"
    assert "auditoría" in sobre["hint"] and "AP-78" in sobre["hint"]
    fm, cuerpo = _fm(vault, sobre["path"])
    assert fm["evaluacion_por_afectado"] == "parcial"
    assert "- auditoría" in cuerpo
    # The party is listed once even when named by both options.
    assert cuerpo.count("consumidores de la cola") == 1


@pytest.mark.parametrize("entrada,codigo", [
    ({"affected": "x", "likelihood": 0, "impact": 3, "mitigation": "m"}, "INVALID_LIKELIHOOD"),
    ({"affected": "x", "likelihood": "3", "impact": 3, "mitigation": "m"}, "INVALID_LIKELIHOOD"),
    ({"affected": "x", "likelihood": 3, "impact": 6, "mitigation": "m"}, "INVALID_IMPACT"),
    ({"affected": "x", "likelihood": 3, "impact": True, "mitigation": "m"}, "INVALID_IMPACT"),
    ({"affected": "x", "likelihood": 3, "impact": 3, "mitigation": "  "}, "INVALID_VALUE"),
    ({"affected": "", "likelihood": 3, "impact": 3, "mitigation": "m"}, "INVALID_VALUE"),
    ("solo texto", "INVALID_VALUE"),
])
def test_ap78_invalid_assessment_is_refused_and_writes_nothing(vault, entrada, codigo):
    corrida = _decidir(vault, "Reintento mal evaluado", "high",
                       "--assessment", json.dumps([entrada]))
    sobre = corrida.envelope
    assert corrida.codigo == 1 and sobre["ok"] is False
    assert sobre["error_code"] == codigo
    assert not (vault / "16_AI_Governance/decisions").exists() or \
        not list((vault / "16_AI_Governance/decisions").glob("*.md"))
    assert not (vault / "16_AI_Governance/.decisions-log.json").exists()


def test_ap78_assessment_that_is_not_a_list_is_refused(vault):
    corrida = _decidir(vault, "Reintento sin lista", "high",
                       "--assessment", json.dumps({"affected": "x"}))
    assert corrida.codigo == 1 and corrida.envelope["error_code"] == "INVALID_VALUE"


def test_ap78_previous_behavior_without_the_option_is_unchanged(vault):
    """`--affected` alone writes what it wrote before: no new field, no new key."""
    corrida = _decidir(vault, "Reintento con afectados", "critical",
                       "--affected", json.dumps(["consumidores de la cola - latencia mayor"]))
    sobre = corrida.envelope
    assert corrida.codigo == 0 and sobre["impact_assessment"] == "completa"
    assert "evaluacion_por_afectado" not in sobre and "hint" not in sobre
    fm, cuerpo = _fm(vault, sobre["path"])
    assert "evaluacion_por_afectado" not in fm
    assert "A quién afecta:\n\n- consumidores de la cola - latencia mayor" in cuerpo
    assert "| Afectado |" not in cuerpo
    entrada = next(d for d in _indice(vault) if d["relPath"] == sobre["path"])
    assert "evaluacion_por_afectado" not in entrada


def test_ap78_scales_are_the_risk_owner_scales():
    import vault_ai_decision
    import vault_risk_save

    assert vault_ai_decision.LIKELIHOOD_LABELS is vault_risk_save.LIKELIHOOD_LABELS
    assert vault_ai_decision.IMPACT_LABELS is vault_risk_save.IMPACT_LABELS


# ── AP-78: the audit work list ───────────────────────────────────────────────

@pytest.fixture
def vault_en_proceso(tmp_path):
    raiz = tmp_path / "a"
    for seccion in ("00_System", "07_Knowledge", "16_AI_Governance/decisions"):
        (raiz / seccion).mkdir(parents=True)
    previo = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previo)


def _decision(raiz, nombre, **fm):
    base = {"title": nombre, "type": "ai-decision", "status": "draft"}
    escribir_nota(raiz, f"16_AI_Governance/decisions/{nombre}.md", {**base, **fm},
                  f"# {nombre}\n\nTexto de la decisión con su porqué.\n")


def test_ap78_audit_lists_high_impact_decisions_without_party_assessment(vault_en_proceso):
    import vault_audit

    raiz = vault_en_proceso
    _decision(raiz, "solo-afectados", impact_level="high", impact_assessment="completa")
    _decision(raiz, "parcial", impact_level="critical", impact_assessment="completa",
              evaluacion_por_afectado="parcial")
    _decision(raiz, "evaluada", impact_level="high", impact_assessment="completa",
              evaluacion_por_afectado="completa")
    _decision(raiz, "menor", impact_level="low", impact_assessment="completa")
    # AP-65's case, not AP-78's: it does not even say who is affected.
    _decision(raiz, "pendiente", impact_level="high", impact_assessment="pendiente")
    _decision(raiz, "plantilla", impact_level="high", impact_assessment="completa",
              status="template")
    escribir_nota(raiz, "07_Knowledge/fuera.md",
                  {"title": "fuera", "impact_level": "high", "impact_assessment": "completa"},
                  "# fuera\n\nNo es una decisión de IA.\n")

    lista = vault_audit.vault_audit()["aiDecisionsWithoutPartyAssessment"]
    assert lista["norm"] == "AP-78"
    assert lista["checked"] == 3
    marcadas = {d["path"]: d for d in lista["missing"]}
    assert set(marcadas) == {"16_AI_Governance/decisions/solo-afectados.md",
                             "16_AI_Governance/decisions/parcial.md"}
    assert all(d["norm"] == "AP-78" for d in marcadas.values())
    assert marcadas["16_AI_Governance/decisions/parcial.md"]["evaluacion_por_afectado"] == "parcial"
    assert marcadas["16_AI_Governance/decisions/solo-afectados.md"]["evaluacion_por_afectado"] is None


def test_ap78_audit_reads_what_the_tool_writes(vault):
    """End to end: the tool's two outcomes, seen by the audit."""
    _decidir(vault, "Sin detalle", "high", "--affected", json.dumps(["usuarios"]))
    _decidir(vault, "Con detalle", "high", "--assessment", json.dumps(EVALUACION))
    previo = vault_io.set_vault_root(vault)
    try:
        import vault_audit

        lista = vault_audit.vault_audit()["aiDecisionsWithoutPartyAssessment"]
    finally:
        vault_io.set_vault_root(previo)
    assert [Path(d["path"]).name for d in lista["missing"]] == ["demo-sin-detalle.md"]

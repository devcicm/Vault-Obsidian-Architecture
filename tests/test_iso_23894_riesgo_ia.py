"""ISO/IEC 23894 — AI risks with their identify, assess, treat and review cycle.

`vault_risk_save` is the risk owner. It gains the `ai` risk type and an
optional review cadence (`--review_every_days`): the note then declares
`revisado_en` and `cadencia_dias`, the same contract the rest of the vault
uses for reviews (AP-76), and an AI risk always gets one (90 days unless
said). Saving the risk again is the review: the date moves to today and the
history keeps every earlier row. A risk that does not use the cadence is
written exactly as before.

`vault_audit` publishes the work list of AI risks whose review is overdue,
with the review arithmetic of its single owner
(`vault_norms_catalog.estado_de_revision`). Read-only: overdue is work, not
failure.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
import yaml

from apoyo import correr_tool, escribir_nota

import vault_io

# The tool dates reviews with `vault_lib.utcnow` (UTC). `date.today()` is the
# local date, which differs from UTC near midnight and made these tests fail
# between 18:00 and 24:00 in UTC-6 (2026-11-18).
HOY = datetime.now(timezone.utc).date()


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "v"
    for seccion in ("00_System", "01_Projects", "02_Observability", "99_Index"):
        (raiz / seccion).mkdir(parents=True)
    assert correr_tool("vault_project", "--add", "demo", vault=raiz).envelope["ok"]
    return raiz


def _riesgo(raiz, titulo, *extra):
    return correr_tool("vault_risk_save", "--project", "demo", "--title", titulo,
                       "--likelihood", "3", "--impact", "4", "--owner", "ana",
                       *extra, vault=raiz)


def _partes(raiz, rel):
    texto = (raiz / rel).read_text(encoding="utf-8")
    _, fm, cuerpo = texto.split("---", 2)
    return yaml.safe_load(fm), cuerpo


def _fecha(valor):
    return valor.isoformat() if isinstance(valor, date) else str(valor)


# ── The risk owner records the AI risk and its review ────────────────────────

def test_23894_ai_risk_gets_the_default_review_cadence(vault):
    corrida = _riesgo(vault, "Deriva del modelo de clasificación", "--risk_type", "ai",
                      "--threat", "El modelo clasifica peor con datos nuevos",
                      "--treatment", "mitigate", "--controls", '["Monitor de deriva"]')
    sobre = corrida.envelope
    assert corrida.codigo == 0 and sobre["ok"] is True
    assert sobre["risk_type"] == "ai"
    proxima = (HOY + timedelta(days=90)).isoformat()
    assert sobre["review"] == {"revisado_en": HOY.isoformat(), "cadencia_dias": 90,
                               "vence_en": proxima}
    fm, cuerpo = _partes(vault, sobre["path"])
    assert _fecha(fm["revisado_en"]) == HOY.isoformat()
    assert fm["cadencia_dias"] == 90
    assert fm["iso_ai_risk"] == "ISO/IEC 23894:2023"
    # identify -> assess -> treat -> review, all in the record
    assert "## Amenaza" in cuerpo and "## Análisis de riesgo" in cuerpo
    assert "## Controles de tratamiento" in cuerpo and "## Historial de revisiones" in cuerpo
    assert f"Próxima revisión: **{proxima}** (cada 90 días" in cuerpo
    assert "ISO/IEC 23894:2023" in cuerpo


def test_23894_explicit_cadence_on_any_risk_type(vault):
    sobre = _riesgo(vault, "Proveedor cloud cae", "--risk_type", "operational",
                    "--review_every_days", "30").envelope
    assert sobre["review"]["cadencia_dias"] == 30
    fm, _ = _partes(vault, sobre["path"])
    assert fm["cadencia_dias"] == 30 and _fecha(fm["revisado_en"]) == HOY.isoformat()
    assert "iso_ai_risk" not in fm


@pytest.mark.parametrize("valor", ["0", "-5"])
def test_23894_cadence_must_be_positive_and_nothing_is_written(vault, valor):
    corrida = _riesgo(vault, "Cadencia inválida", "--risk_type", "ai",
                      "--review_every_days", valor)
    assert corrida.codigo == 1
    assert corrida.envelope["error_code"] == "INVALID_VALUE"
    assert not list((vault / "02_Observability").rglob("*cadencia-invalida*.md"))


def test_23894_previous_behavior_without_cadence_is_unchanged(vault):
    """A non-AI risk without the option declares no review fields at all."""
    sobre = _riesgo(vault, "SQL injection en búsqueda", "--risk_type", "security").envelope
    assert "review" not in sobre
    fm, cuerpo = _partes(vault, sobre["path"])
    assert "revisado_en" not in fm and "cadencia_dias" not in fm
    assert "Próxima revisión" not in cuerpo and "23894" not in cuerpo


def test_23894_saving_again_is_the_review_and_keeps_the_history(vault):
    sobre = _riesgo(vault, "Sesgo en el ranking", "--risk_type", "ai").envelope
    ruta = vault / sobre["path"]
    # Simulate that the risk was identified 100 days ago.
    antes = (HOY - timedelta(days=100)).isoformat()
    texto = ruta.read_text(encoding="utf-8")
    texto = texto.replace(f"revisado_en: '{HOY.isoformat()}'", f"revisado_en: '{antes}'")
    texto = texto.replace(f"revisado_en: {HOY.isoformat()}", f"revisado_en: {antes}")
    texto = texto.replace(f"| {HOY.isoformat()} | ana | Riesgo identificado",
                          f"| {antes} | ana | Riesgo identificado")
    ruta.write_bytes(texto.encode("utf-8"))  # Python 3.9 floor: no write_text(newline=)

    corrida = correr_tool("vault_risk_save", "--project", "demo", "--title", "Sesgo en el ranking",
                          "--risk_type", "ai", "--likelihood", "2", "--impact", "4",
                          "--owner", "ana", "--treatment", "mitigate", vault=vault)
    assert corrida.codigo == 0
    fm, cuerpo = _partes(vault, sobre["path"])
    assert _fecha(fm["revisado_en"]) == HOY.isoformat()
    assert f"| {antes} | ana | Riesgo identificado |" in cuerpo
    assert (f"| {HOY.isoformat()} | ana | Riesgo revisado: probabilidad 2 × impacto 4 "
            "= 8 (Medium), tratamiento mitigate |") in cuerpo


def test_23894_ai_is_a_closed_risk_type():
    import vault_risk_save

    assert "ai" in vault_risk_save.RISK_TYPES
    assert vault_risk_save.CADENCIA_RIESGO_IA_POR_DEFECTO == 90


# ── The work list of overdue AI risk reviews ─────────────────────────────────

@pytest.fixture
def vault_en_proceso(tmp_path):
    raiz = tmp_path / "a"
    for seccion in ("00_System", "02_Observability/risks", "07_Knowledge"):
        (raiz / seccion).mkdir(parents=True)
    previo = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previo)


def _nota_riesgo(raiz, nombre, **fm):
    base = {"title": f"Riesgo: {nombre}", "type": "risk", "status": "in-progress",
            "risk_state": "open", "owner": "ana"}
    escribir_nota(raiz, f"02_Observability/risks/{nombre}.md", {**base, **fm},
                  f"# Riesgo: {nombre}\n\nTexto del riesgo con su análisis.\n")


def test_23894_audit_lists_overdue_ai_risk_reviews(vault_en_proceso):
    import vault_audit

    raiz = vault_en_proceso
    viejo = (HOY - timedelta(days=200)).isoformat()
    _nota_riesgo(raiz, "vencido", risk_type="ai", revisado_en=viejo, cadencia_dias=90)
    _nota_riesgo(raiz, "al-dia", risk_type="ai", revisado_en=HOY.isoformat(), cadencia_dias=90)
    _nota_riesgo(raiz, "no-es-ia", risk_type="operational", revisado_en=viejo, cadencia_dias=90)
    _nota_riesgo(raiz, "cerrado", risk_type="ai", risk_state="closed", status="archived",
                 revisado_en=viejo, cadencia_dias=90)
    _nota_riesgo(raiz, "sin-fecha", risk_type="ai")
    _nota_riesgo(raiz, "ilegible", risk_type="ai", revisado_en="ayer", cadencia_dias=90)

    lista = vault_audit.vault_audit()["aiRisksReviewOverdue"]
    assert lista["norm"] == "AP-76"
    assert lista["checked"] == 4
    assert [d["path"] for d in lista["overdue"]] == ["02_Observability/risks/vencido.md"]
    vencido = lista["overdue"][0]
    assert vencido["owner"] == "ana" and vencido["vencida"] is True
    assert vencido["vence_en"] == (HOY - timedelta(days=110)).isoformat()
    assert lista["without_review"] == ["02_Observability/risks/sin-fecha.md"]
    assert [d["path"] for d in lista["unreadable"]] == ["02_Observability/risks/ilegible.md"]


def test_23894_audit_uses_the_review_arithmetic_owner(vault_en_proceso, monkeypatch):
    """The arithmetic is not re-implemented: patching its owner changes the list."""
    import vault_audit
    import vault_norms_catalog

    _nota_riesgo(vault_en_proceso, "al-dia", risk_type="ai",
                 revisado_en=HOY.isoformat(), cadencia_dias=90)
    llamadas = []
    original = vault_norms_catalog.estado_de_revision

    def espia(*args, **kwargs):
        llamadas.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(vault_norms_catalog, "estado_de_revision", espia)
    vault_audit.vault_audit()
    assert llamadas and llamadas[0][1] == 90

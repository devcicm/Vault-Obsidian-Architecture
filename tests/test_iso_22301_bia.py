"""ISO 22301 §8.2.2: the recovery runbook carries the business impact analysis.

`vault_runbook_save --bia` records the critical function, its impact, RTO, RPO
and MTPD on the runbook that recovers it. Approving the continuity plan stays
the organization's act.
"""

import json

import pytest
import yaml

from apoyo import correr_tool
from vault.kernel.normativa import procesos_iso as pi

BIA = {"critical_function": "checkout", "impact": "ventas perdidas",
       "rto": "4h", "rpo": "15min", "mtpd": "1d"}


@pytest.fixture(scope="module")
def vault(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("iso22301")
    assert correr_tool("vault_init", vault=raiz).codigo == 0
    assert correr_tool("vault_project", "--add", "demo", vault=raiz).codigo == 0
    return raiz


def _runbook(vault, titulo, *extra):
    return correr_tool("vault_runbook_save", "--project", "demo", "--title", titulo,
                       "--trigger", "Checkout caido", "--category", "incident",
                       "--steps", '[{"step": "Restaurar la base"}]', *extra, vault=vault)


def _frontmatter(ruta):
    return yaml.safe_load(ruta.read_text(encoding="utf-8").split("---")[1])


@pytest.mark.parametrize("texto, minutos", [
    ("30min", 30), ("30m", 30), ("4h", 240), ("1.5h", 90), ("2d", 2880), ("1w", 10080),
    ("4 horas", None), ("", None), (None, None),
])
def test_iso_22301_durations(texto, minutos):
    assert pi.duracion_en_minutos(texto) == minutos


@pytest.mark.parametrize("bia, problema", [
    ([], "JSON object"),
    ({"impact": "x"}, "critical_function is required"),
    ({"critical_function": "x", "owner": "y"}, "unknown BIA fields: ['owner']"),
    ({"critical_function": "x", "rto": "pronto"}, "rto must be a duration"),
    ({"critical_function": "x", "rto": "2d", "mtpd": "1d"}, "rto (2d) exceeds mtpd (1d)"),
])
def test_iso_22301_invalid_bia_is_named(bia, problema):
    assert any(problema in p for p in pi.validar_bia(bia))


def test_iso_22301_runbook_records_the_bia(vault):
    r = _runbook(vault, "Restaurar checkout", "--bia", json.dumps(BIA))
    assert r.codigo == 0
    e = r.envelope
    assert e["ok"] is True and e["bia"] == BIA
    nota = vault / e["path"]
    fm = _frontmatter(nota)
    assert {k: fm[f"bia_{k}"] for k in BIA} == BIA
    assert fm["iso_bcm"] == "ISO 22301:2019 §8.2.2"
    texto = nota.read_text(encoding="utf-8")
    assert "## Análisis de impacto (BIA)" in texto
    assert "| **rto** | 4h |" in texto and "| **mtpd** | 1d |" in texto


def test_iso_22301_invalid_bia_is_rejected_and_writes_nothing(vault):
    malo = dict(BIA, rto="2d")
    r = _runbook(vault, "Runbook invalido", "--bia", json.dumps(malo))
    assert r.codigo == 1
    assert r.envelope["error_code"] == "INVALID_VALUE"
    assert "rto (2d) exceeds mtpd (1d)" in r.envelope["message"]
    assert not (vault / "08_Runbooks" / "incident" / "demo-runbook-invalido.md").exists()


def test_iso_22301_bia_that_is_not_json_is_rejected(vault):
    r = _runbook(vault, "Runbook roto", "--bia", "{critical_function")
    assert r.codigo == 1 and r.envelope["error_code"] == "ARG_JSON_INVALID"
    assert not (vault / "08_Runbooks" / "incident" / "demo-runbook-roto.md").exists()


def test_iso_22301_runbook_without_bia_is_unchanged(vault):
    """Previous behavior: no BIA key in the envelope, frontmatter or body."""
    r = _runbook(vault, "Sin analisis")
    assert r.codigo == 0
    assert "bia" not in r.envelope
    nota = vault / r.envelope["path"]
    fm = _frontmatter(nota)
    assert not any(k.startswith("bia_") for k in fm) and "iso_bcm" not in fm
    assert "Análisis de impacto" not in nota.read_text(encoding="utf-8")

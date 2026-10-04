"""Las tools tipadas firman con `VAULT_AGENT` y dejan la nota completa (AP-16, AP-26).

Medido el 2026-10-04 en un vault recién creado solo con las tools oficiales:
healthScore 57 sin una sola nota escrita a mano. `vault_write` honraba
`VAULT_AGENT`, pero `knowledge_save`, `runbook_save`, `ai_decision` y
`project_overview` escribían `agent: system` siempre, y bibliografía, runbook,
decisión y conocimiento salían sin `type`, `status`, `tags` o `updatedAt` —
penalizados por la auditoría del mismo estándar que los escribió.
"""

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402
from vault.autoria.frontmatter import firmante  # noqa: E402
from vault_norms_catalog import STATUS_VOCAB  # noqa: E402

CAMPOS = ("agent", "type", "status", "tags", "updatedAt")


@pytest.fixture
def vault(tmp_path, monkeypatch):
    previo = vault_io.get_vault_root()
    vault_io.set_vault_root(tmp_path)
    monkeypatch.setenv("VAULT_AGENT", "probe")
    import vault_project_overview

    r = vault_project_overview.vault_project_overview("demo", description="Demo.")
    assert r["ok"] is True, r
    yield tmp_path
    vault_io.set_vault_root(previo)


def _fm(vault, rel):
    texto = (vault / rel).read_text(encoding="utf-8")
    return yaml.safe_load(texto.split("---", 2)[1])


def _escrituras():
    import vault_ai_decision
    import vault_bibliography_save
    import vault_knowledge_save
    import vault_runbook_save

    return {
        "knowledge": lambda: vault_knowledge_save.vault_knowledge_save(
            "concept", "JWT", "Token firmado.", project="demo", tags=["auth"]),
        "bibliography": lambda: vault_bibliography_save.vault_bibliography_save(
            "RFC 7519", "https://www.rfc-editor.org/rfc/rfc7519", "JWT.", "web",
            project="demo", tags=["auth"]),
        "runbook": lambda: vault_runbook_save.vault_runbook_save(
            "demo", "Rotar claves", "caducidad", "maintenance",
            [{"action": "Generar clave"}]),
        "ai_decision": lambda: vault_ai_decision.vault_ai_decision(
            "demo", "Usar JWT", "architectural", "Sesiones sin estado.", "Escala."),
    }


@pytest.mark.parametrize("tool", ["knowledge", "bibliography", "runbook", "ai_decision"])
def test_la_tool_tipada_firma_con_vault_agent_y_completa_la_nota(vault, tool):
    r = _escrituras()[tool]()
    assert r["ok"] is True, r
    fm = _fm(vault, r["path"])
    faltan = [c for c in CAMPOS if not fm.get(c)]
    assert faltan == [], (tool, faltan, fm)
    assert fm["agent"] == "probe", fm
    assert isinstance(fm["tags"], list), fm["tags"]
    # CN-03: `runbook_save` escribía `status: active`, fuera del vocabulario.
    assert fm["status"] in STATUS_VOCAB, fm["status"]


def test_el_overview_firma_con_vault_agent(vault):
    fm = _fm(vault, "01_Projects/demo/overview.md")
    assert fm["agent"] == "probe"


def test_firmante_explicito_luego_variable_luego_system():
    assert firmante("a", {"VAULT_AGENT": "b"}) == "a"
    assert firmante(None, {"VAULT_AGENT": "b"}) == "b"
    assert firmante(None, {}) == "system"

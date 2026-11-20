"""Every note generator writes a layered note (nota-escalonada S3-S4, T6).

Measured on 2026-11-19: the seventeen `*_save` tools, `vault_code_module`,
`vault_ai_decision`, `vault_qa_save`, `vault_project_overview` and the
project card wrote their H1 and went straight to the first section. With the
minimal call of each tool not one note had a self-sufficient lead
(`contenido.profundidad_de_nota`), and no event record named the note it
belongs to: a reader without context opened `18_Bugs/open/...` and learnt
neither what the project was nor where to read about it.

The rule, through the public interface and on the written note:

- an article (a section whose documentation class is not `registro`) opens
  with a lead of at least two sentences and twenty real words, built from the
  arguments the tool received: its title is in the lead;
- an event record may stay short, but links its parent, the project card;
- what the tool does not know is a pending marker that the evidence
  criterion (AP-45, `cuerpo_sin_marcadores`) does not count;
- every section the tool wrote before the change is still there, by name.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from apoyo import correr_en_proceso
from vault.kernel.contenido import cuerpo_sin_marcadores, lead_de, profundidad_de_nota
from vault_lib import parse_frontmatter_with_body
from vault_registry import section_documentacion

PROYECTO = "demo"
#: The parent an event record names: the project card, in path form.
FICHA = f"[[01_Projects/{PROYECTO}/project|{PROYECTO}]]"

#: Minimal valid call of each generator, and the H2 sections it wrote on the
#: base commit with that call (measured on bd709ac2): the lead goes before the
#: first of them and none disappears.
CASOS = {
    "vault_bug_save": (
        ["--project", PROYECTO, "--title", "Excepción al guardar",
         "--symptom", "Revienta con acentuación en el título."],
        ["Síntoma", "Ciclo"]),
    "vault_diagram_save": (
        ["--project", PROYECTO, "--title", "Diagrama de migración",
         "--diagram_type", "mermaid", "--category", "component",
         "--content", "flowchart TD\n  A --> B"],
        ["Diagrama"]),
    "vault_flow_save": (
        ["--project", PROYECTO, "--name", "Alta de usuario", "--type", "workflow",
         "--description", "Cómo se da de alta.", "--mermaid", "flowchart TD\n  A --> B"],
        ["Descripcion", "Diagrama"]),
    "vault_infra_save": (
        ["--name", "servidor-de-índices", "--type", "server",
         "--description", "Máquina que sirve los índices.", "--config", '{"cpu": 4}'],
        ["Descripción", "Configuración"]),
    "vault_pattern_save": (
        ["--project", PROYECTO, "--name", "Repositorio por contexto",
         "--type", "architecture", "--status", "implementado"],
        []),
    "vault_requirement_save": (
        ["--project", PROYECTO, "--title", "Búsqueda por categoría",
         "--description", "El usuario busca por categoría.",
         "--type", "functional", "--priority", "must-have"],
        ["Descripcion", "Estado"]),
    "vault_runbook_save": (
        ["--project", PROYECTO, "--title", "Rotación de credenciales",
         "--trigger", "Cada noventa días", "--category", "maintenance",
         "--steps", '[{"step": "Generar la credencial nueva"}]'],
        ["Trigger", "Pasos", "Historial de Ejecuciones"]),
    "vault_test_save": (
        ["--project", PROYECTO, "--title", "Validación de acentos",
         "--test_type", "unit", "--description", "Comprueba la codificación."],
        ["Descripcion", "Estado"]),
    "vault_qa_save": (
        ["--project", PROYECTO, "--title", "Plan de pruebas del alta",
         "--type", "test-plan", "--description", "Qué se prueba del alta."],
        ["Descripción", "Estado"]),
    "vault_code_module": (
        ["--project", PROYECTO, "--file_path", "src/alta.py",
         "--description", "Da de alta a un usuario."],
        ["Proposito"]),
    "vault_ai_decision": (
        ["--project", PROYECTO, "--title", "Usar un índice por sección",
         "--decision_type", "architectural", "--description", "Un índice por sección.",
         "--rationale", "Regenerar uno no reescribe los demás."],
        ["Descripcion", "Justificacion"]),
    "vault_incident_save": (
        ["--project", PROYECTO, "--title", "Caída del índice"],
        ["Datos del incidente", "Impacto"]),
    "vault_ncr_save": (
        ["--project", PROYECTO, "--title", "Una no conformidad"],
        ["Datos de la no conformidad", "Historial"]),
    "vault_privacy_save": (
        ["--project", PROYECTO, "--title", "Un tratamiento",
         "--purpose", "Analítica interna", "--legal_basis", "consent"],
        ["Información del tratamiento", "Referencias"]),
    "vault_release_save": (
        ["--project", PROYECTO, "--version", "1.0.0"],
        ["Estado del release", "Cambios incluidos", "Procedimiento de rollback"]),
    "vault_risk_save": (
        ["--project", PROYECTO, "--title", "Un riesgo de migración"],
        ["Clasificación", "Amenaza", "Historial de revisiones"]),
    "vault_slo_save": (
        ["--project", PROYECTO, "--service", "api", "--slo_type", "availability",
         "--target", "99.9"],
        []),
    "vault_env_save": (
        ["--project", PROYECTO, "--environment", "staging", "--vars",
         '[{"name": "API_URL", "description": "Dirección del servicio",'
         ' "required": true, "provider": "env-file"}]'],
        ["staging"]),
    "vault_bibliography_save": (
        ["--title", "Guía de diseño", "--url", "https://example.org/guia",
         "--summary", "Un resumen corto.", "--source_type", "docs"],
        ["Resumen"]),
    "vault_knowledge_save": (
        ["--category", "concept", "--title", "Un concepto con acentuación",
         "--content", "Una línea.\nOtra línea.\nY una tercera con palabras."],
        []),
    "vault_project_overview": (
        ["--project", PROYECTO],
        []),
}

_H2 =re.compile(r"^## (.+?)\s*$", re.MULTILINE)


@pytest.fixture(scope="module")
def vault(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("saves-escalonados")
    assert correr_en_proceso("vault_init", vault=raiz).codigo == 0
    alta = correr_en_proceso("vault_project", "--add", PROYECTO, vault=raiz)
    assert alta.codigo == 0, alta.stdout[-800:] + alta.stderr[-800:]
    return raiz


_NOTAS: dict = {}


def _nota(vault, tool):
    if tool not in _NOTAS:
        argv, _ = CASOS[tool]
        r = correr_en_proceso(tool, *argv, vault=vault, agente="pytest")
        assert r.codigo == 0, r.stdout[-800:] + r.stderr[-800:]
        envelope = r.envelope
        assert envelope.get("ok") is True, envelope
        ruta = envelope.get("path") or envelope.get("file") or envelope.get("overview")
        p = Path(ruta) if Path(ruta).is_absolute() else vault / ruta
        rel = str(p.relative_to(vault)).replace("\\", "/")
        _, cuerpo = parse_frontmatter_with_body(p.read_text(encoding="utf-8"))
        _NOTAS[tool] = (rel, cuerpo, envelope)
    return _NOTAS[tool]


def _es_registro(rel):
    return section_documentacion(rel.split("/", 1)[0]) == "registro"


def _titulo(cuerpo):
    for linea in cuerpo.splitlines():
        if linea.startswith("# "):
            return linea[2:].strip()
    return ""


@pytest.mark.parametrize("tool", sorted(CASOS))
def test_cada_nota_abre_con_lead_o_enlaza_su_padre(vault, tool):
    rel, cuerpo, _ = _nota(vault, tool)
    assert _titulo(cuerpo), f"{tool}: the note does not open with its H1 (CN-04)"
    if _es_registro(rel):
        assert FICHA in cuerpo, f"{tool} ({rel}): an event record must link {FICHA}"
        return
    perfil = profundidad_de_nota(cuerpo)
    assert perfil["tiene_lead"], (tool, rel, perfil, lead_de(cuerpo))


@pytest.mark.parametrize("tool", sorted(CASOS))
def test_el_lead_sale_de_lo_que_la_tool_recibio(vault, tool):
    """Not invented (AP-45): an article's lead names its subject as the tool received it."""
    rel, cuerpo, _ = _nota(vault, tool)
    if _es_registro(rel):
        pytest.skip("an event record names its parent, not a summary")
    lead = lead_de(cuerpo)
    sujeto = {"vault_code_module": "src/alta.py", "vault_project_overview": PROYECTO,
              "vault_env_save": PROYECTO, "vault_release_save": "1.0.0"}.get(tool)
    sujeto = sujeto or _titulo(cuerpo).split(": ", 1)[-1]
    assert sujeto in lead, (tool, sujeto, lead)


@pytest.mark.parametrize("tool", sorted(CASOS))
def test_lo_que_falta_no_cuenta_como_evidencia(vault, tool):
    _, cuerpo, _ = _nota(vault, tool)
    pendientes = [ln for ln in cuerpo.splitlines() if ln.startswith("> _Pendiente:")]
    limpio = cuerpo_sin_marcadores(cuerpo)
    for linea in pendientes:
        assert linea not in limpio, (tool, linea)
        assert linea.rstrip().endswith("._"), (tool, linea)


@pytest.mark.parametrize("tool", sorted(CASOS))
def test_ninguna_seccion_existente_desaparece(vault, tool):
    _, cuerpo, _ = _nota(vault, tool)
    _, esperadas = CASOS[tool]
    escritas = _H2.findall(cuerpo)
    for seccion in esperadas:
        assert seccion in escritas, (tool, seccion, escritas)


def test_la_ficha_de_un_proyecto_nuevo_abre_con_su_lead(vault):
    """The card `vault_project --add` writes is the parent every record links."""
    ficha = vault / "01_Projects" / PROYECTO / "project.md"
    _, cuerpo = parse_frontmatter_with_body(ficha.read_text(encoding="utf-8"))
    perfil = profundidad_de_nota(cuerpo)
    assert perfil["tiene_lead"], perfil
    assert f"`{PROYECTO}`" in lead_de(cuerpo)
    assert "00_System/.local/project-paths.json" in cuerpo, "the existing guidance stays"


def test_un_registro_guardado_dos_veces_no_cambia(vault):
    """The lead is deterministic: re-saving the same record leaves the bytes alone."""
    rel, _, _ = _nota(vault, "vault_risk_save")
    antes = (vault / rel).read_bytes()
    argv, _ = CASOS["vault_risk_save"]
    r = correr_en_proceso("vault_risk_save", *argv, vault=vault, agente="pytest")
    assert r.codigo == 0, r.stdout[-800:]
    assert (vault / rel).read_bytes() == antes


def test_el_envelope_no_cambia_de_forma(vault):
    """Only the body gains its lead: every envelope still names the note it wrote."""
    for tool in sorted(CASOS):
        _, _, envelope = _nota(vault, tool)
        assert json.dumps(envelope, ensure_ascii=False).count('"ok": true') == 1, tool

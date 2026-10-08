"""ISO/IEC 42005 — una decisión de IA de impacto alto dice a quién afecta.

`vault_ai_decision` registraba qué se decidió y por qué, pero no a quién le
cuesta. Con `impact_level` en los dos niveles superiores y sin `--affected`, la
evaluación queda `pendiente` en el frontmatter —donde la lee el audit— y la
tool lo dice en el envelope en vez de callarlo. Se lee lo escrito en disco.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_ai_decision  # noqa: E402
import vault_io  # noqa: E402
from vault.kernel.frontmatter_parsing import separar_frontmatter  # noqa: E402


def _correr(raiz, script, *args):
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               VAULT_AGENT="probe", PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=300)
    sobre = json.loads(p.stdout)
    assert sobre.get("ok") is True, p.stdout[-600:]
    return sobre


def _vault(tmp_path):
    for seccion in ("00_System", "01_Projects", "16_AI_Governance", "99_Index"):
        (tmp_path / seccion).mkdir()
    _correr(tmp_path, "vault_project.py", "--add", "demo")
    return tmp_path


def _decidir(raiz, titulo, impacto, *extra):
    return _correr(raiz, "vault_ai_decision.py", "--project", "demo", "--title", titulo,
                   "--decision_type", "process", "--impact_level", impacto,
                   "--description", "Colas con reintento acotado.",
                   "--rationale", "No perder mensajes sin saturar al consumidor.", *extra)


def _leer(raiz, rel):
    fm, cuerpo = separar_frontmatter((raiz / rel).read_text(encoding="utf-8"))
    return (yaml.safe_load(fm) if isinstance(fm, str) else fm), cuerpo


def test_42005_el_criterio_es_puro():
    assert set(vault_ai_decision.EVALUACION_EXIGIDA) == {"critical", "high"}
    assert vault_ai_decision.estado_de_evaluacion("high", None) == "pendiente"
    assert vault_ai_decision.estado_de_evaluacion("critical", ["  "]) == "pendiente"
    assert vault_ai_decision.estado_de_evaluacion("low", []) == "no_exigida"
    assert vault_ai_decision.estado_de_evaluacion("low", ["equipo"]) == "completa"


def test_42005_impacto_alto_sin_afectados_queda_pendiente_y_lo_dice(tmp_path):
    raiz = _vault(tmp_path)
    s = _decidir(raiz, "Reintento acotado", "high")
    assert s["impact_assessment"] == "pendiente"
    assert "42005" in s["hint"]
    fm, cuerpo = _leer(raiz, s["path"])
    assert fm["impact_assessment"] == "pendiente"
    assert "## Evaluacion de Impacto" in cuerpo and "AP-65" in cuerpo


def test_42005_con_afectados_la_evaluacion_es_completa(tmp_path):
    raiz = _vault(tmp_path)
    s = _decidir(raiz, "Reintento con afectados", "critical",
                 "--affected", json.dumps(["consumidores de la cola - latencia mayor"]))
    assert s["impact_assessment"] == "completa" and "hint" not in s
    fm, cuerpo = _leer(raiz, s["path"])
    assert fm["impact_assessment"] == "completa"
    assert "- consumidores de la cola - latencia mayor" in cuerpo


def test_42005_impacto_bajo_no_la_exige(tmp_path):
    raiz = _vault(tmp_path)
    s = _decidir(raiz, "Reintento menor", "low")
    assert s["impact_assessment"] == "no_exigida" and "hint" not in s
    fm, cuerpo = _leer(raiz, s["path"])
    assert fm["impact_assessment"] == "no_exigida"
    assert "## Evaluacion de Impacto" not in cuerpo


# ── AP-65: el audit mide lo que la tool declara ──────────────────────────────

@pytest.mark.parametrize("rel,fm,marcada", [
    ("16_AI_Governance/decisions/a.md", {"impact_level": "high"}, True),
    ("16_AI_Governance/decisions/a.md", {"impact_level": "critical",
                                         "impact_assessment": "pendiente"}, True),
    ("16_AI_Governance/decisions/a.md", {"impact_level": "HIGH",
                                         "impact_assessment": "completa"}, False),
    ("16_AI_Governance/decisions/a.md", {"impact_level": "medium"}, False),
    ("16_AI_Governance/decisions/a.md", {"impact_level": "high", "status": "template"}, False),
    # El ámbito es del criterio, no del detector.
    ("07_Knowledge/a.md", {"impact_level": "critical"}, False),
    ("16_AI_Governance\\decisions\\a.md", {"impact_level": "high"}, True),
])
def test_ap65_criterio(rel, fm, marcada):
    from vault.kernel.contenido import falta_de_evaluacion_de_impacto
    assert bool(falta_de_evaluacion_de_impacto(rel, fm, ("critical", "high"))) is marcada


def test_ap65_los_niveles_exigidos_salen_de_la_escala_del_registro():
    from vault.kernel.contenido import niveles_de_impacto_exigidos
    from vault_vocabulario import valores
    assert niveles_de_impacto_exigidos(valores("severidad")) == ("critical", "high")
    assert niveles_de_impacto_exigidos(("x", "y", "z")) == ("x", "y")


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "v"
    for s in ("00_System", "16_AI_Governance/decisions", "07_Knowledge"):
        (raiz / s).mkdir(parents=True)
    previo = vault_io.get_vault_root()
    vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previo)


def test_ap65_scan_y_auditoria_marcan_lo_mismo(vault):
    """Una decisión de antes de v41.3 no declara `impact_assessment`: que no
    lo declare no dice que alguien la evaluase, y se marca."""
    import vault_norms
    from vault.gobernanza.auditoria_runtime import auditar_runtime
    notas = {
        "16_AI_Governance/decisions/antigua.md": "impact_level: high",
        "16_AI_Governance/decisions/pendiente.md": "impact_level: critical\nimpact_assessment: pendiente",
        "16_AI_Governance/decisions/completa.md": "impact_level: high\nimpact_assessment: completa",
        "16_AI_Governance/decisions/menor.md": "impact_level: low\nimpact_assessment: no_exigida",
        "07_Knowledge/nota.md": "impact_level: critical",
    }
    for rel, extra in notas.items():
        (vault / rel).write_text(f"---\ntitle: D\ntype: ai-decision\nstatus: draft\n{extra}\n---\n# D\n\ntexto\n",
                                 encoding="utf-8")
    esperadas = {"16_AI_Governance/decisions/antigua.md", "16_AI_Governance/decisions/pendiente.md"}
    auditoria = {v["path"] for v in auditar_runtime(vault)["violations"] if v["norm"] == "AP-65"}
    assert auditoria == esperadas, auditoria
    for rel in notas:
        scan = vault_norms.vault_norms_scan(rel)
        marcada = any(n["code"] == "AP-65" for n in scan["applicable_norms"])
        assert marcada is (rel in esperadas), rel


def test_ap65_catalogo():
    from vault_norms_catalog import norma_por_codigo
    ap65 = norma_por_codigo("AP-65")
    assert ap65["enforcement"] == "audit" and ap65["tools_detecting"] == ["vault_norms"]
    assert "AP-64" in ap65["distinguido_de"]
    assert "AP-65" in norma_por_codigo("AP-64")["distinguido_de"]

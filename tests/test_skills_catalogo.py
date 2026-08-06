"""La capa de skills tiene contrato ejecutable, y el SDD no envejece en silencio.

Dos huecos que las seis puertas del checklist no miraban:

1. **La skill estaba fuera del catálogo.** Cuatro versiones con `vault-sdd-init`
   documentada en `docs/SKILLS.md`, con tests de contrato propios, y sin entrada
   ni en `tools-catalog.json` ni en `00_System/tool-spec.json`. `--check-contracts`
   verifica catálogo → contrato, así que lo que no está en ninguno de los dos no
   lo echa en falta nadie: AP-42 sobre la puerta de entrada de los agentes.

2. **El SDD generado se quedó atrás.** El rango de antipatrones se deriva de
   `NORM_CATALOG` en cada ejecución, así que el fichero recién escrito nunca
   miente. Lo que envejece es el de la ejecución anterior: se commiteó y se quedó
   quieto un mes mientras el registro pasaba de AP-35 a AP-47. Es AP-47 —artefacto
   derivado desfasado— aplicado a la documentación del propio estándar.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_sdd_init as sdd  # noqa: E402
from vault_mcp_catalog import GROUPS, TOOLS_CATALOG  # noqa: E402


# ── La skill está publicada ───────────────────────────────────────────────────

def _entry_points_de_skills():
    """Entry point de cada `.claude/skills/<x>/SKILL.md`, por convención de nombre."""
    return {
        p.parent.name.replace("-", "_")
        for p in (REPO_ROOT / ".claude" / "skills").glob("*/SKILL.md")
    }


def test_toda_skill_tiene_entrada_en_el_catalogo():
    """Una skill fuera del catálogo es una capacidad que MCP no ve (AP-42)."""
    fuera = sorted(_entry_points_de_skills() - set(TOOLS_CATALOG))
    assert not fuera, (
        f"skills sin entrada en TOOLS_CATALOG: {fuera}. La definición la descubre "
        f"un agente por ruta, pero la capa MCP solo ve el catálogo."
    )


def test_toda_skill_tiene_contrato_en_el_tool_spec():
    spec = json.loads(
        (REPO_ROOT / "vault-sandbox" / "00_System" / "tool-spec.json")
        .read_text(encoding="utf-8")
    )
    fuera = sorted(_entry_points_de_skills() - set(spec["tools"]))
    assert not fuera, f"skills sin contrato en tool-spec.json: {fuera}"


def test_el_grupo_skills_existe_y_no_esta_vacio():
    assert GROUPS.get("Skills"), "el grupo Skills desapareció del catálogo"


def test_el_catalogo_declara_que_sanacion_no_escribe():
    """El `side_effects: []` es el contrato, no un descuido de relleno."""
    entrada = TOOLS_CATALOG["vault_sanacion"]
    assert entrada["side_effects"] == [], (
        "vault_sanacion declaró side effects: si escribe, deja de ser diagnóstico"
    )


# ── AP-47 sobre el SDD ────────────────────────────────────────────────────────

def _sdd(tmp_path, contenidos):
    """Un `docs/sdd/` con los 14 ficheros, diciendo lo que se le pida."""
    sdd_dir = tmp_path / "docs" / "sdd"
    sdd_dir.mkdir(parents=True)
    for fname in sdd.EXPECTED_OUTPUTS:
        (sdd_dir / fname).write_text(
            contenidos.get(fname, "sin rango declarado\n"), encoding="utf-8"
        )
    return tmp_path


def test_sin_directorio_es_sdd_missing(tmp_path):
    envelope = sdd.sdd_coherence(tmp_path)
    assert envelope["status"] == "sdd_missing"
    assert envelope["ok"] is False


def test_rango_al_dia_pasa(tmp_path):
    vigente = sdd.ap_range_label()
    envelope = sdd.sdd_coherence(
        _sdd(tmp_path, {"04-antipatterns.md": f"Catálogo {vigente}\n"})
    )
    assert envelope["status"] == "sdd_ok"
    assert envelope["ok"] is True
    assert envelope["found_ranges"] == [vigente]


def test_rango_desfasado_se_reporta_con_el_fichero(tmp_path):
    """El defecto real: el cuerpo decía AP-35 con el registro en AP-47."""
    envelope = sdd.sdd_coherence(
        _sdd(tmp_path, {"04-antipatterns.md": "Catálogo completo de AP-01..AP-35\n"})
    )
    assert envelope["status"] == "sdd_stale"
    assert envelope["ok"] is False
    assert envelope["stale_files"] == [
        {"file": "04-antipatterns.md", "found": "AP-01..AP-35"}
    ]
    assert envelope["expected_range"] == sdd.ap_range_label()


def test_cuerpo_e_indice_desfasados_se_reportan_los_dos(tmp_path):
    """Fueron dos ficheros con dos rangos distintos, y ninguno era el vigente."""
    envelope = sdd.sdd_coherence(_sdd(tmp_path, {
        "04-antipatterns.md": "AP-01..AP-35\n",
        "README.md": "| 04 | Antipatterns | Catálogo AP-01..AP-25 |\n",
    }))
    assert {f["file"] for f in envelope["stale_files"]} == {
        "04-antipatterns.md", "README.md"
    }
    assert envelope["found_ranges"] == ["AP-01..AP-25", "AP-01..AP-35"]


def test_fichero_ausente_es_partial_no_stale(tmp_path):
    """Falta un documento y falta un rango son deudas distintas."""
    raiz = _sdd(tmp_path, {})
    (raiz / "docs" / "sdd" / "09-metrics.md").unlink()
    envelope = sdd.sdd_coherence(raiz)
    assert envelope["status"] == "sdd_partial"
    assert envelope["missing_files"] == ["09-metrics.md"]


def test_el_sdd_del_repo_esta_al_dia():
    """La puerta, corriendo sobre el artefacto real que se commitea."""
    envelope = sdd.sdd_coherence(REPO_ROOT)
    assert envelope["ok"], (
        f"docs/sdd/ desfasado: {envelope['stale_files']} — regenera con "
        f"`python scripts/vault_sdd_init.py --bilingual --force --vault-root .`"
    )


def test_gaps_md_no_se_pisa_ni_con_force():
    """`--force` levanta la idempotencia, no el permiso para pisar lo escrito a mano.

    Se comprueba sobre el fuente porque el defecto es de **condición**: el
    `and not args.force` estaba en la línea que decide, y un `--force` para
    refrescar el rango se llevó por delante 85 hallazgos redactados a mano.
    """
    fuente = (SCRIPTS / "vault_sdd_init.py").read_text(encoding="utf-8")
    decision = [
        ln for ln in fuente.splitlines()
        if "gaps_path.exists()" in ln and not ln.lstrip().startswith("#")
    ]
    assert len(decision) == 1, decision
    assert "force" not in decision[0], (
        "la preservación de gaps.md volvió a depender de --force"
    )

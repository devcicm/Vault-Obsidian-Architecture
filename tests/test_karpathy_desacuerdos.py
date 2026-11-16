"""PAT-7: a declared disagreement is information, not AP-05 debt.

Karpathy's lint looks for contradictions between pages; some of them are
legitimate (two sources measured differently, the evidence is not settled).
The author declares it with the ontology predicate `contradicts` in either
note's frontmatter. Then `vault_fuente_unica` stops counting that conflict as
AP-05 debt, and `vault_context_pack` delivers both sides of it.
"""

import json
from pathlib import Path

from apoyo import correr_tool, escribir_nota
from vault_base import copiar_vault

ROOT = Path(__file__).resolve().parent.parent


def _infra(raiz: Path, contradice: bool, tercera: bool = False) -> None:
    extra = {"contradicts": ["[[medicion-b]]"]} if contradice else {}
    escribir_nota(raiz, "09_Infrastructure/medicion-a.md",
                  {"title": "Medición A", "ip": "10.0.0.1", **extra}, "# A\n")
    escribir_nota(raiz, "09_Infrastructure/medicion-b.md",
                  {"title": "Medición B", "ip": "10.0.0.2"}, "# B\n")
    if tercera:
        escribir_nota(raiz, "09_Infrastructure/medicion-c.md",
                      {"title": "Medición C", "ip": "10.0.0.3"}, "# C\n")


def test_pat7_la_ontologia_declara_el_predicado():
    from vault.kernel.normativa.desacuerdos import PREDICADO

    ontologia = json.loads((ROOT / "scripts" / "vault_ontology.json").read_text(encoding="utf-8"))
    predicado = ontologia["predicates"][PREDICADO]
    assert predicado["inverse"] == "contradicted_by"
    assert PREDICADO in ontologia["edge_priority"]


def test_pat7_sin_declaracion_el_conflicto_es_deuda_ap05(tmp_path):
    from vault.gobernanza import fuente_unica

    _infra(tmp_path, contradice=False)
    r = fuente_unica.check(tmp_path)

    assert [c["clave"] for c in r["conflicts"]] == ["ip"]
    assert r["declared_disagreements"] == []


def test_pat7_un_desacuerdo_declarado_no_es_deuda_ap05(tmp_path):
    from vault.gobernanza import fuente_unica

    _infra(tmp_path, contradice=True)
    r = fuente_unica.check(tmp_path)

    assert r["conflicts"] == [] and r["new_conflicts"] == [], r
    assert [d["clave"] for d in r["declared_disagreements"]] == ["ip"]


def test_pat7_una_tercera_nota_que_discrepa_sin_declarar_mantiene_la_deuda(tmp_path):
    from vault.gobernanza import fuente_unica

    _infra(tmp_path, contradice=True, tercera=True)
    r = fuente_unica.check(tmp_path)

    assert [c["clave"] for c in r["conflicts"]] == ["ip"]
    assert r["declared_disagreements"] == []


def test_pat7_el_catalogo_la_declara_recommended():
    import vault_norms_catalog

    norma = vault_norms_catalog.norma_por_codigo("PAT-7")
    assert norma and norma["type"] == "pattern" and norma["enforcement"] == "recommended"


# ── vault_context_pack: both sides ───────────────────────────────────────────

def _pack_vault(tmp_path: Path, contradice: bool) -> Path:
    raiz = copiar_vault(tmp_path / "vault")
    extra = {"contradicts": ["[[postura-zeta]]"]} if contradice else {}
    escribir_nota(raiz, "07_Knowledge/postura-alfa.md",
                  {"title": "Postura alfa", "status": "draft", **extra},
                  "# Postura alfa\n\nEl ornitorrinco cuántico arranca en frío.\n")
    escribir_nota(raiz, "07_Knowledge/postura-zeta.md",
                  {"title": "Postura zeta", "status": "draft"},
                  "# Postura zeta\n\nLa medición dice otra cosa sobre el arranque.\n")
    assert correr_tool("vault_reindex", vault=raiz).envelope["ok"] is True
    return raiz


def _incluidas(raiz: Path) -> dict:
    env = correr_tool("vault_context_pack", "--query", "ornitorrinco cuántico",
                      vault=raiz).envelope
    assert env["ok"] is True, env
    return {i["path"]: i for i in env["included"]}


def test_pat7_el_paquete_sin_declaracion_solo_trae_la_nota_buscada(tmp_path):
    incluidas = _incluidas(_pack_vault(tmp_path, contradice=False))

    assert "07_Knowledge/postura-alfa.md" in incluidas
    assert "07_Knowledge/postura-zeta.md" not in incluidas


def test_pat7_el_paquete_trae_los_dos_lados_de_un_desacuerdo(tmp_path):
    incluidas = _incluidas(_pack_vault(tmp_path, contradice=True))

    assert "07_Knowledge/postura-alfa.md" in incluidas
    assert "07_Knowledge/postura-zeta.md" in incluidas, incluidas
    assert incluidas["07_Knowledge/postura-alfa.md"]["disagrees_with"] == [
        "07_Knowledge/postura-zeta.md"]
    assert incluidas["07_Knowledge/postura-zeta.md"]["via"] == {
        "contradicts": "07_Knowledge/postura-alfa.md"}

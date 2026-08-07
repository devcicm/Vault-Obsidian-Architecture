"""AP-47 — el índice y el grafo son proyecciones del disco, y se comprueba.

El vault es la fuente de verdad; `search-index.json` y `graph.json` son
proyecciones suyas. Con consistencia eventual el desfase es esperable —el
estándar no lleva base de datos, y eso es normativo—, pero **nadie lo medía**:
`vault_reindex --check` comprobaba `len(notes) > 0`, así que un índice con una
entrada sobre un vault de 300 notas devolvía `index_ok`.

Medido antes del arreglo:

    vault-sandbox     disco=111  search-index=110  graph.nodes=100
    vault-builderx    disco=317  search-index=290  graph.nodes=232

Los dos pasaban la puerta. Un índice que miente no es un detalle de higiene: el
agente busca una nota que existe, no la encuentra, y la vuelve a escribir.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_norms  # noqa: E402
import vault_reindex  # noqa: E402


def _vault(tmp_path, notas, indexadas=None, grafo=None):
    """Vault mínimo: notas en disco y un índice que dice lo que se le pida."""
    raiz = tmp_path / "vault"
    (raiz / "07_Knowledge").mkdir(parents=True)
    for n in notas:
        (raiz / "07_Knowledge" / n).write_text(
            f"---\ntype: knowledge\nstatus: draft\n---\n\nCuerpo de {n}.\n",
            encoding="utf-8",
        )
    if indexadas is not None:
        idx = raiz / "99_Index"
        idx.mkdir(parents=True, exist_ok=True)
        (idx / "search-index.json").write_text(
            json.dumps(
                {"notes": [{"path": f"07_Knowledge/{n}", "title": n} for n in indexadas]}
            ),
            encoding="utf-8",
        )
    if grafo is not None:
        idx = raiz / "99_Index"
        idx.mkdir(parents=True, exist_ok=True)
        (idx / "graph.json").write_text(
            json.dumps({"nodes": [{"id": n} for n in grafo]}), encoding="utf-8"
        )
    return raiz


# ── La norma ──────────────────────────────────────────────────────────────────

def test_la_norma_esta_registrada_con_enforcement_real():
    ap47 = next((n for n in vault_norms.NORM_CATALOG if n["code"] == "AP-47"), None)
    assert ap47 is not None, "AP-47 no está en el catálogo"
    assert ap47["enforcement"] in {"guard", "audit", "guard+audit", "recommended"}


# ── index_coherence ───────────────────────────────────────────────────────────

def test_un_indice_completo_pasa(tmp_path):
    raiz = _vault(tmp_path, ["a.md", "b.md"], indexadas=["a.md", "b.md"])
    assert vault_reindex.index_coherence(raiz)["ok"]


def test_una_nota_fuera_del_indice_es_desfase(tmp_path):
    """El caso que el check anterior aprobaba: hay entradas, pero no todas."""
    raiz = _vault(tmp_path, ["a.md", "b.md", "c.md"], indexadas=["a.md"])
    r = vault_reindex.index_coherence(raiz)
    assert not r["ok"] and r["status"] == "index_stale"
    assert r["missing_count"] == 2
    assert "07_Knowledge/b.md" in r["missing_in_index"]


def test_una_entrada_que_ya_no_existe_tambien_es_desfase(tmp_path):
    """La otra dirección: el agente la encuentra y luego no puede abrirla."""
    raiz = _vault(tmp_path, ["a.md"], indexadas=["a.md", "borrada.md"])
    r = vault_reindex.index_coherence(raiz)
    assert not r["ok"]
    assert r["stale_count"] == 1
    assert "07_Knowledge/borrada.md" in r["stale_in_index"]


def test_un_indice_que_falta_no_se_confunde_con_uno_desfasado(tmp_path):
    raiz = _vault(tmp_path, ["a.md"])
    assert vault_reindex.index_coherence(raiz)["status"] == "index_missing"


def test_un_indice_corrupto_se_declara_como_tal(tmp_path):
    raiz = _vault(tmp_path, ["a.md"], indexadas=[])
    (raiz / "99_Index" / "search-index.json").write_text("{roto", encoding="utf-8")
    r = vault_reindex.index_coherence(raiz)
    assert r["status"] == "index_corrupt" and not r["ok"]


def test_un_vault_vacio_con_indice_vacio_esta_coherente(tmp_path):
    """Cero notas y cero entradas es un reflejo correcto, no un fallo."""
    raiz = _vault(tmp_path, [], indexadas=[])
    assert vault_reindex.index_coherence(raiz)["ok"]


def test_el_desfase_del_grafo_se_informa_pero_no_veta(tmp_path):
    """`graph.json` se regenera solo con --graph: vetarlo sería ruido."""
    raiz = _vault(tmp_path, ["a.md", "b.md"], indexadas=["a.md", "b.md"], grafo=["a.md"])
    r = vault_reindex.index_coherence(raiz)
    assert r["ok"], "el grafo no debe decidir el veredicto"
    assert r["graph_drift"] == 1, "pero el desfase tiene que verse"


# ── El audit ──────────────────────────────────────────────────────────────────

def test_el_audit_reporta_el_indice_desfasado(tmp_path):
    raiz = _vault(tmp_path, ["a.md", "b.md"], indexadas=["a.md"])
    res = vault_norms.vault_norms_audit(root=raiz)
    ap47 = [v for v in res["violations"] if v["norm"] == "AP-47"]
    assert len(ap47) == 1, "un hallazgo por vault, no uno por nota que falta"
    assert "vault_reindex" in ap47[0]["detail"]


def test_el_audit_calla_cuando_el_indice_esta_al_dia(tmp_path):
    raiz = _vault(tmp_path, ["a.md"], indexadas=["a.md"])
    res = vault_norms.vault_norms_audit(root=raiz)
    assert not [v for v in res["violations"] if v["norm"] == "AP-47"]


# ── La verificación mide lo que el arreglo arregla (AP-44) ────────────────────

def test_comprobar_y_reconstruir_usan_el_mismo_criterio():
    """Si `--check` contara con criterio propio, reportaría un desfase que
    `vault_reindex` no cierra nunca — la puerta quedaría roja para siempre."""
    # Desde v40.0 el criterio vive en el dominio, así que la comprobación se
    # hace donde ahora está: `vault/indices/enumeracion.py` es el único sitio
    # que hace `rglob("*.md")` para el contexto, y tanto la coherencia como la
    # reconstrucción lo consumen. Un segundo `rglob` filtrando por su cuenta
    # sería otra definición de "nota indexable", y el desfase que reportara no
    # sería el que `vault_reindex` cierra.
    from pathlib import Path

    dominio = Path(SCRIPTS).parent / "vault" / "indices"
    enumeracion = (dominio / "enumeracion.py").read_text(encoding="utf-8")
    assert enumeracion.count("def notas_en_disco") == 1
    assert enumeracion.count('rglob("*.md")') == 1

    otros = [
        f.name
        for f in dominio.glob("*.py")
        if f.name != "enumeracion.py"
        and 'rglob("*.md")' in f.read_text(encoding="utf-8")
    ]
    assert not otros, f"más de un sitio enumera notas indexables: {otros}"

    # Y el adaptador no puede recuperar su copia por la puerta de atrás.
    fuente = (SCRIPTS / "vault_reindex.py").read_text(encoding="utf-8")
    assert 'rglob("*.md")' not in fuente
    assert "def _is_vault_note" not in fuente

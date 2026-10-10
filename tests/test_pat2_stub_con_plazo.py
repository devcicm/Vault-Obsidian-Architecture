"""PAT-2 tiene quien lo aplique y quien lo vigile (capa 4 del plano).

La señal de PAT-2 —«los stubs del vault tienen `status: stub` y fecha
`expand_by`»— y la de AP-03 —«`vault_audit` reporta notas con `status: stub`
sin `expand_by` o con `expand_by` vencido»— las afirmaba el catálogo sin que
ninguna línea de código escribiera ni leyera `expand_by`. El único escritor de
stubs del toolkit, `vault_graph_fix._create_stub`, los creaba sin plazo.

Ahora el escritor aplica el patrón y el audit lo vigila en una clave propia
(`stubsSinPlazo`), sin fila en `PENALIZACIONES`: la cifra se publica antes de
pesarla, como se hizo con AP-02.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _ruta in (ROOT / "scripts", ROOT):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

import yaml  # noqa: E402

import vault_grafo_import as gi  # noqa: E402


def _frontmatter(path: Path) -> dict:
    texto = path.read_text(encoding="utf-8")
    return yaml.safe_load(texto.split("---", 2)[1])


def test_pat2_el_stub_de_graph_fix_nace_con_status_y_expand_by(tmp_path):
    from vault_graph_fix import PLAZO_DE_ENRIQUECIMIENTO_DIAS, _create_stub
    from vault_lib import Config

    vault = tmp_path / "vault"
    vault.mkdir()
    r = _create_stub(vault, "destino-nuevo", ["01_Projects/a.md"], {"category": "no_match"})
    assert r["created"] is True
    fm = _frontmatter(vault / "02_Observability/maintenance/stubs/destino-nuevo.md")
    assert fm["status"] == "stub"
    # El plazo no es una cifra nueva: es el mismo en que una nota pasa a stale.
    assert PLAZO_DE_ENRIQUECIMIENTO_DIAS == Config.STALE_DAYS
    esperado = date.today() + timedelta(days=PLAZO_DE_ENRIQUECIMIENTO_DIAS)
    # El stub fecha en UTC y `date.today()` es local: un día de holgura a cada lado.
    assert str(fm["expand_by"])[:10] in {(esperado + timedelta(days=d)).isoformat()
                                         for d in (-1, 0, 1)}


def test_pat2_el_audit_ve_el_stub_sin_plazo_y_el_vencido(tmp_path, monkeypatch):
    import vault_audit
    import vault_io

    vault = tmp_path / "vault"
    (vault / "07_Knowledge").mkdir(parents=True)
    ayer = (date.today() - timedelta(days=1)).isoformat()
    manana = (date.today() + timedelta(days=1)).isoformat()
    notas = {
        "sin-plazo": "---\nstatus: stub\n---\n# a\n",
        "vencido": f"---\nstatus: stub\nexpand_by: {ayer}\n---\n# b\n",
        "en-plazo": f"---\nstatus: stub\nexpand_by: {manana}\n---\n# c\n",
        "ilegible": "---\nstatus: stub\nexpand_by: pronto\n---\n# d\n",
        "no-stub": "---\nstatus: draft\n---\n# e\n",
    }
    for nombre, texto in notas.items():
        (vault / "07_Knowledge" / f"{nombre}.md").write_text(texto, encoding="utf-8")
    monkeypatch.setattr(vault_io, "get_vault_root", lambda: vault)
    monkeypatch.setattr(vault_audit, "_raiz", lambda: vault)

    hallazgos = vault_audit._detect_stubs_sin_plazo(sorted((vault / "07_Knowledge").glob("*.md")))
    por_nota = {Path(h["path"]).stem: h for h in hallazgos}
    assert set(por_nota) == {"sin-plazo", "vencido", "ilegible"}
    assert por_nota["sin-plazo"]["reason"] == "sin_expand_by"
    assert por_nota["vencido"]["reason"] == "expand_by_vencido"
    assert por_nota["ilegible"]["reason"] == "expand_by_ilegible"
    assert all(h["norm_code"] == "AP-03" and h["patron"] == "PAT-2" for h in hallazgos)


def test_pat2_el_audit_publica_la_clave_sin_pesarla():
    import vault_audit_catalog

    fuente = gi.codigo_de(ROOT / "scripts" / "vault_audit.py").read_text(encoding="utf-8")
    assert '"stubsSinPlazo"' in fuente
    assert not [p for p in vault_audit_catalog.PENALIZACIONES
                if "stub" in str(p).lower() and "plazo" in str(p).lower()]

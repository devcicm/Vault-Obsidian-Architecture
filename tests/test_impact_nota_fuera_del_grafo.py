"""vault_impact distingue «sin dependientes» de «no sé qué nota es» (AP-51 / AP-36).

Medido 2026-10-02: `--changed ../../README.md`, una errata o una nota que el
grafo aún no tiene devolvían lo mismo que una nota sana sin dependientes:
ok, impact_radius 0, «Sin impacto detectado en el grafo». Quien pregunta si
puede tocar una nota recibía un sí sin que nadie la hubiera mirado.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _vault(tmp_path):
    import vault_io

    root = tmp_path / "v"
    (root / "00_System").mkdir(parents=True)
    (root / "99_Index").mkdir()
    (root / "07_Knowledge").mkdir()
    for n in ("a", "b"):
        (root / "07_Knowledge" / f"{n}.md").write_text(f"---\ntitle: {n}\n---\n", encoding="utf-8")
    grafo = {"nodes": {"07_Knowledge/a.md": {}, "07_Knowledge/b.md": {}},
             "edges": [{"from": "07_Knowledge/a.md", "to": "07_Knowledge/b.md"}]}
    (root / "99_Index" / "graph.json").write_text(json.dumps(grafo), encoding="utf-8")
    vault_io.set_vault_root(root)
    import vault_impact
    return vault_impact


def test_ap51_una_nota_que_el_grafo_no_tiene_se_nombra(tmp_path):
    vi = _vault(tmp_path)
    r = vi.vault_impact(["07_Knowledge/errata.md"])
    assert r["not_in_graph"] == ["07_Knowledge/errata.md"]
    assert "Sin impacto detectado" not in r["summary"]


def test_ap51_una_nota_sana_sin_dependientes_sigue_limpia(tmp_path):
    vi = _vault(tmp_path)
    r = vi.vault_impact(["07_Knowledge/a.md"])
    assert r["ok"] is True and r["not_in_graph"] == []


def test_ap36_una_ruta_que_sale_del_vault_se_rechaza(tmp_path):
    vi = _vault(tmp_path)
    r = vi.vault_impact(["../../README.md"])
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH"


def test_la_barra_de_windows_resuelve_la_misma_nota(tmp_path):
    vi = _vault(tmp_path)
    r = vi.vault_impact(["07_Knowledge\\b.md"])
    assert r["not_in_graph"] == [] and r["impact_radius"] == 1

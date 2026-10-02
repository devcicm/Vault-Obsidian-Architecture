"""AP-51: `vault_graph_merge` dice de dónde sacó la ontología, y lee la del vault.

Dos cadenas rotas a la vez. `vault_init` copia la ontología a
`00_System/vault-ontology.json` y nadie la leía: `vault_graph_merge` miraba solo
`__file__/vault_ontology.json`, así que personalizarla en el vault no tenía
efecto. Y cuando esa ruta no existía —la wheel salía sin ella— devolvía `{}` en
silencio: cero clases, cero predicados válidos, `ontology_version: unknown`, y
un `ok: true` indistinguible de un grafo bien tipado.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import vault_io  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    for seccion in ("00_System", "07_Knowledge", "99_Index"):
        (tmp_path / seccion).mkdir(parents=True, exist_ok=True)
    (tmp_path / "07_Knowledge" / "nota.md").write_text(
        "---\ntitle: Nota\n---\n\nCuerpo.\n", encoding="utf-8"
    )
    vault_io.set_vault_root(tmp_path)
    return tmp_path


def test_ap51_la_ontologia_del_vault_manda_sobre_la_del_paquete(vault):
    import vault_graph_merge

    (vault / "00_System" / "vault-ontology.json").write_text(
        json.dumps({"version": "propia-del-vault", "predicates": {}}), encoding="utf-8"
    )
    r = vault_graph_merge.vault_graph_merge()
    assert r["metadata"]["ontology_source"] == "vault"
    assert r["metadata"]["ontology_version"] == "propia-del-vault"


def test_ap51_sin_copia_en_el_vault_usa_la_del_paquete(vault):
    import vault_graph_merge

    empaquetada = json.loads(vault_graph_merge.ONTOLOGY_FILE.read_text(encoding="utf-8"))
    r = vault_graph_merge.vault_graph_merge()
    assert r["metadata"]["ontology_source"] == "paquete"
    assert r["metadata"]["ontology_version"] == empaquetada["version"]


def test_ap51_sin_ontologia_lo_dice_en_vez_de_tipar_con_vacio(vault, monkeypatch, tmp_path):
    import vault_graph_merge

    monkeypatch.setattr(vault_graph_merge, "ONTOLOGY_FILE", tmp_path / "no-existe.json")
    r = vault_graph_merge.vault_graph_merge()
    assert r["metadata"]["ontology_source"] == "ausente"
    assert any("ontolog" in a.lower() for a in r["nextActions"]), r["nextActions"]

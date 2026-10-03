"""El `path` que devuelve vault_infra_map existe y dice lo que hay (AP-44).

Sin componentes, la tool devolvía `ok: true` y el `path` de un mapa que no
escribía: el consumidor abría un fichero inexistente o, peor, el mapa de una
ejecución anterior con componentes que ya no están en el índice.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


@pytest.fixture
def vault(tmp_path):
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "09_Infrastructure"):
        (root / sec).mkdir(parents=True)
    vault_io.set_vault_root(root)
    return root


def _indice(componentes):
    import vault_infra_map

    f = vault_infra_map._index_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"components": componentes, "locations": {}}), encoding="utf-8")


def test_ap44_sin_componentes_el_path_devuelto_existe(vault):
    import vault_infra_map

    r = vault_infra_map.vault_infra_map()
    assert r["ok"] and r["nodesTotal"] == 0
    assert (vault / r["path"]).is_file()


def test_ap44_vaciar_el_indice_no_deja_el_mapa_anterior(vault):
    import vault_infra_map

    _indice([{"name": "db-viejo", "project": "p", "location": "local", "connections": []}])
    vault_infra_map.vault_infra_map()
    _indice([])
    r = vault_infra_map.vault_infra_map()
    assert "db-viejo" not in (vault / r["path"]).read_text(encoding="utf-8")

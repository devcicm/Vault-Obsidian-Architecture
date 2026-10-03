"""AP-58: `vault_lib` pide la raíz a su dueño, no a `vault_io`.

`vault_lib.get_vault_path` importaba `vault_io` dentro de la función por un
solo nombre, `get_vault_root`, cuyo dueño en el núcleo es `vault_raiz` (una
hoja). Ese import diferido cerraba el ciclo vault_lib <-> vault_io y lo
mantenía en `ciclos-baseline.json` con su pareja `vault_io -> vault_lib`.
Invertido, las dos aristas dejan de esquivar nada y salen de la baseline.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_ciclos as C  # noqa: E402


def test_ap58_vault_lib_no_vuelve_a_vault_io():
    medidos = C.medir()["deferred_cyclic"]
    assert "vault_lib->vault_io" not in medidos
    assert "vault_io->vault_lib" not in medidos


def test_ap58_la_baseline_ya_no_las_lleva():
    base = C._baseline()
    assert "vault_lib->vault_io" not in base and "vault_io->vault_lib" not in base


def test_ap58_get_vault_path_sigue_resolviendo_contra_la_raiz(tmp_path):
    import vault_io
    import vault_lib

    vault_io.set_vault_root(tmp_path)
    assert vault_lib.get_vault_path("search_index") == tmp_path / vault_lib.Config.SEARCH_INDEX

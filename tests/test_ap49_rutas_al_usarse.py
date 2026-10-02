"""AP-49: las rutas de índice se resuelven al usarse, no al importar el módulo.

Siete módulos hacían `INDEX_FILE = _code_dir() / ".code-index.json"` (y sus
variantes) a nivel de módulo. `_code_dir()` resuelve el vault al llamarse, pero
la llamada ocurría una sola vez, al importar: después de `set_vault_root()` la
tool seguía leyendo —y tres de ellas escribiendo— en el vault de antes.

La puerta de AP-49 no los veía porque solo mira asignaciones que nombran
`VAULT_ROOT`. Y `set_vault_root()` lo tapaba: `vault_raiz._reanclar_constantes`
reescribe las constantes en MAYÚSCULAS de todo `vault_*` que estén bajo la raíz
vieja. Ese parche es la mitigación declarada mientras quedan módulos sin migrar,
no el arreglo (lo dice el `conftest`), así que estos tests lo apagan: miden si
el módulo resuelve su ruta al usarla, no si alguien se la corrige por fuera.
"""

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_io  # noqa: E402

MODULOS = [
    "vault_code_map", "vault_code_module", "vault_code_query",
    "vault_code_relation", "vault_infra_map", "vault_mcp_context",
    "vault_relation_add",
]


@pytest.fixture(autouse=True)
def _sin_reanclaje(monkeypatch):
    import vault_raiz

    monkeypatch.setattr(vault_raiz, "_reanclar_constantes", lambda anterior, nueva: [])


def _importar_con_raiz(modulo: str, raiz: Path):
    vault_io.set_vault_root(raiz)
    return importlib.reload(importlib.import_module(modulo))


@pytest.mark.parametrize("modulo", MODULOS)
def test_ap49_ninguna_ruta_del_modulo_queda_en_el_vault_del_import(modulo, tmp_path):
    antes, despues = tmp_path / "antes", tmp_path / "despues"
    antes.mkdir(), despues.mkdir()
    mod = _importar_con_raiz(modulo, antes)
    vault_io.set_vault_root(despues)
    congeladas = [
        nombre for nombre, valor in vars(mod).items()
        if isinstance(valor, Path) and antes.resolve() in valor.resolve().parents
    ]
    assert not congeladas, f"{modulo}: {congeladas} siguen en el vault del import"


def test_ap49_el_contexto_mcp_se_guarda_en_la_raiz_vigente(tmp_path):
    """El caso que se ve desde fuera: `save_context` decía guardar —y
    guardaba— en el vault que había al importar el módulo."""
    antes, despues = tmp_path / "antes", tmp_path / "despues"
    antes.mkdir(), despues.mkdir()
    mod = _importar_con_raiz("vault_mcp_context", antes)
    vault_io.set_vault_root(despues)
    r = mod.save_context()
    assert Path(r["path"]).resolve().is_relative_to(despues.resolve()), r
    assert not any(antes.rglob("vault_context.json"))

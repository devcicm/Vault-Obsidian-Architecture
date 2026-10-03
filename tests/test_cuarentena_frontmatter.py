"""AP-46: retener y devolver una nota no le rompe el frontmatter.

`_serializar_frontmatter` escribía cada `str` crudo tras `k: `. Un título que
la nota original guardaba citado —`"a: b #c"`— salía como `title: a: b #c`:
YAML inválido. La nota retenida perdía el bloque entero, y al devolverla lo
perdía también en su sitio. El criterio es el del consumidor (AP-44):
`yaml.safe_load` tiene que devolver lo que había.
"""

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from vault.kernel.frontmatter_parsing import separar_frontmatter  # noqa: E402

TITULO = "a: b #c"


@pytest.fixture
def vault(tmp_path):
    import vault_io

    root = tmp_path / "v"
    (root / "00_System").mkdir(parents=True)
    (root / "07_Knowledge").mkdir()
    vault_io.set_vault_root(root)
    return root


def _fm(path: Path) -> dict:
    bloque, _ = separar_frontmatter(path.read_text(encoding="utf-8"))
    datos = yaml.safe_load(bloque)
    assert isinstance(datos, dict), path.read_text(encoding="utf-8")[:300]
    return datos


def test_retener_y_devolver_conserva_un_titulo_citado(vault):
    from vault_quarantine import _servicio

    nota = vault / "07_Knowledge" / "n.md"
    nota.write_text(
        f'---\ntitle: "{TITULO}"\ntags: ["Ñandú"]\nn: 3\n'
        "createdAt: 2026-10-02T00:00:00Z\n---\n\ncuerpo\n",
        encoding="utf-8",
    )
    servicio = _servicio(vault)
    r = servicio.retener("07_Knowledge/n.md", "razon: con #almohadilla", "suspicious", "bot")
    retenida = _fm(vault / r["path"])
    assert retenida["title"] == TITULO and retenida["tags"] == ["Ñandú"]
    assert retenida["n"] == 3 and retenida["quarantine_reason"] == "razon: con #almohadilla"

    servicio.devolver(r["path"], "bot")
    devuelta = _fm(nota)
    assert devuelta["title"] == TITULO and devuelta["tags"] == ["Ñandú"]
    assert not any(k.startswith("quarantine_") for k in devuelta)

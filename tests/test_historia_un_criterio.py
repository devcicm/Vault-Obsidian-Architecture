"""Un solo criterio para nombrar y leer las versiones de `.history/`.

Medido en v41.2: cuatro lectores con cuatro criterios. `vault_undo` filtraba por
el prefijo `carpeta__stem-`, así que las versiones de `a-b.md` salían como
versiones de `a.md` y `--restore` podía devolverle a una nota el contenido de
otra; además ordenaba por mtime, que una copia del vault reescribe. `vault_write`
nombraba la versión por `slugify(title)` y no por el fichero. El dueño es
`vault.kernel.historia`; estos tests fijan que los lectores delegan en él.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ))

from vault.kernel import historia  # noqa: E402

import vault_diff  # noqa: E402
import vault_read  # noqa: E402
import vault_undo  # noqa: E402


@pytest.fixture
def vault(tmp_path, monkeypatch):
    raiz = tmp_path / "v"
    hist = raiz / ".history"
    hist.mkdir(parents=True)
    (raiz / "07_Knowledge").mkdir()
    for nombre in ("a.md", "a-b.md"):
        (raiz / "07_Knowledge" / nombre).write_text("x\n", encoding="utf-8")
    versiones = {
        "07_Knowledge__a-2026-01-01T00-00-00.md": 3,
        "07_Knowledge__a-2026-03-01T00-00-00.md": 1,
        "07_Knowledge__a-2026-03-01T00-00-00-1.md": 2,
        "07_Knowledge__a-b-2026-09-01T00-00-00.md": 0,
    }
    for nombre, edad in versiones.items():
        f = hist / nombre
        f.write_text(nombre, encoding="utf-8")
        # mtime al revés que el sello: quien ordene por mtime se delata.
        t = 1_700_000_000 + edad * 1000
        os.utime(f, (t, t))
    for mod in (vault_undo, vault_read, vault_diff):
        monkeypatch.setattr(mod, "_raiz", lambda r=raiz: r)
        monkeypatch.setattr(mod, "_history_dir", lambda h=hist: h)
    return raiz


ESPERADO = [
    "07_Knowledge__a-2026-03-01T00-00-00-1.md",
    "07_Knowledge__a-2026-03-01T00-00-00.md",
    "07_Knowledge__a-2026-01-01T00-00-00.md",
]


def test_el_dueno_no_mezcla_a_con_a_b_y_ordena_por_sello(vault):
    nombres = [v["filename"] for v in historia.versiones(vault / ".history", "07_Knowledge/a.md")]
    assert nombres == ESPERADO


def test_vault_undo_delega(vault):
    assert [v["filename"] for v in vault_undo.get_history_versions("07_Knowledge/a.md")] == ESPERADO


def test_vault_read_delega(vault):
    assert vault_read.get_history_versions(vault / "07_Knowledge" / "a.md") == ESPERADO


def test_vault_diff_delega(vault):
    assert vault_diff.get_history(vault / "07_Knowledge" / "a.md") == ESPERADO


def test_dos_versiones_en_el_mismo_segundo_no_se_pisan(tmp_path):
    ahora = datetime(2026, 5, 1, tzinfo=timezone.utc)
    primera = historia.nombre_libre(tmp_path, "s/n.md", ahora)
    primera.write_text("1", encoding="utf-8")
    segunda = historia.nombre_libre(tmp_path, "s/n.md", ahora)
    assert primera != segunda
    assert historia.parsear(segunda.name)["secuencia"] == 1


def test_la_historia_vieja_se_sigue_leyendo():
    """La forma que escribían `vault_undo` y `vault_write` antes de v41.3."""
    meta = historia.parsear("01_Projects__ans__architecture-2026-05-09T01-53-23.md")
    assert meta["stem"] == historia.clave("01_Projects/ans/architecture.md")


def test_nadie_fuera_del_kernel_construye_el_nombre_de_una_version():
    """El sello `%Y-%m-%dT%H-%M-%S` era la huella de cada copia del criterio."""
    huella = "%Y-%m-%dT%H-%M-%S"
    copias = [p.name for p in (RAIZ / "scripts").glob("*.py")
              if huella in p.read_text(encoding="utf-8")]
    assert copias == [], copias

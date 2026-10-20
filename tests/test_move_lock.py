"""F1/CIA-I — `vault_move` escribe bajo el lock de lo que reescribe.

Medido en v40.34: `vault_move` reescribía con `atomic_write_text` las notas que
enlazaban a la movida, `search-index.json`, `graph.json` y `move-log.json` sin
tomar ningún lock. Un `vault_append` concurrente sobre una nota que enlazaba
se perdía entero (el move escribía encima su lectura vieja), y dos moves en
paralelo se comían la entrada del otro en el índice y en el log. Todo con
`ok: true`.

Se mide la parte determinista: con lo que hay que reescribir tomado por otro
escritor, el move no lo pisa y lo dice.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.kernel.errores import problemas_de_forma  # noqa: E402
from vault.kernel import bloqueo  # noqa: E402
pytestmark = pytest.mark.slow  # carril rápido (-m "not slow"): el perfil de la suite del 2026-10-20 midió aquí llamadas > 25 s



def _mover(raiz: Path, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_move.py"), *argv, "--json"],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=180,
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


def _ocupar(objetivo: Path) -> None:
    """Otro proceso acaba de tomar el lock de `objetivo`."""
    lock_dir = objetivo.parent / ".locks" / f"{objetivo.name}.lock"
    lock_dir.mkdir(parents=True)
    (lock_dir / "owner.json").write_text(
        json.dumps(bloqueo.ficha_del_dueno("otro")), encoding="utf-8")


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for d in ("00_System", "99_Index", "07_Knowledge/viejo", "07_Knowledge/otra"):
        (raiz / d).mkdir(parents=True)
    k = raiz / "07_Knowledge"
    (k / "viejo" / "a.md").write_text("---\ntitle: a\n---\n# a\n", encoding="utf-8")
    (k / "otra" / "r.md").write_text("---\ntitle: r\n---\nver [[a]]\n", encoding="utf-8")
    (raiz / "99_Index" / "search-index.json").write_text(
        json.dumps({"notes": [{"path": "07_Knowledge/viejo/a.md"}]}), encoding="utf-8")
    return raiz


def test_con_la_nota_origen_tomada_no_mueve_nada(vault):
    origen = vault / "07_Knowledge" / "viejo" / "a.md"
    _ocupar(origen)
    r = _mover(vault, "--from", "07_Knowledge/viejo/a.md", "--to", "07_Knowledge/nuevo/z.md")
    assert r["ok"] is False and r["error_code"] == "NOTE_LOCKED", r
    assert problemas_de_forma(r) == [], r
    assert origen.read_text(encoding="utf-8").endswith("# a\n")
    assert not (vault / "07_Knowledge" / "nuevo").exists()
    assert "[[a]]" in (vault / "07_Knowledge" / "otra" / "r.md").read_text(encoding="utf-8")


def test_una_nota_que_enlaza_tomada_no_se_pisa_y_se_declara(vault):
    enlaza = vault / "07_Knowledge" / "otra" / "r.md"
    _ocupar(enlaza)
    r = _mover(vault, "--from", "07_Knowledge/viejo/a.md", "--to", "07_Knowledge/nuevo/z.md")
    # El movimiento ocurrió: ok:false mentiría. Pero el enlace pendiente se dice.
    assert r["ok"] is True, r
    assert r["links_pending"] == ["07_Knowledge/otra/r.md"], r
    assert r["degraded"], r
    assert enlaza.read_text(encoding="utf-8").endswith("ver [[a]]\n")
    assert (vault / "07_Knowledge" / "nuevo" / "z.md").exists()


def test_el_indice_tomado_no_se_pisa_y_se_declara(vault):
    indice = vault / "99_Index" / "search-index.json"
    antes = indice.read_bytes()
    _ocupar(indice)
    r = _mover(vault, "--from", "07_Knowledge/viejo/a.md", "--to", "07_Knowledge/nuevo/z.md")
    assert r["ok"] is True, r
    assert any(d.startswith("search-index") for d in r["degraded"]), r
    assert r["next"], r
    assert indice.read_bytes() == antes

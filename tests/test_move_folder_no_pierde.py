"""F1/CIA-A — mover una carpeta no borra nada de lo que contiene.

Medido en v40.34: `vault_move --folder viejo --to-folder destino` con una
subcarpeta y un adjunto devolvió `ok: true, notes_moved: 2` y dejó en disco
solo `a.md`. `sub/b.md` e `imagen.png` desaparecieron: ni en el destino ni en
`00_System/.trash/`. `move_folder` buscaba cada nota por `relative.name` (sin
subcarpeta), la de la subcarpeta fallaba con FILE_NOT_FOUND, y el
`shutil.rmtree(source)` final se llevaba por delante todo lo que no se había
movido.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _mover(raiz: Path, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_move.py"), *argv, "--json"],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for d in ("00_System", "99_Index", "07_Knowledge/viejo/sub", "07_Knowledge/otra"):
        (raiz / d).mkdir(parents=True)
    k = raiz / "07_Knowledge"
    (k / "viejo" / "a.md").write_text("---\ntitle: a\n---\n# a\n", encoding="utf-8")
    (k / "viejo" / "sub" / "b.md").write_text("---\ntitle: b\n---\n# b\n", encoding="utf-8")
    (k / "viejo" / "imagen.png").write_bytes(b"PNG")
    (k / "otra" / "r.md").write_text("---\ntitle: r\n---\nver [[b]]\n", encoding="utf-8")
    return raiz


def _contenido(raiz: Path) -> dict:
    return {f.relative_to(raiz).as_posix(): f.read_bytes()
            for f in raiz.rglob("*") if f.is_file() and ".locks" not in f.parts}


def test_mover_carpeta_conserva_subcarpetas_y_adjuntos(vault):
    r = _mover(vault, "--folder", "07_Knowledge/viejo", "--to-folder", "07_Knowledge/destino")
    assert r["ok"], r
    destino = vault / "07_Knowledge" / "destino"
    assert (destino / "a.md").read_text(encoding="utf-8").endswith("# a\n")
    assert (destino / "sub" / "b.md").read_text(encoding="utf-8").endswith("# b\n")
    assert (destino / "imagen.png").read_bytes() == b"PNG"
    assert r["notes_moved"] == 2, r
    assert not any((vault / "07_Knowledge" / "viejo").rglob("*.md"))


def test_un_destino_ocupado_no_mueve_nada(vault):
    (vault / "07_Knowledge" / "destino" / "sub").mkdir(parents=True)
    (vault / "07_Knowledge" / "destino" / "sub" / "b.md").write_text("ya estaba", encoding="utf-8")
    # El destino de carpeta existe: se rechaza antes de tocar nada.
    antes = _contenido(vault)
    r = _mover(vault, "--folder", "07_Knowledge/viejo", "--to-folder", "07_Knowledge/destino")
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH", r
    despues = _contenido(vault)
    assert {k: v for k, v in despues.items() if not k.startswith("00_System")} == \
           {k: v for k, v in antes.items() if not k.startswith("00_System")}


@pytest.mark.parametrize("argv", [
    ["--from", "07_Knowledge/viejo/sub/b.md", "--to", "07_Knowledge/nuevo/z.md"],
    ["--folder", "07_Knowledge/viejo", "--to-folder", "07_Knowledge/destino"],
])
def test_dry_run_no_toca_el_disco(vault, argv):
    """Medido en v40.34: la simulación reescribía `[[b]]` → `[[z]]` en las
    notas que enlazaban y creaba la carpeta destino con su índice. Tras un
    dry-run el vault quedaba con enlaces a una nota que no se movió."""
    antes = _contenido(vault)
    r = _mover(vault, *argv, "--dry-run")
    assert r["ok"] and r["dry_run"], r
    despues = _contenido(vault)
    traza = "00_System/.tool-trace.json"
    antes.pop(traza, None)
    despues.pop(traza, None)
    assert despues == antes
    assert not (vault / "07_Knowledge" / "nuevo").exists()
    assert not (vault / "07_Knowledge" / "destino").exists()

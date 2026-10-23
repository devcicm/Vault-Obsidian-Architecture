"""La acción `moved` se emite de verdad en el change-log de SP-01.

`vault_write`, `vault_delete`, `vault_undo` y el append dejaban su fila en
`00_System/change-log.md` y `.change-log.json`; el movimiento solo quedaba en el
move-log binario y en `.tool-trace.json`. La acción `moved` existía en el
contrato de `vault_change_log_add` (`new_path` obligatorio y todo) pero ninguna
tool la emitía — la tercera pata del trío move-log/change-log/tool-trace se
medía con su propio criterio. Medido contra un vault ajeno al estándar
(sonda CRUD de rutas, 2026-10-22): delete dejaba fila, move no.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "vault_move.py"


def _mover(raiz, *args):
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=env,
                          timeout=120)


def _vault_con_nota(tmp_path):
    """Un vault mínimo de una nota: `vault_move` rastrilla índices y grafo, así
    que la nota basta — los derivados que no existen solo quedan `degraded`."""
    raiz = tmp_path / "vault"
    origen = raiz / "07_Knowledge" / "a.md"
    origen.parent.mkdir(parents=True, exist_ok=True)
    destino = raiz / "07_Knowledge" / "movida.md"
    origen.write_text("---\ntitle: a\n---\n\nCuerpo de la nota a.\n",
                      encoding="utf-8")
    return raiz, origen, destino


def test_la_fila_moved_queda_en_el_change_log(tmp_path):
    raiz, origen, destino = _vault_con_nota(tmp_path)
    p = _mover(raiz, "--from", origen.relative_to(raiz).as_posix(),
               "--to", destino.relative_to(raiz).as_posix(), "--json")
    assert p.returncode == 0, (p.stdout, p.stderr)
    sobre = json.loads(p.stdout)
    assert sobre["ok"] is True

    # El envelope declara la fila que dejó.
    assert sobre["change_log"]["action"] == "moved"
    assert sobre["change_log"]["id"]

    # La fila existe en las dos caras de SP-01, con origen y destino.
    filas = json.loads((raiz / "00_System" / ".change-log.json")
                       .read_text(encoding="utf-8"))
    moved = [e for e in filas if e["action"] == "moved"]
    assert len(moved) == 1
    assert moved[0]["path"] == "07_Knowledge/a.md"
    assert moved[0]["new_path"] == "07_Knowledge/movida.md"

    legible = (raiz / "00_System" / "change-log.md").read_text(encoding="utf-8")
    assert "moved" in legible and "07_Knowledge/movida.md" in legible


def test_el_dry_run_no_deja_fila_de_moved(tmp_path):
    """El dry-run no toca el vault: menos un registro de algo que no pasó."""
    raiz, origen, destino = _vault_con_nota(tmp_path)
    p = _mover(raiz, "--from", origen.relative_to(raiz).as_posix(),
               "--to", destino.relative_to(raiz).as_posix(), "--dry-run", "--json")
    assert p.returncode == 0
    sobre = json.loads(p.stdout)
    assert sobre["change_log"] is None
    jsonl = raiz / "00_System" / ".change-log.json"
    if jsonl.exists():
        filas = json.loads(jsonl.read_text(encoding="utf-8"))
        assert [e for e in filas if e["action"] == "moved"] == []
    else:
        # Ni change-log: la simulación ni por ración escribe.
        assert not (raiz / "00_System" / "change-log.md").exists()

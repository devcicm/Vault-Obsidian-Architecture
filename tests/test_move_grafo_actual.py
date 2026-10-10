"""AP-47 — mover una nota actualiza el `graph.json` que escribe el productor de hoy.

`update_graph` solo conocía las formas legacy de `nodes` (lista de strings o de
objetos). El grafo actual —el de `vault_graph` y del refresco nota a nota— guarda
`nodes` como dict indexado por ruta, y recorrerlo con `enumerate` asignaba
`nodes[0]` sobre el dict: `RuntimeError: dictionary changed size during
iteration`. Medido como consumidor el 2026-10-10: todo `vault_move` salía con
`graph_updated: false` y `degraded`, así que el grafo nunca seguía a la nota.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _run(raiz: Path, script: str, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    return json.loads(texto[texto.index("{"):])


def _vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    for s in ("00_System", "07_Knowledge", "08_Runbooks", "99_Index"):
        (raiz / s).mkdir(parents=True)
    (raiz / "07_Knowledge" / "movible.md").write_text(
        "---\ntitle: movible\nstatus: draft\ntype: knowledge\n---\n# movible\n",
        encoding="utf-8")
    (raiz / "07_Knowledge" / "apunta.md").write_text(
        "---\ntitle: apunta\nstatus: draft\ntype: knowledge\n---\n# apunta\n\nver [[movible]]\n",
        encoding="utf-8")
    # El grafo lo escribe su productor, no el test: así tiene la forma de hoy.
    assert _run(raiz, "vault_graph.py").get("ok") is not False
    return raiz


def test_move_actualiza_el_grafo_indexado_por_ruta(tmp_path):
    # AP-47: el grafo derivado sigue a la nota movida, sin reconstruir.
    raiz = _vault(tmp_path)
    grafo = json.loads((raiz / "99_Index" / "graph.json").read_text(encoding="utf-8"))
    assert isinstance(grafo["nodes"], dict) and "07_Knowledge/movible.md" in grafo["nodes"]

    env = _run(raiz, "vault_move.py", "--from", "07_Knowledge/movible.md",
               "--to", "07_Knowledge/movida.md", "--json")
    assert env["ok"] is True, env
    assert env["degraded"] == [], env["degraded"]
    assert env["graph_updated"] is True, env

    grafo = json.loads((raiz / "99_Index" / "graph.json").read_text(encoding="utf-8"))
    assert "07_Knowledge/movible.md" not in grafo["nodes"]
    assert "07_Knowledge/movida.md" in grafo["nodes"]
    destinos = {(e["from"], e["to"]) for e in grafo["edges"]}
    assert ("07_Knowledge/apunta.md", "07_Knowledge/movida.md") in destinos, destinos
    assert not any(e["to"] == "07_Knowledge/movible.md" for e in grafo["edges"])


def test_move_dry_run_no_toca_el_grafo_indexado_por_ruta(tmp_path):
    raiz = _vault(tmp_path)
    antes = (raiz / "99_Index" / "graph.json").read_bytes()
    env = _run(raiz, "vault_move.py", "--from", "07_Knowledge/movible.md",
               "--to", "07_Knowledge/movida.md", "--json", "--dry-run")
    assert env["ok"] is True and env["degraded"] == [], env
    assert (raiz / "99_Index" / "graph.json").read_bytes() == antes

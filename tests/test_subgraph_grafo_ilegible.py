"""AP-51 — un grafo ilegible no se anuncia como un grafo que falta.

Medido como consumidor el 2026-10-10: con `99_Index/graph.json` corrupto,
`vault_subgraph` respondía GRAPH_MISSING «No hay grafo». El agente que confía en
el código busca un fichero que sí existe; la causa es otra y la receta del
catálogo para leerlo (GRAPH_LOAD_ERROR) ya decía regenerarlo.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _run(raiz: Path, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_subgraph.py"), *args],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    assert texto, p.stderr
    return json.loads(texto[texto.index("{"):])


def _vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    for d in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / d).mkdir(parents=True)
    return raiz


def test_grafo_corrupto_no_es_grafo_ausente_ap51(tmp_path):
    raiz = _vault(tmp_path)
    (raiz / "99_Index" / "graph.json").write_text("{roto", encoding="utf-8")
    env = _run(raiz, "--seeds", "nota")
    assert env["ok"] is False
    assert env["error_code"] == "GRAPH_LOAD_ERROR", env


def test_grafo_ausente_sigue_siendo_ausente(tmp_path):
    env = _run(_vault(tmp_path), "--seeds", "nota")
    assert env["error_code"] == "GRAPH_MISSING", env

"""AP-51 — `vault_impact` no anuncia un grafo ilegible como ausente.

Medido como consumidor el 2026-10-10, el mismo defecto que `vault_subgraph`:
con `99_Index/graph.json` corrupto, `vault_impact` respondía INDEX_NOT_FOUND
«graph.json not found». El fichero existe; lo que falla es leerlo.
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
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_impact.py"), *args],
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
    env = _run(raiz, "--changed", "07_Knowledge/nota.md")
    assert env["ok"] is False
    assert env["error_code"] == "GRAPH_LOAD_ERROR", env


def test_grafo_ausente_sigue_siendo_ausente(tmp_path):
    env = _run(_vault(tmp_path), "--changed", "07_Knowledge/nota.md")
    assert env["error_code"] == "INDEX_NOT_FOUND", env

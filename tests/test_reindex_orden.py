"""AP-47 — la reconstrucción no deja fuera del índice lo que ella misma escribe.

Medido el 2026-10-07 con `tests/banco_agente.py`: a un vault le faltaba
`21_QA/index.md`, `vault_reindex --graph` lo volvía a escribir al rehacer los
índices de sección, pero eso pasaba DESPUÉS de construir `search-index.json`.
El `--check` siguiente seguía en `index_stale` con la nota recién creada en
`missing_in_index`, y hacía falta una segunda pasada. Una recuperación que
hay que ejecutar dos veces no es una recuperación.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))


def _reindex(raiz: Path, *argv: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_reindex.py"), *argv],
        env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=str(raiz.parent), timeout=300)
    salida = p.stdout.strip()
    assert salida, p.stderr[-1000:]
    return json.loads(salida[salida.index("{"):])


def test_ap47_una_pasada_de_reindex_deja_el_indice_al_dia(tmp_path):
    from vault.ciclo_de_vida import producto

    raiz = tmp_path / "vault"
    assert producto.inicializar_runtime(raiz)["ok"]
    assert _reindex(raiz, "--graph")["ok"] is True
    (raiz / "21_QA" / "index.md").unlink()

    r = _reindex(raiz, "--graph")
    assert r["ok"] is True and r.get("indexes_rebuilt"), r
    assert (raiz / "21_QA" / "index.md").is_file(), "la reconstrucción lo reescribe"

    r = _reindex(raiz, "--check")
    assert r["ok"] is True, {k: r.get(k) for k in ("status", "missing_in_index", "stale_in_index")}

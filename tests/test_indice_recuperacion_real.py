"""La recuperación de `INDEX_NOT_FOUND` hace lo que su pista promete.

Medido el 2026-10-01 con la wheel en un venv limpio: tras `vault init`, la
recuperación publicada era `vault_reindex` con `args: []` y la pista decía
que regeneraba «graph.json, search-index.json». Sin `--graph` solo escribe el
de búsqueda: el consumidor la seguía al pie de la letra y `vault_validate`
seguía fallando por `99_Index/graph.json (missing)`.

Se mide con el criterio del consumidor (AP-44): se ejecuta la recuperación
tal cual la publica el catálogo, en otro proceso, sobre un runtime nuevo.
"""

import os
import subprocess
import sys
from pathlib import Path

from vault.ciclo_de_vida import producto
from vault.kernel.errores import ERROR_CATALOG

ROOT = Path(__file__).resolve().parent.parent


def test_la_recuperacion_publicada_regenera_los_indices_que_nombra(tmp_path):
    raiz = tmp_path / "runtime"
    assert producto.inicializar_runtime(raiz)["ok"]
    recuperacion = ERROR_CATALOG["INDEX_NOT_FOUND"]["recovery"]

    proceso = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / f"{recuperacion['tool']}.py"),
         *recuperacion["args"]],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(tmp_path), timeout=300,
    )
    assert proceso.returncode == 0, proceso.stderr[-1000:]

    # Los dos son los que `vault_validate` exige; la pista tiene que nombrarlos
    # y la recuperación escribirlos. Quitar uno de la pista no es arreglarlo.
    for indice in ("search-index.json", "graph.json"):
        assert indice in recuperacion["hint"], recuperacion["hint"]
        assert (raiz / "99_Index" / indice).is_file(), (
            f"la pista promete {indice} y la recuperación no lo escribe")

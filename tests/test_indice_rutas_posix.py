"""El índice de búsqueda escribe rutas con `/` en toda plataforma.

Medido en Windows antes del arreglo: `vault_write` pasaba al índice
`str(relative_to)`, así que `search-index.json` guardaba
`07_Knowledge\\Resiliencia.md`. `vault_context_pack` separa la sección con
`split("/")`, y en cuanto la consulta inducía una sección —«como funciona el
circuit breaker» infiere `07_Knowledge`— descartaba toda coincidencia léxica:
`candidates_considered: 0` con la nota en disco y `vault_search` encontrándola.

La CI ejecuta la suite en `windows-latest`; en Linux este test pasa también sin
el arreglo, porque allí `str(relative_to)` ya lleva `/`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

CONTENIDO = (
    "# Resiliencia\n\n"
    "El servicio usa circuit breaker con umbral de cinco fallos.\n\n"
    "Los reintentos usan backoff exponencial con jitter.\n\n"
    "Los tiempos de espera se fijan por dependencia externa."
)


def _ejecutar(raiz: Path, script: str, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / f"{script}.py"), *argv],
        env=dict(
            os.environ,
            VAULT_ROOT=str(raiz),
            VAULT_STRICT_ROOT="1",
            PYTHONIOENCODING="utf-8",
            VAULT_AGENT="system",
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(SCRIPTS),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    raiz.mkdir()
    assert _ejecutar(raiz, "vault_init", "--no-audit")["ok"]
    escrito = _ejecutar(
        raiz, "vault_write", "--folder", "07_Knowledge", "--title", "Resiliencia",
        "--tags", "resiliencia", "--content", CONTENIDO,
    )
    assert escrito["ok"], escrito
    return raiz


def test_el_indice_guarda_rutas_con_barra(vault):
    indice = json.loads(
        (vault / "99_Index" / "search-index.json").read_text(encoding="utf-8")
    )
    rutas = [n["path"] for n in indice["notes"]]
    assert "07_Knowledge/resiliencia.md" in rutas
    assert not [r for r in rutas if "\\" in r]


def test_consulta_con_seccion_inferida_entrega_la_nota(vault):
    paquete = _ejecutar(
        vault, "vault_context_pack",
        "--query", "como funciona el circuit breaker",
        "--budget", "800", "--format", "json",
    )
    assert paquete["ok"], paquete
    # La precondición del defecto: la consulta induce la sección.
    assert paquete["structured"]["sections"] == ["07_Knowledge"]
    incluidas = [n["path"] for n in paquete["included"]]
    assert "07_Knowledge/resiliencia.md" in incluidas, paquete

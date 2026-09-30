"""AP-37 — la consulta no presenta un grafo desfasado como si estuviera al día.

Medido en v40.34: tras escribir una nota después de `vault_graph`,
`vault_subgraph --seeds <nota>` respondía «Ninguna semilla existe en el
grafo» sobre una nota que existe, y `vault_context_pack` devolvía el paquete
sin aviso alguno aunque las aristas de la nota nueva no contaran. Además
`graph-enriched.json` se prefería siempre, también cuando era más viejo que
un `graph.json` regenerado después.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CUERPO = "uno dos tres cuatro cinco seis\nsiete ocho nueve diez once\ndoce trece catorce quince"


def _ejecutar(raiz: Path, script: str, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


def _escribir(raiz: Path, titulo: str, extra: str = "") -> None:
    env = _ejecutar(raiz, "vault_write.py", "--folder", "07_Knowledge", "--title", titulo,
                    "--content", CUERPO + extra, "--tags", "t",
                    "--meta", json.dumps({"agent": "pytest"}))
    assert env["ok"] is True, env


@pytest.fixture
def raiz(tmp_path):
    raiz = tmp_path / "vault"
    raiz.mkdir()
    assert _ejecutar(raiz, "vault_init.py")["ok"] is True
    _escribir(raiz, "Alfa")
    assert _ejecutar(raiz, "vault_graph.py")["ok"] is True
    return raiz


def test_grafo_al_dia_no_se_declara_desfasado(raiz):
    env = _ejecutar(raiz, "vault_subgraph.py", "--seeds", "Alfa")
    assert env["ok"] is True, env
    assert env["stale_graph"] is False, env["stale"]


def test_ap37_una_nota_nueva_se_declara_en_vez_de_negarse(raiz):
    _escribir(raiz, "Beta", " [[Alfa]]")
    env = _ejecutar(raiz, "vault_subgraph.py", "--seeds", "Beta")
    assert env["ok"] is False and env["error_code"] == "NO_SEEDS_RESOLVED"
    assert env["stale_graph"] is True
    assert env["stale"]["new"] == 1
    assert "07_Knowledge/Beta.md" in env["stale"]["sample_new"]
    assert "vault_graph" in env["error"]


def test_ap37_context_pack_avisa_del_desfase(raiz):
    _escribir(raiz, "Beta", " [[Alfa]]")
    env = _ejecutar(raiz, "vault_context_pack.py", "--query", "Beta siete ocho")
    assert env["ok"] is True, env
    assert any("grafo desactualizado" in w for w in env["warnings"]), env["warnings"]


def test_un_enriquecido_mas_viejo_no_tapa_al_grafo_basico(raiz):
    indices = raiz / "99_Index"
    enriquecido = indices / "graph-enriched.json"
    enriquecido.write_text(json.dumps({"nodes": {}, "edges": []}), encoding="utf-8")
    viejo = time.time() - 3600
    os.utime(enriquecido, (viejo, viejo))
    env = _ejecutar(raiz, "vault_subgraph.py", "--seeds", "Alfa")
    assert env["ok"] is True, env
    assert env["stats"]["graph_source"] == "graph.json"

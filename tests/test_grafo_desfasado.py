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


def _escribir_a_mano(raiz: Path, slug: str, extra: str = "") -> None:
    """Una nota que llega por fuera del toolkit —Obsidian, un editor—: no pasa
    por `atomic_write_text` y por eso tampoco por el gancho que refresca el
    grafo. Es el único caso en que el grafo puede quedar desfasado."""
    (raiz / "07_Knowledge" / f"{slug}.md").write_text(
        f"---\ntitle: {slug.title()}\ntags: [t]\n---\n\n{CUERPO}{extra}\n", encoding="utf-8"
    )


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


def test_ap47_una_nota_escrita_por_el_toolkit_ya_esta_en_el_grafo(raiz):
    """Desde el gancho `_auto_grafo` la escritura refresca el grafo: lo que
    antes había que declarar como desfase ya no ocurre por esta vía."""
    _escribir(raiz, "Beta", " [[Alfa]]")
    env = _ejecutar(raiz, "vault_subgraph.py", "--seeds", "Beta")
    assert env["ok"] is True, env
    assert env["stale_graph"] is False, env["stale"]
    assert "07_Knowledge/alfa.md" in {n["path"] for n in env["nodes"]}


def test_ap37_una_nota_nueva_se_declara_en_vez_de_negarse(raiz):
    # superseded_by: v40.x (AP-47) — escribía con `vault_write`, que ahora
    # refresca el grafo; el desfase solo lo produce una escritura de fuera.
    _escribir_a_mano(raiz, "beta", " [[Alfa]]")
    env = _ejecutar(raiz, "vault_subgraph.py", "--seeds", "Beta")
    assert env["ok"] is False and env["error_code"] == "NO_SEEDS_RESOLVED"
    assert env["stale_graph"] is True
    assert env["stale"]["new"] == 1
    assert "07_Knowledge/beta.md" in env["stale"]["sample_new"]
    assert "vault_graph" in env["error"]


def test_ap37_context_pack_avisa_del_desfase(raiz):
    _escribir_a_mano(raiz, "beta", " [[Alfa]]")
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

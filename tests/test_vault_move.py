"""vault_move sobre vaults preexistentes — esquemas legacy y atomicidad.

Los dos defectos que cubre este archivo se encontraron sanando un vault real
(BuilderX, v32) con el toolkit actual:

1. `graph.json` guardaba `nodes` como lista de **strings**, no de objetos. El
   `node.get("id")` reventaba con AttributeError.
2. Peor: el crash ocurría **después** del `shutil.move`. La nota ya estaba en su
   destino y la tool devolvía `ok:false`. El agente concluía que no había movido
   nada — la forma más cara de mentir, porque el vault y el reporte discrepan.

Un vault preexistente es exactamente el caso de uso de la reubicación, así que
tolerar su esquema no es una concesión: es el contrato.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


GRAPH_LEGACY = {"nodes": ["nota-vieja", "otra"], "edges": [], "stats": {}}
GRAPH_MODERNO = {
    "nodes": [{"id": "nota-vieja", "path": "01_Projects/nota-vieja.md"}],
    "edges": [],
    "stats": {},
}


def _vault(tmp_path: Path, graph: dict, search: object) -> Path:
    root = tmp_path / "vault"
    for carpeta in ("00_System", "99_Index", "01_Projects", "03_Decisions"):
        (root / carpeta).mkdir(parents=True)
    (root / "01_Projects" / "nota-vieja.md").write_text(
        "---\nid: nota-vieja\ntitle: Nota\nagent: claude\n---\n\n# Nota\n",
        encoding="utf-8",
    )
    (root / "99_Index" / "graph.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )
    (root / "99_Index" / "search-index.json").write_text(
        json.dumps(search), encoding="utf-8"
    )
    return root


def _mover(root: Path, extra=()) -> dict:
    salida = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "vault_move.py"),
            "--from", "01_Projects/nota-vieja.md",
            "--to", "03_Decisions/nota-vieja.md",
            "--json",
            *extra,
        ],
        capture_output=True,
        encoding="utf-8",
        env={
            **_env(),
            "VAULT_ROOT": str(root),
            "VAULT_AGENT": "pytest",
            "VAULT_VOICE": "0",
        },
        cwd=str(REPO_ROOT),
    )
    texto = (salida.stdout or "").strip()
    assert texto, f"sin salida; stderr={salida.stderr}"
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return json.loads(texto.splitlines()[-1])


def _env() -> dict:
    import os

    e = dict(os.environ)
    e["PYTHONIOENCODING"] = "utf-8"
    e.pop("VAULT_STRICT_ROOT", None)
    return e


# ─── Esquemas de índice que un vault preexistente puede traer ────────────────


@pytest.mark.parametrize(
    "graph,search",
    [
        (GRAPH_LEGACY, {"notes": [{"path": "01_Projects/nota-vieja.md"}]}),
        (GRAPH_MODERNO, {"notes": [{"path": "01_Projects/nota-vieja.md"}]}),
        (GRAPH_LEGACY, {"notes": ["01_Projects/nota-vieja.md"]}),
        ({"nodes": []}, []),
    ],
    ids=["nodes-str", "nodes-dict", "notes-str", "search-lista"],
)
def test_mueve_pese_al_esquema_del_indice(tmp_path, graph, search):
    root = _vault(tmp_path, graph, search)
    r = _mover(root)
    assert r["ok"] is True, r
    assert not (root / "01_Projects" / "nota-vieja.md").exists()
    assert (root / "03_Decisions" / "nota-vieja.md").exists()


def test_nodes_str_se_reescribe_no_se_ignora(tmp_path):
    """Tolerar el esquema legacy no puede significar dejar el grafo mintiendo."""
    root = _vault(tmp_path, GRAPH_LEGACY, {"notes": []})
    assert _mover(root)["ok"] is True
    grafo = json.loads((root / "99_Index" / "graph.json").read_text(encoding="utf-8"))
    assert "nota-vieja" in grafo["nodes"], "el stem sigue siendo el mismo tras el move"


# ─── El reporte no puede contradecir al disco ────────────────────────────────


def test_un_indice_corrupto_no_convierte_el_move_en_fracaso(tmp_path):
    """El fallo real: crash tras el shutil.move y ok:false con la nota ya movida."""
    root = _vault(tmp_path, GRAPH_LEGACY, {"notes": []})
    (root / "99_Index" / "graph.json").write_text("{no es json", encoding="utf-8")

    r = _mover(root)
    movida = (root / "03_Decisions" / "nota-vieja.md").exists()

    assert movida, "precondición: el move se ejecutó"
    assert r["ok"] is True, "la nota está movida en disco; ok:false sería falso"
    assert r["degraded"], "un índice que no se pudo actualizar tiene que salir en el reporte"
    assert r["next"] == "vault_reindex --graph"


def test_sin_degradacion_no_hay_ruido(tmp_path):
    root = _vault(tmp_path, GRAPH_MODERNO, {"notes": []})
    r = _mover(root)
    assert r["degraded"] == []
    assert r["next"] is None


# ─── Contrato básico que ya existía y no puede romperse ──────────────────────


def test_dry_run_no_toca_el_disco(tmp_path):
    root = _vault(tmp_path, GRAPH_LEGACY, {"notes": []})
    antes = (root / "99_Index" / "graph.json").read_text(encoding="utf-8")
    r = _mover(root, extra=("--dry-run",))
    assert r["ok"] is True
    assert (root / "01_Projects" / "nota-vieja.md").exists()
    assert not (root / "03_Decisions" / "nota-vieja.md").exists()
    assert (root / "99_Index" / "graph.json").read_text(encoding="utf-8") == antes


def test_origen_inexistente_si_es_error(tmp_path):
    root = _vault(tmp_path, GRAPH_MODERNO, {"notes": []})
    (root / "01_Projects" / "nota-vieja.md").unlink()
    assert _mover(root)["ok"] is False

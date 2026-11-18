"""Flow QA (2026-11-17): following a `vault_audit` nextAction ends the action.

- QA-FL-08 (a): with code notes and no typed relation, `untyped_graph` kept
  prescribing `vault_graph --typed` after that pass had already run: the pass
  cannot create typed edges that no relation declares.
- QA-FL-08 (b): `moved_node` echoed the last five moves forever, also after
  `vault_graph` had regenerated the graph it asked to regenerate.
- QA-FL-09: `missing_tags` built a `vault_write --folder … --title …` that wrote
  a second note next to the untagged one, with a hard-coded `--tags ans`.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List

import pytest

from apoyo import correr_tool, escribir_nota


@pytest.fixture(scope="module")
def _vault_base(tmp_path_factory) -> Path:
    vault = tmp_path_factory.mktemp("auditoria") / "vault"
    vault.mkdir()
    assert correr_tool("vault_init", vault=vault).envelope["ok"]
    assert correr_tool("vault_project", "--add", "demo", vault=vault).envelope["ok"]
    return vault


@pytest.fixture
def vault(_vault_base, tmp_path) -> Path:
    copia = tmp_path / "vault"
    shutil.copytree(_vault_base, copia)
    return copia


def _acciones(vault: Path, categoria: str) -> List[dict]:
    informe = correr_tool("vault_audit", vault=vault).envelope
    assert informe["ok"], informe
    return [a for a in informe["nextActions"] if a.get("category") == categoria]


def _modulo(vault: Path, tmp_path: Path, nombre: str) -> None:
    fuente = tmp_path / "src" / f"{nombre}.py"
    fuente.parent.mkdir(exist_ok=True)
    fuente.write_text("def f():\n    return 1\n", encoding="utf-8")
    r = correr_tool("vault_code_module", "--project", "demo", "--file_path", fuente,
                    "--description", "Modulo de prueba para el grafo tipado", vault=vault)
    assert r.envelope["ok"], r.envelope


# ── QA-FL-08 (a) ──────────────────────────────────────────────────────────────

def test_fl08_grafo_tipado_ya_generado_no_vuelve_a_prescribir_la_misma_pasada(vault, tmp_path):
    _modulo(vault, tmp_path, "mod")
    for _ in range(2):
        assert correr_tool("vault_graph", "--typed", vault=vault).envelope["ok"]

    acciones = _acciones(vault, "untyped_graph")
    assert acciones, "AP-31 still measures the untyped graph"
    for accion in acciones:
        assert "vault_graph.py --typed" not in accion["command"], accion
        assert "vault_code_relation.py" in accion["command"], accion


def test_fl08_relacion_nueva_tras_la_pasada_tipada_pide_regenerarla(vault, tmp_path):
    _modulo(vault, tmp_path, "a")
    _modulo(vault, tmp_path, "b")
    assert correr_tool("vault_graph", "--typed", vault=vault).envelope["ok"]
    r = correr_tool("vault_code_relation", "--project", "demo",
                    "--from_file", "a.py", "--to_file", "b.py",
                    "--relation_type", "imports", vault=vault)
    assert r.envelope["ok"], r.envelope

    acciones = _acciones(vault, "untyped_graph")
    assert acciones
    assert all(a["command"] == "python scripts/vault_graph.py --typed" for a in acciones), acciones


# ── QA-FL-08 (b) ──────────────────────────────────────────────────────────────

_ORIGEN = "07_Knowledge/00-07_knowledge-primer.md"
_DESTINO = "07_Knowledge/primer-movido.md"


def test_fl08_nodo_movido_deja_de_pedir_el_grafo_cuando_el_grafo_es_posterior(vault):
    r = correr_tool("vault_move", "--from", _ORIGEN, "--to", _DESTINO, "--json", vault=vault)
    assert r.envelope["ok"], r.envelope
    grafo = vault / "99_Index" / "graph.json"
    # The move leaves a graph that already has it: nothing to ask for.
    assert _DESTINO in grafo.read_text(encoding="utf-8")
    assert _acciones(vault, "moved_node") == []

    # A graph older than the move (written before it) is reported...
    os.utime(grafo, (grafo.stat().st_atime, grafo.stat().st_mtime - 3600))
    antes = _acciones(vault, "moved_node")
    assert [(a["from"], a["to"]) for a in antes] == [(_ORIGEN, _DESTINO)]
    assert "vault_graph.py" in antes[0]["command"]

    # ...and following the action ends it, instead of echoing it forever.
    assert correr_tool("vault_graph", vault=vault).envelope["ok"]
    assert _acciones(vault, "moved_node") == []


# ── QA-FL-09 ──────────────────────────────────────────────────────────────────

_SIN_TAGS = "05_Patterns/code/demo-repository.md"


def _nota_sin_tags(vault: Path) -> None:
    escribir_nota(vault, _SIN_TAGS, {
        "title": "Repository", "type": "pattern", "status": "draft", "project": "demo",
        "agent": "pytest", "createdAt": "2026-11-17T00:00:00Z",
        "updatedAt": "2026-11-17T00:00:00Z",
    }, """
        # Repository

        Patron de acceso a datos con una interfaz por agregado.
        Separa la persistencia del dominio.
        Lo usan los servicios de la aplicacion.
    """)


def test_fl09_missing_tags_apunta_a_la_nota_existente_sin_tags_fijos(vault):
    _nota_sin_tags(vault)

    acciones = [a for a in _acciones(vault, "missing_tags") if a.get("path") == _SIN_TAGS]
    assert len(acciones) == 1, acciones
    accion = acciones[0]
    assert _SIN_TAGS in accion["command"], accion
    assert "vault_write" not in accion["command"], accion
    assert "--tags" not in accion["command"] and " ans" not in accion["command"], accion

    # Following it writes no second note next to the untagged one.
    antes = sorted(p.name for p in (vault / "05_Patterns" / "code").glob("*.md"))
    r = correr_tool("vault_tags", "--suggest", _SIN_TAGS, vault=vault)
    assert r.codigo == 0 and r.envelope["ok"], r.envelope
    assert r.envelope["path"] == _SIN_TAGS
    assert sorted(p.name for p in (vault / "05_Patterns" / "code").glob("*.md")) == antes

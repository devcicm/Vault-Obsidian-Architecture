"""Tests TDD del motor nativo de análisis estructural de grafo (estilo Graphify).

Verifica en Python stdlib puro (0 BD, 0 embeddings, 0 dependencias externas):
- Etiquetado epistémico canónico en aristas (`EXTRACTED`, `INFERRED`, `AMBIGUOUS`).
- Detección determinista de *God Nodes* (hubs estructurales de alto grado).
- Detección determinista de comunidades (*Label Propagation*) y puentes entre clústeres.
- Consultas `vault_subgraph --path`, `--explain` y `--report` (JSON y Markdown).
- Reporte opcional en `vault_graph --report`.
- Lector de interoperabilidad `importar_grafo_graphify()` (NetworkX node-link).
- Guía «Grafo primero» en `vault_preferences --adapters` dentro del tope de líneas.
"""

from __future__ import annotations

import json
from pathlib import Path

from apoyo import SCRIPTS, correr_tool


def _grafo_dos_comunidades() -> dict:
    """Dos clústeres densos (A: 03_Decisions, B: 07_Knowledge) unidos por 1 puente."""
    nodes = {
        "03_Decisions/adr-hub.md": {"title": "ADR Hub", "type": "03_Decisions", "tags": ["arch"], "status": "active"},
        "03_Decisions/adr-1.md": {"title": "ADR 1", "type": "03_Decisions", "tags": ["arch"], "status": "active"},
        "03_Decisions/adr-2.md": {"title": "ADR 2", "type": "03_Decisions", "tags": ["arch"], "status": "active"},
        "03_Decisions/adr-3.md": {"title": "ADR 3", "type": "03_Decisions", "tags": ["arch"], "status": "active"},
        "07_Knowledge/kb-hub.md": {"title": "KB Hub", "type": "07_Knowledge", "tags": ["kb"], "status": "active"},
        "07_Knowledge/kb-1.md": {"title": "KB 1", "type": "07_Knowledge", "tags": ["kb"], "status": "active"},
        "07_Knowledge/kb-2.md": {"title": "KB 2", "type": "07_Knowledge", "tags": ["kb"], "status": "active"},
        "07_Knowledge/kb-3.md": {"title": "KB 3", "type": "07_Knowledge", "tags": ["kb"], "status": "active"},
        "07_Knowledge/aislada.md": {"title": "Nota Aislada", "type": "07_Knowledge", "tags": [], "status": "active"},
    }
    edges = [
        # Clúster A (triángulo completo + hub)
        {"from": "03_Decisions/adr-hub.md", "to": "03_Decisions/adr-1.md", "type": "wiki-link"},
        {"from": "03_Decisions/adr-hub.md", "to": "03_Decisions/adr-2.md", "type": "wiki-link"},
        {"from": "03_Decisions/adr-hub.md", "to": "03_Decisions/adr-3.md", "type": "wiki-link"},
        {"from": "03_Decisions/adr-1.md", "to": "03_Decisions/adr-2.md", "predicate": "supersedes"},
        {"from": "03_Decisions/adr-2.md", "to": "03_Decisions/adr-3.md", "predicate": "related"},
        {"from": "03_Decisions/adr-3.md", "to": "03_Decisions/adr-1.md", "predicate": "depends_on"},
        # Clúster B (triángulo completo + hub)
        {"from": "07_Knowledge/kb-hub.md", "to": "07_Knowledge/kb-1.md", "type": "wiki-link"},
        {"from": "07_Knowledge/kb-hub.md", "to": "07_Knowledge/kb-2.md", "type": "wiki-link"},
        {"from": "07_Knowledge/kb-hub.md", "to": "07_Knowledge/kb-3.md", "type": "wiki-link"},
        {"from": "07_Knowledge/kb-1.md", "to": "07_Knowledge/kb-2.md", "predicate": "mentions"},
        {"from": "07_Knowledge/kb-2.md", "to": "07_Knowledge/kb-3.md", "predicate": "shared_tag"},
        {"from": "07_Knowledge/kb-3.md", "to": "07_Knowledge/kb-1.md", "predicate": "implements"},
        # Puente único entre clúster A y clúster B + arista ambigua + retornos al hub
        {"from": "03_Decisions/adr-hub.md", "to": "07_Knowledge/kb-hub.md", "predicate": "implements"},
        {"from": "03_Decisions/adr-1.md", "to": "03_Decisions/adr-hub.md", "predicate": "references"},
        {"from": "03_Decisions/adr-2.md", "to": "03_Decisions/adr-hub.md", "predicate": "references"},
        {"from": "03_Decisions/adr-1.md", "to": "03_Decisions/adr-3.md", "predicate": "custom_guess"},
    ]
    return {"nodes": nodes, "edges": edges}


def test_clasificacion_epistemica_y_consolidacion_aristas():
    from vault.grafo.aristas import (
        CONFIANZA_EPISTEMICA,
        clasificar_arista_epistemica,
        consolidar_aristas,
    )

    assert CONFIANZA_EPISTEMICA == ("EXTRACTED", "INFERRED", "AMBIGUOUS")
    assert clasificar_arista_epistemica({"type": "wiki-link"}) == ("EXTRACTED", 1.0)
    assert clasificar_arista_epistemica({"predicate": "implements"}) == ("EXTRACTED", 1.0)
    assert clasificar_arista_epistemica({"predicate": "shared_tag"}) == ("INFERRED", 0.75)
    assert clasificar_arista_epistemica({"predicate": "mentions"}) == ("INFERRED", 0.8)
    assert clasificar_arista_epistemica({"predicate": "unknown_rel"}) == ("AMBIGUOUS", 0.5)
    # Respeta etiqueta explícita si ya viene válida
    assert clasificar_arista_epistemica({"predicate": "related", "epistemic": "INFERRED", "confidence": 0.82}) == ("INFERRED", 0.82)

    consolidadas = consolidar_aristas([
        {"from": "a.md", "to": "b.md", "type": "wiki-link"},
        {"from": "a.md", "to": "b.md", "type": "wiki-link"},
        {"from": "a.md", "to": "c.md", "predicate": "shared_tag"},
    ])
    assert len(consolidadas) == 2
    assert consolidadas[0]["epistemic"] == "EXTRACTED" and consolidadas[0]["confidence"] == 1.0
    assert consolidadas[0]["occurrences"] == 2
    assert consolidadas[1]["epistemic"] == "INFERRED" and consolidadas[1]["confidence"] == 0.75


def test_god_nodes_comunidades_puentes_y_reporte_determinista():
    from vault.grafo.analisis import (
        detectar_comunidades,
        detectar_god_nodes,
        formatear_reporte_markdown,
        reporte_grafo,
    )

    g = _grafo_dos_comunidades()
    gods = detectar_god_nodes(g, top_k=5)
    assert gods[0]["path"] == "03_Decisions/adr-hub.md"
    assert gods[0]["total_degree"] == 6

    c1 = detectar_comunidades(g)
    c2 = detectar_comunidades(g)
    assert c1 == c2, "Label Propagation debe ser 100 % determinista"
    assert c1["isolated_nodes"] == 1
    assert c1["total_communities"] >= 1
    # Si hay >= 2 comunidades, debe existir el puente adr-hub -> kb-hub
    if c1["total_communities"] >= 2:
        assert any(
            b["from"] == "03_Decisions/adr-hub.md" and b["to"] == "07_Knowledge/kb-hub.md"
            for b in c1["bridges"]
        ), c1["bridges"]

    rep = reporte_grafo(g)
    assert rep["ok"] is True
    assert rep["summary"]["total_nodes"] == 9
    assert rep["summary"]["epistemic"]["EXTRACTED"] == 13
    assert rep["summary"]["epistemic"]["INFERRED"] == 2
    assert rep["summary"]["epistemic"]["AMBIGUOUS"] == 1

    md = formatear_reporte_markdown(rep)
    assert "GRAPH_REPORT" in md
    assert "God Nodes" in md
    assert "EXTRACTED" in md and "INFERRED" in md and "AMBIGUOUS" in md


def test_path_y_explain_nativos():
    from vault.grafo.analisis import camino_mas_corto, explicar_nodo

    g = _grafo_dos_comunidades()
    p = camino_mas_corto(g, "adr-1", "kb-2")
    assert p["ok"] is True and p["found"] is True
    assert p["hops"] == 3
    assert p["nodes"][0] == "03_Decisions/adr-1.md"
    assert p["nodes"][-1] == "07_Knowledge/kb-2.md"
    assert "EXTRACTED" in p["trace"]

    sin_camino = camino_mas_corto(g, "adr-1", "aislada")
    assert sin_camino["ok"] is True and sin_camino["found"] is False

    exp = explicar_nodo(g, "adr-hub")
    assert exp["ok"] is True
    assert exp["node"]["path"] == "03_Decisions/adr-hub.md"
    assert exp["node"]["is_god_node"] is True
    assert exp["node"]["out_degree"] == 4
    assert exp["node"]["in_degree"] == 2
    assert exp["epistemic_breakdown"]["EXTRACTED"] == 6


def test_importar_grafo_graphify_node_link(tmp_path: Path):
    from vault.grafo.analisis import importar_grafo_graphify

    archivo = tmp_path / "graph.json"
    archivo.write_text(
        json.dumps({
            "nodes": [
                {"id": "auth.py::login", "label": "login", "type": "function", "file": "src/auth.py"},
                {"id": "db.py::query", "label": "query", "type": "function", "file": "src/db.py"},
            ],
            "links": [
                {"source": "auth.py::login", "target": "db.py::query", "relation": "calls", "confidence_label": "EXTRACTED", "confidence": 1.0},
            ],
        }),
        encoding="utf-8",
    )
    grafo = importar_grafo_graphify(archivo)
    assert grafo["source_format"] == "graphify"
    assert grafo["stats"]["totalNodes"] == 2
    assert grafo["stats"]["epistemic"]["EXTRACTED"] == 1
    assert grafo["edges"][0]["predicate"] == "calls"


def test_cli_vault_graph_y_vault_subgraph_path_explain_report_y_adapters(tmp_path: Path):
    vault = tmp_path / "vault"
    for d in ("00_System", "03_Decisions", "07_Knowledge", "17_Preferences", "99_Index"):
        (vault / d).mkdir(parents=True)

    (vault / "03_Decisions" / "adr-hub.md").write_text(
        "---\ntitle: ADR Hub\nstatus: accepted\n---\nEnlaza [[adr-uno]] y [[kb-hub]].\n",
        encoding="utf-8",
    )
    (vault / "03_Decisions" / "adr-uno.md").write_text(
        "---\ntitle: ADR Uno\nstatus: accepted\n---\nParte de [[adr-hub]].\n",
        encoding="utf-8",
    )
    (vault / "07_Knowledge" / "kb-hub.md").write_text(
        "---\ntitle: KB Hub\nstatus: verified\n---\nEnlaza [[kb-dos]] y [[adr-hub]].\n",
        encoding="utf-8",
    )
    (vault / "07_Knowledge" / "kb-dos.md").write_text(
        "---\ntitle: KB Dos\nstatus: verified\n---\nDetalle de [[kb-hub]].\n",
        encoding="utf-8",
    )

    r_g = correr_tool("vault_graph.py", "--report", vault=vault, cwd=SCRIPTS)
    assert r_g.codigo == 0, r_g.stderr
    env_g = r_g.envelope
    assert env_g["ok"] is True
    assert env_g["stats"]["epistemic"]["EXTRACTED"] >= 4
    assert env_g["graph_report"]["summary"]["total_nodes"] == 4

    r_p = correr_tool("vault_subgraph.py", "--path", "adr-uno", "kb-dos", vault=vault, cwd=SCRIPTS)
    assert r_p.codigo == 0, r_p.stderr
    env_p = r_p.envelope
    assert env_p["ok"] is True and env_p["found"] is True and env_p["hops"] == 3

    r_e = correr_tool("vault_subgraph.py", "--explain", "adr-hub", vault=vault, cwd=SCRIPTS)
    assert r_e.codigo == 0, r_e.stderr
    env_e = r_e.envelope
    assert env_e["ok"] is True and env_e["node"]["path"] == "03_Decisions/adr-hub.md"

    r_m = correr_tool("vault_subgraph.py", "--report", "--format", "markdown", vault=vault, cwd=SCRIPTS)
    assert r_m.codigo == 0, r_m.stderr
    assert "# Reporte Estructural del Grafo (GRAPH_REPORT)" in r_m.stdout
    assert "God Nodes" in r_m.stdout

    # Adaptador de preferencias incluye guía Grafo primero dentro del tope de líneas
    destino = tmp_path / "proyecto-consumidor"
    destino.mkdir()
    r_a = correr_tool("vault_preferences.py", "--adapters", str(destino), vault=vault, cwd=SCRIPTS)
    assert r_a.codigo == 0, r_a.stderr
    claude_md = (destino / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Grafo primero" in claude_md
    assert len(claude_md.splitlines()) <= 120

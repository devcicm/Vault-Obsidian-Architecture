#!/usr/bin/env python3
"""Tests for vault_graph_merge — knowledge graph enrichment."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def _apuntar_al_vault(raiz):
    """Se apunta la raíz, no cada constante del módulo.

    Antes se reasignaba `mod.VAULT_ROOT`, que desde v40.0 ya no existe: el
    módulo resuelve la raíz al usarla (AP-49). Reasignarla dejó de tener efecto
    y el test habría corrido contra el vault detectado sin avisar. El override
    lo deshace el fixture autouse de `conftest.py`.
    """
    import vault_io

    vault_io.set_vault_root(raiz)


class TestOntologyLoading:
    def test_ontology_file_exists(self, scripts_dir):
        ontology_file = scripts_dir / "vault_ontology.json"
        assert ontology_file.exists(), "vault_ontology.json must exist"
        data = json.loads(ontology_file.read_text(encoding="utf-8"))
        assert "node_classes" in data
        assert "predicates" in data
        assert len(data["node_classes"]) >= 17

    def test_ontology_has_key_predicates(self, scripts_dir):
        ontology_file = scripts_dir / "vault_ontology.json"
        data = json.loads(ontology_file.read_text(encoding="utf-8"))
        predicates = data["predicates"]
        assert "depends_on" in predicates
        assert "implements" in predicates
        assert "extends" in predicates
        assert "calls" in predicates
        assert "imports" in predicates
        assert "wiki_link" in predicates

    def test_ontology_node_classes_have_folder_mapping(self, scripts_dir):
        ontology_file = scripts_dir / "vault_ontology.json"
        data = json.loads(ontology_file.read_text(encoding="utf-8"))
        for class_name, cls in data["node_classes"].items():
            assert "folder" in cls, f"Node class {class_name} missing folder"


class TestStemNormalization:
    def test_normalize_uniformity(self):
        from vault_graph_merge import _normalize_stem
        assert _normalize_stem("Hello-World") == _normalize_stem("hello_world")
        assert _normalize_stem("My File.md") == _normalize_stem("myfile")
        assert _normalize_stem("Test-Case") == _normalize_stem("test_case")

    def test_normalize_removes_suffix(self):
        from vault_graph_merge import _normalize_stem
        assert _normalize_stem("note.md") == _normalize_stem("note")
        assert _normalize_stem("my-note") == _normalize_stem("my.note")


class TestFolderToClass:
    def test_system_maps_to_system(self):
        from vault_graph_merge import _folder_to_class
        assert _folder_to_class("00_System") == "system"

    def test_knowledge_maps_to_knowledge(self):
        from vault_graph_merge import _folder_to_class
        assert _folder_to_class("07_Knowledge") == "knowledge"

    def test_unknown_folder(self):
        from vault_graph_merge import _folder_to_class
        assert _folder_to_class("99_Unknown") == "unknown"


class TestClosestPredicate:
    def test_exact_match(self):
        from vault_graph_merge import _closest_predicate
        valid = {"depends_on", "implements", "calls", "extends"}
        result = _closest_predicate("depends_on", valid)
        assert result == "depends_on"

    def test_typo_recovery(self):
        from vault_graph_merge import _closest_predicate
        valid = {"depends_on", "implements", "calls", "extends"}
        result = _closest_predicate("depend_on", valid)
        assert result == "depends_on"

    def test_no_match(self):
        from vault_graph_merge import _closest_predicate
        valid = {"depends_on", "implements", "calls"}
        result = _closest_predicate("xyz_unknown", valid)
        assert result is None


class TestBuildWikiLinkGraph:
    def test_empty_vault(self, tmp_test_dir):
        from vault_graph_merge import _build_wiki_link_graph
        import vault_graph_merge as mod
        _apuntar_al_vault(tmp_test_dir)
        try:
            nodes, edges, broken, stem_map = _build_wiki_link_graph()
            assert len(nodes) == 0
            assert len(edges) == 0
        finally:
            pass

    def test_single_note_no_links(self, tmp_test_dir):
        import vault_graph_merge as mod
        _apuntar_al_vault(tmp_test_dir)
        try:
            (tmp_test_dir / "07_Knowledge").mkdir()
            note = tmp_test_dir / "07_Knowledge" / "test-note.md"
            note.write_text(
                "---\ntitle: Test Note\ntags: [test]\n---\n\nContent without links.\n",
                encoding="utf-8",
            )
            nodes, edges, broken, stem_map = mod._build_wiki_link_graph()
            assert len(nodes) == 1
            assert "07_Knowledge/test-note.md" in nodes
            assert nodes["07_Knowledge/test-note.md"]["class"] == "knowledge"
            assert len(edges) == 0
        finally:
            pass

    def test_two_notes_with_wikilink(self, tmp_test_dir):
        import vault_graph_merge as mod
        _apuntar_al_vault(tmp_test_dir)
        try:
            (tmp_test_dir / "07_Knowledge").mkdir()
            note_a = tmp_test_dir / "07_Knowledge" / "note-a.md"
            note_b = tmp_test_dir / "07_Knowledge" / "note-b.md"
            note_a.write_text(
                "---\ntitle: Note A\ntags: [test]\n---\n\nSee [[note-b]] for details.\n",
                encoding="utf-8",
            )
            note_b.write_text(
                "---\ntitle: Note B\ntags: [test]\n---\n\nB content.\n",
                encoding="utf-8",
            )
            nodes, edges, broken, stem_map = mod._build_wiki_link_graph()
            assert len(nodes) == 2
            assert len(edges) >= 1
            assert any(e["predicate"] == "wiki_link" for e in edges)
        finally:
            pass


class TestDetectOrphans:
    def test_orphan_note(self):
        from vault_graph_merge import _detect_orphans
        nodes = {
            "07_Knowledge/orphan.md": {"title": "Orphan", "type": "07_Knowledge"},
        }
        edges = []
        result = _detect_orphans(nodes, edges)
        assert len(result) == 1
        assert result[0]["path"] == "07_Knowledge/orphan.md"

    def test_non_orphan_ignores_system_and_sessions(self):
        from vault_graph_merge import _detect_orphans
        nodes = {
            "00_System/config.md": {"title": "Config", "type": "00_System"},
            "04_Sessions/2026-07-04.md": {"title": "Session", "type": "04_Sessions"},
            "07_Knowledge/linked.md": {"title": "Linked", "type": "07_Knowledge"},
        }
        edges = [{"from": "somewhere.md", "to": "07_Knowledge/linked.md", "predicate": "wiki_link"}]
        result = _detect_orphans(nodes, edges)
        assert len(result) == 0


class TestSiloDetection:
    def test_no_files(self, tmp_test_dir):
        import vault_graph_merge as mod
        _apuntar_al_vault(tmp_test_dir)
        try:
            result = mod._detect_silos()
            assert not result.get("entity_relations_exist", False)
            assert not result.get("code_relations_exist", False)
        finally:
            pass


class TestPredicateCounts:
    def test_empty_edges(self):
        from vault_graph_merge import _build_predicate_topology
        result = _build_predicate_topology([])
        assert result == {}

    def test_mixed_predicates(self):
        from vault_graph_merge import _build_predicate_topology
        edges = [
            {"predicate": "wiki_link"},
            {"predicate": "wiki_link"},
            {"predicate": "depends_on"},
            {"predicate": "implements"},
            {"predicate": "calls"},
        ]
        result = _build_predicate_topology(edges)
        assert result["wiki_link"] == 2
        assert result["depends_on"] == 1
        assert result["implements"] == 1
        assert result["calls"] == 1

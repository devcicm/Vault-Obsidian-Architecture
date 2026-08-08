#!/usr/bin/env python3
"""Tests for vault_relation_add — entity relationship registration."""

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


class TestRelationTypes:
    def test_all_types_valid(self):
        from vault_relation_add import RELATION_TYPES
        assert "has_one" in RELATION_TYPES
        assert "has_many" in RELATION_TYPES
        assert "belongs_to" in RELATION_TYPES
        assert "many_to_many" in RELATION_TYPES
        assert "implements" in RELATION_TYPES
        assert "extends" in RELATION_TYPES
        assert "depends_on" in RELATION_TYPES
        assert "uses" in RELATION_TYPES
        assert "calls" in RELATION_TYPES
        assert "owns" in RELATION_TYPES
        assert "aggregates" in RELATION_TYPES
        assert len(RELATION_TYPES) == 11

    def test_invalid_type_rejected(self, tmp_test_dir):
        import vault_relation_add as mod
        _apuntar_al_vault(tmp_test_dir)
        try:
            result = mod.vault_relation_add(
                project="test",
                from_entity="A",
                to_entity="B",
                relation_type="invalid_type",
            )
            assert result["ok"] is False
            assert result["error_code"] == "INVALID_VALUE"
            assert "Tipo inválido" in result["message"]
        finally:
            pass


class TestEntityTypes:
    def test_all_entity_types(self):
        from vault_relation_add import ENTITY_TYPES
        assert "database" in ENTITY_TYPES
        assert "module" in ENTITY_TYPES
        assert "service" in ENTITY_TYPES
        assert "class" in ENTITY_TYPES
        assert "api" in ENTITY_TYPES
        assert "component" in ENTITY_TYPES
        assert len(ENTITY_TYPES) == 6


class TestMermaidSymbols:
    def test_all_relations_have_symbols(self):
        from vault_relation_add import RELATION_TYPES, RELATION_MERMAID
        for rel_type in RELATION_TYPES:
            assert rel_type in RELATION_MERMAID, f"Missing Mermaid symbol for {rel_type}"

    def test_symbol_values(self):
        from vault_relation_add import RELATION_MERMAID
        assert RELATION_MERMAID["has_one"] == "||--||"
        assert RELATION_MERMAID["has_many"] == "||--o{"
        assert RELATION_MERMAID["belongs_to"] == "}o--||"
        assert RELATION_MERMAID["many_to_many"] == "}o--o{"
        assert RELATION_MERMAID["implements"] == "..>"
        assert RELATION_MERMAID["extends"] == "--|>"
        assert RELATION_MERMAID["depends_on"] == "-->"


class TestSlugify:
    def test_basic(self):
        from vault_relation_add import slugify
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        from vault_relation_add import slugify
        assert slugify("Service@API") == "serviceapi"

    def test_multiple_spaces(self):
        from vault_relation_add import slugify
        assert slugify("  My   Project  ") == "my-project"


class TestLoadSaveRelations:
    def test_load_nonexistent_returns_empty(self, tmp_test_dir):
        import vault_relation_add as mod
        try:
            data = mod.load_relations("test-project")
            assert data["project"] == "test-project"
            assert data["relations"] == []
        finally:
            pass

    def test_save_and_load_roundtrip(self, tmp_test_dir):
        import vault_relation_add as mod
        try:
            data = {"project": "test", "relations": [{"id": "1", "fromEntity": "A", "toEntity": "B", "relationType": "uses"}]}
            mod.save_relations("test", data)
            loaded = mod.load_relations("test")
            assert loaded["project"] == "test"
            assert len(loaded["relations"]) == 1
            assert loaded["relations"][0]["fromEntity"] == "A"
        finally:
            pass

    def test_deduplication(self, tmp_test_dir):
        import vault_relation_add as mod
        _apuntar_al_vault(tmp_test_dir)
        try:
            mod._entity_dir().mkdir(parents=True, exist_ok=True)
            result1 = mod.vault_relation_add(
                project="testproj",
                from_entity="User",
                to_entity="Order",
                relation_type="has_many",
            )
            result2 = mod.vault_relation_add(
                project="testproj",
                from_entity="User",
                to_entity="Order",
                relation_type="has_many",
            )
            assert result1["ok"] is True
            assert result2["ok"] is True
            assert result2.get("deduplicated") is True
        finally:
            pass


class TestDetectIsDatabaseLike:
    def test_empty_relations(self):
        from vault_relation_add import detect_is_database_like
        assert not detect_is_database_like([])

    def test_has_many_makes_db_like(self):
        from vault_relation_add import detect_is_database_like
        relations = [{"relationType": "has_many"}]
        assert detect_is_database_like(relations)

    def test_calls_not_db_like(self):
        from vault_relation_add import detect_is_database_like
        relations = [{"relationType": "calls"}]
        assert not detect_is_database_like(relations)


class TestGenerateErdMermaid:
    def test_erd_mode(self):
        from vault_relation_add import generate_erd_mermaid
        relations = [
            {"fromEntity": "User", "toEntity": "Order", "relationType": "has_many", "label": ""}
        ]
        result = generate_erd_mermaid("test", relations)
        assert result.startswith("erDiagram")

    def test_graph_mode(self):
        from vault_relation_add import generate_erd_mermaid
        relations = [
            {"fromEntity": "ServiceA", "toEntity": "ServiceB", "relationType": "calls"}
        ]
        result = generate_erd_mermaid("test", relations)
        assert result.startswith("graph TD")

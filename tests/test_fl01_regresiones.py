"""Regresiones FL-01: identidad de nota, conflicto de proyecto, encoding.

- Update: misma nota (mismo category+slug+project) → segunda escritura OK
- Conflicto de proyecto: mismo slug, project diferente → IDENTITY_CONFLICT
- Slug collision: título diferente que produce el mismo slug, project diferente → IDENTITY_CONFLICT
- YAML no-objeto: frontmatter que yaml.safe_load rechaza → archivo creado sin crash
- Encoding inválido: archivo binario con bytes no-UTF8 → IDENTITY_CONFLICT controlada
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vault.autoria.conocimiento import guardar_conocimiento, recuperar_conocimiento
from vault.ciclo_de_vida.producto import inicializar_runtime


def _runtime(tmp_path):
    root = tmp_path / "runtime"
    inicializar_runtime(root)
    return root


class TestNotaUpdateMismoProyecto:
    """FL-01 — mismo category+slug+project → update intencional, sin conflicto."""

    def test_segunda_escritura_ok(self, tmp_path):
        root = _runtime(tmp_path)
        title = "Nota de同一测试"
        r1 = guardar_conocimiento(root, "concept", title, "Contenido original")
        assert r1["ok"]
        nota_path = root / r1["path"]

        r2 = guardar_conocimiento(root, "concept", title, "Contenido actualizado")
        assert r2["ok"], f"update rechazado: {r2}"
        assert r2["path"] == r1["path"]

        contenido = nota_path.read_text(encoding="utf-8")
        assert "Contenido actualizado" in contenido
        assert "Contenido original" not in contenido

    def test_update_sin_project_es_ok(self, tmp_path):
        root = _runtime(tmp_path)
        title = "Sin project"
        r1 = guardar_conocimiento(root, "concept", title, "v1")
        assert r1["ok"]
        r2 = guardar_conocimiento(root, "concept", title, "v2")
        assert r2["ok"]
        assert r2["path"] == r1["path"]

    def test_update_con_project_diferente_a_none(self, tmp_path):
        root = _runtime(tmp_path)
        title = "Con project"
        guardar_conocimiento(root, "concept", title, "v1", project="proj-A")
        guardar_conocimiento(root, "concept", title, "v2", project="proj-A")
        r3 = guardar_conocimiento(root, "concept", title, "v3", project="proj-A")
        assert r3["ok"]


class TestIdentidadConflicto:
    """FL-01 — identidad (category+slug) existe con project diferente → IDENTITY_CONFLICT."""

    def test_mismo_slug_project_diferente_rechazado(self, tmp_path):
        root = _runtime(tmp_path)
        guardar_conocimiento(root, "concept", "Mi Title", "contenido A", project="proj-A")
        resultado = guardar_conocimiento(root, "concept", "Mi Title", "contenido B", project="proj-B")
        assert resultado["ok"] is False
        assert resultado["error_code"] == "IDENTITY_CONFLICT"
        assert resultado["conflict_project"] == "proj-A"
        assert resultado["attempted_project"] == "proj-B"
        assert "path" in resultado

    def test_project_none_vs_project_presente_rechazado(self, tmp_path):
        root = _runtime(tmp_path)
        guardar_conocimiento(root, "concept", "TestNote", "contenido", project="proj-A")
        resultado = guardar_conocimiento(root, "concept", "TestNote", "contenido")
        assert resultado["ok"] is False
        assert resultado["error_code"] == "IDENTITY_CONFLICT"
        assert resultado["conflict_project"] == "proj-A"
        assert resultado["attempted_project"] is None

    def test_none_vs_project_presente_rechazado(self, tmp_path):
        root = _runtime(tmp_path)
        guardar_conocimiento(root, "concept", "TestNote", "contenido")
        resultado = guardar_conocimiento(root, "concept", "TestNote", "contenido", project="proj-B")
        assert resultado["ok"] is False
        assert resultado["error_code"] == "IDENTITY_CONFLICT"
        assert resultado["conflict_project"] is None
        assert resultado["attempted_project"] == "proj-B"

    def test_slug_collision_diferente_titulo_mismo_slug_project_diferente(self, tmp_path):
        """'Mi Title' y 'MI  TITLE' producen el mismo slug; project diferente → conflicto."""
        root = _runtime(tmp_path)
        guardar_conocimiento(root, "concept", "Mi Title", "contenido A", project="proj-A")
        resultado = guardar_conocimiento(root, "concept", "MI  TITLE", "contenido B", project="proj-B")
        assert resultado["ok"] is False
        assert resultado["error_code"] == "IDENTITY_CONFLICT"

    def test_mismo_slug_mismo_project_no_es_conflicto(self, tmp_path):
        """Mismo slug y mismo project = update, no conflicto."""
        root = _runtime(tmp_path)
        guardar_conocimiento(root, "concept", "Mi Title", "v1", project="proj-A")
        r2 = guardar_conocimiento(root, "concept", "MI  TITLE", "v2", project="proj-A")
        assert r2["ok"]


class TestYamlYEncoding:
    """FL-01 — YAML malformado e encoding inválido no hacen crash la tool."""

    def test_yaml_no_objeto_crea_archivo(self, tmp_path):
        root = _runtime(tmp_path)
        nota = tmp_path / "runtime" / "07_Knowledge" / "concepts" / "manual.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_text("---\ntitle: Test\n---\n- item1\n- item2\n", encoding="utf-8")
        resultado = guardar_conocimiento(root, "concept", "TestNote", "contenido nuevo")
        assert resultado["ok"], f"debe crear archivo nuevo: {resultado}"
        assert nota.exists()

    def test_encoding_invalido_misma_ruta_retorna_conflicto(self, tmp_path):
        """Archivo binario pre-existente en la ruta del slug → IDENTITY_CONFLICT controlada."""
        root = _runtime(tmp_path)
        nota = root / "07_Knowledge" / "concepts" / "testnote.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_bytes(b"\x80\x81no es utf-8")
        resultado = guardar_conocimiento(root, "concept", "TestNote", "nuevo contenido")
        assert resultado["ok"] is False
        assert resultado["error_code"] == "IDENTITY_CONFLICT"
        assert "path" in resultado

    def test_recuperar_conocimiento_no_crashea_con_yaml_malformado(self, tmp_path):
        root = _runtime(tmp_path)
        nota = tmp_path / "runtime" / "07_Knowledge" / "concepts" / "malformed.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_text("---\ntitle: [bad\n---\nbody", encoding="utf-8")
        resultado = recuperar_conocimiento(root, "test")
        assert resultado["ok"] is True
        assert resultado["warnings"] != []
        assert any("malformed.md" in w for w in resultado["warnings"])

    def test_recuperar_conocimiento_registra_unreadable_files(self, tmp_path):
        """Archivo binario no-UTF8 encontrado durante la recuperación."""
        root = _runtime(tmp_path)
        nota = tmp_path / "runtime" / "07_Knowledge" / "concepts" / "binarynote.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_bytes(b"\x80\x82bytes no-utf8")
        resultado = recuperar_conocimiento(root, "test")
        assert resultado["ok"] is True
        assert "unreadable_files" in resultado
        assert any(e["path"].endswith("binarynote.md") for e in resultado["unreadable_files"])
        assert resultado["unreadable_count"] >= 1


class TestWriterExtensibility:
    """FL-01 — writer y report preserved."""

    def test_writer_inyectado_recibe_nota_completa(self, tmp_path):
        """writer recibe (path, text) donde text es la nota completa con frontmatter."""
        root = _runtime(tmp_path)
        llamado = {}

        def writer(path, text):
            llamado["path"] = str(path)
            llamado["text"] = text

        guardar_conocimiento(root, "concept", "Test", "contenido body", writer=writer)
        assert "path" in llamado
        assert "title: Test" in llamado["text"]
        assert "contenido body" in llamado["text"]

    def test_report_inyectado_se_incorpora(self, tmp_path):
        root = _runtime(tmp_path)

        def report():
            return {"escribio": True}

        resultado = guardar_conocimiento(root, "concept", "Test", "contenido", report=report)
        assert resultado["ok"] is True
        assert resultado.get("escribio") is True

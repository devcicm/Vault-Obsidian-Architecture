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
from vault.kernel.frontmatter_parsing import parse_frontmatter_with_body


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

    def test_update_conserva_id_y_createdAt(self, tmp_path):
        """FL-01 — update intencional preserva id y createdAt; solo updatedAt cambia."""
        import time
        root = _runtime(tmp_path)
        title = "UpdateFieldTest"
        r1 = guardar_conocimiento(root, "concept", title, "v1")
        assert r1["ok"]
        nota_path = root / r1["path"]

        fm1, _ = parse_frontmatter_with_body(nota_path.read_text(encoding="utf-8"))
        id1 = fm1.get("id")
        created1 = fm1.get("createdAt")
        updated1 = fm1.get("updatedAt")
        assert id1, "primera escritura debe tener id"
        assert created1, "primera escritura debe tener createdAt"

        time.sleep(1.1)
        r2 = guardar_conocimiento(root, "concept", title, "v2 - contenido actualizado")
        assert r2["ok"], f"update rechazado: {r2}"

        fm2, _ = parse_frontmatter_with_body(nota_path.read_text(encoding="utf-8"))
        assert fm2.get("id") == id1, "id debe conservarse en update"
        assert fm2.get("createdAt") == created1, "createdAt debe conservarse en update"
        assert fm2.get("updatedAt") != updated1, "updatedAt debe cambiar en update"
        assert fm2.get("updatedAt") != fm2.get("createdAt"), "updatedAt debe diferir de createdAt"

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

    def test_mismo_slug_mismo_project_mismo_titulo_update(self, tmp_path):
        """Mismo slug, mismo project, título EXACTO → update, no conflicto."""
        root = _runtime(tmp_path)
        guardar_conocimiento(root, "concept", "Mi Title", "v1", project="proj-A")
        r2 = guardar_conocimiento(root, "concept", "Mi Title", "v2", project="proj-A")
        assert r2["ok"]
        assert r2["path"] == "07_Knowledge/concepts/mi-title.md"

    def test_titulo_equivalente_mismo_project_es_update(self, tmp_path):
        """'MI  TITLE' es 'Mi Title' para cualquier lector: clave de equivalencia igual → update.

        Hasta v40.34 la comparación era `==` y esto salía IDENTITY_CONFLICT; el
        criterio vive en vault.kernel.normalizacion.clave_de_equivalencia.
        """
        root = _runtime(tmp_path)
        r1 = guardar_conocimiento(root, "concept", "Mi Title", "contenido A", project="proj-A")
        r2 = guardar_conocimiento(root, "concept", "MI  TITLE", "contenido B", project="proj-A")
        assert r2["ok"], f"update rechazado: {r2}"
        assert r2["path"] == r1["path"]

    @pytest.mark.parametrize("primero,segundo", [("C++", "C#"), ("Café", "Cafe")])
    def test_titulo_distinto_mismo_slug_mismo_project_rechazado(self, tmp_path, primero, segundo):
        """Mismo slug, título distinto → IDENTITY_CONFLICT; el original queda byte-por-byte.

        C++ y C# comparten `c.md`; Café y Cafe comparten `cafe.md`. La clave de
        equivalencia conserva símbolos y acentos, así que no los confunde.
        """
        root = _runtime(tmp_path)
        r1 = guardar_conocimiento(root, "concept", primero, "contenido A", project="proj-A")
        assert r1["ok"]
        nota = root / r1["path"]
        original_bytes = nota.read_bytes()
        resultado = guardar_conocimiento(root, "concept", segundo, "contenido B", project="proj-A")
        assert resultado["ok"] is False, f"no debe sobrescribir: {resultado}"
        assert resultado["error_code"] == "IDENTITY_CONFLICT"
        assert resultado["conflict_title"] == primero
        assert resultado["attempted_title"] == segundo
        assert nota.read_bytes() == original_bytes, "archivo original debe ser byte-por-byte idéntico"

    def test_titulo_que_yaml_lee_como_numero_es_el_mismo_titulo(self, tmp_path):
        """`title: 2026` sin comillas llega como int; sigue siendo el título '2026'."""
        root = _runtime(tmp_path)
        nota = root / "07_Knowledge" / "concepts" / "2026.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_text("---\ntitle: 2026\ncategory: concept\n---\n\nv1\n", encoding="utf-8")
        resultado = guardar_conocimiento(root, "concept", "2026", "v2")
        assert resultado["ok"], f"update rechazado: {resultado}"

    def test_sin_frontmatter_rechaza_titulo_nuevo(self, tmp_path):
        """Archivo sin frontmatter (sin título verificable) → IDENTITY_CONFLICT ante título no-None."""
        root = _runtime(tmp_path)
        nota = root / "07_Knowledge" / "concepts" / "testnote.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_text("# Solo prosa\n\nSin metadatos.\n", encoding="utf-8")
        original_bytes = nota.read_bytes()
        resultado = guardar_conocimiento(root, "concept", "TestNote", "contenido nuevo")
        assert resultado["ok"] is False
        assert resultado["error_code"] == "IDENTITY_CONFLICT"
        assert nota.read_bytes() == original_bytes


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

    def test_yaml_lista_existente_misma_ruta_rechazado(self, tmp_path):
        """Frontmatter con raíz lista → IDENTITY_CONFLICT; archivo byte-por-byte idéntico."""
        root = _runtime(tmp_path)
        nota = root / "07_Knowledge" / "concepts" / "testnote.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_text("---\n- item1\n- item2\n---\nbody", encoding="utf-8")
        original = nota.read_bytes()
        resultado = guardar_conocimiento(root, "concept", "TestNote", "contenido nuevo")
        assert resultado["ok"] is False
        assert resultado["error_code"] == "IDENTITY_CONFLICT"
        assert nota.read_bytes() == original

    def test_yaml_false_root_existente_rechazado(self, tmp_path):
        """Frontmatter con raíz false (YAML bool) → IDENTITY_CONFLICT; conserva bytes."""
        root = _runtime(tmp_path)
        nota = root / "07_Knowledge" / "concepts" / "testnote.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_text("---\nfalse\n---\nbody original\n", encoding="utf-8")
        original = nota.read_bytes()
        resultado = guardar_conocimiento(root, "concept", "TestNote", "contenido nuevo")
        assert resultado["ok"] is False
        assert resultado["error_code"] == "IDENTITY_CONFLICT"
        assert nota.read_bytes() == original

    def test_yaml_zero_root_existente_rechazado(self, tmp_path):
        """Frontmatter con raíz 0 (YAML int) → IDENTITY_CONFLICT; conserva bytes."""
        root = _runtime(tmp_path)
        nota = root / "07_Knowledge" / "concepts" / "testnote.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_text("---\n0\n---\nbody original\n", encoding="utf-8")
        original = nota.read_bytes()
        resultado = guardar_conocimiento(root, "concept", "TestNote", "contenido nuevo")
        assert resultado["ok"] is False
        assert resultado["error_code"] == "IDENTITY_CONFLICT"
        assert nota.read_bytes() == original

    def test_yaml_sintaxis_invalida_existente_misma_ruta_rechazado(self, tmp_path):
        """Frontmatter YAML sintácticamente roto (title: [broken) → IDENTITY_CONFLICT."""
        root = _runtime(tmp_path)
        nota = root / "07_Knowledge" / "concepts" / "testnote.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_text("---\ntitle: [broken\n---\nbody original\n", encoding="utf-8")
        original = nota.read_bytes()
        resultado = guardar_conocimiento(root, "concept", "TestNote", "contenido nuevo")
        assert resultado["ok"] is False
        assert resultado["error_code"] == "IDENTITY_CONFLICT"
        assert nota.read_bytes() == original

    def test_fecha_yaml_invalida_sin_comillas_rechazado(self, tmp_path):
        """Fecha YAML sin comillas que PyYAML no puede convertir → IDENTITY_CONFLICT."""
        root = _runtime(tmp_path)
        nota = root / "07_Knowledge" / "concepts" / "testnote.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_text("---\ndate: 2026-13-45\n---\nbody original\n", encoding="utf-8")
        original = nota.read_bytes()
        resultado = guardar_conocimiento(root, "concept", "TestNote", "contenido nuevo")
        assert resultado["ok"] is False
        assert resultado["error_code"] == "IDENTITY_CONFLICT"
        assert nota.read_bytes() == original

    def test_alias_yaml_recursivo_rechazado(self, tmp_path):
        """Alias YAML recursivo (item: &item {child: *item}) causa RecursionError → IDENTITY_CONFLICT."""
        from vault.kernel.frontmatter_parsing import FrontmatterParseError
        root = _runtime(tmp_path)

        nota = root / "07_Knowledge" / "concepts" / "testnote.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        fm = "---\nitem: &item {child: *item}\n---\nbody"
        nota.write_text(fm, encoding="utf-8")
        original = nota.read_bytes()

        with pytest.raises(FrontmatterParseError, match="anidamiento"):
            parse_frontmatter_with_body(fm)

        resultado = guardar_conocimiento(root, "concept", "TestNote", "contenido nuevo")
        assert resultado["ok"] is False
        assert resultado["error_code"] == "IDENTITY_CONFLICT"
        assert nota.read_bytes() == original

        recuperado = recuperar_conocimiento(root, "test")
        assert recuperado["ok"] is True
        assert any(e["path"].endswith("testnote.md") for e in recuperado.get("unreadable_files", []))

    def test_yaml_lista_no_crashes_recuperar(self, tmp_path):
        """Frontmatter YAML lista no hace crash en recuperación; se cuenta como defectuoso."""
        root = _runtime(tmp_path)
        nota = tmp_path / "runtime" / "07_Knowledge" / "concepts" / "listafm.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_text("---\n- alpha\n- beta\n---\nbody", encoding="utf-8")
        resultado = recuperar_conocimiento(root, "alpha")
        assert resultado["ok"] is True
        assert resultado["warnings"] != []
        assert resultado["unreadable_count"] >= 1

    def test_encoding_invalido_misma_ruta_retorna_conflicto(self, tmp_path):
        """Archivo binario pre-existente en la ruta del slug → IDENTITY_CONFLICT."""
        root = _runtime(tmp_path)
        nota = root / "07_Knowledge" / "concepts" / "testnote.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_bytes(b"\x80\x81no es utf-8")
        original = nota.read_bytes()
        resultado = guardar_conocimiento(root, "concept", "TestNote", "nuevo contenido")
        assert resultado["ok"] is False
        assert resultado["error_code"] == "IDENTITY_CONFLICT"
        assert "path" in resultado
        assert nota.read_bytes() == original

    def test_tags_lista_campo_valido(self, tmp_path):
        """tags: [tag1] como CAMPO es válido y se conserva en el archivo."""
        root = _runtime(tmp_path)
        r = guardar_conocimiento(root, "concept", "TestTags", "body", tags=["tag1"])
        assert r["ok"]
        nota = root / r["path"]
        contenido = nota.read_text(encoding="utf-8")
        assert "tags:" in contenido

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

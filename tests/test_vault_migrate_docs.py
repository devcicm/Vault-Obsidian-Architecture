"""`vault_migrate_docs` — migra documentación existente al vault.

3 fases: STAGING → CLASSIFICATION → DISTRIBUTION.
Nunca migra código fuente (.py, .js, .ts, etc.).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_subproceso


def _correr(script, vault_root, *args):
    r = vault_subproceso.ejecutar(
        [sys.executable, str(SCRIPTS / script), *args],
        env={
            **subprocess.os.environ,
            "VAULT_ROOT": str(vault_root),
            "PYTHONIOENCODING": "utf-8",
            "VAULT_TOOL_TIMEOUT": "600",
        },
        capture_output=True,
        timeout=600,
    )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Script returned non-JSON: {r.stdout[:500]}\nSTDERR: {r.stderr[:500]}")


@pytest.fixture
def fuente_con_docs(tmp_path):
    """Fuente de documentación con archivos de distintos tipos."""
    docs = tmp_path / "docs_origen"
    docs.mkdir()
    (docs / "README.md").write_text("# Proyecto\n\nDocumentación principal.", encoding="utf-8")
    (docs / "api.md").write_text("# API\n\nEndpoints REST.", encoding="utf-8")
    (docs / " guia.md").write_text("# Guía\n\nInstrucciones.", encoding="utf-8")
    (docs / "notas.txt").write_text("Notas sueltas en texto plano.", encoding="utf-8")
    (src := docs / "src").mkdir()
    (src / "main.py").write_text("print('code')", encoding="utf-8")
    return docs


@pytest.fixture
def vault_preparado(tmp_path, fuente_con_docs):
    """Vault inicializado con la fuente de docs disponible."""
    v = tmp_path / "vault-test-migrate"
    v.mkdir()
    _correr("vault_init.py", v)
    return v, fuente_con_docs


class TestFaseStaging:
    """Los archivos de documentación se copian a 10_Migrated/_staging/."""

    def test_staging_crea_carpeta(self, vault_preparado):
        v, fuente = vault_preparado
        _correr(
            "vault_migrate_docs.py", v,
            "--source_path", str(fuente),
            "--project", "testpr",
            "--no-dry_run",
        )
        staging = v / "10_Migrated" / "_staging"
        assert staging.exists(), "No se creó 10_Migrated/_staging"

    def test_archivos_md_se_estadian(self, vault_preparado):
        v, fuente = vault_preparado
        _correr(
            "vault_migrate_docs.py", v,
            "--source_path", str(fuente),
            "--project", "testpr",
            "--no-dry_run",
        )
        migrated = v / "10_Migrated"
        md_files = list(migrated.rglob("*.md"))
        assert len(md_files) >= 3, f"Solo se migraron {len(md_files)} archivos .md"

    def test_archivos_de_codigo_no_se_estadian(self, vault_preparado):
        v, fuente = vault_preparado
        _correr(
            "vault_migrate_docs.py", v,
            "--source_path", str(fuente),
            "--project", "testpr",
            "--no-dry_run",
        )
        staging = v / "10_Migrated" / "_staging"
        py_files = list(staging.rglob("*.py")) if staging.exists() else []
        assert not py_files, f"Archivos .py se estadiaron (no deberían): {py_files}"


class TestClasificacion:
    """Cada archivo se clasifica como direct/indirect/excluded."""

    def test_clasificacion_presente_en_resultado(self, vault_preparado):
        v, fuente = vault_preparado
        resultado = _correr(
            "vault_migrate_docs.py", v,
            "--source_path", str(fuente),
            "--project", "testpr",
        )
        assert "classified" in resultado, "No hay campo 'classified' en el resultado"

    def test_codigo_fuente_es_excluded(self, vault_preparado):
        v, fuente = vault_preparado
        resultado = _correr(
            "vault_migrate_docs.py", v,
            "--source_path", str(fuente),
            "--project", "testpr",
        )
        classified = resultado.get("classified", [])
        src_classified = [c for c in classified if "src" in c.get("originalName", "")]
        assert not src_classified, f"Archivos src fueron clasificados: {src_classified}"


class TestDryRun:
    """--dry_run (default True) no escribe archivos reales."""

    def test_dry_run_no_crea_archivos_en_vault(self, vault_preparado):
        v, fuente = vault_preparado
        staging_dir = v / "10_Migrated" / "_staging"
        _correr(
            "vault_migrate_docs.py", v,
            "--source_path", str(fuente),
            "--project", "testpr",
        )
        assert not staging_dir.exists(), "dry_run=true creó archivos (debería solo informar)"


class TestMigratedFrom:
    """El campo migratedFrom es portable (slash, no backslash)."""

    def test_migratedfrom_usa_slashes(self, vault_preparado):
        v, fuente = vault_preparado
        _correr(
            "vault_migrate_docs.py", v,
            "--source_path", str(fuente),
            "--project", "testpr",
            "--no-dry_run",
        )
        migrated = v / "10_Migrated"
        md_files = list(migrated.rglob("*.md"))
        for f in md_files:
            content = f.read_text(encoding="utf-8")
            if "migratedFrom:" in content:
                lines_with_migrated = [
                    l for l in content.splitlines() if "migratedFrom:" in l
                ]
                for line in lines_with_migrated:
                    path_part = line.split("migratedFrom:", 1)[1].strip()
                    assert "\\" not in path_part, (
                        f"migratedFrom usa backslash en {f.name}: {line}"
                    )


class TestOkFlag:
    """El resultado devuelve ok: true cuando termina bien."""

    def test_ok_true_en_dry_run(self, vault_preparado):
        v, fuente = vault_preparado
        resultado = _correr(
            "vault_migrate_docs.py", v,
            "--source_path", str(fuente),
            "--project", "testpr",
        )
        assert resultado.get("ok") is True, f"dry_run debería dar ok=true: {resultado}"

    def test_ok_true_en_migracion_real(self, vault_preparado):
        v, fuente = vault_preparado
        resultado = _correr(
            "vault_migrate_docs.py", v,
            "--source_path", str(fuente),
            "--project", "testpr",
            "--no-dry_run",
        )
        assert resultado.get("ok") is True, f"migración real debería dar ok=true: {resultado}"

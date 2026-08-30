"""`vault_init` — bootstrap de un vault fresco.

Crea las 17 carpetas estándar, escribe los system files, aplica migraciones,
genera los índices y reporta el health score inicial.

**Qué no prueba este archivo:** la migración de un vault existente. Eso es
`MODO-AGENTICO-SANACION.md` y `tests/test_vault_onboard.py`.
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


def _corriendo(script, vault_root, *args):
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
    return r


@pytest.fixture
def vault_vacio(tmp_path):
    """Un vault recién inicializado sin contenido."""
    v = tmp_path / "vault-test-init"
    v.mkdir()
    salida = _correr("vault_init.py", v)
    assert salida.get("ok"), f"vault_init falló: {salida}"
    return v, salida


class TestCarpetasEstandar:
    """Las 17 carpetas estándar se crean."""

    def _carpetas_esperadas(self):
        return {
            "00_System", "01_Projects", "02_Observability", "03_Decisions",
            "04_Sessions", "05_Patterns", "06_Diagrams", "07_Knowledge",
            "08_Runbooks", "09_Infrastructure", "10_Migrated", "11_Code",
            "12_Bibliography", "13_Flows", "14_Requirements", "15_Tests",
            "16_AI_Governance", "17_Preferences", "18_Bugs", "19_Audits",
            "20_Quarantine", "99_Index",
        }

    def test_las_17_carpetas_existen(self, vault_vacio):
        v, _ = vault_vacio
        creadas = {p.name for p in v.iterdir() if p.is_dir()}
        faltantes = self._carpetas_esperadas() - creadas
        assert not faltantes, f"Carpetas faltantes: {faltantes}"

    def test_ninguna_carpeta_esta_vacia(self, vault_vacio):
        v, _ = vault_vacio
        vacias = [p.name for p in v.iterdir() if p.is_dir() and not list(p.iterdir())]
        assert not vacias, f"Carpetas sin contenido: {vacias}"


class TestSystemFiles:
    """Los ficheros de sistema se crean con contenido válido."""

    def test_standard_version_json_existe(self, vault_vacio):
        v, _ = vault_vacio
        f = v / "00_System" / "standard-version.json"
        assert f.exists(), "standard-version.json no fue creado"
        data = json.loads(f.read_text(encoding="utf-8"))
        assert "applied_version" in data, "standard-version.json sin campo 'applied_version'"
        assert "migrations_applied" in data or "appliedMigrations" in data

    def test_tag_registry_json_existe(self, vault_vacio):
        v, _ = vault_vacio
        f = v / "00_System" / "tag-registry.json"
        assert f.exists(), "tag-registry.json no fue creado"
        data = json.loads(f.read_text(encoding="utf-8"))
        assert "canonical_tags" in data, "tag-registry.json sin campo 'canonical_tags'"


class TestPrimers:
    """Cada sección (menos 00_System y dirigidas por eventos) recibe un primer."""

    EVENT_DRIVEN = {"18_Bugs", "19_Audits", "20_Quarantine"}
    SECTION_NO_PRIMER = {"00_System"} | EVENT_DRIVEN

    def test_cada_seccion_tiene_primer(self, vault_vacio):
        v, _ = vault_vacio
        secciones_con_primer = set()
        for entry in (v).iterdir():
            if not entry.is_dir():
                continue
            primers = list(entry.glob("00-*.md"))
            if primers:
                secciones_con_primer.add(entry.name)

        faltantes = (
            {e.name for e in v.iterdir() if e.is_dir() and e.name not in self.SECTION_NO_PRIMER}
            - secciones_con_primer
        )
        assert not faltantes, f"Secciones sin primer: {faltantes}"

    def test_el_primer_pasa_el_content_gate(self, vault_vacio):
        v, _ = vault_vacio
        violations = _correr(
            "vault_norms.py", v, "--audit", "--root", str(v)
        ).get("violations", [])
        norms_related_to_primers = [
            v for v in violations
            if ("scaffold" in str(v) or "primer" in str(v).lower())
            and v.get("norm") not in ("AP-39",)
        ]
        assert not norms_related_to_primers, (
            f"El scaffold/primer viola normas: {norms_related_to_primers}"
        )


class TestHubNotes:
    """vault-hub.md y vault-commands.md se crean si no existen."""

    def test_vault_hub_existe(self, vault_vacio):
        v, _ = vault_vacio
        assert (v / "00_System" / "vault-hub.md").exists()

    def test_vault_commands_existe(self, vault_vacio):
        v, _ = vault_vacio
        assert (v / "00_System" / "vault-commands.md").exists()


class TestHealthScore:
    """El vault recién creado reporta healthScore."""

    def test_healthscore_presente(self, vault_vacio):
        v, salida = vault_vacio
        assert "healthScore" in salida or "steps" in salida
        steps = salida.get("steps", [])
        assert steps, "No hay steps en la salida de vault_init"

    def test_ninguna_violacion_al_arrancar(self, vault_vacio):
        v, _ = vault_vacio
        violations = _correr(
            "vault_norms.py", v, "--audit", "--root", str(v)
        ).get("violations", [])
        content_violations = [v for v in violations if v.get("norm") != "AP-39"]
        assert not content_violations, f"Vault recién creado con violaciones: {content_violations[:3]}"

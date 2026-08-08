"""Tests del Marco de Datos y Gobernanza (v39).

El fallo estructural que estos tests previenen es el de la Era 4 del estándar:
documentar conceptos sin código que los sostenga. Aquí el registro canónico es
la fuente y el manifiesto es el derivado — si divergen, falla el build.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from vault_fundamentals import (  # noqa: E402
    BIGDATA_VS,
    CIA_TRIAD,
    FAIR_PRINCIPLES,
    FRAMEWORK_REGISTRIES,
    FUNDAMENTALS,
    ISO_COVERAGE,
    TRACEABILITY_MATRIX,
    framework_ids,
    traceability_matrix,
)
from vault_norms import framework_drift_check  # noqa: E402

SPEC = Path(__file__).parent.parent / "vault-obsidian-architecture.md"
SCRIPTS = Path(__file__).parent.parent / "scripts"


# ── Integridad de los registros ───────────────────────────────────────────────


def test_registries_are_populated():
    assert len(CIA_TRIAD) == 3
    assert len(FUNDAMENTALS) == 8
    assert len(FAIR_PRINCIPLES) == 4
    assert len(BIGDATA_VS) >= 5
    assert len(ISO_COVERAGE) >= 12


def test_framework_ids_are_unique():
    ids = framework_ids()
    assert len(ids) == len(set(ids)), "ids duplicados en los registros del marco"


def test_every_entry_has_id_and_description():
    for name, registry in FRAMEWORK_REGISTRIES.items():
        for entry in registry:
            assert entry.get("id"), f"{name}: entrada sin id"
            assert entry.get("name") or entry.get("norm"), f"{name}/{entry['id']}: sin nombre"


def test_cia_triad_fields_and_values():
    fields = {c["frontmatter_field"] for c in CIA_TRIAD}
    assert fields == {"cia_integrity", "cia_availability", "cia_sensitivity"}
    for c in CIA_TRIAD:
        assert c["default"] in c["values"]


# ── Coherencia con el resto del código ────────────────────────────────────────


def test_every_referenced_tool_script_exists():
    """Ninguna tool citada en el marco puede ser inventada (AP-04)."""
    missing = set()
    for registry in FRAMEWORK_REGISTRIES.values():
        for entry in registry:
            for tool in entry.get("tools", []):
                if not (SCRIPTS / f"{tool}.py").exists():
                    missing.add(tool)
    assert not missing, f"tools citadas sin script: {sorted(missing)}"


def test_all_dq_dimensions_covered_by_fundamentals():
    """Las 8 dimensiones de F1-F8 más uniqueness son las 9 de quality_check."""
    dims = {f["dq_dimension"] for f in FUNDAMENTALS}
    expected = {
        "integrity",
        "consistency",
        "completeness",
        "accuracy",
        "validity",
        "timeliness",
        "authenticity",
        "non_repudiation",
    }
    assert dims == expected


def test_iso_citations_use_canonical_format():
    """Toda cita ISO del registro lleva año — evita 'ISO 9001' vs 'ISO 9001:2015'."""
    for entry in ISO_COVERAGE:
        norm = entry["norm"]
        assert norm.startswith("ISO"), norm
        # ISO 8601 es la única sin año de edición en su cita habitual
        assert ":" in norm or norm == "ISO 8601", f"cita sin año: {norm}"


# ── Matriz de trazabilidad ────────────────────────────────────────────────────


def test_matrix_rows_are_complete():
    required = {"concept", "metric", "threshold", "tool", "artifact", "enforcement"}
    for row in TRACEABILITY_MATRIX:
        assert required <= set(row), f"fila incompleta: {row.get('concept')}"
        assert all(str(row[k]).strip() for k in required)


def test_matrix_enforcement_vocabulary():
    allowed = {"guard", "audit", "guard+audit", "recommended", "automático"}
    for row in TRACEABILITY_MATRIX:
        base = row["enforcement"].split(" ")[0]
        assert base in allowed, f"enforcement desconocido: {row['enforcement']}"


def test_matrix_tool_command_resolves_to_a_script():
    for row in TRACEABILITY_MATRIX:
        tool = row["tool"].split(" ")[0]  # "vault_norms --audit" -> "vault_norms"
        assert (SCRIPTS / f"{tool}.py").exists(), f"tool inexistente en matriz: {tool}"


def test_traceability_matrix_envelope():
    result = traceability_matrix()
    assert result["ok"] and result["total"] == len(TRACEABILITY_MATRIX)


# ── Guard anti-drift contra el manifiesto ─────────────────────────────────────


def test_manifest_documents_every_framework_id():
    """El manifiesto es la representación pública: no puede omitir ningún id."""
    result = framework_drift_check(SPEC)
    assert result["ok"], f"ids ausentes del manifiesto: {result['missing']}"


def test_drift_check_detects_a_missing_id(tmp_path):
    """El guard debe fallar de verdad, no solo pasar siempre."""
    fake = tmp_path / "spec.md"
    fake.write_text("# spec sin marco de datos\n", encoding="utf-8")
    result = framework_drift_check(fake)
    assert not result["ok"] and result["missing_count"] == len(framework_ids())


def test_drift_check_reports_missing_spec(tmp_path):
    """El código va en `error_code`, no escondido en el texto del error.

    Esto afirmaba `result["error"] == "spec_not_found"`: un código de máquina
    metido en el campo de texto libre, que es literalmente AP-52. El
    consumidor no puede decidir con eso — no sabe si reintentar, si es su
    culpa, ni qué hacer. Ahora el envelope sale por `emit_error` y trae
    `error_code` del catálogo y el `recovery` que le corresponde.
    """
    result = framework_drift_check(tmp_path / "no-existe.md")
    assert not result["ok"]
    assert result["error_code"] == "FILE_NOT_FOUND"
    assert result["recovery"], "un error sin recuperación no le sirve a nadie"
    assert "no-existe.md" in result["message"]


# ── El manifiesto como representación pública ─────────────────────────────────


def test_manifest_has_framework_section():
    text = SPEC.read_text(encoding="utf-8")
    assert "## Marco de Datos y Gobernanza" in text
    assert "## Qué es este estándar" in text
    assert "### Política de no-derogación" in text


def test_manifest_changelog_is_chronological():
    """La entrada de v27 estuvo intercalada entre v37 y v34.3 sin que nadie lo notara."""
    text = SPEC.read_text(encoding="utf-8")
    changelog = text[text.index("\n## Changelog") :]
    versions = [
        tuple(int(p) for p in (m.group(1).split(".") + ["0"])[:2])
        for m in re.finditer(r"^### v(\d+(?:\.\d+)?) — ", changelog, re.MULTILINE)
    ]
    assert versions == sorted(versions, reverse=True), "changelog fuera de orden"


def test_manifest_changelog_has_no_pending_hashes_for_released_versions():
    text = SPEC.read_text(encoding="utf-8")
    changelog = text[text.index("\n## Changelog") :]
    pending = re.findall(r"^### (v[\d.]+) — [\d-]+ `git: pending`", changelog, re.MULTILINE)
    # La versión en curso puede llevar `pending`: su commit no existe todavía
    # cuando se escribe la entrada. Se deriva de `CURRENT_VERSION` en vez de
    # fijarla aquí — un literal obliga a editar el test en cada release, y el
    # que lo edita a la carrera acaba ampliando la excepción a la versión
    # anterior, que es justo la que este guard tiene que cazar.
    from vault_standard_upgrade import CURRENT_VERSION

    assert pending in ([], [CURRENT_VERSION]), f"hashes sin fijar: {pending}"


def test_no_git_command_uses_the_nonexistent_docs_path():
    """El archivo nunca vivió en docs/ — el comando de ejemplo devolvía vacío.

    La ruta antigua sí puede aparecer citada en el changelog al describir esta
    corrección; lo que no puede es volver a aparecer dentro de un comando.
    """
    bad = [
        line
        for line in SPEC.read_text(encoding="utf-8").splitlines()
        if "git log" in line and "docs/vault-obsidian-architecture.md" in line
    ]
    assert not bad, f"comandos con ruta inexistente: {bad}"

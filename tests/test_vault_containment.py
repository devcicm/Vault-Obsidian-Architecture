"""Tests de contención de rutas (AP-36, v39).

Síntoma que originó estas pruebas: carpetas de vault (00_System/, 99_Index/,
vault-backups/) y el contrato de tools se generaban FUERA de todo vault-*.

Tres causas, una prueba por cada una:
  1. _detect_vault_root() devolvía la raíz del repo sin marcarlo.
  2. La rama spec-repo hacía mkdir() en tiempo de importación.
  3. vault_restore derivaba su ruta de __file__.parent.parent.parent, dos
     niveles por encima del vault, donde el guard AP-36 no miraba.
"""

import json
import subprocess

import vault_subproceso
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402
from vault_norms import _CONTAMINATION_DEPTH, _VAULT_ARTIFACT_NAMES, vault_norms_audit  # noqa: E402


def _run_detect(tmp_path: Path, env_extra=None):
    """Ejecuta la detección en un proceso limpio con scripts/ copiado en tmp."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for src in SCRIPTS.glob("*.py"):
        (scripts_dir / src.name).write_bytes(src.read_bytes())
    for src in SCRIPTS.glob("*.json"):
        (scripts_dir / src.name).write_bytes(src.read_bytes())
    code = (
        "import sys; sys.path.insert(0, '.');"
        "from vault_io import VAULT_ROOT, vault_root_origin;"
        "import json; print(json.dumps({'root': str(VAULT_ROOT), 'origin': vault_root_origin()}))"
    )
    import os

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop("VAULT_ROOT", None)
    if env_extra:
        env.update(env_extra)
    proc = vault_subproceso.ejecutar(
        [sys.executable, "-c", code],
        cwd=scripts_dir,
        capture_output=True,
        env=env,
    )
    return proc


# ── 1. Detección del vault root ───────────────────────────────────────────────


def test_repo_without_vault_is_flagged_as_low_confidence(tmp_path):
    """Sin vault-*/ la detección cae a la raíz del repo, pero lo declara."""
    proc = _run_detect(tmp_path)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data["origin"] == "repo_root_fallback"
    assert Path(data["root"]) == tmp_path


def test_strict_root_refuses_to_guess(tmp_path):
    """VAULT_STRICT_ROOT convierte la suposición en error explícito."""
    proc = _run_detect(tmp_path, {"VAULT_STRICT_ROOT": "1"})
    assert proc.returncode != 0
    # Subcadena ASCII: stderr del subproceso puede llegar con la codificación
    # de consola de Windows y romper los acentos.
    assert "RuntimeError" in proc.stderr
    assert "VAULT_ROOT" in proc.stderr


def test_sibling_vault_dir_is_confident(tmp_path):
    """Con un vault-*/ real la detección es de alta confianza."""
    (tmp_path / "vault-demo" / "00_System").mkdir(parents=True)
    proc = _run_detect(tmp_path)
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data["origin"] == "sibling_vault_dir"
    assert Path(data["root"]) == tmp_path / "vault-demo"


def test_importing_vault_io_creates_no_directories(tmp_path):
    """Importar no debe escribir en disco.

    La rama spec-repo hacía sandbox.mkdir() dentro de _detect_vault_root(), que
    corre al importar el módulo: cualquier repo con el manifiesto como doc de
    referencia recibía un vault-sandbox/ por el mero hecho de importar.
    """
    (tmp_path / "vault-obsidian-architecture.md").write_text("# spec\n", encoding="utf-8")
    proc = _run_detect(tmp_path)
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data["origin"] == "spec_repo_sandbox"
    assert Path(data["root"]) == tmp_path / "vault-sandbox"
    assert not (tmp_path / "vault-sandbox").exists(), "importar creó el directorio"


def test_vault_root_origin_values_are_known():
    assert vault_io.vault_root_origin() in {
        "env",
        "sibling_vault_dir",
        "sibling_vault_dir_fresh",
        "scripts_inside_vault",
        "spec_repo_sandbox",
        "repo_root_fallback",
    }
    assert vault_io.vault_root_is_confident() == (
        vault_io.vault_root_origin() not in vault_io.LOW_CONFIDENCE_ORIGINS
    )


# ── 2. Guard de contaminación a N niveles ─────────────────────────────────────


def _make_vault(root: Path):
    for section in ("00_System", "99_Index", "01_Projects"):
        (root / section).mkdir(parents=True, exist_ok=True)


@pytest.mark.parametrize("level", [1, 2])
@pytest.mark.parametrize("artifact", ["00_System", "99_Index", "vault-backups"])
def test_contamination_detected_at_each_level(tmp_path, level, artifact):
    """El guard debe ver artefactos hasta _CONTAMINATION_DEPTH niveles arriba.

    Hasta v38.1 solo miraba level=1, así que el patrón legacy
    parent.parent.parent (level=2) era invisible.
    """
    vault = tmp_path / "a" / "b" / "vault-demo"
    _make_vault(vault)
    stray = vault.parents[level - 1] / artifact
    stray.mkdir(parents=True, exist_ok=True)

    result = vault_norms_audit(vault)
    ap36 = [v for v in result["violations"] if v["norm"] == "AP-36"]
    assert any(str(stray) in v["detail"] for v in ap36), (
        f"contaminación en nivel {level} no detectada: {stray}"
    )


def test_clean_vault_reports_no_contamination(tmp_path):
    vault = tmp_path / "a" / "b" / "vault-demo"
    _make_vault(vault)
    result = vault_norms_audit(vault)
    strays = [
        v for v in result["violations"]
        if v["norm"] == "AP-36" and "por encima del vault" in v["detail"]
    ]
    assert strays == []


def test_own_artifacts_are_not_flagged(tmp_path):
    """00_System/ DENTRO del vault es correcto, no contaminación."""
    vault = tmp_path / "vault-demo"
    _make_vault(vault)
    result = vault_norms_audit(vault)
    assert not any(
        "por encima del vault" in v["detail"]
        for v in result["violations"]
        if v["norm"] == "AP-36"
    )


def test_contamination_depth_covers_legacy_pattern():
    """parent.parent.parent son 2 niveles: el guard debe cubrir al menos eso."""
    assert _CONTAMINATION_DEPTH >= 2
    assert "vault-backups" in _VAULT_ARTIFACT_NAMES


# ── 3. Contrato de tools dentro del vault ─────────────────────────────────────


def test_tool_spec_path_is_inside_the_vault():
    path = vault_io.tool_spec_path()
    assert path.parent.name == "00_System"
    assert path.parent.parent == vault_io.get_vault_root()


def test_tool_spec_resolves_to_canonical_location():
    """En este repo el contrato ya está migrado a <vault>/00_System/."""
    resolved = vault_io.resolve_tool_spec()
    assert resolved is not None, "contrato no encontrado en ninguna ubicación"
    assert resolved == vault_io.tool_spec_path()


def test_tool_spec_is_valid_and_has_tools():
    spec = json.loads(vault_io.resolve_tool_spec().read_text(encoding="utf-8"))
    assert spec.get("tools"), "contrato sin tools"


def test_legacy_tool_spec_location_is_read_only():
    """La ruta legacy se conserva como fallback de LECTURA (no-derogación)."""
    assert vault_io.LEGACY_TOOL_SPEC.name == "tool-spec.json"
    assert vault_io.LEGACY_TOOL_SPEC.parent == SCRIPTS
    # Ya no debe existir en este repo: se movió, no se duplicó.
    assert not vault_io.LEGACY_TOOL_SPEC.exists(), "hay dos copias del contrato — riesgo de drift"


def test_no_script_writes_the_contract_outside_the_vault():
    """Ninguna tool debe volver a escribir tool-spec.json junto a los scripts."""
    offenders = []
    for script in SCRIPTS.glob("vault_*.py"):
        text = script.read_text(encoding="utf-8", errors="replace")
        if 'SCRIPTS_DIR / "tool-spec.json"' in text or '_HERE / "tool-spec.json"' in text:
            offenders.append(script.name)
    assert not offenders, f"contrato resuelto fuera del vault en: {offenders}"


# ── 4. vault_restore: rutas y wipe ────────────────────────────────────────────


def test_restore_backup_root_follows_the_active_vault(tmp_path):
    """La raíz de backups sale del vault activo, no de una constante congelada.

    La propiedad no cambió con la migración a `vault/durabilidad/`; cambió
    dónde se comprueba. Ahora ni siquiera hace falta `set_vault_root()`: la
    raíz se inyecta, que es de lo que va AP-49.
    """
    from vault.durabilidad.repositorio import RepositorioDurabilidad
    from vault.kernel import construir

    assert RepositorioDurabilidad(construir(tmp_path)).raiz_backups == \
        (tmp_path / "vault-backups").resolve()


def test_restore_never_wipes_the_backup_directory():
    """El wipe previo al restore no puede borrar el snapshot que va a leer.

    Al mover los backups dentro del vault (v38.1) el bucle de limpieza pasó a
    incluir vault-backups/ en su barrido.
    """
    from vault.durabilidad.restauracion import NO_BORRAR

    assert "vault-backups" in NO_BORRAR


def test_restore_no_longer_uses_the_grandparent_pattern():
    source = (SCRIPTS / "vault_restore.py").read_text(encoding="utf-8")
    assert "BACKUP_ROOT = Path(__file__).parent.parent.parent" not in source


def test_restore_reports_both_locations_when_missing():
    import vault_restore

    result = vault_restore.vault_restore("no-existe-jamas", confirm=True)
    assert result["ok"] is False
    assert len(result["searched"]) == 2

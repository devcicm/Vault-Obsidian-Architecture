"""Contrato del ciclo de vida instalado: runtime externo, sin scripts."""

import json
import shutil
from pathlib import Path

import pytest

from vault.ciclo_de_vida import producto
from vault.product_cli import main


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def test_seed_empaquetado_es_proyeccion_del_registro_canonico():
    import sys

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        import vault_registry
        assert list(producto.cargar_seed().sections) == vault_registry.standard_folders()
        assert producto.cargar_seed().standard_version == __import__("vault_version").CURRENT_VERSION
    finally:
        sys.path.remove(str(scripts))


def test_una_semilla_desfasada_rompe_la_puerta_del_catalogo(monkeypatch, tmp_path):
    """v40.35: el bump dejó la semilla en v40.34 y ninguna puerta lo vio, así
    que `vault init` creaba runtimes que `vault doctor` rechazaba. La semilla
    viaja ahora con el catálogo: `--check` falla si envejece y `--sync` la
    regenera desde `vault_registry`."""
    import sys

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        import vault_mcp_catalog as MC

        seed = tmp_path / "runtime-seed.json"
        seed.write_text(MC._runtime_seed_text().replace(MC.CURRENT_VERSION, "v0.0"), encoding="utf-8")
        monkeypatch.setattr(MC, "_runtime_seed_path", lambda: seed)
        result = MC.check_sync()
        assert result["ok"] is False
        assert any("runtime seed" in diff for diff in result["diffs"])

        seed.unlink()
        assert MC.check_sync()["ok"] is False, "una semilla ausente no puede pasar"
    finally:
        sys.path.remove(str(scripts))


def test_el_rechazo_previo_de_vault_run_no_ofrece_un_force_que_no_existe(monkeypatch, tmp_path, capsys):
    """Medido con la wheel 40.35: la pista de PREFLIGHT_REJECTED decía «Repetir
    con --force asume el riesgo», pero `vault run` no tiene `--force`: se pasa a
    la tool y el pre-flight vuelve a rechazar igual. La pista mandaba al
    consumidor a un camino cerrado."""
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    monkeypatch.setenv("VAULT_ROOT", str(vault))
    for extra in ([], ["--force"]):
        codigo = main(["run", "vault_read", "--path", "../fuera/nota.md", *extra])
        envelope = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
        assert codigo != 0 and envelope["error_code"] == "PREFLIGHT_REJECTED"
        assert envelope["blocked"] is True
        assert "--force" not in envelope["recovery"]["hint"], envelope["recovery"]["hint"]


def test_un_runtime_recien_creado_valida_limpio(tmp_path):
    """Medido el 2026-10-01 con la wheel instalada: `vault init` y luego
    `vault_validate` daban VALIDATION_FAILED por `00_System/vault-hub.md`
    sin frontmatter. Se mide con el validador real, en otro proceso."""
    import os
    import subprocess
    import sys

    root = tmp_path / "consumer-runtime"
    assert producto.inicializar_runtime(root)["ok"]
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    env = dict(os.environ, VAULT_ROOT=str(root), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run(
        [sys.executable, str(scripts / "vault_validate.py"), "--check", "frontmatter"],
        env=env, capture_output=True, text=True, encoding="utf-8", cwd=str(scripts))
    salida = p.stdout.strip()
    resultado = json.loads(salida[salida.index("{"):])
    assert resultado["ok"] is True, resultado.get("invalid")
    assert "00_System/vault-hub.md" in resultado["valid"]


def test_init_crea_runtime_minimo_e_idempotente(tmp_path):
    root = tmp_path / "consumer-runtime"
    first = producto.inicializar_runtime(root)
    assert first["ok"] and first["state"] == producto.CREATED
    assert (root / "00_System" / "standard-version.json").is_file()
    assert (root / "00_System" / "vault-hub.md").is_file()
    assert all((root / section).is_dir() for section in producto.cargar_seed().sections)
    before = _snapshot(root)
    second = producto.inicializar_runtime(root)
    assert second == {"ok": True, "state": producto.ALREADY_INITIALIZED, "runtime": str(root)}
    assert _snapshot(root) == before


def test_init_rechaza_directorio_no_vacio_que_no_es_runtime(tmp_path):
    root = tmp_path / "not-runtime"
    root.mkdir()
    (root / "user.md").write_text("no tocar", encoding="utf-8")
    result = producto.inicializar_runtime(root)
    assert result["state"] == producto.CONFLICT
    assert (root / "user.md").read_text(encoding="utf-8") == "no tocar"


def test_init_falla_sin_publicar_runtime_parcial(tmp_path, monkeypatch):
    root = tmp_path / "failing-runtime"

    def broken_write(_root, _seed):
        raise OSError("injected failure")

    monkeypatch.setattr(producto, "_write_seed", broken_write)
    result = producto.inicializar_runtime(root)
    assert result["state"] == producto.FAILED
    assert not root.exists()
    assert not list(tmp_path.glob(".failing-runtime.init-*"))


def test_doctor_y_status_son_read_only_y_detectan_datos_rotos(tmp_path):
    root = tmp_path / "runtime"
    assert producto.inicializar_runtime(root)["ok"]
    before = _snapshot(root)
    doctor = producto.diagnosticar_runtime(root)
    status = producto.estado_runtime(root)
    assert doctor["ok"] and doctor["compatibility"] == "compatible"
    assert status["ok"] and status["sections_present"] == len(producto.cargar_seed().sections)
    assert _snapshot(root) == before
    (root / "00_System" / "standard-version.json").write_text("{broken", encoding="utf-8")
    assert producto.diagnosticar_runtime(root)["state"] == "STANDARD_VERSION_INVALID"


def test_doctor_detecta_seccion_y_version_incompatibles(tmp_path):
    root = tmp_path / "runtime"
    assert producto.inicializar_runtime(root)["ok"]
    shutil.rmtree(root / "07_Knowledge")
    assert producto.diagnosticar_runtime(root)["state"] == "SYSTEM_FILES_MISSING"
    (root / "07_Knowledge").mkdir()
    version = root / "00_System" / "standard-version.json"
    data = json.loads(version.read_text(encoding="utf-8"))
    data["applied_version"] = "v999.0"
    version.write_text(json.dumps(data), encoding="utf-8")
    result = producto.diagnosticar_runtime(root)
    assert result["state"] == "STANDARD_INCOMPATIBLE"
    assert result["compatibility"] == "unsupported_newer"


def test_runtime_es_portable_y_no_contiene_toolkit(tmp_path):
    original = tmp_path / "original"
    moved = tmp_path / "moved"
    assert producto.inicializar_runtime(original)["ok"]
    shutil.copytree(original, moved)
    assert producto.diagnosticar_runtime(moved)["ok"]
    names = {path.name for path in moved.rglob("*")}
    assert not {"scripts", "cli", "tests", "pyproject.toml", ".git"} & names
    assert not any(path.name == "product_cli.py" for path in moved.rglob("*"))


def test_cli_lifecycle_emite_contrato_estable(tmp_path, capsys, monkeypatch):
    root = tmp_path / "runtime"
    # El entry point real lee metadata instalada; este unit test ejecuta desde
    # source y sólo caracteriza el despacho lifecycle.
    monkeypatch.setattr("vault.product_cli.toolkit_version", lambda: "test")
    assert main(["init", str(root)]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["state"] == producto.CREATED
    assert main(["doctor", str(root)]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "RUNTIME_OK"
    assert main(["status", str(root)]) == 0
    assert json.loads(capsys.readouterr().out)["sections_present"]
    assert main(["doctor", str(tmp_path / "missing")]) != 0
    error = json.loads(capsys.readouterr().err)
    assert error["ok"] is False and error["state"] == "RUNTIME_MISSING"


def test_producto_lifecycle_no_importa_scripts_ni_checkout():
    source = Path(producto.__file__).read_text(encoding="utf-8")
    assert "scripts/" not in source
    assert "REPO_ROOT" not in source
    assert "sys.path" not in source


def test_cada_fallo_del_ciclo_de_vida_lleva_su_codigo_y_su_pista(tmp_path, capsys, monkeypatch):
    """Medido el 2026-10-01 con la wheel: `vault init` sobre un padre que no
    existe salía como INVALID_ACTION con la pista «Ejecutar el script con
    --help para ver las acciones disponibles». Todo fallo de init, doctor y
    status salía igual: el consumidor no podía distinguir una ruta mala de un
    runtime dañado, y la pista no tenía nada que ver con ninguno."""
    from vault.kernel.errores import ERROR_CATALOG

    monkeypatch.setattr("vault.product_cli.toolkit_version", lambda: "test")
    fichero = tmp_path / "fichero.txt"
    fichero.write_text("x", encoding="utf-8")
    ocupado = tmp_path / "ocupado"
    ocupado.mkdir()
    (ocupado / "nota.md").write_text("de otro", encoding="utf-8")
    sin_seccion = tmp_path / "sin-seccion"
    assert producto.inicializar_runtime(sin_seccion)["ok"]
    shutil.rmtree(sin_seccion / "07_Knowledge")
    casos = {
        "INIT_INVALID_TARGET": ["init", str(tmp_path / "no-existe" / "hijo")],
        "INIT_CONFLICT": ["init", str(ocupado)],
        "RUNTIME_MISSING": ["doctor", str(tmp_path / "no-existe")],
        "NOT_RUNTIME": ["doctor", str(fichero)],
        "STANDARD_VERSION_MISSING": ["doctor", str(ocupado)],
        "SYSTEM_FILES_MISSING": ["status", str(sin_seccion)],
    }
    for estado, argv in casos.items():
        assert main(argv) != 0
        error = json.loads(capsys.readouterr().err)
        assert error["state"] == estado, error
        assert error["error_code"] in ERROR_CATALOG, error
        assert error["error_code"] != "INVALID_ACTION", (estado, error)
        assert "--help" not in error["recovery"]["hint"], (estado, error)

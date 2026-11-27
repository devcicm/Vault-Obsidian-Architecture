"""Tests TDD de regresión para los hallazgos de la auditoría externa 2026-11-27 (H-02..H-24).

Verifica con evidencia ejecutable:
- H-02: `IsolationUnavailable` expone su causa real en el envelope de `vault_errors`.
- H-04: `SagaPreSha` preserva trabajo sucio previo al lote, retira archivos nuevos
  del lote a `.history/saga-rolled-back/` y preserva binarios byte a byte.
- H-05: `merkle_vivo` acepta `ilegibles` y no lanza `NameError` ante `PermissionError`.
- H-06: `registrar_baul_maestro` rechaza colisiones de identidad sin `allow_update=True`.
- H-07: los 72/72 patrones de `CATALOGO_PATRONES` tienen regla de detección real.
- H-15: `vault.kernel.acceso_baules` y `vault.kernel.registry` se importan sin `scripts/`.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import textwrap

import pytest

from apoyo import ROOT, correr_python


def test_h04_saga_preserva_trabajo_sucio_retira_nuevos_y_protege_binarios(tmp_path):
    from vault.kernel.ciclo_ejecucion import SagaPreSha

    repo = tmp_path / "vault-saga"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)

    (repo / "sucia.md").write_text("v1-commit", encoding="utf-8")
    (repo / "limpia.md").write_text("v1-limpia", encoding="utf-8")
    bytes_bin = b"\x89PNG\r\n\x1a\n\x00\x01\xff\xfe"
    (repo / "imagen.bin").write_bytes(bytes_bin)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    # Trabajo sin commit previo al lote (NO debe perderse)
    (repo / "sucia.md").write_text("v2-trabajo-del-usuario", encoding="utf-8")

    saga = SagaPreSha(repo, "lote-h04")
    assert saga.begin()

    # Mutaciones del lote: toca sucia.md, limpia.md, imagen.bin y crea nueva.md
    (repo / "sucia.md").write_text("v3-lote-fallido", encoding="utf-8")
    (repo / "limpia.md").write_text("v2-lote-fallido", encoding="utf-8")
    (repo / "imagen.bin").write_bytes(b"corrupto")
    (repo / "nueva-del-lote.md").write_text("archivo nuevo fallido", encoding="utf-8")

    res = saga.compensate()
    assert res["ok"] is True
    assert (repo / "sucia.md").read_text(encoding="utf-8") == "v2-trabajo-del-usuario"
    assert (repo / "limpia.md").read_text(encoding="utf-8") == "v1-limpia"
    assert (repo / "imagen.bin").read_bytes() == bytes_bin
    assert not (repo / "nueva-del-lote.md").exists()
    assert (repo / ".history" / "saga-rolled-back" / "lote-h04" / "nueva-del-lote.md").is_file()


def test_h05_merkle_vivo_no_lanza_nameerror_con_ficheros_ilegibles(tmp_path, monkeypatch):
    from vault.durabilidad import snapshot

    (tmp_path / "07_Knowledge").mkdir(parents=True)
    ok_file = tmp_path / "07_Knowledge" / "ok.md"
    locked = tmp_path / "07_Knowledge" / "bloqueado.md"
    ok_file.write_text("# OK\n", encoding="utf-8")
    locked.write_text("# Lock\n", encoding="utf-8")

    original = pathlib.Path.read_bytes

    def _fail_locked(self):
        if self.name == "bloqueado.md":
            raise PermissionError("bloqueado en Windows")
        return original(self)

    monkeypatch.setattr(pathlib.Path, "read_bytes", _fail_locked)
    ilegibles: list[str] = []
    raiz, count = snapshot.merkle_vivo(tmp_path, ilegibles=ilegibles)
    assert count == 1
    assert isinstance(raiz, str) and len(raiz) > 0
    assert ilegibles == ["07_Knowledge/bloqueado.md"]


def test_h06_registro_maestro_rechaza_colision_de_identidad_sin_allow_update(tmp_path):
    from vault.kernel.acceso_baules import leer_registro_maestro, registrar_baul_maestro

    casa = tmp_path / ".vault-master"
    v1 = tmp_path / "v1"
    v2 = tmp_path / "v2"
    v1.mkdir()
    v2.mkdir()

    registrar_baul_maestro("redes", v1, casa=casa)
    with pytest.raises(ValueError, match="Conflicto de identidad"):
        registrar_baul_maestro("redes", v2, casa=casa)
    with pytest.raises(ValueError, match="Conflicto de identidad"):
        registrar_baul_maestro("otro-nombre", v1, casa=casa)

    # Misma (name, path) actualiza metadatos; allow_update=True permite reubicar
    registrar_baul_maestro("redes", v1, descripcion="actualizada", casa=casa)
    registrar_baul_maestro("redes", v2, allow_update=True, casa=casa)
    entradas = leer_registro_maestro(casa)["vaults"]
    assert len(entradas) == 1
    assert pathlib.Path(entradas[0]["path"]).resolve() == v2.resolve()


def test_h07_todos_los_72_patrones_tienen_detector_real_y_detectan_los_6_nuevos(tmp_path):
    from vault.kernel.patrones_diseno import CATALOGO_PATRONES, detectar_patrones

    txt = (ROOT / "vault" / "kernel" / "patrones_diseno.py").read_text(encoding="utf-8")
    cuerpo = (
        txt[txt.index("def _detectar_python"):]
        + txt[txt.index("_REGLAS_GENERICAS"):txt.index("def normalizar_nombre_patron")]
    )
    sin_regla = [p["id"] for p in CATALOGO_PATRONES if p["id"] not in cuerpo]
    assert sin_regla == [], f"Patrones sin regla de deteccion: {sin_regla}"

    repo = tmp_path / "seis-patrones"
    repo.mkdir()
    (repo / "arch.py").write_text(
        textwrap.dedent(
            """\
            from functools import cached_property

            class BillingModuleBoundary: pass
            class OrdersServiceDiscoveryClient: pass
            class LegacyStranglerRouter: pass
            class MobileBff: pass
            class TelemetrySidecarProxy: pass
            class ConfigService:
                @cached_property
                def client(self):
                    return object()
            """
        ),
        encoding="utf-8",
    )
    det = detectar_patrones(repo)
    ids = {p["id"] for p in det["patterns"]}
    for esperado in (
        "modular-monolith",
        "microservices-architecture",
        "strangler-fig",
        "backend-for-frontend",
        "sidecar-ambassador",
        "lazy-initialization",
    ):
        assert esperado in ids, f"Falto detectar {esperado}: {sorted(ids)}"


def test_h15_kernel_acceso_baules_y_registry_importables_sin_scripts_en_syspath():
    # Proceso aislado eliminando cualquier entrada `scripts` de sys.path (AP-69 + H-15)
    res = correr_python(
        "-c",
        "import sys; sys.path = [p for p in sys.path if not p.rstrip('/\\\\').endswith('scripts')]; "
        "from vault.kernel.acceso_baules import Principal, evaluar_acceso_cruzado; "
        "from vault.kernel.registry import ORDERED_SECTIONS; "
        "assert len(ORDERED_SECTIONS) >= 20; print('OK')",
        cwd=ROOT,
        timeout=30,
    )
    assert res.returncode == 0, res.stderr
    assert "OK" in res.stdout


def test_h02_vault_errors_expone_causa_de_isolation_unavailable(monkeypatch, capsys):
    import json
    import vault_errors
    import vault.kernel.aislamiento as aislamiento
    from vault.kernel.aislamiento import IsolationUnavailable

    def _fallar_aislado(*args, **kwargs):
        raise IsolationUnavailable("pidfd_open no disponible en este build de Python")

    def _dummy_main():
        return 0

    monkeypatch.setattr(aislamiento, "ejecutar_aislado", _fallar_aislado)
    monkeypatch.setattr(_dummy_main, "__module__", "vault_errors")
    monkeypatch.setattr(vault_errors, "_dummy_main_h02", _dummy_main, raising=False)
    _dummy_main.__qualname__ = "_dummy_main_h02"

    code = vault_errors.wrap_main(_dummy_main, "vault_test_h02")
    assert code == 1
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["ok"] is False
    assert "pidfd_open" in payload["message"]
    assert "pidfd_open" in (payload.get("args") or {}).get("causa", "")


def test_python_minimo_310_avisa_version_vieja():
    from vault.kernel.version_python import PYTHON_MINIMO, comprobar_python_minimo

    assert PYTHON_MINIMO == (3, 10)
    aviso = comprobar_python_minimo((3, 9))
    assert aviso is not None
    assert "3.9" in aviso and "3.10" in aviso and "actualizar" in aviso.lower()
    assert comprobar_python_minimo((3, 10)) is None
    assert comprobar_python_minimo((3, 12)) is None

"""Cobertura observable de onboarding con datos reales y vault temporal."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

import vault_io
import vault_onboard


@pytest.fixture
def entorno(tmp_path):
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    proyecto = tmp_path / "proyecto"
    (proyecto / "src").mkdir(parents=True)
    (proyecto / "tests").mkdir()
    (proyecto / "src" / "core.py").write_text(
        '"""Núcleo con evidencia de código."""\n\ndef ejecutar():\n    return 1\n', encoding="utf-8")
    (proyecto / "tests" / "test_core.py").write_text(
        "def test_ejecutar():\n    assert 1 == 1\n", encoding="utf-8")
    (proyecto / "README.md").write_text(
        "# Demo\n\nProyecto de ejemplo con un módulo y pruebas.\n", encoding="utf-8")
    previa = vault_io.get_vault_root()
    vault_io.set_vault_root(vault)
    try:
        yield vault, proyecto
    finally:
        vault_io.set_vault_root(previa)


def _arbol(raiz: Path):
    return {p.relative_to(raiz).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in raiz.rglob("*") if p.is_file()}


def _onboard(proyecto: Path, **kwargs):
    return vault_onboard.vault_onboard(project="demo", path=str(proyecto), no_git=True, **kwargs)


def _fusion_en_proceso(raiz, ruta, encabezado, barrera, salida):
    """Sincroniza una única lectura de la nota para exponer actualizaciones perdidas."""
    vault_io.set_vault_root(raiz)
    original = Path.read_text
    sincronizada = False

    def leer(path, *args, **kwargs):
        nonlocal sincronizada
        texto = original(path, *args, **kwargs)
        if path == Path(ruta) and not sincronizada:
            sincronizada = True
            try:
                barrera.wait(timeout=3)
            except threading.BrokenBarrierError:
                pass  # con lock el segundo proceso aún no puede entrar
        return texto

    Path.read_text = leer
    try:
        salida.put(("ok", vault_onboard._merge_stub(Path(ruta), f"## {encabezado}\n\nEvidencia.\n", False)))
    except Exception as exc:
        salida.put(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        Path.read_text = original


def test_dry_run_preserva_todo_el_arbol_incluidos_archivos_no_markdown(entorno):
    vault, proyecto = entorno
    (vault / "00_System" / "custom.json").write_text('{"dato": 1}', encoding="utf-8")
    (vault / "00_System" / "manual.md").write_text("# Manual\n", encoding="utf-8")
    antes = _arbol(vault)
    resultado = _onboard(proyecto, dry_run=True)
    assert resultado["ok"], resultado
    assert _arbol(vault) == antes


def test_brownfield_preserva_bytes_de_nota_inmutable_y_notifica_omision(entorno):
    vault, proyecto = entorno
    (vault / "00_System" / "inmutable.json").write_text(
        json.dumps({"secciones": ["11_Code"]}), encoding="utf-8")
    nota = vault / "11_Code" / "demo" / "core.md"
    nota.parent.mkdir(parents=True)
    nota.write_text("---\ntitle: core\nstatus: draft\ntags: []\n---\n\n# Manual\n", encoding="utf-8")
    antes = hashlib.sha256(nota.read_bytes()).digest()
    resultado = _onboard(proyecto)
    assert resultado["ok"], resultado
    assert hashlib.sha256(nota.read_bytes()).digest() == antes
    assert any("11_Code/demo/core.md" in str(item).replace("\\", "/")
               for item in resultado["omitidas_por_politica"]), resultado
    assert "11_Code/demo/core.md" in resultado["sections_report"]["11_Code"]["policy_omissions"]


def test_greenfield_declara_la_cobertura_de_cada_seccion(entorno):
    vault, proyecto = entorno
    resultado = _onboard(proyecto)
    assert resultado["ok"], resultado
    vacias = resultado["sections_left_empty_by_design"]
    assert all(isinstance(motivo, str) and motivo.strip() for motivo in vacias.values())
    omitidas = resultado["skipped_no_evidence"]
    assert all(item.get("reason") for item in omitidas), omitidas
    cobertura = resultado["sections_report"]
    assert set(cobertura) == set(vault_onboard.ORDERED_SECTIONS)
    for seccion, entrada in cobertura.items():
        assert entrada["status"] in {"by_design", "planned", "processed", "no_notes", "skipped", "policy"}
        assert entrada["reason"].strip(), seccion
        if seccion in vacias:
            assert entrada["status"] == "by_design"
        elif entrada["status"] == "no_notes":
            assert not list((vault / seccion).rglob("*.md")) or all(
                p.name == "index.md" for p in (vault / seccion).rglob("*.md"))


def test_dry_run_informa_seccion_omitida_sin_escrituras(entorno):
    vault, proyecto = entorno
    antes = _arbol(vault)
    resultado = _onboard(proyecto, dry_run=True, skip=["01"])
    assert resultado["ok"], resultado
    assert resultado["sections_report"]["01_Projects"]["status"] == "skipped"
    assert resultado["sections_report"]["01_Projects"]["reason"]
    assert _arbol(vault) == antes


def test_error_parcial_conserva_notas_y_permita_reintento(entorno, monkeypatch):
    vault, proyecto = entorno
    escribir = vault_onboard._write
    llamadas = 0

    def fallar_en_segunda(*args, **kwargs):
        nonlocal llamadas
        llamadas += 1
        if llamadas == 2:
            raise OSError("fallo de escritura simulado")
        return escribir(*args, **kwargs)

    monkeypatch.setattr(vault_onboard, "_write", fallar_en_segunda)
    with pytest.raises(OSError, match="fallo de escritura simulado"):
        _onboard(proyecto)
    notas = {p: p.read_text(encoding="utf-8") for p in vault.rglob("*.md")
             if p.name != "index.md"}
    assert notas, "no se observó una nota antes del fallo"

    monkeypatch.setattr(vault_onboard, "_write", escribir)
    resultado = _onboard(proyecto)
    assert resultado["ok"], resultado
    for ruta, contenido in notas.items():
        assert ruta.is_file()
        assert contenido in ruta.read_text(encoding="utf-8")


def test_timeout_de_lock_declara_nota_bloqueada_y_posibles_cambios_previos(entorno, monkeypatch):
    vault, proyecto = entorno
    tomar = vault_onboard.file_lock
    rutas = []

    @contextmanager
    def segundo_bloqueado(ruta, **kwargs):
        rutas.append(ruta)
        if len(rutas) == 2:
            raise TimeoutError("bloqueo simulado")
        with tomar(ruta, **kwargs):
            yield

    monkeypatch.setattr(vault_onboard, "file_lock", segundo_bloqueado)
    resultado = _onboard(proyecto)
    assert resultado["ok"] is False, resultado
    assert resultado["error_code"] == "NOTE_LOCKED", resultado
    assert resultado["partial_changes_possible"] is True, resultado
    assert resultado["blocked_path"] == rutas[1].relative_to(vault).as_posix()
    assert rutas[0].is_file(), "la primera nota demuestra que puede haber cambios previos"
    assert not rutas[1].exists(), "la nota bloqueada no debe escribirse"


def test_timeout_en_cuerpo_protegido_no_se_clasifica_como_lock(entorno, monkeypatch):
    _, proyecto = entorno
    def fallo_interno(*args, **kwargs):
        raise TimeoutError("fallo interno")
    monkeypatch.setattr(vault_onboard, "_merge_stub_bajo_lock", fallo_interno)
    with pytest.raises(TimeoutError, match="fallo interno"):
        _onboard(proyecto)


def test_timeout_en_flujo_no_se_oculta_como_exito(entorno, monkeypatch):
    _, proyecto = entorno
    workflows = proyecto / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
    tomar = vault_onboard.file_lock
    alcanzados = []

    @contextmanager
    def flujo_bloqueado(ruta, **kwargs):
        if "13_Flows" in ruta.parts:
            alcanzados.append(ruta)
            raise TimeoutError("lock simulado en flujo")
        with tomar(ruta, **kwargs):
            yield

    monkeypatch.setattr(vault_onboard, "file_lock", flujo_bloqueado)
    resultado = _onboard(proyecto)
    assert alcanzados, "no se alcanzó la creación del flujo"
    assert resultado["ok"] is False and resultado["error_code"] == "NOTE_LOCKED"
    assert resultado["partial_changes_possible"] is True


def test_cli_notifica_timeout_de_lock_y_cambios_previos(entorno, monkeypatch, capsys):
    import sys

    _, proyecto = entorno
    tomar = vault_onboard.file_lock
    llamadas = []

    @contextmanager
    def segundo_bloqueado(ruta, **kwargs):
        llamadas.append(ruta)
        if len(llamadas) == 2:
            raise TimeoutError("lock simulado")
        with tomar(ruta, **kwargs):
            yield

    monkeypatch.setattr(vault_onboard, "file_lock", segundo_bloqueado)
    monkeypatch.setattr(sys, "argv", ["vault_onboard", "--project", "demo",
                                      "--path", str(proyecto), "--no-git"])
    assert vault_onboard.main() == 1
    resultado = json.loads(capsys.readouterr().out)
    assert resultado["ok"] is False
    assert resultado["error_code"] == "NOTE_LOCKED"
    assert resultado["partial_changes_possible"] is True
    assert not Path(resultado["blocked_path"]).is_absolute()


def test_fusiones_en_dos_procesos_no_pierden_secciones(entorno):
    vault, _ = entorno
    nota = vault / "11_Code" / "demo" / "core.md"
    nota.parent.mkdir(parents=True)
    nota.write_text(
        "---\ntitle: core\nid: x\ntype: code\ncreatedAt: 2026-01-01T00:00:00.000Z\n"
        "updatedAt: 2026-01-01T00:00:00.000Z\nstatus: draft\ntags: []\n---\n\n# Manual\n",
        encoding="utf-8")
    ctx = multiprocessing.get_context("spawn")
    barrera, salida = ctx.Barrier(2), ctx.Queue()
    procesos = [ctx.Process(target=_fusion_en_proceso,
                            args=(str(vault), str(nota), titulo, barrera, salida))
                for titulo in ("A", "B")]
    for proceso in procesos:
        proceso.start()
    try:
        for proceso in procesos:
            proceso.join(timeout=30)
        assert all(not p.is_alive() for p in procesos), "la fusión concurrente no terminó"
        assert all(p.exitcode == 0 for p in procesos)
    finally:
        for proceso in procesos:
            if proceso.is_alive():
                proceso.terminate()
                proceso.join(timeout=5)
    resultados = [salida.get(timeout=5) for _ in procesos]
    assert all(estado == "ok" for estado, _ in resultados), resultados
    texto = nota.read_text(encoding="utf-8")
    assert "## A" in texto and "## B" in texto

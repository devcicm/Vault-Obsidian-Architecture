"""Migrating documentation and undoing it: the round trip must close.

QA-FL-02 (flow QA, 2026-11-17, c09473ab): on Windows the migration report
held `[[10_Migratedexcludeddeploy.md]]`. The relative paths were written with
`str(relative_to())`, so they carried backslashes, and `safe_wikilink` strips
backslashes. `vault_migrate_rollback` then found none of the migrated files,
deleted nothing, and still deleted the report, the only map back. The
migration could no longer be undone.

QA-PORT-01: the stub's link to its copy had the same defect. QA-PORT-03: the
absolute source path (drive, user name) was written into the vault, in
`migratedFrom` and in the stub's `**Origen:**`.
"""
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from apoyo import SCRIPTS, correr_tool


def _cli(vault: Path, script: str, *args: str):
    return correr_tool(script, *args, vault=vault, cwd=SCRIPTS)


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    assert _cli(vault, "vault_project.py", "--add", "demo").envelope["ok"]
    return vault


def _fuente(tmp_path: Path) -> Path:
    fuente = tmp_path / "olddocs"
    fuente.mkdir()
    (fuente / "arquitectura.md").write_text(
        "# Arquitectura\n\nEl servicio demo usa arquitectura hexagonal con puertos "
        "y adaptadores.\n", encoding="utf-8")
    (fuente / "deploy.md").write_text(
        "# Guia de despliegue\n\nPasos para desplegar el servicio demo en "
        "produccion.\n", encoding="utf-8")
    return fuente


def _informe() -> str:
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"10_Migrated/_report-demo-{fecha}.md"


def _migrar(tmp_path: Path) -> tuple:
    vault = _vault(tmp_path)
    fuente = _fuente(tmp_path)
    r = _cli(vault, "vault_migrate_docs.py", "--source_path", str(fuente),
             "--project", "demo", "--dry_run", "false").envelope
    assert r["ok"] is True, r
    return vault, fuente, r


def _migrados(r: dict) -> list:
    return sorted(d["destPath"] for d in r["distributedFiles"])


def test_qa_fl02_el_informe_enlaza_rutas_posix(tmp_path):
    vault, _fuente_, r = _migrar(tmp_path)
    migrados = _migrados(r)
    assert migrados and all("\\" not in p and p.startswith("10_Migrated/") for p in migrados), r
    assert r["reportFile"] == _informe(), r
    assert all("\\" not in p for p in r["subfoldersCreated"]), r

    informe = (vault / _informe()).read_text(encoding="utf-8")
    for ruta in migrados:
        assert f"[[{ruta}]]" in informe, informe
        assert f"[[{ruta.rsplit('/', 1)[0]}/_stub-{ruta.rsplit('/', 1)[1]}]]" in informe, informe


def test_qa_port01_el_stub_enlaza_su_copia_con_ruta_posix(tmp_path):
    vault, _fuente_, r = _migrar(tmp_path)

    for ruta in _migrados(r):
        carpeta, nombre = ruta.rsplit("/", 1)
        stub = (vault / carpeta / f"_stub-{nombre}").read_text(encoding="utf-8")
        assert f"[[{ruta}|" in stub, stub


def test_qa_port03_la_migracion_no_guarda_rutas_de_esta_maquina(tmp_path):
    vault, fuente, r = _migrar(tmp_path)
    absolutas = {str(fuente), fuente.as_posix(), str(tmp_path), tmp_path.as_posix()}

    for ruta in sorted(vault.rglob("*.md")):
        texto = ruta.read_text(encoding="utf-8")
        filtradas = [a for a in absolutas if a in texto]
        assert not filtradas, (ruta, filtradas)

    for ruta in _migrados(r):
        carpeta, nombre = ruta.rsplit("/", 1)
        origen = f"olddocs/{nombre}"
        stub = (vault / carpeta / f"_stub-{nombre}").read_text(encoding="utf-8")
        assert f"**Origen:** `{origen}`" in stub, stub
        nota = (vault / ruta).read_text(encoding="utf-8")
        assert yaml.safe_load(nota.split("---", 2)[1])["migratedFrom"] == origen, nota


def test_qa_fl02_migrar_y_deshacer_borra_lo_migrado(tmp_path):
    vault, fuente, r = _migrar(tmp_path)
    migrados = _migrados(r)
    stubs = [f"{p.rsplit('/', 1)[0]}/_stub-{p.rsplit('/', 1)[1]}" for p in migrados]
    assert all((vault / p).is_file() for p in migrados + stubs)

    corrida = _cli(vault, "vault_migrate_rollback.py", "--report_path", _informe(),
                   "--confirm", "true")
    d = corrida.envelope
    assert corrida.codigo == 0 and d["ok"] is True, d
    assert sorted(d["deleted"]) == sorted(migrados + stubs), d
    assert d["deletedCount"] == len(migrados) * 2, d
    assert d["notFound"] == [], d
    assert d["reportDeleted"] is True, d
    assert not any((vault / p).exists() for p in migrados + stubs)
    assert not (vault / _informe()).exists()
    # The source is never touched.
    assert sorted(p.name for p in fuente.iterdir()) == ["arquitectura.md", "deploy.md"]


def test_qa_fl02_un_informe_con_rutas_perdidas_no_se_borra(tmp_path):
    """A report written by the old version names files that cannot be found.

    Rollback does not guess where they are: it reports them and keeps the
    report, so the migration stays undoable once the report is corrected.
    """
    vault, _fuente_, r = _migrar(tmp_path)
    migrados = _migrados(r)
    ruta = vault / _informe()
    # What the old version wrote on Windows: every separator stripped.
    viejo = re.sub(r"\[\[(10_Migrated/[^\]]+)\]\]",
                   lambda m: "[[" + m.group(1).replace("/", "") + "]]",
                   ruta.read_text(encoding="utf-8"))
    perdidos = re.findall(r"\[\[(10_Migrated[^/\]]+)\]\]", viejo)
    assert len(perdidos) == len(migrados) * 2, viejo
    ruta.write_bytes(viejo.encode("utf-8"))

    corrida = _cli(vault, "vault_migrate_rollback.py", "--report_path", _informe(),
                   "--confirm", "true")
    d = corrida.envelope
    assert corrida.codigo == 0 and d["ok"] is True, d
    assert sorted(d["notFound"]) == sorted(perdidos), d
    assert d["deleted"] == [] and d["deletedCount"] == 0, d
    assert d["reportDeleted"] is False, d
    assert "notFound" in d["message"] or "not found" in d["message"], d
    assert ruta.read_text(encoding="utf-8") == viejo
    assert all((vault / p).is_file() for p in migrados)


def test_el_preview_del_rollback_sigue_sin_borrar_nada(tmp_path):
    """Previous behaviour of `--confirm false`: a preview, nothing deleted."""
    vault, _fuente_, r = _migrar(tmp_path)
    migrados = _migrados(r)

    d = _cli(vault, "vault_migrate_rollback.py", "--report_path", _informe(),
             "--confirm", "false").envelope
    assert d["ok"] is True and d["preview"] is True, d
    assert all(p in d["toDelete"] for p in migrados), d
    assert d["notFound"] == [], d
    assert all((vault / p).is_file() for p in migrados)
    assert (vault / _informe()).is_file()


def test_el_rollback_no_borra_lo_que_la_migracion_encontro_y_no_creo(tmp_path):
    """A second migration of the same project finds its destinations taken.

    It leaves them untouched and declares them under `## Conflictos`, but the
    same rows are also listed in `## Archivos Distribuidos`, which is the table
    the rollback reads. Rolling back that report deleted the files the owner
    already had, including edits made after the first migration (W1 advisory,
    2026-11-17). Rollback only deletes what that migration created.
    """
    vault, fuente, r = _migrar(tmp_path)
    migrados = _migrados(r)
    editada = vault / migrados[0]
    original = editada.read_text(encoding="utf-8")
    editada.write_text(f"{original}\nEdicion del propietario.\n", encoding="utf-8")
    antes = {p: (vault / p).read_bytes() for p in migrados}

    segunda = _cli(vault, "vault_migrate_docs.py", "--source_path", str(fuente),
                   "--project", "demo", "--dry_run", "false").envelope
    assert segunda["ok"] is True, segunda
    assert "## Conflictos" in (vault / _informe()).read_text(encoding="utf-8")

    corrida = _cli(vault, "vault_migrate_rollback.py", "--report_path", _informe(),
                   "--confirm", "true")
    d = corrida.envelope
    assert corrida.codigo == 0 and d["ok"] is True, d
    assert not set(migrados) & set(d["deleted"]), d
    assert sorted(d["keptConflicts"]) == sorted(migrados), d
    assert {p: (vault / p).read_bytes() for p in migrados} == antes

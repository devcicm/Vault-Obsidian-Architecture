"""AP-63 — `vault_project`: la puerta de entrada al registro de proyectos.

Lo que fija: un nombre resuelve a un slug o falla con su código; dar de alta
no reasigna un nombre que ya es de otro; la ruta local del repositorio vive en
`00_System/.local/`, con su propio `.gitignore`, y nunca en una nota; el audit
nombra los fantasmas sin contar los ejemplos del manifiesto.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _ejecutar(raiz: Path, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_project.py"), *argv],
        env=dict(
            os.environ,
            VAULT_ROOT=str(raiz),
            VAULT_STRICT_ROOT="1",
            PYTHONIOENCODING="utf-8",
            VAULT_AGENT="system",
        ),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.fixture
def raiz(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "01_Projects", "07_Knowledge", "99_Index"):
        (raiz / seccion).mkdir(parents=True)
    return raiz


def test_ap63_alta_resolucion_por_alias_y_ficha_legible(raiz):
    r = _ejecutar(raiz, "--add", "VCloud SaaS", "--title", "VCloud: SaaS", "--alias", "vcloud")
    assert r["ok"] and r["action"] == "added" and r["project"] == "vcloud-saas", r
    assert r["created"] >= 1
    ficha = raiz / "01_Projects" / "vcloud-saas" / "project.md"
    fm = yaml.safe_load(ficha.read_text(encoding="utf-8").split("---")[1])
    assert fm["title"] == "VCloud: SaaS" and fm["type"] == "project"
    assert fm["project"] == "vcloud-saas" and fm["aliases"] == ["vcloud"]

    r = _ejecutar(raiz, "--resolve", "VCLOUD")
    assert r["project"] == "vcloud-saas" and r["project_resolved_from"] == "alias", r


def test_ap63_resolver_un_nombre_libre_falla_sin_crear_nada(raiz):
    (raiz / "01_Projects" / "mi-api-real").mkdir()
    r = _ejecutar(raiz, "--resolve", "mi-api")
    assert not r["ok"] and r["error_code"] == "PROJECT_NOT_FOUND", r
    assert r["sugerencias"] == ["mi-api-real"]
    assert not (raiz / "01_Projects" / "mi-api").exists()
    # La recuperación lleva al alta explícita. Hasta aquí mandaba a
    # `vault_project_overview`, que creaba la carpeta: el proyecto fantasma
    # que AP-63 existe para impedir, recomendado por su propio error.
    assert r["recovery"]["tool"] == "vault_project", r["recovery"]
    assert r["recovery"]["args"] == ["--add", "<project>"]


def test_ap63_un_alias_ajeno_no_se_reasigna(raiz):
    _ejecutar(raiz, "--add", "alfa", "--alias", "core")
    r = _ejecutar(raiz, "--add", "beta", "--alias", "Core")
    assert not r["ok"] and r["error_code"] == "PROJECT_AMBIGUOUS", r
    assert not (raiz / "01_Projects" / "beta").exists()


def test_sumar_alias_conserva_el_cuerpo_y_repetir_no_escribe(raiz):
    _ejecutar(raiz, "--add", "ans", "--alias", "ans-api")
    ficha = raiz / "01_Projects" / "ans" / "project.md"
    cuerpo = ficha.read_text(encoding="utf-8").split("---", 2)[2]
    r = _ejecutar(raiz, "--add", "ans", "--alias", "ans-core")
    # `written` cuenta además los índices que la escritura regenera, y los que
    # llevan fecha cambian con el minuto: lo que se fija es que hubo trabajo.
    assert r["ok"] and r["action"] == "aliased" and r["written"] >= 1, r
    texto = ficha.read_text(encoding="utf-8")
    assert texto.split("---", 2)[2] == cuerpo
    assert yaml.safe_load(texto.split("---")[1])["aliases"] == ["ans-api", "ans-core"]
    r = _ejecutar(raiz, "--add", "ans", "--alias", "ANS-CORE")
    assert r["ok"] and r["written"] == 0, r


def test_la_ruta_local_va_a_punto_local_con_su_gitignore(raiz, tmp_path):
    repo = tmp_path / "repo-ans"
    repo.mkdir()
    _ejecutar(raiz, "--add", "ans")
    r = _ejecutar(raiz, "--link", "ANS", "--path", str(repo))
    assert r["ok"] and r["project"] == "ans", r
    local = raiz / "00_System" / ".local"
    assert json.loads((local / "project-paths.json").read_text(encoding="utf-8")) == {
        "ans": str(repo.resolve())}
    assert (local / ".gitignore").read_text(encoding="utf-8") == "*\n"
    # La ruta de una máquina no entra en ninguna nota.
    for nota in raiz.rglob("*.md"):
        assert str(repo) not in nota.read_text(encoding="utf-8"), nota
    r = _ejecutar(raiz, "--link", "ans", "--path", str(repo))
    assert r["ok"] and r["written"] == 0, r


def test_link_a_un_directorio_inexistente_es_invalid_path(raiz, tmp_path):
    _ejecutar(raiz, "--add", "ans")
    r = _ejecutar(raiz, "--link", "ans", "--path", str(tmp_path / "no-existe"))
    assert not r["ok"] and r["error_code"] == "INVALID_PATH", r


def test_rebuild_deriva_el_registro(raiz):
    _ejecutar(raiz, "--add", "ans", "--alias", "ans-api")
    r = _ejecutar(raiz, "--rebuild")
    assert r["ok"] and r["projects_total"] == 1 and r["written"] == 1, r
    datos = json.loads((raiz / "00_System" / "project-registry.json").read_text(encoding="utf-8"))
    assert [p["slug"] for p in datos["projects"]] == ["ans"]
    assert datos["projects"][0]["aliases"] == ["ans-api"]


def test_ap63_audit_nombra_fantasmas_y_claves_no_canonicas(raiz):
    _ejecutar(raiz, "--add", "ans")
    k = raiz / "07_Knowledge"
    (k / "a.md").write_text("---\ntype: concept\nproject: ANS\n---\nx\n", encoding="utf-8")
    (k / "b.md").write_text("---\ntype: concept\nproject: mi-api\n---\nx\n", encoding="utf-8")
    (k / "c.md").write_text("---\ntype: concept\nPROJECT: ans\n---\nx\n", encoding="utf-8")
    r = _ejecutar(raiz, "--audit")
    assert r["ok"] and r["norm"] == "AP-63", r
    assert [(f["project"], f["kind"]) for f in r["phantoms"]] == [("mi-api", "no_registrado")]
    assert r["non_canonical_keys"] == [{"note": "07_Knowledge/c.md", "key": "PROJECT"}]


def test_las_acciones_son_excluyentes(raiz):
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_project.py"), "--list", "--audit"],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS),
    )
    assert proceso.returncode != 0

"""`vault_arquitectura_en` — la arquitectura de un proyecto vista en una fecha o versión.

Pedido el 2026-10-07: viajar en el tiempo como en Google Maps, pero sobre la
arquitectura. El caso de estos tests es el del pedido: en la v1.0 el proyecto
decidía un monolito; entre medias se propone clean architecture, se aprueba y
sustituye al monolito; la v1.5 sale con ella. Se ejecuta por subprocess con
`VAULT_ROOT` y `VAULT_STRICT_ROOT=1`, como la ve un consumidor.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CLEAN = "05_Patterns/architecture/clean.md"
MONOLITO = "03_Decisions/adr-monolito.md"


def _ejecutar(raiz: Path, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_arquitectura_en.py"), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=300,
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


def _nota(raiz: Path, rel: str, fm: str, cuerpo: str = "\n# Nota\n") -> Path:
    p = raiz / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(f"---\n{fm}\n---\n{cuerpo}".encode("utf-8"))
    return p


def _release(raiz: Path, version: str, fecha: str) -> None:
    _nota(raiz, f"08_Runbooks/deploy/demo-release-{version}.md",
          f"title: Release {version}\nproject: demo\nversion: {version}\n"
          f"deploy_at: '{fecha}T12:00:00Z'\ncreatedAt: '{fecha}T12:00:00Z'\nstatus: implemented")


def _paths(grupo):
    return [e["path"] for e in grupo]


@pytest.fixture
def raiz(tmp_path):
    raiz = tmp_path / "vault"
    for s in ("00_System", "01_Projects/demo", "03_Decisions", "05_Patterns/architecture", "07_Knowledge",
              "08_Runbooks/deploy", ".history"):
        (raiz / s).mkdir(parents=True)
    _release(raiz, "v1.0", "2026-01-10")
    _release(raiz, "v1.5", "2026-03-15")
    _nota(raiz, MONOLITO, "title: Monolito\ntype: adr\nproject: demo\nstatus: approved\n"
          "createdAt: '2026-01-05T09:00:00Z'\nsuperseded_by: '[[clean]]'")
    _nota(raiz, CLEAN, "title: Clean architecture\ntype: architecture\nproject: demo\n"
          "status: approved\ncreatedAt: '2026-02-01T09:00:00Z'\n"
          "files:\n  - src/domain/\n  - src/adapters/")
    # Antes de aprobarse, el 2026-03-01, era una propuesta: vault_undo guarda la
    # versión tapada con la fecha en el nombre.
    _nota(raiz, ".history/05_Patterns__architecture__clean-2026-03-01T10-00-00.md",
          "title: Clean architecture (propuesta)\ntype: architecture\nproject: demo\n"
          "status: draft\ncreatedAt: '2026-02-01T09:00:00Z'\nfiles:\n  - src/domain/")
    _nota(raiz, "05_Patterns/architecture/primer.md", "title: Primer\ntype: primer\n"
          "createdAt: '2026-01-01T00:00:00Z'")
    _nota(raiz, "07_Knowledge/jwt.md", "title: JWT\ntype: concept\nproject: demo\n"
          "createdAt: '2026-01-01T00:00:00Z'")
    return raiz


def test_en_la_v1_0_regia_el_monolito(raiz):
    r = _ejecutar(raiz, "--version", "v1.0", "--project", "demo")
    assert r["ok"], r
    assert r["punto"]["release"] == "08_Runbooks/deploy/demo-release-v1.0.md"
    assert _paths(r["vigentes"]) == [MONOLITO]
    assert not r["propuestas"] and not r["retiradas"]


def test_entre_versiones_la_propuesta_se_lee_de_su_version_guardada(raiz):
    r = _ejecutar(raiz, "--fecha", "2026-02-15")
    assert r["ok"], r
    (clean,) = r["propuestas"]
    assert clean["path"] == CLEAN
    assert clean["fuente"] == ".history/05_Patterns__architecture__clean-2026-03-01T10-00-00.md"
    assert clean["title"] == "Clean architecture (propuesta)"
    assert clean["files"] == ["src/domain/"]
    # La sustituta ya existía: el monolito estaba retirado, aunque la anotación
    # se escribió sin dejar versión.
    (monolito,) = r["retiradas"]
    assert monolito["path"] == MONOLITO and monolito["motivo"] == "sustituida"
    assert monolito["sustituida_por"] == CLEAN


def test_en_la_v1_5_rige_clean_con_sus_ficheros(raiz):
    r = _ejecutar(raiz, "--version", "v1.5", "--project", "demo")
    (clean,) = r["vigentes"]
    assert clean["fuente"] == "actual" and clean["status"] == "approved"
    assert clean["files"] == ["src/domain/", "src/adapters/"]


def test_el_rango_cuenta_la_historia(raiz):
    r = _ejecutar(raiz, "--desde", "v1.0", "--hasta", "v1.5", "--project", "demo")
    assert r["ok"], r
    assert _paths(r["entraron"]) == [CLEAN]
    assert [(e["path"], e["motivo"]) for e in r["salieron"]] == [(MONOLITO, "sustituida")]
    eventos = [(e["evento"], e["path"]) for e in r["eventos"]]
    assert eventos == [("creada", CLEAN), ("reescrita", CLEAN),
                       ("release", "08_Runbooks/deploy/demo-release-v1.5.md")]


def test_vigente_desde_manda_sobre_la_fecha(raiz):
    """Una nota escrita antes de la v1.0 pero que declara regir desde la 1.5."""
    _nota(raiz, "03_Decisions/adr-eventos.md", "title: Eventos\ntype: adr\nproject: demo\n"
          "status: approved\ncreatedAt: '2026-01-02T00:00:00Z'\nvigente_desde: v1.5")
    assert "03_Decisions/adr-eventos.md" not in _paths(
        _ejecutar(raiz, "--version", "v1.0", "--project", "demo")["vigentes"])
    assert "03_Decisions/adr-eventos.md" in _paths(
        _ejecutar(raiz, "--version", "1.5", "--project", "demo")["vigentes"])


def test_sin_release_ni_vigente_desde_la_version_no_se_inventa(raiz):
    r = _ejecutar(raiz, "--version", "v2.0", "--project", "demo")
    assert r["ok"] is False and r["error_code"] == "VERSION_NOT_FOUND"


def test_una_nota_sin_fecha_es_indeterminada_no_vigente(raiz):
    _nota(raiz, "03_Decisions/adr-sin-fecha.md", "title: Sin fecha\ntype: adr\nstatus: approved")
    r = _ejecutar(raiz, "--fecha", "2026-02-15")
    (indet,) = [e for e in r["indeterminadas"] if e["path"] == "03_Decisions/adr-sin-fecha.md"]
    assert indet["motivo"] == "sin createdAt"


def test_primers_y_notas_que_no_son_de_arquitectura_no_cuentan(raiz):
    r = _ejecutar(raiz, "--fecha", "2026-12-31")
    todas = [e["path"] for k in ("vigentes", "propuestas", "retiradas", "indeterminadas")
             for e in r[k]]
    assert "05_Patterns/architecture/primer.md" not in todas
    assert "07_Knowledge/jwt.md" not in todas
    assert "architecture" in r["criterio"]["tipos"] and "primer" not in r["criterio"]["tipos"]


@pytest.mark.parametrize("argv,codigo", [
    ((), "MISSING_REQUIRED_ARG"),
    (("--fecha", "2026-02-15", "--version", "v1.0"), "MISSING_REQUIRED_ARG"),
    (("--desde", "v1.0"), "MISSING_REQUIRED_ARG"),
    (("--fecha", "2026-02-30"), "INVALID_VALUE"),
    (("--fecha", "ayer"), "INVALID_VALUE"),
])
def test_entradas_invalidas(raiz, argv, codigo):
    r = _ejecutar(raiz, *argv)
    assert r["ok"] is False and r["error_code"] == codigo, r


def test_ap63_el_proyecto_se_resuelve_antes_de_filtrar(raiz):
    """Un nombre que no es proyecto no devuelve una arquitectura vacía con
    ok: true: falla como en toda tool con --project."""
    r = _ejecutar(raiz, "--fecha", "2026-02-15", "--project", "demoo")
    assert r["ok"] is False and r["error_code"] == "PROJECT_NOT_FOUND", r
    assert _ejecutar(raiz, "--fecha", "2026-02-15", "--project", "Demo")["project"] == "demo"


def test_es_solo_lectura(raiz):
    def huella():
        return {p.relative_to(raiz).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in raiz.rglob("*") if p.is_file()}
    antes = huella()
    _ejecutar(raiz, "--desde", "2026-01-01", "--hasta", "2026-12-31")
    assert huella() == antes


def test_un_error_solo_toca_la_traza(raiz):
    """Regla 7 contra /ans: un `VERSION_NOT_FOUND` cambió la huella de la copia. Lo
    único que escribe es la traza de `emit_error`; ninguna nota."""
    def huella():
        return {p.relative_to(raiz).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in raiz.rglob("*") if p.is_file()}
    antes = huella()
    assert _ejecutar(raiz, "--version", "v9.9")["error_code"] == "VERSION_NOT_FOUND"
    despues = huella()
    cambiados = {k for k in antes.keys() | despues.keys() if antes.get(k) != despues.get(k)}
    assert cambiados <= {"00_System/.tool-trace.json"}, cambiados

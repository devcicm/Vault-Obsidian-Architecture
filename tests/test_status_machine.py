"""AP-41 — la máquina de estados se recorre, no solo se dibuja.

`STATUS_TRANSITIONS` existía desde v38, bien formada y con tests que verificaban
que el grafo era correcto. Nadie lo recorría: su único consumidor era ese test.
Un estado que no controla su transición es una etiqueta.

Los tests de identidad que acompañan a la norma no son colaterales: para poder
comprobar una transición hay que leer el frontmatter previo, y ese camino de
lectura estaba en la rama equivocada del `if` — cada actualización acuñaba un
`id` nuevo y reseteaba `createdAt`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from vault_lib import canonical_utc, parse_frontmatter_with_body  # noqa: E402
from vault_norms import (  # noqa: E402
    NORM_CATALOG,
    STATUS_TRANSITIONS,
    vault_norms_audit,
)

CUERPO = (
    "## Contexto\nUna nota con tres lineas reales de contenido suficiente.\n\n"
    "## Detalle\nSuficiente para pasar el guard AP-11 sin problemas de longitud.\n\n"
    "## Cierre\nFin del documento de prueba de transiciones.\n"
)


# ── El guard, contra el vault de pruebas ─────────────────────────────────────

def _escribir(vault: Path, titulo: str, status=None, tags="test"):
    cmd = [
        sys.executable, str(SCRIPTS / "vault_write.py"),
        "--folder", "07_Knowledge", "--title", titulo,
        "--tags", tags, "--content", CUERPO,
    ]
    if status:
        cmd += ["--meta", json.dumps({"status": status})]
    # Entorno heredado: un env mínimo deja al subproceso sin encontrar PyYAML,
    # y el fallo se disfraza de UNEXPECTED_ERROR en la rama de actualización.
    env = dict(os.environ)
    env.update({
        "VAULT_ROOT": str(vault),
        "VAULT_AGENT": "pytest-ap41",
        "PYTHONIOENCODING": "utf-8",
    })
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8")
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault-ap41"
    for sec in ("00_System", "07_Knowledge", "99_Index", ".history"):
        (root / sec).mkdir(parents=True)
    return root


def test_una_transicion_ilegal_se_rechaza(vault):
    assert _escribir(vault, "Nota", "draft")["ok"]
    r = _escribir(vault, "Nota", "verified")
    assert not r["ok"]
    assert r["error_code"] == "illegal_status_transition"
    assert r["norm_code"] == "AP-41"
    assert r["from_status"] == "draft" and r["to_status"] == "verified"
    assert "reviewed" in r["allowed"], "el mensaje dice a dónde sí se puede ir"


def test_una_transicion_legal_pasa_y_se_reporta(vault):
    _escribir(vault, "Nota", "draft")
    r = _escribir(vault, "Nota", "reviewed")
    assert r["ok"]
    assert r["status_transition"] == "draft -> reviewed"


def test_un_estado_terminal_no_admite_salida(vault):
    _escribir(vault, "Nota", "draft")
    _escribir(vault, "Nota", "archived")
    r = _escribir(vault, "Nota", "draft")
    assert not r["ok"] and r["error_code"] == "illegal_status_transition"
    assert r["allowed"] == [], "'archived' es terminal en la máquina"


def test_actualizar_sin_status_no_degrada_la_nota(vault):
    """Tocar una nota revisada para corregir una frase la dejaba en 'draft'."""
    _escribir(vault, "Nota", "draft")
    _escribir(vault, "Nota", "reviewed")
    assert _escribir(vault, "Nota")["ok"]
    fm, _ = parse_frontmatter_with_body(
        (vault / "07_Knowledge" / "Nota.md").read_text(encoding="utf-8")
    )
    assert fm["status"] == "reviewed"


def test_repetir_el_mismo_status_no_es_una_transicion(vault):
    _escribir(vault, "Nota", "draft")
    r = _escribir(vault, "Nota", "draft")
    assert r["ok"] and "status_transition" not in r


# ── Identidad de la nota: el camino de lectura que estaba muerto ─────────────

def test_el_id_sobrevive_a_la_actualizacion(vault):
    primero = _escribir(vault, "Nota", "draft")
    segundo = _escribir(vault, "Nota", "in-progress")
    assert segundo["id"] == primero["id"], "cada update acuñaba un id nuevo"
    assert segundo["created"] is False


def test_el_id_devuelto_es_el_id_del_archivo(vault):
    r = _escribir(vault, "Nota", "draft")
    fm, _ = parse_frontmatter_with_body(
        (vault / "07_Knowledge" / "Nota.md").read_text(encoding="utf-8")
    )
    assert fm["id"] == r["id"], "eran dos uuid4 distintos: el devuelto no existía"


def test_created_at_no_se_resetea_ni_cambia_de_forma(vault):
    _escribir(vault, "Nota", "draft")
    nota = vault / "07_Knowledge" / "Nota.md"
    original = parse_frontmatter_with_body(nota.read_text(encoding="utf-8"))[0]["createdAt"]
    for _ in range(3):
        _escribir(vault, "Nota")
    final = parse_frontmatter_with_body(nota.read_text(encoding="utf-8"))[0]["createdAt"]
    assert final == original


# ── canonical_utc: leer y reescribir tiene que ser idempotente ──────────────

@pytest.mark.parametrize(
    "entrada",
    [
        "2026-07-30T07:42:40.000Z",
        "2026-07-30T07:42:40+00:00",
        "2026-07-30T07:42:40Z",
    ],
)
def test_canonical_utc_lleva_todo_a_la_forma_que_se_escribe(entrada):
    assert canonical_utc(entrada) == "2026-07-30T07:42:40.000Z"


def test_canonical_utc_es_idempotente():
    una = canonical_utc("2026-07-30T07:42:40+00:00")
    assert canonical_utc(una) == una


def test_canonical_utc_no_inventa_lo_que_no_entiende():
    assert canonical_utc("ayer por la tarde") == "ayer por la tarde"
    assert canonical_utc("") == ""
    assert canonical_utc(None) == ""


# ── El audit sobre lo ya ocurrido ────────────────────────────────────────────

def _vault_auditable(tmp_path: Path) -> Path:
    root = tmp_path / "vault-hist"
    for sec in ("00_System", "01_Projects", "99_Index"):
        (root / sec).mkdir(parents=True)
    (root / "01_Projects" / "index.md").write_text(
        "---\ntitle: idx\n---\n# idx\n", encoding="utf-8"
    )
    (root / "01_Projects" / "n.md").write_text(
        "---\ntitle: N\nstatus: draft\n---\n# N\nx\n", encoding="utf-8"
    )
    (root / ".history").mkdir()
    return root


def _version(root: Path, ts: str, status: str):
    (root / ".history" / f"01_Projects__n-{ts}.md").write_text(
        f"---\ntitle: N\nstatus: {status}\n---\n# N\nx\n", encoding="utf-8"
    )


def test_el_audit_reporta_la_transicion_ilegal_del_historial(tmp_path):
    root = _vault_auditable(tmp_path)
    _version(root, "2026-07-01T10-00-00", "archived")
    _version(root, "2026-07-02T10-00-00", "draft")   # archived es terminal
    r = vault_norms_audit(root)
    assert "AP-41" in r["by_norm"]
    detalle = next(v for v in r["violations"] if v["norm"] == "AP-41")
    assert detalle["path"] == "01_Projects/n.md"
    assert "archived" in detalle["detail"] and "draft" in detalle["detail"]


def test_el_audit_no_inventa_violaciones_en_un_historial_legal(tmp_path):
    root = _vault_auditable(tmp_path)
    _version(root, "2026-07-01T10-00-00", "draft")
    _version(root, "2026-07-02T10-00-00", "in-progress")
    _version(root, "2026-07-03T10-00-00", "reviewed")
    assert "AP-41" not in vault_norms_audit(root)["by_norm"]


def test_el_audit_ordena_por_marca_de_tiempo_no_por_nombre(tmp_path):
    """Si leyera en orden de directorio, la secuencia sería la contraria."""
    root = _vault_auditable(tmp_path)
    _version(root, "2026-07-09T10-00-00", "in-progress")
    _version(root, "2026-07-10T10-00-00", "reviewed")
    assert "AP-41" not in vault_norms_audit(root)["by_norm"]


def test_un_estado_no_canonico_del_historial_no_rompe_el_audit(tmp_path):
    """La deuda de vocabulario la reportan CN-03/AP-38, no esta norma."""
    root = _vault_auditable(tmp_path)
    _version(root, "2026-07-01T10-00-00", "implementado")
    _version(root, "2026-07-02T10-00-00", "draft")
    r = vault_norms_audit(root)
    assert r["ok"] is not None  # no revienta


# ── La norma existe y tiene un consumidor real ───────────────────────────────

def test_ap41_esta_en_el_catalogo_con_enforcement_real():
    norma = next((n for n in NORM_CATALOG if n["code"] == "AP-41"), None)
    assert norma is not None
    assert norma["enforcement"] == "guard+audit"
    assert "vault_write" in norma["tools_enforcing"]


def test_la_maquina_tiene_un_consumidor_fuera_de_los_tests():
    """Lo que falló durante una versión entera: la tabla existía y solo la leía
    su propio test. Si esta importación desaparece, la norma vuelve a ser prosa."""
    fuente = (SCRIPTS / "vault_write.py").read_text(encoding="utf-8")
    assert "STATUS_TRANSITIONS" in fuente


def test_el_frontmatter_previo_se_lee_donde_la_nota_existe():
    """El defecto original: la extracción vivía en la rama del `else`."""
    codigo = (SCRIPTS / "vault_write.py").read_text(encoding="utf-8")
    assert "existing_status = str(fm_previo.get" in codigo
    assert "parse_frontmatter_with_body(existing_content)" in codigo


def test_todo_estado_del_vocabulario_tiene_transiciones_declaradas():
    for estado in STATUS_TRANSITIONS:
        assert isinstance(STATUS_TRANSITIONS[estado], set)

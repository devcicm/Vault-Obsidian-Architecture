"""AP-53 — el changelog del manifiesto, contrastado contra git.

Lo que este módulo protege no es el formato del changelog: es que nadie pueda
volver a afirmar a mano un hecho del historial sin que git lo desmienta. La
primera pasada encontró 55 entradas, 31 con hash real, los 31 existentes y
**5 fechas que contradecían al commit que citaban** — cuatro por un día, la de
v39.0 por once.

El riesgo específico de un guard como este es salir verde por no mirar: si el
patrón deja de reconocer las entradas, `problems` queda vacío y la puerta pasa.
Por eso el primer test es que el barrido encuentra algo, y varios de los
siguientes comprueban el guard contra un changelog fabricado en vez de contra el
real, que está —y debe estar— limpio.
"""

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_changelog_check as C  # noqa: E402


# ── El barrido ve algo ───────────────────────────────────────────────────────


def test_el_barrido_reconoce_las_entradas_del_manifiesto():
    """Sin esto, todo lo demás pasaría por no mirar (AP-44)."""
    todas = C.entradas()
    assert len(todas) > 40, f"solo {len(todas)} entradas reconocidas"
    con_hash = [e for e in todas if e["hash"] not in C.NO_HASH]
    assert len(con_hash) > 25, "casi ninguna entrada trae hash: ¿cambió el formato?"


def test_el_separador_es_una_raya_larga():
    """El formato usa `—`, no `-`. Confundirlos deja el guard ciego."""
    assert C.RE_ENTRADA.findall("### v1.0 — 2026-01-01 `git: abc1234`")
    assert not C.RE_ENTRADA.findall("### v1.0 - 2026-01-01 `git: abc1234`")


# ── El veredicto sobre el manifiesto real ────────────────────────────────────


def test_el_changelog_no_contradice_a_git():
    """La puerta. Cero problemas, no «cero conocidos»."""
    r = C.comprobar()
    assert r["ok"], r["problems"]


def test_todos_los_hashes_publicados_existen():
    """Comprobación separada: un hash inventado es peor que una fecha torcida."""
    if not C.hay_git():
        pytest.skip("sin repositorio git")
    inexistentes = [
        e["version"] for e in C.entradas()
        if e["hash"] not in C.NO_HASH
        and C._git("cat-file", "-t", e["hash"]) != "commit"
    ]
    assert not inexistentes, f"versiones con hash inexistente: {inexistentes}"


def test_la_baseline_esta_vacia():
    """Las cinco divergencias se corrigieron; no se anotaron.

    Si esto empieza a fallar, alguien anotó una divergencia en vez de
    corregirla. Puede estar justificado —un commit que dejó de existir— pero
    debe ser una decisión visible, no el camino de menor resistencia.
    """
    assert C._cargar_baseline() == {}, (
        "la baseline dejó de estar vacía: revisa por qué no se pudo corregir"
    )


# ── El guard detecta lo que dice detectar ────────────────────────────────────


def _fabricar(monkeypatch, cuerpo):
    """Sustituye el changelog leído por uno de prueba."""
    monkeypatch.setattr(C, "_changelog", lambda texto=None: cuerpo)


def test_detecta_un_pending_de_una_version_ya_cerrada(monkeypatch):
    _fabricar(monkeypatch, """## Changelog

### v9.1 — 2026-01-02 `git: pending`
### v9.0 — 2026-01-01 `git: pending`
""")
    r = C.comprobar(version_en_curso="v9.1")
    sin_fijar = [p["version"] for p in r["problems"]
                 if p["problema"] == "hash_sin_fijar"]
    assert sin_fijar == ["v9.0"], r["problems"]
    assert not r["ok"]


def test_la_version_en_curso_puede_llevar_pending(monkeypatch):
    """Su commit no existe todavía: exigirle un hash sería imposible."""
    _fabricar(monkeypatch, """## Changelog

### v9.1 — 2026-01-02 `git: pending`
""")
    assert C.comprobar(version_en_curso="v9.1")["ok"]


def test_detecta_un_hash_inexistente(monkeypatch):
    if not C.hay_git():
        pytest.skip("sin repositorio git")
    _fabricar(monkeypatch, """## Changelog

### v9.0 — 2026-01-01 `git: 0000000`
""")
    r = C.comprobar(version_en_curso="v9.0")
    assert [p["problema"] for p in r["problems"]] == ["hash_inexistente"]


def test_detecta_una_fecha_que_contradice_al_commit(monkeypatch):
    """El defecto original: v39.0 con once días de adelanto."""
    if not C.hay_git():
        pytest.skip("sin repositorio git")
    head = C._git("rev-parse", "--short", "HEAD")
    _fabricar(monkeypatch, f"""## Changelog

### v9.0 — 1999-01-01 `git: {head}`
""")
    r = C.comprobar(version_en_curso="v9.0")
    assert [p["problema"] for p in r["problems"]] == ["fecha_divergente"]
    assert "1999-01-01" in r["problems"][0]["detalle"]


def test_detecta_el_changelog_fuera_de_orden(monkeypatch):
    """Una entrada de v27 estuvo intercalada entre v37 y v34.3."""
    _fabricar(monkeypatch, """## Changelog

### v9.0 — 2026-01-01 `git: —`
### v9.2 — 2026-01-02 `git: —`
""")
    r = C.comprobar(version_en_curso="v9.2")
    assert [p["problema"] for p in r["problems"]] == ["fuera_de_orden"]


def test_las_entradas_sin_hash_no_se_inventan_un_problema(monkeypatch):
    """`git: —` es el histórico anterior a git, no una omisión."""
    _fabricar(monkeypatch, """## Changelog

### v2 — 2026-01-02 `git: —`
### v1 — 2026-01-01 `git: —`
""")
    r = C.comprobar(version_en_curso="v2")
    assert r["ok"] and r["entries_with_hash"] == 0


def test_un_manifiesto_sin_changelog_no_sale_verde(monkeypatch):
    """El modo de fallo que mata a un guard: `problems: []` por no ver nada.

    Regla 7 — dos copias archivadas del manifiesto en el vault /ans (ajeno a
    este repo) no conservan la sección de changelog. Ahí un guard que solo
    contara problemas habría dicho «ok» sobre un fichero que ni siquiera supo
    leer. Devuelve `PARSE_FAILED`, que es un veredicto distinto de «limpio».
    """
    _fabricar(monkeypatch, "# manifiesto sin changelog\n")
    r = C.comprobar(version_en_curso="v9.0")
    assert not r["ok"]
    assert r["error_code"] == "PARSE_FAILED"
    assert r["recovery"], "un error sin recuperación no le sirve a nadie"


def test_el_envelope_de_error_no_finge_ser_un_informe(monkeypatch):
    """Y el informe no finge ser un error.

    Las dos formas son disjuntas a propósito: `problems` solo existe cuando
    hubo un barrido de verdad. El consumidor decide por `ok` + `error_code`,
    no adivinando qué claves vinieron. Un test que pedía `r["problems"]` a
    secas reventaba con KeyError sobre estas copias.
    """
    _fabricar(monkeypatch, "# vacío\n")
    assert "problems" not in C.comprobar(version_en_curso="v9.0")

    _fabricar(monkeypatch, "## Changelog\n\n### v9.0 — 2026-01-01 `git: —`\n")
    limpio = C.comprobar(version_en_curso="v9.0")
    assert limpio["ok"] and limpio["problems"] == []
    assert "error_code" not in limpio


# ── La fecha se toma de autoría, no de commit ────────────────────────────────


def test_usa_la_fecha_de_autoria():
    """`%cs` la reescribe un rebase; `%as` no.

    Si esto cambiase a `%cs`, reordenar el historial estrenaría divergencias
    en entradas que nadie tocó — y el arreglo sería anotarlas en la baseline,
    o sea normalizar la mentira.
    """
    fuente = (RAIZ / "scripts" / "vault_changelog_check.py").read_text(
        encoding="utf-8")
    assert "%as" in fuente
    assert '"--format=%cs"' not in fuente


# ── --fijar-hash ─────────────────────────────────────────────────────────────


def test_fijar_hash_no_escribe_en_dry_run(tmp_path, monkeypatch):
    """Y dice exactamente qué haría, incluido el mensaje de commit."""
    if not C.hay_git():
        pytest.skip("sin repositorio git")
    falso = tmp_path / "manifiesto.md"
    falso.write_text(
        "## Changelog\n\n### v99.9 — 1999-01-01 `git: pending`\n",
        encoding="utf-8",
    )
    antes = falso.read_text(encoding="utf-8")
    monkeypatch.setattr(C, "SPEC", falso)
    monkeypatch.setitem(sys.modules, "vault_standard_upgrade",
                        type(sys)("vault_standard_upgrade"))
    sys.modules["vault_standard_upgrade"].CURRENT_VERSION = "v99.9"

    r = C.fijar_hash(dry_run=True)
    assert r["ok"] and r["dry_run"]
    assert falso.read_text(encoding="utf-8") == antes, "escribió en dry-run"
    assert r["commit_message"].startswith("docs: fijar hash del changelog v99.9")
    # La fecha se corrige contra el commit: es el dato que se desincronizó.
    assert r["changes"]["date_corrected"] is True
    assert r["changes"]["date_after"] != "1999-01-01"


def test_fijar_hash_escribe_el_hash_y_la_fecha_reales(tmp_path, monkeypatch):
    if not C.hay_git():
        pytest.skip("sin repositorio git")
    falso = tmp_path / "manifiesto.md"
    falso.write_text(
        "## Changelog\n\n### v99.9 — 1999-01-01 `git: pending`\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(C, "SPEC", falso)
    monkeypatch.setitem(sys.modules, "vault_standard_upgrade",
                        type(sys)("vault_standard_upgrade"))
    sys.modules["vault_standard_upgrade"].CURRENT_VERSION = "v99.9"

    head = C._git("rev-parse", "--short", "HEAD")
    fecha = C._git("show", "-s", "--format=%as", "HEAD")
    r = C.fijar_hash()
    assert r["ok"]
    escrito = falso.read_text(encoding="utf-8")
    assert f"`git: {head}`" in escrito
    assert fecha in escrito
    assert "pending" not in escrito


def test_fijar_hash_no_inventa_nada_si_no_hay_pending(tmp_path, monkeypatch):
    falso = tmp_path / "manifiesto.md"
    falso.write_text(
        "## Changelog\n\n### v99.9 — 1999-01-01 `git: abc1234`\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(C, "SPEC", falso)
    monkeypatch.setitem(sys.modules, "vault_standard_upgrade",
                        type(sys)("vault_standard_upgrade"))
    sys.modules["vault_standard_upgrade"].CURRENT_VERSION = "v99.9"
    if not C.hay_git():
        pytest.skip("sin repositorio git")
    r = C.fijar_hash()
    assert not r["ok"] and r["error_code"] == "NOTHING_TO_FIX"
    assert "recovery" in r


def test_fijar_hash_rechaza_un_commit_que_no_existe(monkeypatch):
    if not C.hay_git():
        pytest.skip("sin repositorio git")
    r = C.fijar_hash("0000000")
    assert not r["ok"]


# ── La puerta y el registro ──────────────────────────────────────────────────


def test_la_puerta_esta_registrada():
    import vault_gate

    ids = [p["id"] for p in vault_gate.PUERTAS]
    assert "changelog" in ids, "la puerta no está en el registro PUERTAS"


def test_ap53_esta_en_el_catalogo_de_normas():
    import vault_norms

    norma = next((n for n in vault_norms.NORM_CATALOG
                  if n["code"] == "AP-53"), None)
    assert norma is not None, "AP-53 no está catalogada"
    assert norma["enforcement"] != "manual", "ninguna norma nueva puede ser manual"
    assert norma["tools_enforcing"], "una norma con guard declara su tool"


def test_la_tool_corre_por_cli():
    """El camino que corre la puerta, comprobado donde se ejecuta."""
    r = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "vault_changelog_check.py"),
         "--check", "--strict"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(RAIZ), timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr

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

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_changelog_check as C  # noqa: E402


# ── El barrido ve algo ───────────────────────────────────────────────────────

import vault_grafo_import as gi  # noqa: E402


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
    fuente = gi.codigo_de(RAIZ / "scripts" / "vault_changelog_check.py").read_text(
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
    monkeypatch.setattr(importlib.import_module("vault_version"),
                        "CURRENT_VERSION", "v99.9")

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
    monkeypatch.setattr(importlib.import_module("vault_version"),
                        "CURRENT_VERSION", "v99.9")

    head = C._git("rev-parse", "--short", "HEAD")
    fecha = C._git("show", "-s", "--format=%as", "HEAD")
    r = C.fijar_hash()
    assert r["ok"]
    escrito = falso.read_text(encoding="utf-8")
    assert f"`git: {head}`" in escrito
    assert fecha in escrito
    assert "pending" not in escrito


def test_fijar_hash_conserva_lf(tmp_path, monkeypatch):
    """Medido el 2026-10-05 al fijar v40.36: en Windows `write_text` dejaba el
    manifiesto entero en CRLF en la copia de trabajo de un repo con eol=lf."""
    if not C.hay_git():
        pytest.skip("sin repositorio git")
    falso = tmp_path / "manifiesto.md"
    falso.write_bytes(b"# M\n\n## Changelog\n\n### v99.9 \xe2\x80\x94 1999-01-01 `git: pending`\n\ntexto\n")
    monkeypatch.setattr(C, "SPEC", falso)
    monkeypatch.setitem(sys.modules, "vault_standard_upgrade",
                        type(sys)("vault_standard_upgrade"))
    monkeypatch.setattr(importlib.import_module("vault_version"),
                        "CURRENT_VERSION", "v99.9")
    assert C.fijar_hash()["ok"]
    assert b"\r\n" not in falso.read_bytes()


def test_fijar_hash_no_inventa_nada_si_no_hay_pending(tmp_path, monkeypatch):
    falso = tmp_path / "manifiesto.md"
    falso.write_text(
        "## Changelog\n\n### v99.9 — 1999-01-01 `git: abc1234`\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(C, "SPEC", falso)
    monkeypatch.setitem(sys.modules, "vault_standard_upgrade",
                        type(sys)("vault_standard_upgrade"))
    monkeypatch.setattr(importlib.import_module("vault_version"),
                        "CURRENT_VERSION", "v99.9")
    if not C.hay_git():
        pytest.skip("sin repositorio git")
    r = C.fijar_hash()
    # v41.22: sellar lo que ya está sellado es un no-op explícito, no un
    # error — la idempotencia del ritual de release. Lo que no puede pasar es
    # que se invente un hash: el manifiesto queda intacto.
    assert r["ok"] is True, r
    assert r.get("already_sealed") is True, r
    assert "v99.9" in r.get("detalle", ""), r
    assert falso.read_text(encoding="utf-8").count("abc1234") == 1, "no invento un hash"


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


# ── La baseline la lee y la escribe su dueño (AP-57) ─────────────────────────


def test_una_baseline_corrupta_no_se_lee_como_vacia(tmp_path, monkeypatch):
    """Hasta v40.36 un JSON roto devolvía `{}`: el fallo que `vault_baseline`
    existe para impedir (AP-51), escrito una novena vez aquí."""
    import vault_baseline
    roto = tmp_path / "changelog-baseline.json"
    roto.write_bytes(b"{ no es json")
    monkeypatch.setattr(C, "BASELINE", roto)
    with pytest.raises(vault_baseline.BaselineIlegible):
        C._cargar_baseline()


def test_congelar_conserva_lo_que_no_entiende_y_escribe_en_lf(tmp_path, monkeypatch):
    """Escribir a mano el JSON borraba las claves ajenas, como `objetivo`."""
    import json
    if not C.hay_git():
        pytest.skip("sin repositorio git")
    base = tmp_path / "changelog-baseline.json"
    base.write_bytes(json.dumps({
        "fechas_divergentes": {},
        "objetivo": {"tamano": 0, "fecha_limite": "2027-01-01",
                     "cadencia_dias": 30, "dueno": "changelog"},
    }).encode("utf-8"))
    monkeypatch.setattr(C, "BASELINE", base)
    r = C.congelar()
    assert r["ok"] is True, r
    crudo = base.read_bytes()
    assert b"\r\n" not in crudo
    datos = json.loads(crudo)
    assert datos["objetivo"]["dueno"] == "changelog"
    assert datos["fechas_divergentes"] == {}


def test_sellar_dos_veces_es_un_no_op(tmp_path, monkeypatch):
    """Sellar una version ya sellada no es un fallo: es idempotencia.

    El ritual de release ejecuta `--fijar-hash` en su segundo commit, con la
    version ya sellada. Antes eso devolvia un error (`NOTHING_TO_FIX`), y el
    ejemplo documentado de la tool —`--fijar-hash --dry-run`— quedaba
    roto la mitad de las veces: entre releases no hay nada pendiente (AP-42).

    El no-op dice explicitamente que version es y que no hay nada que hacer:
    callar tambien seria mentir, solo que de otra manera.
    """
    import json as _json

    import vault_changelog_check as cc

    manifiesto = tmp_path / "manifiesto.md"
    manifiesto.write_text(
        "## Changelog\n\n"
        "### v41.99 — 2026-10-22 `git: 0123456`\n\n"
        "una entrada ya sellada\n",
        encoding="utf-8")
    monkeypatch.setattr(cc, "SPEC", manifiesto)
    import vault_version
    monkeypatch.setattr(vault_version, "CURRENT_VERSION", "v41.99")
    monkeypatch.setattr(cc, "hay_git", lambda: True)
    def _git_falso(*a):
        if a[0] == "rev-parse":
            return "0123456"
        if a[0] == "cat-file":
            return "commit"
        return "2026-10-22"

    monkeypatch.setattr(cc, "_git", _git_falso)

    env = cc.fijar_hash(dry_run=True)
    assert env["ok"] is True, env
    assert env.get("already_sealed") is True, env
    assert "v41.99" in env.get("detalle", ""), env
    # y el manifiesto no se toca: sellar lo que ya esta sellado no escribe
    antes = manifiesto.read_text(encoding="utf-8")
    cc.fijar_hash()
    assert manifiesto.read_text(encoding="utf-8") == antes


def test_una_version_sin_entrada_en_el_changelog_sigue_siendo_error(tmp_path, monkeypatch):
    """El otro caso, que no se puede tapar con el no-op: la version en curso no
    tiene fila. Eso es deriva — se subio el numero sin escribir su entrada — y
    un error es lo que corresponde."""
    import vault_changelog_check as cc

    manifiesto = tmp_path / "manifiesto.md"
    manifiesto.write_text("## Changelog\n\n### v41.98 — 2026-10-22 `git: abc`\n",
                          encoding="utf-8")
    monkeypatch.setattr(cc, "SPEC", manifiesto)
    import vault_version
    monkeypatch.setattr(vault_version, "CURRENT_VERSION", "v41.99")
    monkeypatch.setattr(cc, "hay_git", lambda: True)
    def _git_falso(*a):
        if a[0] == "rev-parse":
            return "0123456"
        if a[0] == "cat-file":
            return "commit"
        return "2026-10-22"

    monkeypatch.setattr(cc, "_git", _git_falso)

    env = cc.fijar_hash(dry_run=True)
    assert env["ok"] is False, env
    assert env.get("error_code") == "NOTHING_TO_FIX", env


# ── Autoría != aprobación (H3 de la auditoría) ───────────────────────────────
#
# La fase v41.22 publicaba `aprobado_por` derivado del **autor** del commit
# (`git show -s --format=%an`). Eso presentaba identidad de autoría como si
# fuera evidencia de aprobación: un agente que genera un commit con la
# identidad del titular —aquí comparten acto local— aparecía como «aprobado»
# sin que nadie acreditara nada. Los cuatro conceptos se separan: AUTORÍA
# (git, `%an`) es procedencia; RESPONSABILIDAD (banner del manifiesto, ADR);
# APROBACIÓN (el registro canónico de aprobaciones, con binding
# versión↔commit↔alcance y evidencia); PUBLICACIÓN (el ritual de release).
# El registro vive en la raíz de docs del repo; la tool no lo escribe: solo
# lo lee, lo valida y clasifica. Sin registro, la aprobación es desconocida;
# con registro sin evidencia verificable, declarada; con negación explícita,
# denegada; con evidencia que se verifica, acreditada. Nada se infiere de
# quién hizo el commit.


def test_la_autoria_no_aparece_como_aprobacion():
    """Test A (y B a la vez): commit sin aprobación → autor identificado,
    aprobación no acreditada. El manifiesto real lo deja bien a la vista:
    el autor de todas las entradas es el titular del estándar, y aun así la
    aprobación de ninguna de ellas puede presumirse de ahí.
    """
    filas = C.listar()["entries"]
    con_hash = [f for f in filas if f["hash"] not in C.NO_HASH]
    assert len(con_hash) > 25, "el barrido no está mirando (AP-44)"
    for f in con_hash:
        assert f.get("commit_author"), (
            "la autoría debe seguir disponible: es procedencia legítima"
        )
        assert f["approval_status"] in ("desconocida", "denegada", "declarada"), (
            f"{f['version']} afirma aprobación sin registro que lo sostenga"
        )
        assert f["approved_by"] is None or f["approval_status"] == "acreditada"
        assert f["aprobado_por"] == f["approved_by"], (
            f"la clave compatible diverge de la nueva en {f['version']}"
        )


def test_una_aprobacion_con_evidencia_verificada_es_acreditada(monkeypatch):
    """Test C: registro con evidencia válida → aprobación verificable.

    La firma se simula porque el git de este repo no lleva ninguna firmada;
    el clasificador es lo que la tool posee.
    """
    registro = [{
        "version": "v9.1", "commit": "abc0000", "aprobante": "Mantenedor",
        "alcance": "release v9.1",
        "evidencia": [{"tipo": "firma_git", "firmante": "Mantenedor"}],
    }]
    monkeypatch.setattr(C, "_leer_aprobaciones", lambda: registro)
    monkeypatch.setattr(C, "_firma_de_hash", lambda h: (True, "Mantenedor"))
    assert C._estado_de_aprobacion("v9.1", "abc0000", registro) == "acreditada"
    assert C._problemas_de_aprobaciones(
        [{"version": "v9.1", "hash": "abc0000"}], registro) == []


def test_una_aprobacion_ligada_a_otro_commit_se_rechaza(monkeypatch):
    """Test D: la aprobación de otro commit no es reutilizable. El binding
    versión↔commit es parte del contrato: un registro cuyo commit no
    coincide con el de la entrada es un problema de la puerta, no un dato.
    """
    _fabricar(monkeypatch, """## Changelog

### v9.0 — 2026-01-01 `git: abc0000`
""")
    registro = [{
        "version": "v9.0", "commit": "fff1111", "aprobante": "Mantenedor",
        "alcance": "release v9.0", "evidencia": [],
    }]
    monkeypatch.setattr(C, "_leer_aprobaciones", lambda: registro)
    problemas = C._problemas_de_aprobaciones(C.entradas(), registro)
    assert any(p["problema"] == "aprobacion_desviada" for p in problemas), problemas

    r = C.comprobar(version_en_curso="v9.0")
    assert not r["ok"]
    assert any(p["problema"] == "aprobacion_desviada" for p in r["problems"]), (
        r["problems"]
    )


def test_evidencia_no_verificada_no_acredita_y_no_confunde_con_negacion(monkeypatch):
    """Test E: evidencia ausente, inválida o no verificable → «no acreditada»,
    y la ausencia no se presenta como denegación (ni al revés).

    Con la firma que no se verifica (hoy no hay ninguna firmada), un
    registro con evidencia declarada queda `declarada`; sin registro,
    `desconocida`; con `no_aprobada` explícita, `denegada`. Y una firma que
    no es del aprobante no acredita al aprobante.
    """
    registro = [{
        "version": "v9.1", "commit": "abc0000", "aprobante": "Mantenedor",
        "alcance": "release v9.1",
        "evidencia": [{"tipo": "firma_git", "firmante": "Mantenedor"}],
    }]
    monkeypatch.setattr(C, "_leer_aprobaciones", lambda: registro)

    monkeypatch.setattr(C, "_firma_de_hash", lambda h: (False, None))
    assert C._estado_de_aprobacion("v9.1", "abc0000", registro) == "declarada"

    # la firma es de otro: acredita a otro, no al aprobante
    monkeypatch.setattr(C, "_firma_de_hash", lambda h: (True, "Alguien Más"))
    assert C._estado_de_aprobacion("v9.1", "abc0000", registro) == "declarada"

    sin_evidencia = [dict(registro[0], evidencia=[])]
    assert C._estado_de_aprobacion("v9.1", "abc0000", sin_evidencia) == "declarada"
    assert C._estado_de_aprobacion("v9.1", "abc0000", []) == "desconocida"
    assert C._estado_de_aprobacion("v9.9", "abc0000", registro) == "desconocida"

    denegada = [dict(registro[0], evidencia=[], no_aprobada=True)]
    assert C._estado_de_aprobacion("v9.1", "abc0000", denegada) == "denegada"


def test_el_contrato_de_listar_mantiene_aprobado_por(monkeypatch):
    """Test F: los consumidores de la clave `aprobado_por` siguen recibiendo
    la clave — ahora con la semántica del aprobante acreditado (o None), no
    con la del autor del commit.
    """
    primera = next(
        (e for e in C.entradas() if e["hash"] not in C.NO_HASH), None)
    if primera is None or not C.hay_git():
        pytest.skip("sin entradas con hash o sin repositorio git")
    registro = [{
        "version": primera["version"], "commit": primera["hash"],
        "aprobante": "Mantenedor", "alcance": f"release {primera['version']}",
        "evidencia": [{"tipo": "firma_git", "firmante": "Mantenedor"}],
    }]
    monkeypatch.setattr(C, "_leer_aprobaciones", lambda: registro)
    monkeypatch.setattr(C, "_firma_de_hash", lambda h: (True, "Mantenedor"))

    filas = {f["version"]: f for f in C.listar()["entries"]}
    acreditada = filas[primera["version"]]
    assert acreditada["approval_status"] == "acreditada"
    assert acreditada["approved_by"] == "Mantenedor"
    assert acreditada["aprobado_por"] == "Mantenedor"
    assert acreditada["commit_author"], "la autoría no se pierde por acreditada"

    # el resto del manifiesto no hereda la aprobación de la única acreditada
    otras = [f for v, f in filas.items() if v != primera["version"]]
    assert sum(1 for f in otras if f["approved_by"] is None) > 25, (
        "una acreditación se filtró a versiones que no la tienen (no es "
        "reutilizable ni propagable)"
    )


def test_el_registro_canonico_de_aprobaciones_es_valido():
    """El fichero del repo, tal como viaja hoy: JSON legible, esquema y
    registros completos. Un registro incompleto no es una opinión vacía, es
    evidencia corrupta.
    """
    aprobaciones = C._leer_aprobaciones()
    assert isinstance(aprobaciones, list)
    for a in aprobaciones:
        for campo in ("version", "commit", "aprobante", "alcance"):
            assert a.get(campo), f"registro incompleto en el registro: {a}"


def test_el_registro_corrupto_para_toda_la_gobernanza(monkeypatch):
    """AP-51 aplicado al registro nuevo: un JSON roto no se lee como vacío.

    «No hay aprobaciones» y «no sé qué hay aprobado» son cosas distintas, y
    la segunda está parada en la puerta ilegible (`registro_ilegible`), no
    en el verde que pasaría por silencio.
    """
    def _corrupto():
        raise ValueError("el registro de aprobaciones no se puede leer: roto")

    monkeypatch.setattr(C, "_leer_aprobaciones", _corrupto)

    r = C.comprobar(version_en_curso=None)
    assert not r["ok"]
    ilegibles = [p for p in r["problems"]
                 if p["problema"] == "registro_ilegible"]
    assert ilegibles, r["problems"]

    listado = C.listar()
    assert listado["ok"] is False
    assert any(p["problema"] == "registro_ilegible"
               for p in listado.get("problems", [])), listado.get("problems")

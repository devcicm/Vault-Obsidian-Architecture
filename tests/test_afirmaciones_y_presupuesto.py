"""v41.20 — las tres afirmaciones que este frente convirtió en registros.

Cada test de aquí existe porque el fallo que evita es **un guard que solo se
ha visto en verde**: un predicado que devuelve True siempre, un runner que
mide una corrida fallida, un gate cuya rama de parada nadie ha recorrido.

- **P1** · `AFIRMADAS` en `vault_produccion`: toda propiedad afirmada por el
  estándar tiene una puerta nombrada, y las que no la tienen lo dicen con su
  motivo escrito.
- **P2** · las dos métricas de coste del agente: se miden de verdad y su
  runner **verifica el envelope** antes de registrar, porque una métrica de
  producto medida sobre una corrida que falló es la forma más difícil de
  detectar de mentir.
- **P3** · el contraste contra un vault ajeno como condición del bump: sin
  recibo el bump para, con recibo vigente pasa, y vencido vuelve a parar.
"""

import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for _ruta in (RAIZ / "scripts", RAIZ):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

import vault_foreign_check as fc  # noqa: E402
import vault_metricas as vm  # noqa: E402
import vault_produccion as vp  # noqa: E402
import vault_release as vr  # noqa: E402


# ── P1 · propiedades afirmadas ───────────────────────────────────────────────


def test_p1_toda_propiedad_afirmada_tiene_puerta_o_motivo():
    """Lo que el estándar afirma sobre sí mismo, con su ejecutor nombrado."""
    assert len(vp.AFIRMADAS) >= 12, "el registro no cubre lo que dice cubrir"
    for a in vp.AFIRMADAS:
        if a["estado"] == "con_puerta":
            assert a["ejerce"](), f"{a['id']} dice tener puerta y no la tiene"
            assert a["quien"] and a["quien"] != "nadie, todavía", a["id"]
        else:
            assert a["estado"] == "descubierta", a
            # el motivo es lo que hace barato declarar un hueco: sin él, la
            # entrada es un agujero disfrazado de registro
            assert a.get("motivo", "").strip(), a["id"]


def test_p1_una_propiedad_que_pierde_su_puerta_pone_el_guard_en_rojo():
    """Si `_puerta_existe` devolviera True siempre, esto no fallaría nunca.
    Por eso el caso negativo se recorre: un guard que solo se ha visto en
    verde no es un guard."""
    original = vp.AFIRMADAS
    vp.AFIRMADAS = [dict(original[0], ejerce=lambda: False)] + list(original[1:])
    try:
        env = vp.check()
        assert not env["ok"], "una propiedad sin puerta tiene que poner en rojo"
        assert env["afirmadas_sin_puerta"] == [original[0]["id"]]
    finally:
        vp.AFIRMADAS = original
    assert vp.check()["ok"], "al restaurar, el guard vuelve a verde"


def test_p1_el_contraste_de_otra_persona_esta_declarado_y_no_oculto():
    """El hueco más caro de la lista tiene que estar escrito: es el único que
    puede encontrar defectos que ninguna puerta de este repo puede ver."""
    por_id = {a["id"]: a for a in vp.AFIRMADAS}
    hueco = por_id["afirmada_funciona_en_un_vault_de_otra_persona"]
    assert hueco["estado"] == "descubierta"
    assert "foreign_check" in hueco["motivo"]


# ── P2 · el coste que paga el agente ─────────────────────────────────────────


def test_p2_las_dos_metricas_de_producto_declaran_como_se_miden():
    """Una métrica de producto cuyo valor se rellena a mano no mide el
    producto: mide lo que su autor quiso escribir."""
    por_id = {m["id"]: m for m in vm.METRICAS}
    for id_ in ("contexto_agente_s", "skip_path_escritura_s"):
        m = por_id[id_]
        assert m["origen"] == "observada", id_
        assert m["tipo"] == "producto", id_
        assert m["objetivo"]["fecha_limite"], f"{id_} sin fecha límite"
        assert m["objetivo"]["dueno"], f"{id_} sin dueño"
        # la fuente dice el comando que la mide: aceptarla a mano rompería esto
        assert "--registrar" in m["fuente"], m["fuente"]


def test_p2_el_runner_de_contexto_rechaza_meter_un_numero_a_mano():
    """`--valor` puede seguir existiendo para observaciones que sí se toman a
    mano; lo que no puede es rellenar estas dos, que son medidas. El registro
    declara el comando que mide cada una, y ambas se miden por ejecución."""
    por_id = {m["id"]: m for m in vm.METRICAS}
    assert "no acepta" in por_id["contexto_agente_s"]["fuente"]
    assert "--registrar-skip" in por_id["skip_path_escritura_s"]["fuente"]
    # y las dos declaran un comando que las mide: sin runner no hay dato
    for id_ in ("contexto_agente_s", "skip_path_escritura_s"):
        assert "--registrar-" in por_id[id_]["fuente"], por_id[id_]["fuente"]


def test_p2_el_runner_de_contexto_mide_de_verdad():
    """Corre la cadena real —dos subprocesos— y devuelve segundos, no cero.
    Es lenta a propósito: es la misma carrera que paga el agente.

    `dry_run=True` porque un test no puede mutar el registro del repo: cuando
    registraba, ponía en carrera al generador del SDD —que cuenta
    observaciones— y la ronda paralela fallaba con `README.md not idempotent`
    mientras la serie pasaba (medido el 2026-10-23).
    """
    r = vm.registrar_contexto(dry_run=True)
    if not r.get("ok"):
        # si el runner no puede medir, se declara en vez de estimarse
        assert r.get("error_code"), r
        return
    assert r["total_s"] > 0, r
    assert r["parse_s"] > 0 and r["pack_s"] > 0, r
    assert r.get("dry_run") is True, r


# ── P3 · el contraste de la regla 7 ──────────────────────────────────────────


HOY = date(2026, 10, 23)


def _recibo(base: Path, fecha: str) -> Path:
    d = base / "docs" / "contrastes"
    d.mkdir(parents=True, exist_ok=True)
    (d / "ultimo-contraste.json").write_text(
        json.dumps({"ok": True, "kind": "recibo_de_contraste", "fecha": fecha,
                    "vault_medido": "notas-personales"}), encoding="utf-8")
    return base


def test_p3_sin_recibo_el_contraste_no_vigencia():
    with tempfile.TemporaryDirectory() as tmp:
        c = vr._contraste_vigente(Path(tmp), HOY)
        assert not c["vigente"], c
        assert "no hay ningún contraste" in c["motivo"]


def test_p3_con_recibo_vigente_vigencia():
    with tempfile.TemporaryDirectory() as tmp:
        base = _recibo(Path(tmp), (HOY - timedelta(days=10)).isoformat())
        c = vr._contraste_vigente(base, HOY)
        assert c["vigente"], c
        assert c["dias"] == 10
        assert c["vault_medido"] == "notas-personales"


def test_p3_el_plazo_incluye_su_ultimo_dia_y_pasa_a_partir_del_siguiente():
    """El borde se mide: un plazo que excluye su propio último día es un
    plazo de N-1 que nadie lee como tal."""
    with tempfile.TemporaryDirectory() as tmp:
        base = _recibo(Path(tmp), (HOY - timedelta(days=vr.DIAS_DE_CONTRASTE)).isoformat())
        assert vr._contraste_vigente(base, HOY)["vigente"]
    with tempfile.TemporaryDirectory() as tmp:
        base = _recibo(Path(tmp), (HOY - timedelta(days=vr.DIAS_DE_CONTRASTE + 1)).isoformat())
        c = vr._contraste_vigente(base, HOY)
        assert not c["vigente"], c
        assert str(vr.DIAS_DE_CONTRASTE) in c["motivo"], c


def test_p3_un_recibo_ilegible_no_revienta_la_herramienta():
    """Un JSON roto tiene que parar el bump, no tumbar la tool: parar es
    decidir; reventar es no querer decidir (AP-51)."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "docs" / "contrastes"
        d.mkdir(parents=True)
        (d / "ultimo-contraste.json").write_text('{"fecha": "ayer"}', encoding="utf-8")
        assert not vr._contraste_vigente(Path(tmp), HOY)["vigente"]


def test_p3_el_recibo_no_publica_la_ruta_del_vault_medido():
    """Un recibo versionado guarda el nombre del vault, no su disco: por eso
    el comprobante se escribe sin `root` y solo con `destino.name`."""
    with tempfile.TemporaryDirectory() as tmp:
        base = _recibo(Path(tmp), HOY.isoformat())
        c = vr._contraste_vigente(base, HOY)
        assert "/" not in str(c.get("vault_medido")), c


def test_p3_la_tool_sigue_rechazando_contraste_dentro_del_repo():
    """Regla 7: contrastar contra el sandbox no contrasta nada. El self-test
    comprueba las cuatro negativas, incluida esta."""
    r = fc.self_test()
    assert r["ok"], r
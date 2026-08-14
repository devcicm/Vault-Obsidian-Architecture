"""AP-55: las cinco medidas muerden, y el catálogo vivo pasa las cinco.

Cada test inyecta un catálogo sintético con **un solo defecto**, porque un guard
que solo se prueba contra el catálogo real no demuestra que detecte nada: si el
catálogo está limpio, un detector roto y un detector correcto dan el mismo cero.
Es la misma trampa que AP-55 describe, cometida en la suite en vez de en el guard.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_norms_coherence as coherencia  # noqa: E402


def _norma(**campos):
    base = {
        "code": "AP-99",
        "name": "sintética",
        "type": "antipattern",
        "category": "process",
        "severity": "high",
        "enforcement": "audit",
        "description": "d",
        "tools_enforcing": [],
        "tools_detecting": [],
    }
    base.update(campos)
    return base


def _con_catalogo(monkeypatch, normas):
    monkeypatch.setattr(coherencia, "_catalogo", lambda: normas)
    return coherencia.scan()


# ── C1 ────────────────────────────────────────────────────────────────────────


def test_c1_muerde_cuando_el_enforcer_no_resuelve(monkeypatch):
    r = _con_catalogo(monkeypatch, [
        _norma(tools_detecting=["vault_no_existe_en_absoluto"])])
    assert [p["value"] for p in r["unknown_tools"]] == ["vault_no_existe_en_absoluto"]


def test_c1_muerde_sobre_el_flag_pegado_a_la_tool(monkeypatch):
    """El defecto real: 54 entradas que mezclaban la tool con su flag.

    `vault_norms` existe; `vault_norms --audit` no es nada que un consumidor
    pueda resolver contra `mapa_de_grupos()`.
    """
    r = _con_catalogo(monkeypatch, [_norma(tools_detecting=["vault_norms --audit"])])
    assert [p["value"] for p in r["unknown_tools"]] == ["vault_norms --audit"]


def test_un_helper_que_existe_no_es_c1_pero_se_publica_aparte(monkeypatch):
    """`vault_io.atomic_write_text` no es una tool y sí es donde AP-46 se cumple."""
    r = _con_catalogo(monkeypatch, [
        _norma(code="AP-46", tools_enforcing=["vault_io.atomic_write_text"])])
    assert r["unknown_tools"] == []
    assert [p["value"] for p in r["non_catalog_enforcers"]] == [
        "vault_io.atomic_write_text"]


def test_un_simbolo_inventado_dentro_de_un_modulo_real_sigue_siendo_c1(monkeypatch):
    """Admitir helpers no puede degenerar en admitir cualquier cadena con punto."""
    r = _con_catalogo(monkeypatch, [
        _norma(tools_enforcing=["vault_io.esta_funcion_no_existe"])])
    assert [p["value"] for p in r["unknown_tools"]] == [
        "vault_io.esta_funcion_no_existe"]


# ── C2 ────────────────────────────────────────────────────────────────────────


def test_c2_muerde_cuando_el_modulo_no_nombra_la_norma(monkeypatch):
    """El caso que el guard de AP-43 no podía ver, por leer el catálogo."""
    r = _con_catalogo(monkeypatch, [
        _norma(code="AP-05", tools_detecting=["vault_graph_inspect"])])
    assert [c["claim"] for c in r["untraceable_claims"]] == [
        "AP-05::tools_detecting::vault_graph_inspect"]


def test_c2_calla_cuando_la_afirmacion_si_tiene_traza(monkeypatch):
    r = _con_catalogo(monkeypatch, [
        _norma(code="AP-55", tools_detecting=["vault_norms_coherence"])])
    assert r["untraceable_claims"] == []


# ── C3 ────────────────────────────────────────────────────────────────────────


def test_c3_prohibe_el_enforcement_manual(monkeypatch):
    """Regla 5: ninguna norma puede tener enforcement `manual`."""
    r = _con_catalogo(monkeypatch, [
        _norma(enforcement="manual", tools_detecting=["vault_audit"])])
    assert any("manual" in p["problem"] for p in r["enforcement_incoherent"])


def test_c3_muerde_cuando_guard_no_declara_quien_lo_aplica(monkeypatch):
    r = _con_catalogo(monkeypatch, [
        _norma(enforcement="guard", tools_enforcing=[])])
    assert r["enforcement_incoherent"]


def test_c3_calla_si_la_ausencia_de_detector_esta_declarada(monkeypatch):
    """La excepción de v40.11: un campo vacío CON motivo escrito no es C3.

    Es la única forma de retirar una cobertura falsa sin dejar la norma
    indistinguible de una a la que nadie miró.
    """
    r = _con_catalogo(monkeypatch, [
        _norma(enforcement="audit", tools_detecting=[],
               cobertura_descubierta="nadie la mide; el detector exigiría embeddings")])
    assert r["enforcement_incoherent"] == []


def test_c3_muerde_sobre_el_motivo_en_blanco(monkeypatch):
    """Un motivo vacío es un campo vacío con adorno, no una declaración."""
    r = _con_catalogo(monkeypatch, [
        _norma(enforcement="audit", tools_detecting=[], cobertura_descubierta="   ")])
    assert r["enforcement_incoherent"]


def test_c3_muerde_cuando_se_declara_descubierta_y_ademas_se_nombran_tools(monkeypatch):
    """La contradicción inversa: o no la mide nadie, o la mide alguien."""
    r = _con_catalogo(monkeypatch, [
        _norma(enforcement="audit", tools_detecting=["vault_audit"],
               cobertura_descubierta="no la mide nadie")])
    assert any("descubierta" in p["problem"] for p in r["enforcement_incoherent"])


def test_un_patron_declara_quien_lo_sigue_no_quien_lo_detecta(monkeypatch):
    """PAT-x es `recommended`: un patrón no se detecta, se sigue.

    Antes de v40.11 sus tools vivían en `tools_detecting`, y C2 les pedía traza
    a ocho afirmaciones que no afirmaban enforcement de nada — un error de
    categoría contado como deuda.
    """
    r = _con_catalogo(monkeypatch, [
        _norma(code="PAT-1", type="pattern", enforcement="recommended",
               tools_del_patron=["vault_graph_inspect"])])
    assert r["enforcement_incoherent"] == []
    assert r["untraceable_claims"] == [], "a un patrón no se le pide traza de norma"


def test_un_patron_sin_nadie_que_lo_siga_si_es_c3(monkeypatch):
    r = _con_catalogo(monkeypatch, [
        _norma(code="PAT-1", type="pattern", enforcement="recommended",
               tools_del_patron=[])])
    assert r["enforcement_incoherent"]


# ── C6 ────────────────────────────────────────────────────────────────────────


def test_c6_muerde_sobre_una_penalizacion_sin_norma_ni_motivo(monkeypatch):
    """El espejo de C2: código que pesa en el healthIndex sin afirmación detrás.

    C2 mide afirmaciones sin código. Sin C6 nadie medía la dirección contraria,
    y seis entradas de `PENALIZACIONES` llevaban `norma: None` desde v19.
    """
    monkeypatch.setattr(coherencia, "_penalizaciones_crudas", lambda: [
        {"id": "inventada", "familia": "estructura", "norma": None,
         "por_unidad": 1, "tope": 5}])
    r = coherencia.scan()
    assert [p["penalty"] for p in r["penalties_without_norm"]] == ["inventada"]


def test_c6_calla_cuando_la_metrica_declara_que_no_tiene_norma(monkeypatch):
    monkeypatch.setattr(coherencia, "_penalizaciones_crudas", lambda: [
        {"id": "orphans", "familia": "conectividad", "norma": None,
         "por_unidad": 2, "tope": 30,
         "metrica_sin_norma": "una nota sin enlaces entrantes no incumple nada"}])
    assert coherencia.scan()["penalties_without_norm"] == []


def test_c6_muerde_cuando_la_norma_citada_no_existe(monkeypatch):
    """Declarar una norma no basta: tiene que ser una del catálogo."""
    monkeypatch.setattr(coherencia, "_penalizaciones_crudas", lambda: [
        {"id": "x", "familia": "grafo", "norma": "AP-9999",
         "por_unidad": 1, "tope": 5}])
    assert coherencia.scan()["penalties_without_norm"]


def test_c6_no_tiene_baseline_y_nace_en_cero():
    """Sin baseline a propósito: una permitiría añadir una penalización sin
    decidir qué norma la sostiene, que es el vacío que la medida cierra."""
    assert coherencia.scan()["penalties_without_norm"] == []


# ── C4 ────────────────────────────────────────────────────────────────────────


def test_c4_muerde_sobre_la_inversion_real_de_ap22(monkeypatch):
    """El hallazgo, reconstruido: AP-22 `critical` pesando menos que AP-24 `high`.

    Se declara AP-22 como estaba antes de v40.10. Si C4 no lo reporta, la
    corrección del catálogo no está sostenida por nada y volvería a torcerse.
    """
    r = _con_catalogo(monkeypatch, [
        _norma(code="AP-22", severity="critical",
               tools_detecting=["vault_audit"]),
        _norma(code="AP-24", severity="high", tools_detecting=["vault_audit"]),
    ])
    pares = {tuple(sorted(p["norms"])) for p in r["severity_vs_penalty_inverted"]}
    assert ("AP-22", "AP-24") in pares


def test_c4_calla_sobre_el_catalogo_corregido(monkeypatch):
    """AP-22 en `medium` ya no contradice al código que la aplica."""
    r = _con_catalogo(monkeypatch, [
        _norma(code="AP-22", severity="medium", tools_detecting=["vault_audit"]),
        _norma(code="AP-24", severity="high", tools_detecting=["vault_audit"]),
    ])
    assert r["severity_vs_penalty_inverted"] == []


def test_c4_no_confunde_una_ponderacion_con_una_contradiccion(monkeypatch):
    """AP-14 pesa poco por unidad y mucho en total: invierte una medida, no las dos.

    Sin este estrechamiento el guard reportaba diez pares y no se leía, que es
    exactamente cómo AP-22 sobrevivió seis versiones.
    """
    r = _con_catalogo(monkeypatch, [
        _norma(code="AP-14", severity="critical", tools_detecting=["vault_audit"]),
        _norma(code="AP-24", severity="high", tools_detecting=["vault_audit"]),
    ])
    assert r["severity_vs_penalty_inverted"] == []


# ── C5 ────────────────────────────────────────────────────────────────────────


def test_c5_muerde_cuando_la_distincion_es_de_una_sola_parte(monkeypatch):
    """Quien llega leyendo B no ve la diferencia si solo la declara A."""
    r = _con_catalogo(monkeypatch, [
        _norma(code="AP-22", distinguido_de={"AP-24": "el link vacío"},
               tools_detecting=["vault_audit"]),
        _norma(code="AP-24", tools_detecting=["vault_audit"]),
    ])
    assert any(p["norm"] == "AP-22" for p in r["indistinguishable_norms"])


def test_c5_muerde_sobre_un_discriminador_vacio(monkeypatch):
    r = _con_catalogo(monkeypatch, [
        _norma(code="AP-22", distinguido_de={"AP-24": "   "},
               tools_detecting=["vault_audit"]),
        _norma(code="AP-24", distinguido_de={"AP-22": "el desbalance"},
               tools_detecting=["vault_audit"]),
    ])
    assert any("vacío" in p["problem"] for p in r["indistinguishable_norms"])


def test_c5_muerde_cuando_se_distingue_de_una_norma_inexistente(monkeypatch):
    r = _con_catalogo(monkeypatch, [
        _norma(distinguido_de={"AP-9999": "algo"}, tools_detecting=["vault_audit"])])
    assert r["indistinguishable_norms"]


def test_c5_calla_cuando_la_distincion_es_reciproca(monkeypatch):
    r = _con_catalogo(monkeypatch, [
        _norma(code="AP-22", distinguido_de={"AP-24": "el link vacío"},
               tools_detecting=["vault_audit"]),
        _norma(code="AP-24", distinguido_de={"AP-22": "el desbalance"},
               tools_detecting=["vault_audit"]),
    ])
    assert r["indistinguishable_norms"] == []


# ── El catálogo vivo y la baseline ────────────────────────────────────────────


def test_el_catalogo_vivo_pasa_las_cinco_medidas():
    r = coherencia.scan()
    assert r["unknown_tools"] == []
    assert r["enforcement_incoherent"] == []
    assert r["severity_vs_penalty_inverted"] == []
    assert r["indistinguishable_norms"] == []
    assert r["penalties_without_norm"] == []
    assert r["new_untraceable"] == [], (
        "afirmación de cobertura sin traza y sin precedente: se salda nombrando "
        "la norma donde se aplica o retirando la cobertura, no congelándola"
    )


def test_ap55_esta_en_el_catalogo_y_la_aplica_esta_tool():
    from vault_norms import NORM_CATALOG

    ap55 = next(n for n in NORM_CATALOG if n["code"] == "AP-55")
    assert ap55["enforcement"] == "guard+audit"
    assert "vault_norms_coherence" in ap55["tools_enforcing"]
    # AP-55 y AP-44 son parientes cercanos: la reciprocidad de C5 es lo que
    # obliga a que la diferencia esté escrita en las dos.
    assert "AP-44" in ap55["distinguido_de"]


def test_freeze_se_niega_a_congelar_deuda_sin_precedente(monkeypatch, tmp_path):
    """La operación peligrosa, con freno — igual que las otras tres baselines.

    Se apunta la baseline a un fichero vacío en `tmp_path` y se inyecta una
    afirmación sin traza: sin precedente, todo lo que hay es deuda nueva, y
    `--freeze` a secas tiene que negarse sin escribir nada.

    La afirmación se inyecta desde v40.11: el catálogo vivo quedó en cero, así
    que apuntar solo a una baseline vacía ya no producía deuda nueva y el test
    pasaba sin ejercitar la negativa — la trampa de siempre, esta vez en la
    suite.
    """
    destino = tmp_path / "baseline.json"
    monkeypatch.setattr(coherencia, "BASELINE", destino)
    monkeypatch.setattr(coherencia, "_catalogo", lambda: [
        _norma(code="AP-05", tools_detecting=["vault_graph_inspect"])])
    envelope = coherencia.freeze()
    assert envelope["ok"] is False
    assert envelope["error_code"] == "DEBT_WOULD_GROW"
    assert envelope["recovery"], "un error sin recuperación no le sirve a nadie"
    assert not destino.exists(), "se negó y aun así escribió"


def test_la_baseline_publicada_esta_al_dia():
    """Si la baseline y el catálogo divergen, la puerta 14 nace en rojo."""
    datos = json.loads(
        (SCRIPTS / "norms-coherence-baseline.json").read_text(encoding="utf-8"))
    congeladas = {c["claim"] for c in datos["claims"]}
    vivas = {c["claim"] for c in coherencia.scan()["untraceable_claims"]}
    assert vivas - congeladas == set(), "deuda nueva sin congelar"


def test_la_baseline_quedo_saldada_y_no_retirada():
    """v40.11: `claims: []` con el fichero en pie.

    Que la lista esté vacía y el fichero exista es justo lo que distingue una
    deuda saldada de una medida que alguien apagó.
    """
    ruta = SCRIPTS / "norms-coherence-baseline.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["claims"] == []
    assert datos["norm"] == "AP-55"
    assert datos["description"].strip()


def test_la_puerta_14_corre_esta_tool():
    from vault_gate import PUERTAS

    ids = {p["id"] for p in PUERTAS}
    assert "norms_coherence" in ids
    puerta = next(p for p in PUERTAS if p["id"] == "norms_coherence")
    assert puerta["cmd"][0] == "vault_norms_coherence.py"


def test_la_cli_devuelve_exit_0_sobre_el_catalogo_vivo():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_norms_coherence.py"), "--check", "--strict"],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout.strip().splitlines()[0])["ok"] is True


# ── C7 (AP-60) ────────────────────────────────────────────────────────────────
#
# AP-60 — el guard cobra por declarar y regala el silencio. Los tests que
# deciden son los dos primeros: que el silencio se cuente, y que la exención
# escrita salga gratis. Si alguna vez se invierten, el incentivo vuelve a estar
# del revés y la norma deja de significar nada.


def _sin_baseline_distincion(monkeypatch, tmp_path):
    """La baseline real no puede decidir el resultado de un catálogo sintético."""
    monkeypatch.setattr(
        coherencia, "BASELINE_DISTINCION", tmp_path / "no-existe.json")


def test_ap60_una_norma_muda_cuenta_como_deuda(monkeypatch, tmp_path):
    _sin_baseline_distincion(monkeypatch, tmp_path)
    r = _con_catalogo(monkeypatch, [_norma()])
    assert r["norms_without_distinction"] == ["AP-99"]
    assert r["new_norms_without_distinction"] == ["AP-99"]
    assert r["ok"] is False


def test_ap60_la_exencion_escrita_sale_gratis(monkeypatch, tmp_path):
    """El punto entero de la norma: declararse no puede costar más que callarse."""
    _sin_baseline_distincion(monkeypatch, tmp_path)
    r = _con_catalogo(monkeypatch, [
        _norma(**{coherencia.CAMPO_SIN_DISTINCION: "no se confunde con ninguna: motivo"})])
    assert r["norms_without_distinction"] == []


def test_ap60_una_exencion_vacia_no_es_una_exencion(monkeypatch, tmp_path):
    """Sin motivo escrito el hueco queda igual de mudo que el silencio."""
    _sin_baseline_distincion(monkeypatch, tmp_path)
    r = _con_catalogo(monkeypatch, [_norma(**{coherencia.CAMPO_SIN_DISTINCION: "   "})])
    assert r["norms_without_distinction"] == ["AP-99"]


def test_ap60_un_discriminador_vacio_tampoco_salda(monkeypatch, tmp_path):
    """`distinguido_de` con la clave puesta y el texto en blanco no dice nada."""
    _sin_baseline_distincion(monkeypatch, tmp_path)
    r = _con_catalogo(monkeypatch, [_norma(distinguido_de={"AP-01": ""})])
    assert r["norms_without_distinction"] == ["AP-99"]


def test_ap60_mide_el_universo_y_no_solo_a_quien_declaro(monkeypatch, tmp_path):
    """La medida que C5 no podía dar: el denominador es el catálogo entero.

    C5 itera sobre `distinguido_de`, así que sobre este catálogo —una norma
    que habla y dos que callan— no tiene nada que decir. C7 sí.
    """
    _sin_baseline_distincion(monkeypatch, tmp_path)
    r = _con_catalogo(monkeypatch, [
        _norma(code="AP-97", distinguido_de={"AP-98": "se distinguen en esto"}),
        _norma(code="AP-98", distinguido_de={"AP-97": "y en esto"}),
        _norma(code="AP-99"),
    ])
    assert r["indistinguishable_norms"] == []
    assert r["norms_without_distinction"] == ["AP-99"]


def test_ap60_la_baseline_absorbe_lo_viejo_y_no_lo_nuevo(monkeypatch, tmp_path):
    ruta = tmp_path / "baseline.json"
    ruta.write_text(json.dumps({"normas": [{"norm": "AP-97"}]}), encoding="utf-8")
    monkeypatch.setattr(coherencia, "BASELINE_DISTINCION", ruta)
    r = _con_catalogo(monkeypatch, [_norma(code="AP-97"), _norma(code="AP-99")])
    assert r["new_norms_without_distinction"] == ["AP-99"]
    assert r["ok"] is False


def test_ap60_freeze_se_niega_a_congelar_deuda_nueva(monkeypatch, tmp_path):
    ruta = tmp_path / "baseline.json"
    monkeypatch.setattr(coherencia, "BASELINE_DISTINCION", ruta)
    monkeypatch.setattr(coherencia, "_catalogo", lambda: [_norma()])
    r = coherencia.freeze_distincion()
    assert r["ok"] is False and r["error_code"] == "DEBT_WOULD_GROW"
    assert not ruta.exists()
    admitido = coherencia.freeze_distincion(admitir_nuevos=True)
    assert admitido["ok"] is True and admitido["admitted_new"] == ["AP-99"]


def test_ap60_la_baseline_viva_solo_encoge():
    """Lo que hay congelado hoy, y que el fichero declara su norma."""
    datos = json.loads(
        (SCRIPTS / "norms-distincion-baseline.json").read_text(encoding="utf-8"))
    assert datos["norm"] == "AP-60"
    assert datos["description"].strip()
    from vault_norms import NORM_CATALOG

    codigos = {n["code"] for n in NORM_CATALOG}
    congeladas = {e["norm"] for e in datos["normas"]}
    assert congeladas <= codigos, "la baseline congela normas que ya no existen"


def test_ap60_la_norma_esta_en_el_catalogo_y_se_distingue_de_las_dos():
    from vault_norms import NORM_CATALOG

    ap60 = next(n for n in NORM_CATALOG if n["code"] == "AP-60")
    assert ap60["enforcement"] == "guard+audit"
    assert "vault_norms_coherence" in ap60["tools_enforcing"]
    assert set(ap60["distinguido_de"]) == {"AP-55", "AP-37"}

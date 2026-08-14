"""AP-58 — el ciclo que se esquiva metiendo el import dentro de una función.

El test que decide si esto sirve de algo es
`test_un_diferido_ciclico_nuevo_rompe_la_puerta`. Sin él, `vault_ciclos` sería
un informe: mide, publica un número bonito y no impide nada. La regla 4 pide
guard, y un guard que no muerde no es un guard.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_ciclos as C  # noqa: E402


# ── La medida ────────────────────────────────────────────────────────────────

def test_el_grafo_separa_lo_que_se_ve_de_lo_que_no():
    """La distinción ES la medida: sin ella el grafo sale acíclico.

    Este repo declaraba cero ciclos y era verdad mirando solo el nivel de
    módulo. Si `_grafo` dejara de separar, la tool volvería a decir cero.
    """
    g = C._grafo()
    assert g["top"] and g["diferido"]
    diferidas = sum(len(v) for v in g["diferido"].values())
    assert diferidas > 0, (
        "cero imports diferidos: o se saldó la deuda entera —celébralo y baja "
        "esta aserción— o la separación top/diferido dejó de funcionar"
    )


def test_contar_las_diferidas_es_lo_que_destapa_el_ciclo():
    """El contraste que justifica la norma, ejecutado en vez de contado.

    Con solo las aristas de nivel superior no hay componente conexo alguno;
    añadiendo las diferidas aparece el del núcleo. Si algún día el primero
    dejara de dar cero, esta norma habría cambiado de sentido y hay que releerla.
    """
    g = C._grafo()
    solo_visible = C._componentes({m: g["top"].get(m, set()) for m in g["top"]})
    completo = C._componentes(C._completo(g))
    assert solo_visible == [], (
        f"ya hay ciclos visibles a nivel de módulo: {solo_visible}. Eso es "
        f"peor que AP-58, no mejor: Python los detecta al arrancar"
    )
    assert completo, "contar las diferidas dejó de destapar el ciclo del núcleo"


def test_solo_entran_en_la_deuda_las_que_esquivan_un_ciclo():
    """62 de las 92 se difieren por otros motivos y NO son deuda.

    Congelarlas todas daba un número mayor y una señal peor: una baseline llena
    de ruido es una baseline que nadie revisa.
    """
    m = C.medir()
    assert m["deferred_cyclic"], "la clasificación dejó de encontrar cíclicas"
    assert m["deferred_benign"], (
        "todas las diferidas salieron cíclicas: eso apunta a que `_alcanza` "
        "está devolviendo True de más, no a que el repo empeorase"
    )
    assert len(m["deferred_cyclic"]) + len(m["deferred_benign"]) == m["deferred_total"]
    # Ninguna arista puede estar en los dos lados.
    assert not set(m["deferred_cyclic"]) & set(m["deferred_benign"])


def test_una_ciclica_vuelve_de_verdad_al_origen():
    """AP-44 sobre la propia clasificación: se comprueba con el grafo, no con
    la palabra de `_alcanza`, recorriendo la vuelta a mano."""
    g = C._grafo()
    G = C._completo(g)
    for arista in C.medir()["deferred_cyclic"]:
        a, b = arista.split("->")
        assert b in G.get(a, set()), f"{arista} ni siquiera es una arista"
        assert C._alcanza(G, b, a), f"{arista} clasificada cíclica sin vuelta"


# ── El guard, y que muerda ───────────────────────────────────────────────────

def test_la_baseline_no_creció():
    r = C.check()
    assert r["ok"], (
        f"ciclos nuevos esquivados con import diferido: "
        f"{r['new_cyclic_deferrals']}. Se arreglan invirtiendo la dependencia, "
        f"no ampliando ciclos-baseline.json."
    )


def test_la_baseline_esta_al_dia_si_encogio():
    r = C.check()
    assert not r["resolved_since_baseline"], (
        f"estas aristas ya no esquivan ningún ciclo: "
        f"{r['resolved_since_baseline']} — corre "
        f"`python scripts/vault_ciclos.py --freeze` para que no puedan volver"
    )


def test_un_diferido_ciclico_nuevo_rompe_la_puerta(monkeypatch):
    """**El criterio que decide si el guard es real** (AP-44).

    Se retira una arista de la baseline: la que sigue midiéndose pasa a ser
    deuda nueva y el check tiene que ponerse en rojo.
    """
    base = C._baseline()
    assert base, "baseline vacía: el mutante no probaría nada"
    monkeypatch.setattr(C, "_baseline", lambda: base[1:])
    r = C.check()
    assert r["ok"] is False
    assert base[0] in r["new_cyclic_deferrals"]


def test_freeze_se_niega_a_congelar_deuda_sin_precedente(monkeypatch, tmp_path):
    """Congelar en silencio es como una baseline deja de encoger."""
    monkeypatch.setattr(C, "_baseline", lambda: [])
    monkeypatch.setattr(C, "BASELINE", tmp_path / "no-debe-escribirse.json")
    r = C.freeze()
    assert r["ok"] is False
    assert r["error_code"] == "DEBT_WOULD_GROW"
    assert not (tmp_path / "no-debe-escribirse.json").exists(), (
        "se negó en el envelope pero escribió la baseline igualmente"
    )


def test_una_baseline_corrupta_no_se_lee_como_vacia(monkeypatch, tmp_path):
    """AP-51: leerla vacía estrenaría las 30 como deuda nueva, y en `--freeze`
    las congelaría sin que nadie las viera pasar."""
    mala = tmp_path / "rota.json"
    mala.write_text("{no es json", encoding="utf-8")
    monkeypatch.setattr(C, "BASELINE", mala)
    with pytest.raises(RuntimeError, match="corrupta"):
        C._baseline()


# ── Registro y puerta ────────────────────────────────────────────────────────

def test_ap58_esta_en_el_catalogo_con_enforcement_real():
    import vault_norms

    norma = next((n for n in vault_norms.NORM_CATALOG
                  if n["code"] == "AP-58"), None)
    assert norma is not None, "AP-58 no está catalogada"
    assert norma["enforcement"] != "manual", "regla 5: enforcement real"
    assert "vault_ciclos" in norma["tools_enforcing"]


def test_la_puerta_existe_y_apunta_a_la_tool():
    import vault_gate

    puerta = next((p for p in vault_gate.PUERTAS if p["id"] == "ciclos"), None)
    assert puerta is not None, "la puerta `ciclos` no está en el registro"
    assert puerta["cmd"][0] == "vault_ciclos.py"
    assert "AP-58" in puerta["mide"]


def test_la_baseline_esta_publicada_en_el_plano():
    """Una deuda congelada que el plano no publica es una que nadie revisa."""
    plano = (REPO_ROOT / "docs" / "BLUEPRINT.md").read_text(encoding="utf-8")
    assert "ciclos-baseline.json" in plano, (
        "la baseline de AP-58 no aparece en la capa 6 — regenera el plano con "
        "`python scripts/vault_blueprint.py --blueprint`"
    )


def test_el_envelope_declara_su_limite():
    """Verde aquí no prueba que no haya acoplamiento, y tiene que decirlo."""
    r = C.check()
    assert "hint" in r and len(r["hint"]) > 80
    assert r["norm"] == "AP-58"
    json.dumps(r)  # serializable: lo consume la puerta por subproceso

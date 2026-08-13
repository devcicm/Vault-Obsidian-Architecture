"""Tres guards que medían menos de lo que decían medir (v40.16).

Los tres tenían la misma forma que el estándar ya conoce: **verde, y verde no
significaba lo escrito**.

1. `vault_blueprint` capa 4 daba una norma por cubierta si algún fichero de
   `tests/` contenía su código *en cualquier sitio* — un docstring que la citaba
   de pasada bastaba. Como la baseline solo encoge, la certificación falsa era
   irreversible.
2. `vault_blueprint._BASELINES` listaba 6 de las 9 baselines del repo, así que
   la capa 6 publicaba tres deudas congeladas como si no existieran.
3. `vault_norms_coherence` C2 buscaba el código de la norma en el fichero
   entero, cuando su propia baseline dice desde v40.11 que nombrarla en la
   cabecera del módulo no vale.
"""

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_blueprint as bp  # noqa: E402
import vault_criterios as vc  # noqa: E402
import vault_norms_coherence as nc  # noqa: E402


# --- 1) capa 4: mención vs. ejercicio ----------------------------------------

_SOLO_MENCION = '"""Un docstring que cita AP-99 de pasada."""\n\ndef test_x():\n    assert True\n'
_EJERCICIO = 'def test_x():\n    """Sin el codigo aqui."""\n    assert detecta("AP-99")\n'


def test_una_mencion_en_prosa_no_cubre_la_norma():
    assert not bp._test_ejercita("AP-99", _SOLO_MENCION)


def test_el_codigo_en_el_cuerpo_del_test_si_cubre():
    assert bp._test_ejercita("AP-99", _EJERCICIO)


def test_el_docstring_del_propio_test_tampoco_cuenta():
    fuente = 'def test_x():\n    """Cubre AP-99."""\n    assert True\n'
    assert not bp._test_ejercita("AP-99", fuente)


def test_una_norma_descubierta_declarada_no_es_deuda_nueva():
    """Declararse honestamente no puede salir mas caro que callarse.

    AP-04 declara `cobertura_descubierta` con motivo escrito, y aparecia como
    deuda nueva el dia que la cobertura por mencion dejo de valer.
    """
    declaradas = {
        n["code"] for n in bp.cobertura_de_normas() if n["uncovered_declared"]
    }
    assert declaradas, "ninguna norma declara cobertura_descubierta; revisa el catalogo"
    assert not (declaradas & bp._sin_cobertura())


# --- 2) capa 6: ninguna baseline fuera del plano ------------------------------

def test_toda_baseline_del_repo_aparece_en_el_plano():
    listadas = {f for f, _c, _n in bp._BASELINES}
    en_disco = {p.name for p in bp.SCRIPTS_DIR.glob("*baseline*.json")}
    assert en_disco - listadas == set(), "baselines que la capa 6 no publica"


def test_cada_entrada_apunta_a_una_clave_que_existe():
    import json

    for fichero, clave, _norma in bp._BASELINES:
        ruta = bp.SCRIPTS_DIR / fichero
        if not ruta.exists():
            continue
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert clave in datos, f"{fichero}: la clave `{clave}` no existe"


def test_un_dict_de_listas_cuenta_campos_y_no_claves():
    """`field-compat` indexa por tool: contar claves publicaria 111 por miles."""
    assert bp._congelado({"a": [1, 2], "b": [3]}) == 3
    assert bp._congelado({"a": 1}) == 1
    assert bp._congelado([1, 2, 3]) == 3


# --- 3) C2: la cabecera del modulo no salda ----------------------------------

def test_nombrar_la_norma_en_la_cabecera_ya_no_deja_traza():
    fuente = '"""Este modulo cumple AP-99."""\n\ndef f():\n    return 1\n'
    assert "AP-99" not in nc._sin_cabecera(fuente)


def test_nombrarla_en_la_funcion_si_deja_traza():
    fuente = '"""Cabecera limpia."""\n\ndef f():\n    # AP-99: aqui se cumple\n    return 1\n'
    assert "AP-99" in nc._sin_cabecera(fuente)


def test_un_modulo_que_no_parsea_no_se_lee_como_sin_traza():
    """AP-51: el fallo del parser no se presenta como ausencia en el dato."""
    roto = "def f(:\n"
    assert nc._sin_cabecera(roto) == roto


# --- 4) AP-57: el alcance real se publica ------------------------------------

def test_el_envelope_publica_a_cuantos_modulos_llega_de_verdad():
    r = vc.check()
    assert r["modules_measured"] + r["modules_skipped"] <= r["modules_scanned"]
    assert r["modules_skipped"] > 0, (
        "si ya no se salta ninguno, la precondicion del `*.md` desaparecio: "
        "revisa el docstring de `medir` antes de borrar este test"
    )
    assert r["skip_reason"]


def test_la_precondicion_sigue_siendo_la_documentada():
    """El docstring de `medir` declara el coste; que no se despegue del codigo."""
    doc = vc.medir.__doc__ or ""
    assert "*.md" in doc, "el docstring ya no nombra la precondicion"
    assert "modules_skipped" in doc, "el docstring no dice donde se ve el coste"

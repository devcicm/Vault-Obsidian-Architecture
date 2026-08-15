"""El dueño único del fichero de baseline (v40.24).

Hasta v40.23 había trece entradas de baseline en doce ficheros y ocho guards
reimplementaban carga y congelado — tres de ellos con el cuerpo literalmente
idéntico. Estos tests fijan las cuatro cosas que ese dueño tiene que garantizar
y que ninguna de las ocho copias garantizaba a la vez: que una baseline ilegible
no se lea como vacía, que reescribirla no borre lo que el módulo no entiende,
que un `objetivo` a medias no cuente como objetivo, y que la pendiente salga de
git en vez de estar escrita.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_baseline as B  # noqa: E402


# ── Carga ────────────────────────────────────────────────────────────────────

def test_ausente_no_es_lo_mismo_que_corrupta(tmp_path):
    """La distinción entera de AP-51, en dos líneas.

    Ausente es legítimo: una norma recién nacida sin deuda congelada. Corrupta
    no lo es nunca, y leerla como vacía estrena la deuda entera como nueva —
    o peor, la congela en el `--freeze` siguiente sin que nadie la vea pasar.
    """
    assert B.cargar(tmp_path / "no-existe.json", "sitios", "AP-XX") == []
    rota = tmp_path / "rota.json"
    rota.write_text("{no es json", encoding="utf-8")
    with pytest.raises(B.BaselineIlegible, match="corrupta"):
        B.cargar(rota, "sitios", "AP-XX")


def test_una_raiz_que_no_es_objeto_tampoco_se_lee_como_vacia(tmp_path):
    p = tmp_path / "b.json"
    p.write_text('["a", "b"]', encoding="utf-8")
    with pytest.raises(B.BaselineIlegible):
        B.cargar(p, "sitios", "AP-XX")


def test_la_clave_con_otro_tipo_no_pasa_por_lista_vacia(tmp_path):
    """El fallo que v40.23 dejó vivo en `vault_excepcion_declarada` sin verlo:
    la baseline escribía `sitios` y el lector leía `sites`. Nació vacía, así que
    el desajuste no dio la cara — y habría dado como «nuevo» todo lo congelado
    en la primera ejecución tras el primer `--freeze`."""
    p = tmp_path / "b.json"
    p.write_text('{"sitios": {"a": 1}}', encoding="utf-8")
    with pytest.raises(B.BaselineIlegible, match="se esperaba lista"):
        B.cargar(p, "sitios", "AP-XX")


def test_las_trece_baselines_del_repo_se_leen_con_el_dueno():
    """Contraste contra el material real, no contra un fixture.

    Se recorren las entradas que declara el plano: si una deja de poder leerse
    con el contrato, aquí se ve antes que en la puerta.
    """
    import vault_blueprint as BP
    leidas = 0
    for fichero, clave, norma in BP._BASELINES:
        ruta = BP.SCRIPTS_DIR / fichero
        if not ruta.exists():
            continue
        datos = B.cargar_datos(ruta, norma)
        assert clave in datos, f"{fichero}: sin la clave `{clave}` que el plano declara"
        assert B.tamano_congelado(datos[clave]) >= 0
        leidas += 1
    assert leidas >= 12, "el plano dejó de listar las baselines del repo"


# ── Escritura ────────────────────────────────────────────────────────────────

def test_reescribir_no_borra_lo_que_el_modulo_no_entiende(tmp_path):
    """No-derogación. Ahí viven `sites_v1_superseded` y `off_port_crossings`.

    Borrarlas al reescribir sería derogar por descuido — que es como la
    anotación de la migración v1 se perdió una vez, dentro del código escrito
    para conservarla.
    """
    p = tmp_path / "b.json"
    p.write_text(json.dumps({
        "sitios": ["viejo"],
        "sites_v1_superseded": {"reason": "…", "sites": ["a:1"]},
        "otra_lista": [1, 2],
    }), encoding="utf-8")
    B.escribir(p, "sitios", "AP-XX", "nueva descripción", ["nuevo"])
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["sitios"] == ["nuevo"]
    assert d["description"] == "nueva descripción"
    assert d["sites_v1_superseded"]["sites"] == ["a:1"]
    assert d["otra_lista"] == [1, 2]


def test_se_escribe_con_lf_aunque_el_sistema_sea_windows(tmp_path):
    """El default de Windows traduce a CRLF y mete la baseline entera en el
    diff cada vez que se recongela, escondiendo qué firma entró o salió."""
    p = tmp_path / "b.json"
    B.escribir(p, "sitios", "AP-XX", "d", ["a"])
    assert b"\r\n" not in p.read_bytes()


# ── La negativa a crecer ─────────────────────────────────────────────────────

def test_la_negativa_lista_siempre_los_nuevos():
    """Congelar deuda nueva es posible; hacerlo en silencio no.

    Es lo único que el envelope garantiza, y estaba escrito ocho veces con
    mensajes distintos.
    """
    e = B.negativa("t", "freeze", "new_sites", ["a::b", "c::d"], "arréglalo")
    assert e["ok"] is False
    assert e["error_code"] == "DEBT_WOULD_GROW"
    assert e["new_sites"] == ["a::b", "c::d"]
    assert e["recovery"] == "arréglalo"


def test_comparar_devuelve_nuevos_y_resueltos_ordenados():
    assert B.comparar({"b", "a"}, {"b", "z"}) == (["a"], ["z"])


# ── El contrato de `objetivo` ────────────────────────────────────────────────

def test_un_numero_suelto_no_es_un_objetivo():
    """La precondición que la propia deuda declaraba: un `objetivo` sin quién lo
    revisa es una cifra a mano más (AP-47)."""
    assert B.validar_objetivo(12)
    assert B.validar_objetivo({"tamano": 0})
    completo = {"tamano": 0, "fecha_limite": "2027-06-30",
                "cadencia_dias": 180, "dueno": "gobernanza"}
    assert B.validar_objetivo(completo) == []
    assert B.validar_objetivo({**completo, "tamano": -1})
    assert B.validar_objetivo({**completo, "cadencia_dias": 0})
    assert B.validar_objetivo({**completo, "fecha_limite": "junio"})
    assert B.validar_objetivo({**completo, "dueno": " "})


def test_sin_objetivo_no_se_confunde_con_cumplido(tmp_path):
    """No comprometerse no puede salir más barato que comprometerse."""
    p = tmp_path / "b.json"
    p.write_text('{"sitios": ["a", "b"]}', encoding="utf-8")
    assert B.estado_objetivo(p, "sitios", "AP-XX")["estado"] == "sin_objetivo"


@pytest.mark.parametrize("tamano,hoy,esperado", [
    (0, date(2026, 8, 14), "cumple"),
    (3, date(2026, 8, 14), "en_plazo"),
    (3, date(2028, 1, 1), "vencido"),
])
def test_los_tres_estados_de_un_objetivo_vivo(tmp_path, tamano, hoy, esperado):
    p = tmp_path / "b.json"
    p.write_text(json.dumps({
        "sitios": ["x"] * tamano,
        "objetivo": {"tamano": 0, "fecha_limite": "2027-06-30",
                     "cadencia_dias": 180, "dueno": "gobernanza"},
    }), encoding="utf-8")
    assert B.estado_objetivo(p, "sitios", "AP-XX", hoy=hoy)["estado"] == esperado


def test_un_objetivo_a_medias_se_publica_como_invalido_y_no_como_cumplido(tmp_path):
    p = tmp_path / "b.json"
    p.write_text('{"sitios": [], "objetivo": {"tamano": 0}}', encoding="utf-8")
    e = B.estado_objetivo(p, "sitios", "AP-XX")
    assert e["estado"] == "objetivo_invalido" and e["problemas"]


def test_los_objetivos_declarados_en_el_repo_son_validos():
    """Contraste contra el material real: un objetivo inválido en el repo sería
    peor que ninguno, porque el plano lo publicaría como declarado."""
    import vault_blueprint as BP
    for fichero, _clave, norma in BP._BASELINES:
        ruta = BP.SCRIPTS_DIR / fichero
        if not ruta.exists():
            continue
        objetivo = B.objetivo_de(ruta, norma)
        if objetivo is not None:
            assert B.validar_objetivo(objetivo) == [], fichero


# ── La pendiente ─────────────────────────────────────────────────────────────

def test_la_pendiente_no_esta_escrita_en_ningun_fichero():
    """Escribirla sería afirmar sobre la historia sin que git la respalde
    (AP-53). Sale de `git log` cada vez, y por eso no puede envejecer."""
    import vault_blueprint as BP
    for fichero, _clave, norma in BP._BASELINES:
        ruta = BP.SCRIPTS_DIR / fichero
        if not ruta.exists():
            continue
        datos = B.cargar_datos(ruta, norma)
        assert "pendiente" not in datos, fichero
        assert "slope" not in datos, fichero


def test_la_pendiente_de_una_baseline_del_repo_sale_de_git():
    """Sobre una que ya tiene historia. Si git no está, se dice — una serie
    vacía se leería como «esta deuda nunca se movió»."""
    p = RAIZ / "scripts" / "blame-baseline.json"
    r = B.pendiente(p, "sites", "AP-51", ultimos=5)
    assert r["disponible"] is True
    assert r["muestras"] >= 1
    for punto in r["serie"]:
        assert isinstance(punto["tamano"], int)


def test_sin_git_la_pendiente_lo_dice_en_vez_de_devolver_serie_vacia(monkeypatch):
    def revienta(*a, **k):
        raise OSError("git no está")
    monkeypatch.setattr(B.subprocess, "run", revienta)
    r = B.pendiente(RAIZ / "scripts" / "blame-baseline.json", "sites", "AP-51")
    assert r["disponible"] is False and r["serie"] == []


# ── La duplicación que esto vino a cerrar ────────────────────────────────────

def test_ningun_guard_conserva_su_propia_carga_de_baseline():
    """AP-57: el cuerpo estaba copiado en cuatro módulos, palabra por palabra.

    Se comprueba por la forma que delataba la copia —leer y parsear el fichero
    de baseline dentro del propio guard—, no por el nombre de la función: los
    `_baseline()` locales siguen existiendo, reducidos a delegación, porque la
    no-derogación conserva el contrato de llamada.
    """
    migrados = ["vault_criterios", "vault_ciclos", "vault_kernel",
                "vault_fuente_unica", "vault_excepcion_declarada"]
    for modulo in migrados:
        fuente = (RAIZ / "scripts" / f"{modulo}.py").read_text(encoding="utf-8")
        assert "BASELINE.read_text" not in fuente, modulo
        assert "BASELINE.write_text" not in fuente, modulo
        assert "vault_baseline" in fuente, modulo


def test_el_dueno_no_importa_ninguna_tool():
    """Fan-out cero. Lo consumen guards del meta-toolkit y también tools que
    miden vaults; una dependencia hacia arriba desde aquí invertiría la
    dirección que AP-59 vigila."""
    fuente = (RAIZ / "scripts" / "vault_baseline.py").read_text(encoding="utf-8")
    for linea in fuente.splitlines():
        if linea.startswith(("import ", "from ")):
            assert "vault_" not in linea, linea

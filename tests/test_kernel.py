"""AP-59 — el núcleo se declara y nadie lo contrasta (v40.20).

Estos tests no comprueban que `vault_kernel` «funcione»: eso lo dice la puerta 18
al ejecutarse. Comprueban las cuatro cosas que se perderían en silencio.

1. Que los hallazgos **aparecen** cuando la forma del grafo los justifica. Un
   guard que nunca dispara pasa por verde para siempre y nadie lo nota, así que
   los dos hallazgos centrales se prueban con un grafo sintético en el que la
   respuesta correcta se conoce de antemano.
2. Que sin historia de git el churn sale `desconocido` y **no** `0`. Un cero
   fabricado saldría verde por no haber mirado, que es AP-51, y en CI —donde
   `actions/checkout@v4` clona a profundidad 1— es el caso normal, no el raro.
3. Que el umbral publicado en el envelope **es** el derivado del escalón. Si se
   publicara uno y se aplicara otro, el envelope sería decorativo y el número
   real volvería a ser inauditable, que es AP-47.
4. Que `vault_kernel` **no** parsea imports ni reimplementa K1. Es la regresión
   cara: una tool que mide la pureza del núcleo con su propio criterio se
   certifica a sí misma, y eso es AP-44 cometido justo donde existe para
   detectarlo.
"""

import ast
import inspect
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_grafo_import as G  # noqa: E402
import vault_kernel as K  # noqa: E402


# ── Utillaje: un grafo sintético con la respuesta conocida ───────────────────

def _monta(monkeypatch, grafo, kernel, dominio, churns=None, historia=True):
    """Sustituye las tres fuentes de `medir()`: grafo, contextos y git.

    K1 se neutraliza a `[]` a propósito: aquí se prueban K2 y K3. Que K1 sea
    delegada tiene su propio test más abajo, y comprobarla con un doble sería
    justamente reimplementarla.
    """
    monkeypatch.setattr(K.vault_grafo_import, "completo", lambda *a, **k: grafo)
    monkeypatch.setattr(K, "CONTEXTS", {
        K.KERNEL: {"modulos": list(kernel)},
        "dominio_de_prueba": {"modulos": list(dominio)},
    })
    monkeypatch.setattr(K, "dependencias_del_kernel", lambda: [])
    monkeypatch.setattr(K, "_hay_historia", lambda: historia)
    monkeypatch.setattr(K, "churn", lambda m: (churns or {}).get(m, 0))


def _de(medida, tipo):
    return {h["module"] for h in medida["hallazgos"] if h["finding"] == tipo}


# ── 1. Los hallazgos aparecen cuando la forma los justifica ─────────────────

def test_un_modulo_del_kernel_sin_consumidores_se_reporta(monkeypatch):
    """AP-59: declarado núcleo y nadie lo importa.

    Es el caso real que destapó esta tanda —`vault_log_error`, fan-in 0— y el
    que mejor enseña por qué la lista a mano no basta: el módulo no está roto,
    simplemente dejó de ser lo que la lista dice que es, y ninguna medida lo
    contradecía.
    """
    grafo = {"nucleo": set(), "huerfano": set(),
             "a": {"nucleo"}, "b": {"nucleo"}, "c": {"nucleo"}}
    _monta(monkeypatch, grafo, kernel=["nucleo", "huerfano"],
           dominio=["a", "b", "c"])
    m = K.medir()
    assert _de(m, "kernel_sin_consumidores") == {"huerfano"}


def test_un_modulo_de_dominio_por_encima_del_escalon_se_reporta(monkeypatch):
    """El otro lado de AP-59: es núcleo y no está declarado.

    `intruso` tiene tantos consumidores como el núcleo declarado y fan-out cero.
    Si el guard solo mirase hacia dentro del kernel, este caso —el más caro,
    porque cada cambio suyo propaga sin que nadie lo trate como cambio de
    núcleo— sería invisible.
    """
    consumidores = [f"c{i}" for i in range(12)]
    grafo = {"nucleo": set(), "intruso": set()}
    for c in consumidores:
        grafo[c] = {"nucleo", "intruso"}
    grafo["solitario"] = set()
    grafo["c0"].add("solitario")
    _monta(monkeypatch, grafo, kernel=["nucleo"],
           dominio=consumidores + ["intruso", "solitario"])
    m = K.medir()
    assert "intruso" in _de(m, "nucleo_no_declarado")
    assert "solitario" not in _de(m, "nucleo_no_declarado"), (
        "un módulo con un solo consumidor no puede cruzar el escalón"
    )


def test_un_modulo_del_kernel_que_se_mueve_mas_que_el_dominio_se_reporta(monkeypatch):
    grafo = {"nucleo": set(), "a": {"nucleo"}, "b": {"nucleo"}, "c": {"nucleo"}}
    _monta(monkeypatch, grafo, kernel=["nucleo"], dominio=["a", "b", "c"],
           churns={"nucleo": 40, "a": 3, "b": 4, "c": 5})
    m = K.medir()
    assert _de(m, "kernel_inestable") == {"nucleo"}
    assert m["churn_mediana_dominio"] == 4


# ── 2. AP-51: sin historia, `desconocido` — nunca `0` ───────────────────────

def test_sin_historia_de_git_el_churn_es_desconocido_y_no_cero(monkeypatch):
    """El caso normal en CI: `actions/checkout@v4` clona a profundidad 1.

    Un `0` daría K3 verde para todo el mundo, y el verde sería cierto respecto a
    una historia que no se llegó a leer. Es exactamente AP-51: un vacío que no
    se distingue de un resultado legítimo.
    """
    grafo = {"nucleo": set(), "a": {"nucleo"}, "b": {"nucleo"}}
    _monta(monkeypatch, grafo, kernel=["nucleo"], dominio=["a", "b"],
           churns={"nucleo": 99, "a": 1, "b": 1}, historia=False)
    m = K.medir()
    assert m["churn_disponible"] is False
    assert m["churn"]["nucleo"] is None, "el churn desconocido se publicó como número"
    assert m["churn_mediana_dominio"] is None
    assert _de(m, "kernel_inestable") == set(), (
        "sin historia no se puede afirmar inestabilidad: callar es correcto, "
        "inventar un cero no"
    )


def test_hay_historia_devuelve_falso_si_git_no_responde(monkeypatch):
    class Fallo:
        returncode = 128
        stdout = ""
    monkeypatch.setattr(K.subprocess, "run", lambda *a, **k: Fallo())
    monkeypatch.setattr(K, "_CHURN", None)
    assert K._hay_historia() is False
    assert K.churn("vault_io") is None


def test_un_modulo_sin_commits_cuenta_cero_y_no_desconocido():
    """La otra mitad de AP-51: `None` y `0` significan cosas distintas y no
    pueden confundirse en ninguna de las dos direcciones."""
    assert K.churn("vault_io") is not None and K.churn("vault_io") > 0
    assert K.churn("modulo_que_jamas_existio") == 0


# ── 3. El umbral publicado es el aplicado ───────────────────────────────────

def test_el_escalon_es_la_mayor_caida_relativa_y_no_la_caida_a_cero():
    """Los ceros se ignoran: una caída a cero tiene ratio infinito y se llevaría
    siempre el máximo, dejando el umbral pegado al valor más pequeño."""
    umbral, ratio = K.escalon([100, 90, 80, 10, 9, 8, 0, 0])
    assert umbral == 80 and ratio == 8.0
    assert K.escalon([5]) == (None, None)
    assert K.escalon([]) == (None, None)


def test_el_umbral_publicado_coincide_con_el_derivado():
    """Publicar uno y aplicar otro dejaría el envelope decorativo (AP-47)."""
    r = K.check()
    grafo = G.completo()
    fi, fo = G.fan_in(grafo), G.fan_out(grafo)
    esperado_in, ratio_in = K.escalon([len(s) for s in fi.values()])
    esperado_out, ratio_out = K.escalon(
        [len(fo.get(m, ())) for m in r["kernel"]])
    assert (r["threshold_fan_in"], r["threshold_fan_in_ratio"]) == (esperado_in, ratio_in)
    assert (r["threshold_fan_out"], r["threshold_fan_out_ratio"]) == (esperado_out, ratio_out)
    assert r["threshold_fan_in"] is not None, (
        "sin escalón derivable `nucleo_no_declarado` no puede dispararse nunca "
        "y el guard pasaría a ser decorativo sin decirlo"
    )


# ── 4. AP-44: la tool que mide el núcleo no mide con su propio criterio ─────

def test_vault_kernel_no_parsea_imports_por_su_cuenta():
    """La regresión cara. Si esta tool se hace su propio parser vuelve a haber
    dos definiciones de «qué importa este módulo», y la que decide la pureza del
    núcleo sería la que nadie contrasta — AP-57 dentro de AP-59."""
    arbol = ast.parse((RAIZ / "scripts" / "vault_kernel.py").read_text(encoding="utf-8"))
    importados = {
        a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names
    } | {
        n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) and n.module
    }
    assert "ast" not in importados, (
        "vault_kernel importó `ast`: el grafo de imports tiene dueño en "
        "`vault_grafo_import` y esto es AP-44 en la tool que traza el núcleo"
    )
    assert "vault_grafo_import" in importados


def test_k1_se_delega_en_vault_arch_y_no_se_reimplementa():
    """K1 —el núcleo no depende del dominio— ya estaba medida y verde en
    `vault_arch.dependencias_del_kernel()`. Reimplementarla aquí sería medir la
    propia pureza con el propio criterio."""
    fuente = inspect.getsource(K.medir)
    assert "dependencias_del_kernel()" in fuente
    arbol = ast.parse(fuente.lstrip())
    nombres = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
    assert "GANCHOS_DEL_KERNEL" in nombres, (
        "los ganchos declarados se consumen de `vault_arch`, no se vuelven a listar"
    )


def test_una_dependencia_del_kernel_sin_declarar_no_la_absorbe_la_baseline(monkeypatch):
    """K1 es bloqueante y no baselinable: si el núcleo pasa a depender del
    dominio dejó de ser núcleo, y una baseline que se lo tragase convertiría la
    frontera en una sugerencia."""
    monkeypatch.setattr(K, "dependencias_del_kernel",
                        lambda: [{"from": "vault_io", "to": "vault_norms",
                                  "to_context": "gobernanza"}])
    r = K.check()
    assert r["ok"] is False
    assert r["k1_undeclared_kernel_deps"]


# ── 5. La extracción de v40.20 no cambió lo que medían los dos llamadores ────

def test_la_extraccion_no_cambio_lo_que_ven_arch_y_ciclos():
    """El criterio de aceptación de la tanda, ejecutable.

    `vault_arch` y `vault_ciclos` tienen que dar exactamente lo mismo que antes
    de que el grafo tuviera dueño. Se comprueba contra el dueño y no contra
    números escritos aquí: un número copiado envejecería y AP-47 volvería por la
    puerta de atrás.
    """
    import vault_arch as A
    import vault_ciclos as C
    for p in sorted((RAIZ / "scripts").glob("*.py")):
        assert A._importaciones(p) == G.importaciones(p, G.PREFIJO_VAULT)
    assert C._grafo() == G.grafo()


# ── 6. Contrato del envelope y de la baseline ───────────────────────────────

def test_el_check_nombra_la_norma_ap_59_y_publica_lo_que_mide():
    r = K.check()
    assert r["norm"] == "AP-59"
    for clave in ("threshold_fan_in", "threshold_fan_out", "churn_available",
                  "findings", "informational", "baseline_size", "kernel"):
        assert clave in r, f"el envelope dejó de publicar {clave}"


def test_los_ganchos_del_kernel_son_informativos_y_no_bloquean():
    """Decisión de alcance de v40.20, escrita para que se note si cambia.

    El hallazgo apunta a un mecanismo —`objetivo` en las baselines— que aún no
    existe. Bloquear con él solo enseñaría a ampliar baselines, que es lo
    contrario de lo que la norma persigue.
    """
    r = K.check()
    assert r["informational"], "los ganchos dejaron de publicarse"
    assert all(i["finding"] == "gancho_sin_presupuesto" for i in r["informational"])
    firmas = set(r["new_findings"]) | {f"{h['finding']}::{h['module']}"
                                       for h in r["findings"]}
    assert not any(f.startswith("gancho_sin_presupuesto") for f in firmas)


def test_una_baseline_corrupta_no_se_lee_como_vacia(monkeypatch, tmp_path):
    """AP-51. Leerla como vacía estrenaría todos los hallazgos como deuda nueva
    y `--freeze` los congelaría sin que nadie los viera pasar."""
    rota = tmp_path / "kernel-baseline.json"
    rota.write_text("{no es json", encoding="utf-8")
    monkeypatch.setattr(K, "BASELINE", rota)
    with pytest.raises(RuntimeError, match="corrupta"):
        K._baseline()


def test_la_firma_se_indexa_por_modulo_y_no_por_linea():
    """La pertenencia al kernel es estable por naturaleza. Un hash del cuerpo
    haría que cualquier edición reapareciese como hallazgo nuevo — y el churn
    del núcleo es justamente lo que K3 mide."""
    assert K.firma({"finding": "kernel_impuro", "module": "vault_io"}) == \
        "kernel_impuro::vault_io"


def test_freeze_se_niega_a_congelar_deuda_nueva(monkeypatch, tmp_path):
    vacia = tmp_path / "kernel-baseline.json"
    vacia.write_text('{"sitios": []}', encoding="utf-8")
    monkeypatch.setattr(K, "BASELINE", vacia)
    r = K.freeze()
    assert r["ok"] is False and r["error_code"] == "DEBT_WOULD_GROW"
    assert r["new_findings"], "no listó qué se negaba a congelar"


# ── 7. --trace: si toco esto, ¿qué se cae? ──────────────────────────────────

def test_trace_encuentra_el_camino_al_nucleo():
    r = K.trace("vault_context_pack")
    assert r["ok"] and r["path"][0] == "vault_context_pack"
    assert r["reaches"] in set(K.CONTEXTS[K.KERNEL]["modulos"])
    assert r["depth_to_kernel"] == len(r["path"]) - 1


def test_trace_de_un_modulo_del_kernel_tiene_profundidad_cero():
    r = K.trace("vault_errors")
    assert r["in_kernel"] and r["depth_to_kernel"] == 0


def test_trace_de_un_modulo_inexistente_no_devuelve_un_vacio_ambiguo():
    """AP-51: un camino vacío por no existir el módulo no puede parecerse a un
    camino vacío por no depender del núcleo."""
    r = K.trace("vault_que_no_existe")
    assert r["ok"] is False and r.get("error_code") == "NOT_FOUND"

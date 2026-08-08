"""AP-54 y la reentrancia de `file_lock`.

Dos defectos distintos que llegaron juntos y conviene no mezclar:

1. **La causa** — `file_lock` no era reentrante. Un hilo que volvía a pedir un
   lock que él mismo sostenía se bloqueaba contra sí mismo hasta el deadline.
   Se arregla una vez, en el kernel.
2. **La reacción** — casi todos los llamantes contestan a un `TimeoutError`
   escribiendo de todos modos, sin lock. Eso es AP-54, se repite en cada
   llamante, y necesita un guard.

La medida que los destapó: `vault_sdd_init` tomaba 26 veces el lock del fichero
de trazas, fallaba 13, y esperaba 65,14 s — trece por los cinco segundos de
timeout, exactos. Se pasaba del límite de 60 s de la tool y moría dejando
`docs/sdd/` a medio escribir, después de anunciar `PASS`.
"""

import ast
import sys
import threading
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_arch  # noqa: E402
import vault_io  # noqa: E402


# ── La causa: reentrancia por hilo ───────────────────────────────────────────


def test_el_mismo_hilo_puede_volver_a_tomar_el_lock(tmp_path):
    """Antes: 5 s de espera contra uno mismo y un TimeoutError."""
    objetivo = tmp_path / "indice.json"
    objetivo.write_text("{}", encoding="utf-8")

    t0 = time.time()
    with vault_io.file_lock(objetivo, timeout=5):
        with vault_io.file_lock(objetivo, timeout=5):
            pass
    assert time.time() - t0 < 1.0, "el hilo se bloqueó contra sí mismo"


def test_el_bloque_interno_no_libera_el_lock(tmp_path):
    """El fallo sutil de conceder reentrancia sin pensar el `finally`.

    Si el bloque interno liberase al salir, abriría una ventana en mitad de la
    sección crítica que el externo cree cerrada — que es justo lo que el lock
    promete. Se comprueba desde OTRO hilo, que es quien sufriría la ventana.
    """
    objetivo = tmp_path / "indice.json"
    objetivo.write_text("{}", encoding="utf-8")
    entro_el_otro = threading.Event()

    def intruso():
        try:
            with vault_io.file_lock(objetivo, timeout=0.4):
                entro_el_otro.set()
        except TimeoutError:
            pass

    with vault_io.file_lock(objetivo, timeout=5):
        with vault_io.file_lock(objetivo, timeout=5):
            pass
        # Fuera del bloque interno, todavía dentro del externo.
        t = threading.Thread(target=intruso)
        t.start()
        t.join(timeout=3)
        assert not entro_el_otro.is_set(), (
            "otro hilo entró en la sección crítica: el bloque interno liberó"
        )


def test_al_salir_del_bloque_externo_el_lock_queda_libre(tmp_path):
    """Y la reentrancia no puede dejarlo tomado para siempre."""
    objetivo = tmp_path / "indice.json"
    objetivo.write_text("{}", encoding="utf-8")

    with vault_io.file_lock(objetivo, timeout=5):
        with vault_io.file_lock(objetivo, timeout=5):
            pass

    entro = []

    def otro():
        with vault_io.file_lock(objetivo, timeout=5):
            entro.append(True)

    t = threading.Thread(target=otro)
    t.start()
    t.join(timeout=10)
    assert entro, "el lock quedó tomado tras salir del bloque externo"


def test_el_registro_de_locks_sostenidos_es_por_hilo(tmp_path):
    """Si fuese global, un hilo colaría a otro en la sección crítica."""
    objetivo = tmp_path / "indice.json"
    objetivo.write_text("{}", encoding="utf-8")
    resultado = []

    with vault_io.file_lock(objetivo, timeout=5):
        def intruso():
            try:
                with vault_io.file_lock(objetivo, timeout=0.4):
                    resultado.append("entro")
            except TimeoutError:
                resultado.append("timeout")

        t = threading.Thread(target=intruso)
        t.start()
        t.join(timeout=3)

    assert resultado == ["timeout"], (
        f"un hilo ajeno reutilizó la reentrancia de otro: {resultado}"
    )


# ── La reacción: el detector de AP-54 ────────────────────────────────────────


def _modulo(tmp_path, cuerpo, nombre="vault_falso.py"):
    p = tmp_path / nombre
    p.write_text(cuerpo, encoding="utf-8")
    return [p]


def test_detecta_la_escritura_sin_lock_en_el_handler(tmp_path):
    """La forma exacta que tenía `vault_errors_trace` antes de v40.7."""
    rutas = _modulo(tmp_path, """
def log_trace(entry):
    tf = trace_file()
    try:
        with file_lock(tf, timeout=5):
            _append(entry, use_atomic=True)
        return
    except TimeoutError:
        pass
    tf.write_text("...", encoding="utf-8")
""")
    # La escritura está FUERA del try, tras el handler: sigue siendo el mismo
    # camino, pero el detector solo mira el handler. Ver el test siguiente.
    assert vault_arch.escrituras_sin_lock(rutas) == []

    rutas = _modulo(tmp_path, """
def log_trace(entry):
    tf = trace_file()
    try:
        with file_lock(tf, timeout=5):
            _append(entry, use_atomic=True)
    except TimeoutError:
        tf.write_text("...", encoding="utf-8")
""", "vault_falso2.py")
    hallazgos = vault_arch.escrituras_sin_lock(rutas)
    assert len(hallazgos) == 1
    assert hallazgos[0]["call"] == "write_text"


def test_omitir_la_escritura_no_se_marca(tmp_path):
    """La respuesta correcta, que `vault_quality_check` ya tenía.

    Un detector que también marcara esto perseguiría a todo el que toca un lock
    y acabaría desactivado.
    """
    rutas = _modulo(tmp_path, """
def guardar(index_data):
    try:
        with file_lock(_quality_index(), timeout=30.0):
            atomic_write_json(_quality_index(), index_data)
    except TimeoutError:
        pass
""")
    assert vault_arch.escrituras_sin_lock(rutas) == []


def test_una_escritura_sin_file_lock_de_por_medio_no_se_marca(tmp_path):
    """El detector exige que el `try` protegido tomara un lock."""
    rutas = _modulo(tmp_path, """
def guardar(p):
    try:
        cargar(p)
    except TimeoutError:
        p.write_text("fallback", encoding="utf-8")
""")
    assert vault_arch.escrituras_sin_lock(rutas) == []


def test_el_handler_amplio_tambien_cuenta(tmp_path):
    """`except Exception` alrededor de un lock esconde el mismo caso."""
    rutas = _modulo(tmp_path, """
def guardar(p, data):
    try:
        with file_lock(p, timeout=5):
            atomic_write_json(p, data)
    except Exception:
        atomic_write_json(p, data)
""")
    hallazgos = vault_arch.escrituras_sin_lock(rutas)
    assert len(hallazgos) == 1
    assert hallazgos[0]["call"] == "atomic_write_json"


# ── El estado del repo ───────────────────────────────────────────────────────


def test_ningun_modulo_del_repo_escribe_sin_el_lock_que_no_consiguio():
    """La puerta. Cero, sin baseline: el único sitio se corrigió al hallarlo."""
    assert vault_arch.escrituras_sin_lock() == []


def test_el_trace_descarta_en_vez_de_escribir_sin_lock():
    """`vault_errors_trace` fue el caso testigo. Verificado en su AST.

    No basta con que el detector diga cero: se comprueba que el handler no
    tiene ninguna llamada, no que el detector sepa mirarlo.
    """
    fuente = (RAIZ / "scripts" / "vault_errors_trace.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    fn = next(n for n in ast.walk(arbol)
              if isinstance(n, ast.FunctionDef) and n.name == "log_trace")
    handlers = [h for n in ast.walk(fn) if isinstance(n, ast.Try) for h in n.handlers]
    timeouts = [h for h in handlers
                if getattr(h.type, "id", None) == "TimeoutError"]
    assert timeouts, "desapareció el handler de TimeoutError"
    for h in timeouts:
        llamadas = [c for s in h.body for c in ast.walk(s) if isinstance(c, ast.Call)]
        assert not llamadas, f"el handler volvió a hacer trabajo: {llamadas}"


def test_el_trace_no_pasa_por_el_saneado_que_lo_vuelve_a_escribir():
    """El bucle que la reentrancia destapó, y por qué estaba escondido.

    `atomic_write_text` sanea, y cuando aplica un arreglo llama a
    `log_encoding_fixes`, que llama a `log_trace`, que vuelve a escribir el
    fichero de trazas, que se vuelve a sanear. Medido en un solo
    `vault_risk_save`: **196 escrituras del trace** donde debía haber una.

    Llevaba latente desde siempre: el camino que lo dispara —tomar el lock del
    trace estando ya dentro de otro— antes fallaba y caía a la rama sin
    saneado, que rompía el ciclo por accidente. Al hacer el lock reentrante el
    accidente desapareció y el bucle quedó a la vista.
    """
    fuente = (RAIZ / "scripts" / "vault_errors_trace.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    llamadas = [
        n for n in ast.walk(arbol)
        if isinstance(n, ast.Call)
        and getattr(n.func, "id", None) == "atomic_write_text"
    ]
    assert llamadas, "desapareció la escritura atómica del trace"
    for c in llamadas:
        sanitize = next((k for k in c.keywords if k.arg == "sanitize"), None)
        assert sanitize is not None and sanitize.value.value is False, (
            "el trace volvió a pasar por el saneado: eso reabre el bucle"
        )


def test_una_escritura_no_dispara_una_cascada_de_trazas(tmp_path, monkeypatch):
    """La misma regresión, medida en vez de leída en el AST."""
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    vault_io.set_vault_root(tmp_path)
    import vault_errors_trace as T

    veces = []
    original = T._append_trace_entry
    monkeypatch.setattr(
        T, "_append_trace_entry",
        lambda e, use_atomic: (veces.append(1), original(e, use_atomic))[1],
    )

    for i in range(5):
        T.log_trace({"tool": "prueba", "n": i, "ok": True})

    assert len(veces) == 5, (
        f"cinco trazas provocaron {len(veces)} escrituras: la cascada volvió"
    )


def test_la_telemetria_no_cuenta_como_trabajo(tmp_path, monkeypatch):
    """AP-37 mide trabajo sobre el vault, no líneas de observabilidad.

    Contar el fichero de trazas hacía que el indicador **subiera con el número
    de errores registrados**, que es justo al revés de lo que mide.
    """
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    vault_io.set_vault_root(tmp_path)
    vault_io.write_ledger_reset()

    import vault_errors_trace as T

    T.log_trace({"tool": "prueba", "ok": True})
    assert vault_io.write_report()["written"] == 0, vault_io.write_report()
    assert vault_io.write_report()["unchanged"] == 0, vault_io.write_report()
    assert T.trace_file().exists(), "no contar la escritura no es no hacerla"


def test_ap54_esta_en_el_catalogo_de_normas():
    import vault_norms

    norma = next((n for n in vault_norms.NORM_CATALOG
                  if n["code"] == "AP-54"), None)
    assert norma is not None, "AP-54 no está catalogada"
    assert norma["enforcement"] != "manual"
    assert "vault_arch" in " ".join(norma["tools_enforcing"])


# ── El coste, que es lo que lo hizo visible ──────────────────────────────────


@pytest.mark.parametrize("n", [5, 20])
def test_escribir_en_serie_no_cuesta_cinco_segundos_por_escritura(tmp_path, n):
    """La regresión que importa: 13 escrituras costaban 65 s.

    El umbral es holgado a propósito —no se mide rendimiento, se mide que no
    haya una espera de timeout escondida—. Con el defecto, `n=20` tardaría más
    de un minuto y medio.
    """
    objetivo = tmp_path / "indice.json"
    t0 = time.time()
    for i in range(n):
        with vault_io.file_lock(objetivo, timeout=5):
            with vault_io.file_lock(objetivo, timeout=5):
                objetivo.write_text(f"{i}", encoding="utf-8")
    transcurrido = time.time() - t0
    assert transcurrido < n * 0.5, (
        f"{n} escrituras anidadas tardaron {transcurrido:.1f}s — "
        "huele a espera de lock contra uno mismo"
    )

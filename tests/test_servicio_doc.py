"""El doc derivado de la gobernanza: determinista y verificado sin efectos.

`docs/GOBIERNO.md` es un derivado: su contenido debe ser función de los
registros canónicos y de nada más. Dos defectos aparecieron en la auditoría:

1. La fecha de generación se incrustaba con `date.today()`, y `check()`
   compara bytes: el doc válido el día N reportaba `doc_drift` el día N+1 sin
   que cambiara ningún registro (la puerta `servicio` se ponía en rojo sola).
2. `check()` verificaba **escribiendo**: le pedía el doc a la misma función
   que lo persiste, mandada a un `.regenerado.md` dentro del repo, para
   leerlo y borrarlo. Un fallo entre medias dejaba residuo; un checkout
   de solo lectura la rompía; dos corridas concurrentes se disputaban el
   mismo fichero.

El arreglo separa GENERAR de ESCRIBIR de VERIFICAR (`documento()` puro,
`escribir_doc()` que persiste, `check()` que compara en memoria) con el
precedente interno de `vault_metricas.documento()/check_doc()` y
`vault_blueprint.check()`. La fecha de generación desaparece: el cuándo lo
dice el commit que regeneró el doc — `vault_metricas.documento()` ya declaró
el criterio («Sin estados: dependen del día»).
"""

import hashlib
import sys
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_servicio as srv  # noqa: E402

DOC = RAIZ / "docs" / "GOBIERNO.md"


# ── H1: determinismo frente al reloj ────────────────────────────────────────


def test_el_doc_publicado_no_declara_un_dia_de_generacion():
    """La fecha de generación era `date.today()`: el doc válido el día N
    fallaba el guard el día N+1 sin ningún cambio normativo. La línea de
    procedencia ya no puede llevar una fecha: el cuándo lo dice el commit.

    Este test mira solo el fichero publicado, así que es la reproducción
    ejecutable directa del defecto (v41.23 generó el doc el 2026-10-23 y el
    2026-10-24 la puerta ya salía en rojo).
    """
    import re

    texto = DOC.read_text(encoding="utf-8")
    procedencias = [
        line for line in texto.splitlines() if line.startswith("_Derivado")
    ]
    assert len(procedencias) == 1, "falta la línea de procedencia del doc"
    assert not re.search(r"\d{4}-\d{2}-\d{2}", procedencias[0]), (
        "la procedencia declara el día de generación: el doc pasa a ser "
        "inválido al día siguiente sin cambio de registros (H1)"
    )


def test_dos_generaciones_producen_los_mismos_bytes():
    """Criterio A de H1: mismas entradas → mismos bytes (SHA-256)."""
    texto = srv.documento()
    assert srv.documento() == texto
    assert (
        hashlib.sha256(texto.encode("utf-8")).hexdigest()
        == hashlib.sha256(srv.documento().encode("utf-8")).hexdigest()
    )


def test_cambiar_la_fecha_del_sistema_no_cambia_el_contenido(monkeypatch):
    """Criterio B de H1: dos días simulados, mismos registros, el mismo doc.

    Si alguien reintroduce `date.today()` (o cualquier dependencia del
    reloj), la generación simulada a 2033 diverge de la de hoy y el test
    muerde.
    """
    import datetime

    class _FechaFija(datetime.date):
        @classmethod
        def today(cls):
            return cls(2033, 12, 31)

    sin_parche = srv.documento()
    monkeypatch.setattr(datetime, "date", _FechaFija)
    con_parche = srv.documento()
    assert con_parche == sin_parche, (
        "el contenido del doc depende del día: volvió a entrar algo derivado "
        "del reloj (H1)"
    )


def test_un_cambio_legitimo_de_los_registros_se_detecta(monkeypatch):
    """Criterio C de H1: tocar un registro sí despierta el guard —
    que el determinismo no se consiga ignorando lo que verifica.
    """
    limpio = srv.check()
    assert limpio["doc_drift"] is None, limpio["doc_drift"]
    assert limpio["ok"], limpio

    inventado = dict(srv.CAPACIDADES)
    inventado["capacidad_de_prueba"] = {
        "titulo": "Prueba de drift",
        "resultado": "inventada en tests",
        "sirve_a": srv.SERVICIO["id"],
        "grupos": [],
    }
    monkeypatch.setattr(srv, "CAPACIDADES", inventado)
    alterado = srv.check()
    assert not alterado["ok"]
    assert alterado["doc_drift"] and "difiere" in alterado["doc_drift"]


# ── H2: verificar no es escribir ─────────────────────────────────────────────


def test_la_verificacion_no_crea_nada(monkeypatch):
    """Criterio A de H2: `check()` no crea ficheros — ni siquiera
    transitorios. Un espía en `Path.write_text` registra lo que la
    verificación intentara escribir: ni el doc que se verifica (reescribirlo
    sería corromperlo en nombre de verificarlo) ni ningún `.regenerado.md`.
    """
    escrituras = []
    original = Path.write_text

    def _espia(self, texto, *args, **kwargs):
        escrituras.append(str(self))
        return original(self, texto, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _espia)
    r = srv.check()

    sospechosas = [
        p for p in escrituras
        if p.endswith(".regenerado.md") or p == str(DOC)
    ]
    assert not sospechosas, (
        f"la verificación escribió {sospechosas}: GENERAR != ESCRIBIR != "
        "VERIFICAR (H2)"
    )
    assert r["doc_drift"] is None, r["doc_drift"]


def test_el_arbol_queda_igual_tras_verificar():
    """Criterio A de H2 (complemento): nada nuevo ni cambiado en `docs/`
    al terminar `check()`, mirando el árbol y no las llamadas.
    """
    antes = {p.name: p.stat().st_size for p in sorted(
        (RAIZ / "docs").glob("GOBIERNO*"))}
    srv.check()
    despues = {p.name: p.stat().st_size for p in sorted(
        (RAIZ / "docs").glob("GOBIERNO*"))}
    assert despues == antes, (
        f"`check()` alteró docs/: {sorted(set(antes) ^ set(despues))}"
    )


def test_la_verificacion_sobrevive_sin_permiso_de_escritura(monkeypatch):
    """Criterio B de H2: con el disco prohibido para escribir, `check()`
    responde igual. La simulación consistente en todas las plataformas:
    toda `write_text` lanza PermissionError — si la verificación necesita
    escribir, no puede terminar; si no, responde como siempre.
    """
    def _prohibido(self, texto, *args, **kwargs):
        raise PermissionError(f"escritura prohibida: {self}")

    monkeypatch.setattr(Path, "write_text", _prohibido)
    r = srv.check()
    assert r["doc_drift"] is None, r["doc_drift"]


def test_un_fallo_a_medio_verificar_no_deja_residuos(monkeypatch):
    """Criterio E de H2: una excepción entre escribir y limpiar no deja
    residuo. La simulación: la lectura del `.regenerado.md` lanza después
    de que la escritura la hubiera creado. Contra el código anterior el
    fichero quedaba en `docs/` — el residuo que motivó el hallazgo.
    """
    residuo = RAIZ / "docs" / "GOBIERNO.regenerado.md"
    try:
        original = Path.read_text

        def _espia(self, *args, **kwargs):
            if self.name.endswith(".regenerado.md"):
                raise RuntimeError("fallo simulado entre escribir y limpiar")
            return original(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", _espia)
        srv.check()
        assert not residuo.exists(), (
            "la verificación dejó residuo tras un fallo a mitad (H2)"
        )
    finally:
        # el entorno de prueba limpia; si el residuo estuvo, el assert de
        # arriba ya falló y la limpieza no lo enmascara.
        if residuo.exists():
            residuo.unlink()


def test_dos_verificaciones_concurrentes_no_interfieren():
    """Criterio C de H2: dos `check()` a la vez, sin carreras. Antes
    compartían la ruta fija `docs/GOBIERNO.regenerado.md`; ahora nada se
    escribe y la carrera desaparece por construcción.
    """
    resultados = [None, None]

    def _ver(i):
        resultados[i] = srv.check()

    hilos = [threading.Thread(target=_ver, args=(i,)) for i in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(120)
    for i, r in enumerate(resultados):
        assert r is not None, f"la verificación {i} no terminó"
    assert resultados[0]["ok"] == resultados[1]["ok"], (
        "verificaciones concurrentes discreparon: hay estado compartido"
    )


def test_la_escritura_explicita_regenera_donde_se_le_dice(tmp_path):
    """Criterio F de H2: `--doc` sigue disponible, y acepta una ruta fuera
    del repo — lo que antes rompía el envelope (`relative_to`). Idempotente:
    dos escrituras a la misma ruta producen los mismos bytes.
    """
    destino = tmp_path / "GOBIERNO.md"
    r1 = srv.escribir_doc(ruta=destino)
    assert r1["ok"], r1
    assert destino.is_file()
    assert isinstance(r1["bytes"], int) and r1["bytes"] > 0
    assert r1["written"] == str(destino).replace("\\", "/")

    r2 = srv.escribir_doc(ruta=destino)
    assert destino.read_text(encoding="utf-8") == srv.documento()
    assert r2["bytes"] == r1["bytes"]

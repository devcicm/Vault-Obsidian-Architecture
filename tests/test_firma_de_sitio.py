"""La baseline deja de mentir cuando el código se mueve.

Tres audits llevan una baseline que solo puede encoger, y las tres se indexaban
por `módulo:línea`. Ese índice tiene un defecto que costó tres verificaciones
manuales en una sola semana: **insertar diez líneas de comentario encima de un
sitio conocido lo reporta como nuevo y al viejo como resuelto**, sin que la
deuda haya cambiado. Y como `--freeze` legítimo y `--freeze` que esconde deuda
recién estrenada se teclean igual, lo único que los separaba era que alguien
ejecutase bien una receta de tres pasos.

Este fichero comprueba las dos mitades de la corrección:

* la firma **no** cambia cuando cambia lo que no importa (posición, comentarios,
  sangrado, comillas);
* la firma **sí** cambia cuando cambia el cuerpo del sitio, porque entonces la
  deuda congelada ya no es la misma deuda.

Y la mitad que faltaba: `--freeze` se niega a congelar deuda sin precedente.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_blame_audit as blame  # noqa: E402
import vault_error_contract as contrato  # noqa: E402
from vault_firma_sitio import (  # noqa: E402
    SCHEMA,
    firmar,
    firmar_todos,
    mapa_de_qualnames,
)


def _primer_handler(fuente: str):
    arbol = ast.parse(fuente)
    qualnames = mapa_de_qualnames(arbol)
    nodo = next(n for n in ast.walk(arbol) if isinstance(n, ast.ExceptHandler))
    return firmar("m.py", qualnames.get(id(nodo), ""), nodo)


BASE = '''
def leer(p):
    try:
        return p.read_text()
    except Exception:
        return []
'''

DESPLAZADO = "# ruido\n" * 12 + BASE

COMENTADO = '''
def leer(p):
    try:
        return p.read_text()
    except Exception:
        # esto no cambia lo que el intérprete hace
        return []
'''

REESCRITO_COSMETICO = '''
def leer(p):
    try:
        return p.read_text()
    except Exception:
        return list()
'''

CUERPO_DISTINTO = '''
def leer(p):
    try:
        return p.read_text()
    except Exception:
        return {}
'''

OTRA_FUNCION = '''
def escribir(p):
    try:
        return p.read_text()
    except Exception:
        return []
'''


def test_desplazar_el_sitio_no_cambia_su_firma():
    """El defecto original, en una línea: doce líneas arriba, misma deuda."""
    assert _primer_handler(BASE) == _primer_handler(DESPLAZADO)


def test_un_comentario_dentro_del_handler_no_cambia_su_firma():
    assert _primer_handler(BASE) == _primer_handler(COMENTADO)


def test_cambiar_el_cuerpo_si_cambia_la_firma():
    """Si el código que se tragaba el fallo ya no es el mismo, la deuda tampoco.

    `return []` y `return {}` son ambos infracciones de AP-51, pero no son la
    misma infracción: una baseline que las confundiera dejaría pasar una
    reescritura completa del handler como si nada hubiera cambiado.
    """
    assert _primer_handler(BASE) != _primer_handler(CUERPO_DISTINTO)


def test_el_mismo_handler_en_otra_funcion_es_otro_sitio():
    """La función contenedora es parte de la identidad, no decoración."""
    assert _primer_handler(BASE) != _primer_handler(OTRA_FUNCION)


def test_la_firma_no_es_el_texto_literal():
    """`return list()` y `return []` no son el mismo código para el intérprete.

    Se deja escrito para que quede claro qué normaliza `ast.unparse` y qué no:
    formato sí, construcciones equivalentes no. Un cambio de construcción es un
    cambio de código y merece revisarse.
    """
    assert _primer_handler(BASE) != _primer_handler(REESCRITO_COSMETICO)


def test_dos_sitios_identicos_en_la_misma_funcion_se_desempatan():
    fuente = '''
def leer(a, b):
    try:
        return a.x()
    except Exception:
        return []
    try:
        return a.x()
    except Exception:
        return []
'''
    arbol = ast.parse(fuente)
    qualnames = mapa_de_qualnames(arbol)
    handlers = [n for n in ast.walk(arbol) if isinstance(n, ast.ExceptHandler)]
    handlers.sort(key=lambda n: n.lineno)
    firmas = firmar_todos(("m.py", qualnames.get(id(h), ""), h) for h in handlers)
    assert len(set(firmas)) == 2, "dos sitios distintos no pueden compartir clave"
    assert firmas[1].endswith("#2")


# ── Las baselines reales ──────────────────────────────────────────────────────


def test_las_dos_baselines_estan_migradas():
    """Una baseline v1 en el repo dejaría los audits emitiendo MIGRATION_REQUIRED."""
    for path in (SCRIPTS / "blame-baseline.json",
                 SCRIPTS / "error-contract-baseline.json"):
        datos = json.loads(path.read_text(encoding="utf-8"))
        assert datos.get("schema") == SCHEMA, path.name
        # `sites` puede estar **vacío**: AP-52 saldó su deuda entera en v40.6.
        # Lo que no puede es tener el formato viejo — una lista de cadenas
        # `modulo:linea` haría que el audit emitiera MIGRATION_REQUIRED.
        assert all(isinstance(s, dict) and "firma" in s for s in datos["sites"])


def test_la_lista_v1_se_conserva_anotada():
    """No-derogación: la lista que se sustituye se anota, no se borra.

    Es también la única forma de auditar después si la migración perdió o
    inventó un sitio.
    """
    for path in (SCRIPTS / "blame-baseline.json",
                 SCRIPTS / "error-contract-baseline.json"):
        datos = json.loads(path.read_text(encoding="utf-8"))
        v1 = datos["sites_v1_superseded"]
        assert v1["superseded_by"] == "sites[].firma"
        assert v1["reason"].strip()
        assert len(v1["sites"]) >= len(datos["sites"]), (
            f"{path.name}: hay más sitios que en la lista v1 — la baseline "
            "creció, que es justo lo que no puede pasar"
        )


def test_los_audits_no_reportan_deuda_nueva_al_desplazar_codigo(tmp_path):
    """El caso completo, sobre el árbol real y no sobre un fragmento.

    Se copia el módulo, se le inyectan diez líneas y se comprueba que ningún
    audit reporta un solo sitio nuevo ni resuelto. Con el índice por línea esto
    devolvía cuatro de cada.
    """
    victima = SCRIPTS / "vault_code_sync.py"
    original = victima.read_bytes()
    try:
        victima.write_bytes(b"# ruido\n" * 10 + original)
        for modulo in (blame, contrato):
            resultado = modulo.scan()
            assert resultado["new_offenders"] == [], modulo.__name__
            assert resultado["resolved_since_baseline"] == [], modulo.__name__
    finally:
        victima.write_bytes(original)


def test_freeze_se_niega_a_congelar_deuda_sin_precedente():
    """La operación más peligrosa del repo, con freno.

    Se inyecta un handler que infringe AP-51 y se pide `--freeze` sin admitir
    nuevos: la tool tiene que negarse con `DEBT_WOULD_GROW` y **no** tocar la
    baseline. Se comprueba el hash del fichero antes y después.
    """
    victima = SCRIPTS / "vault_code_sync.py"
    baseline = SCRIPTS / "blame-baseline.json"
    original = victima.read_bytes()
    antes = baseline.read_bytes()
    inyectado = (
        "\n\ndef _sitio_de_prueba_ap51(p):\n"
        "    try:\n"
        "        return p.leer_algo_que_no_existe()\n"
        "    except Exception:\n"
        "        return []\n"
    ).encode("utf-8")
    try:
        victima.write_bytes(original + inyectado)
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "vault_blame_audit.py"), "--freeze"],
            capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT),
        )
        envelope = json.loads(proc.stdout.strip().splitlines()[0])
        assert envelope["ok"] is False
        assert envelope["error_code"] == "DEBT_WOULD_GROW"
        assert envelope["recovery"], "un error sin recuperación no le sirve a nadie"
        assert baseline.read_bytes() == antes, "la baseline se tocó pese a negarse"
    finally:
        victima.write_bytes(original)

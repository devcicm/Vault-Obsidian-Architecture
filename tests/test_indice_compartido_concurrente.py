"""El lost update de los índices compartidos, y su lock.

Cinco `*_save` hacían `load_index()` → mutar → `atomic_write_json()` sobre un
`.xxx-index.json` compartido, sin tramo exclusivo. `atomic_write_json` deja el
fichero íntegro y no hace **nada** contra esto: dos guardados concurrentes leen
el mismo índice, cada uno añade su entrada, gana el segundo, y la primera
desaparece con las dos tools devolviendo `ok: true`. Es AP-37 por la puerta de
atrás — trabajo perdido reportado como éxito.

La mitad peor es el correlativo: tres de esos índices son además el contador
(`len(index["bugs"]) + 1`). Sin lock, dos guardados reservan el mismo número,
componen el mismo nombre de fichero y uno pisa la nota del otro.

Estas pruebas no leen el código: lanzan escrituras a la vez y cuentan lo que
sobrevivió. Es el criterio del consumidor y no el propio (AP-44) — un test que
comprobara "existe un `with file_lock`" pasaría igual con el lock puesto en el
sitio equivocado.
"""

import ast
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vault_io import indice_compartido  # noqa: E402

HILOS = 12


def _anadir(destino: Path, n: int) -> None:
    with indice_compartido(destino, {"entradas": []}) as indice:
        indice["entradas"].append({"n": n})


def test_ninguna_entrada_se_pierde_con_escrituras_simultaneas(tmp_path):
    """El lost update, medido: se cuentan las que sobrevivieron."""
    destino = tmp_path / "indice.json"
    with ThreadPoolExecutor(max_workers=HILOS) as pool:
        list(pool.map(lambda n: _anadir(destino, n), range(HILOS)))

    entradas = json.loads(destino.read_text(encoding="utf-8"))["entradas"]
    assert len(entradas) == HILOS, f"se perdieron {HILOS - len(entradas)}"
    assert sorted(e["n"] for e in entradas) == list(range(HILOS))


def test_el_correlativo_derivado_del_indice_no_se_repite(tmp_path):
    """La mitad peor: el número sale del mismo tramo exclusivo que lo consume.

    Reproduce lo que hacen `bug`, `requirement` y `test`: derivar el
    correlativo de la longitud del índice y guardarlo en la misma región.
    """
    destino = tmp_path / "correlativo.json"

    def reservar(_):
        with indice_compartido(destino, {"items": []}) as indice:
            numero = len(indice["items"]) + 1
            indice["items"].append({"id": f"REQ-{numero:03d}"})
            return numero

    with ThreadPoolExecutor(max_workers=HILOS) as pool:
        numeros = list(pool.map(reservar, range(HILOS)))

    assert sorted(numeros) == list(range(1, HILOS + 1)), f"repetidos: {numeros}"
    ids = [i["id"] for i in json.loads(destino.read_text(encoding="utf-8"))["items"]]
    assert len(set(ids)) == HILOS, f"ids duplicados: {ids}"


def test_sin_cambios_no_se_escribe(tmp_path):
    """AP-36/AP-37: las rutas de error salen del `with` sin tocar el disco.

    Tres de los cinco tienen un `return` temprano dentro de la región. Un
    `with` sale por ahí de forma normal, así que sin esta regla el camino de
    fallo estrenaría un side-effect que no tenía.
    """
    destino = tmp_path / "intacto.json"
    with indice_compartido(destino, {"entradas": []}):
        pass
    assert not destino.exists()

    destino.write_text('{"entradas": [{"n": 1}]}', encoding="utf-8")
    antes = destino.stat().st_mtime_ns
    with indice_compartido(destino, {"entradas": []}) as indice:
        _ = indice["entradas"]  # leer no es mutar
    assert destino.stat().st_mtime_ns == antes


def test_el_vacio_no_se_comparte_entre_llamadas(tmp_path):
    """Ceder el mismo objeto haría que la segunda llamada viera lo de la primera."""
    vacio = {"entradas": []}
    with indice_compartido(tmp_path / "a.json", vacio) as a:
        a["entradas"].append({"n": 1})
    with indice_compartido(tmp_path / "b.json", vacio) as b:
        assert b["entradas"] == []
    assert vacio == {"entradas": []}


#: Los ocho módulos que hacían leer-modificar-escribir sobre un índice
#: compartido. Cinco son `*_save`; los otros tres salieron al barrer los 114
#: scripts en vez de quedarme en los diecisiete, que es donde había empezado a
#: mirar. El defecto nunca fue "de los saves": fue de quien comparte un índice.
CONSUMIDORES = [
    "vault_ai_decision",
    "vault_bug_save",
    "vault_code_module",
    "vault_code_relation",
    "vault_infra_save",
    "vault_pattern_save",
    "vault_requirement_save",
    "vault_test_save",
]

#: Nombres que escriben un índice compartido. Un módulo puede *definirlos*
#: —quedan anotados `superseded_by:`, no se borran— pero no *llamarlos*.
ESCRITORES_SUELTOS = {"save_index", "save_pattern_index"}


def _llamadas(arbol: ast.AST) -> set:
    """Los nombres efectivamente invocados, no los que aparecen en el texto."""
    return {
        n.func.id
        for n in ast.walk(arbol)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }


@pytest.mark.parametrize("script", CONSUMIDORES)
def test_los_ocho_consumen_el_tramo_exclusivo(script):
    """Que ninguno vuelva a escribir su índice por fuera del helper.

    No sustituye a los tests de arriba —comprueba forma, no efecto— pero caza
    la regresión concreta: alguien reintroduce un `save_index(index)` suelto y
    el lock deja de cubrir.

    Mira **llamadas**, no texto. La primera versión buscaba el literal
    `atomic_write_json(_index_file()` y fallaba en cuatro de los cinco por los
    helpers que quedaron huérfanos: siguen definidos porque no se derogan, y
    un test que lea el fichero como una cadena no distingue "está escrito" de
    "se ejecuta". Es el mismo error que AP-44 describe, cometido en el test.
    """
    arbol = ast.parse(
        (REPO_ROOT / "scripts" / f"{script}.py").read_text(
            encoding="utf-8", errors="replace"
        )
    )
    llamadas = _llamadas(arbol)
    assert "indice_compartido" in llamadas, f"{script} no usa el tramo exclusivo"
    sueltos = llamadas & ESCRITORES_SUELTOS
    assert not sueltos, f"{script} escribe su índice por fuera del lock: {sueltos}"


@pytest.mark.parametrize("script", CONSUMIDORES)
def test_lo_huerfano_queda_anotado_y_no_borrado(script):
    """No-derogación: el helper sin llamantes se anota, no desaparece.

    Sostiene la otra mitad del test de arriba. Sin esto, la forma más cómoda
    de hacerlo pasar sería borrar los helpers, que es justo lo que la política
    de no-derogación prohíbe.
    """
    fuente = (REPO_ROOT / "scripts" / f"{script}.py").read_text(
        encoding="utf-8", errors="replace"
    )
    arbol = ast.parse(fuente)
    llamadas = _llamadas(arbol)
    huerfanos = [
        f.name
        for f in ast.walk(arbol)
        if isinstance(f, ast.FunctionDef)
        and f.name.startswith(("load_index", "save_index", "load_pattern_index",
                               "save_pattern_index"))
        and f.name not in llamadas
    ]
    assert huerfanos, f"{script} no conserva ningún helper anterior"
    assert fuente.count("superseded_by: vault_io.indice_compartido") == len(
        huerfanos
    ), f"{script}: {len(huerfanos)} huérfanos y anotaciones que no cuadran"

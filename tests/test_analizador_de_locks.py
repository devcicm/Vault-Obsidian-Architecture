"""4.1 — lo que el escáner de carreras comprueba y lo que NO comprueba.

El escáner de `cli/analyzer.py` pregunta al AST si la función **usa** un
lock (`file_lock(...)`, `self.lock`, `with lock:`). Desde v40.30 un
comentario que mencionara `file_lock` ya no cuenta —comprobado contra la
fuente, no contra el texto—, que fue lo que arregló la nota «Concurrency
scanner recognizes lock text in a comment».

Lo que sigue NO lo comprueba, y aquí queda fijado con fixtures **negativas**
—casos que el escáner NO ve, para que nadie lo lea como una garantía que
no da:

- el **orden**: un lock adquirido *después* de la escritura cuenta igual;
- el **recurso**: un lock sobre otro fichero cuenta igual;
- la **sección crítica**: un lock cerrado antes de la escritura cuenta igual;
- los **helpers**: un lock dentro de la función llamada no se ve, y eso es un
  falso positivo (RC-01 salta sobre un escritor que sí está protegido).

Un análisis estático no puede saber cuál de esas cuatro cosas pasa. Lo que
puede —y debe— es decirlo. Aquí se fija el comportamiento real y se
documenta el límite en el propio escáner.
"""

from __future__ import annotations

import sys
from pathlib import Path

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

from cli import analyzer  # noqa: E402


def _analizar(tmp_path: Path, fuente: str):
    """Analiza un fragmento y devuelve sus códigos de hallazgo."""
    ruta = tmp_path / "vacio.py"
    ruta.write_text(fuente, encoding="utf-8")
    return {i.code for i in analyzer.scan_file(ruta)}


ESCRIBE = '''
from pathlib import Path

def escribe(datos):
    ruta = Path("99_Index/search-index.json")
    ruta.write_text(datos)
'''


def test_un_lock_posterior_a_la_escritura_cuenta_igual(tmp_path):
    """El escáner no mira el orden: el lock va después y la escritura antes."""
    codigos = _analizar(tmp_path, f'''
    with file_lock(ruta):
        pass
''')
    # RC-01 no salta: hay un lock en el ámbito de la función.
    assert "RC-01" not in codigos, codigos


def test_un_lock_sobre_otro_recurso_cuenta_igual(tmp_path):
    """El lock protege otro fichero: el escáner no lo distingue."""
    codigos = _analizar(tmp_path, '''
from pathlib import Path

def escribe(datos):
    ruta = Path("99_Index/search-index.json")
    otro = Path("00_System/otro.json")
    with file_lock(otro):
        ruta.write_text(datos)
''')
    assert "RC-01" not in codigos, codigos


def test_un_lock_cerrado_antes_de_la_escritura_cuenta_igual(tmp_path):
    """La sección crítica no cubre la escritura: el escáner no lo mide."""
    codigos = _analizar(tmp_path, '''
from pathlib import Path

def escribe(datos):
    ruta = Path("99_Index/search-index.json")
    with file_lock(ruta):
        pass
    ruta.write_text(datos)
''')
    assert "RC-01" not in codigos, codigos


def test_un_lock_en_el_llamador_no_cubre_el_helper(tmp_path):
    """Falso positivo conocido: el lock está fuera de quien escribe.

    `escribe` bloquea y llama a `_escribir`, que es la que escribe. El
    escáner analiza cada función por separado: en `_escribir` no hay lock, y
    RC-01 salta sobre un escritor que sí está protegido (el lock lo tiene
    quien llama). Un análisis estático no puede seguir la llamada.
    """
    codigos = _analizar(tmp_path, '''
from pathlib import Path

def escribe(datos):
    with file_lock(Path("99_Index/search-index.json")):
        _escribir(datos)

def _escribir(datos):
    ruta = Path("99_Index/search-index.json")
    ruta.write_text(datos)
''')
    assert "RC-01" in codigos, (
        "el escáner no ve el lock del llamador: RC-01 salta sobre un escritor "
        "que sí está protegido. Es un falso positivo conocido y declarado.")


def test_un_comentario_que_nombra_el_lock_no_cuenta(tmp_path):
    """Lo que sí se arregló: un comentario no es un lock (v40.30)."""
    codigos = _analizar(tmp_path, '''
from pathlib import Path

def escribe(datos):
    ruta = Path("99_Index/search-index.json")
    # aquí habría un file_lock(), pero no lo hay
    ruta.write_text(datos)
''')
    assert "RC-01" in codigos, codigos


def test_el_limite_esta_documentado_en_el_escaner():
    """El límite se escribe donde se lee: no basta con que el test lo sepa."""
    fuente = (REPO_ROOT / "cli" / "analyzer.py").read_text(encoding="utf-8")
    assert "no comprueba" in fuente.lower(), (
        "el escáner no declara qué no comprueba (orden, recurso, sección "
        "crítica, helpers): quien lo lea lo toma por una garantía")

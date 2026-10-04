"""Hub, índice maestro y migajas navegan por enlaces que resuelven (AP-21 precisado).

Medido el 2026-10-04 en la QA de producto: el hub —«punto único de
navegación»— nombraba el índice de cada sección en código, el índice maestro
igual, y la migaja de cada índice ponía el maestro y la sección padre en
cursiva (a la del padre le faltaba el cierre). La tabla de subcarpetas pedía
abrir `{folder}/{subcarpeta}/index.md` a mano, con las llaves sin sustituir.
Nada de eso se podía pulsar.

`index` es un nombre que comparten todas las secciones, así que el enlace va
con la ruta entera, que es la carpeta necesaria que `ruta_necesaria` admite.
Y solo se enlaza un índice que existe o que la misma ejecución escribe: un
enlace a un índice que no llega a existir es un enlace roto.

Los enlaces se comprueban con el criterio de Obsidian —nombre de fichero y
sufijos de ruta—, no con el del generador (AP-44).
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from vault.indices.seccion import RE_ALIAS_EN_TABLA, RenderizadorDeIndice, migaja  # noqa: E402
from vault_lib import indice_de_nombres, resolver_wikilink  # noqa: E402
from vault_registry import ORDERED_SECTIONS  # noqa: E402

RE_ENLACE = re.compile(r"\[\[([^\]|#]+)")


def _correr(raiz, *argv):
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               VAULT_AGENT="probe", PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, str(SCRIPTS / argv[0]), *argv[1:]],
                   capture_output=True, env=env, timeout=300, check=True)


@pytest.fixture(scope="module")
def vault(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("navegacion")
    _correr(raiz, "vault_init.py", "--no-audit")
    _correr(raiz, "vault_write.py", "--folder", "02_Observability/errors",
            "--title", "Error X", "--tags", "errores", "--content",
            "Algo falló en producción.\nSe reproduce con carga alta.\n"
            "La causa fue un timeout del pool.\n")
    return raiz


def _leer(raiz, rel):
    return (raiz / rel).read_text(encoding="utf-8")


def test_el_hub_enlaza_el_indice_de_cada_seccion_y_el_maestro(vault):
    """El hub lo crea `vault_init` dentro de una regeneración completa: si lo
    creara el primer andamio, solo enlazaría la sección de ese andamio y,
    como el hub no se reescribe, se quedaría así para siempre."""
    hub = _leer(vault, "00_System/vault-hub.md")
    for seccion in ORDERED_SECTIONS:
        assert f"[[{seccion}/index|índice]]" in hub, seccion
    assert "[[99_Index/index|Índice maestro]]" in hub
    assert "`99_Index/index.md` (Índice Maestro)" not in hub


def test_el_maestro_y_las_migajas_enlazan_y_las_subcarpetas_tambien(vault):
    maestro = _leer(vault, "99_Index/index.md")
    assert "[[02_Observability/index|índice]]" in maestro
    seccion = _leer(vault, "02_Observability/index.md")
    assert "[[99_Index/index|Índice maestro]]" in seccion
    assert "| `02_Observability/errors/` | [[02_Observability/errors/index|índice]] |" in seccion
    assert "{folder}" not in seccion and "{subcarpeta}" not in seccion
    sub = _leer(vault, "02_Observability/errors/index.md")
    assert "[[02_Observability/index|02_Observability]]" in sub
    for texto in (maestro, seccion, sub):
        assert RE_ALIAS_EN_TABLA.search(texto) is None


def test_todo_enlace_de_navegacion_resuelve_a_una_sola_nota(vault):
    """Criterio del consumidor: el índice de nombres de Obsidian, no el
    generador. Un enlace a un índice inexistente o a `[[index]]` falla aquí."""
    relativas = [p.relative_to(vault) for p in vault.rglob("*.md")]
    indice = indice_de_nombres(relativas)
    fuentes = ["00_System/vault-hub.md", "99_Index/index.md"] + [
        str(p.relative_to(vault)) for p in vault.rglob("index.md")]
    for rel in fuentes:
        for bruto in RE_ENLACE.findall(_leer(vault, rel)):
            ruta, candidatos = resolver_wikilink(bruto, Path(rel), indice)
            assert ruta, (rel, bruto, candidatos)


def test_sin_indice_maestro_la_migaja_no_lo_enlaza(tmp_path):
    """Un `vault_section_index` suelto en un vault sin maestro no inventa el
    enlace: lo nombra en texto hasta que el maestro exista."""
    (tmp_path / "07_Knowledge").mkdir()
    _correr(tmp_path, "vault_section_index.py", "--folder", "07_Knowledge")
    texto = _leer(tmp_path, "07_Knowledge/index.md")
    assert "_99_Index/index.md_" in texto
    assert "[[99_Index/index" not in texto
    hub = _leer(tmp_path, "00_System/vault-hub.md")
    assert "[[07_Knowledge/index|índice]]" in hub
    assert "[[01_Projects/index" not in hub


def test_el_renderizador_sin_predicado_no_enlaza_indices():
    """Dominio puro: sin saber qué existe, ningún índice se enlaza."""
    r = RenderizadorDeIndice(lambda k: "d", lambda k: "", lambda s: s)
    texto = r.render("02_Observability", [], "AHORA",
                     subcarpetas=["02_Observability/errors"])
    assert "/index|" not in texto
    assert "| `02_Observability/errors/` | `02_Observability/errors/index.md` |" in texto
    assert migaja("02_Observability/errors").endswith("_02_Observability/index.md_")

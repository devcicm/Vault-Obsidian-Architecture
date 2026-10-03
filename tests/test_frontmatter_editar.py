"""AP-46: el dueño del frontmatter también edita, no solo crea.

Los editores —revocar una preferencia, marcar una propagación, anotar una
fusión, añadir una norma— montaban el bloque a mano con su propio escapado.
`Frontmatter.editar` es el mismo dueño en modo edición: conserva lo que no toca
y reemplaza en su sitio lo que sí, sin dejar una clave duplicada. El criterio
es el del consumidor (AP-44): `yaml.safe_load` del bloque resultante.
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402

BLOQUE = 'title: "a: b #c"\ntags:\n- uno\n- dos\nnotas: |\n  linea\nn: 1\n\n'


def _leer(fm: Frontmatter) -> dict:
    texto = fm.render()
    assert texto.startswith("---\n") and texto.endswith("\n---")
    return yaml.safe_load(texto[4:-4])


def test_editar_conserva_lo_que_no_toca_linea_a_linea():
    fm = Frontmatter.editar(BLOQUE)
    assert fm.render() == "---\n" + BLOQUE.rstrip("\n") + "\n---"


def test_set_reemplaza_la_clave_y_su_continuacion_en_su_sitio():
    fm = Frontmatter.editar(BLOQUE).set("tags", ["tres"]).set("notas", "otra")
    datos = _leer(fm)
    assert datos == {"title": "a: b #c", "tags": ["tres"], "notas": "otra", "n": 1}
    claves = [l.split(":")[0] for l in fm.campos() if l[:1] not in (" ", "-")]
    assert claves == ["title", "tags", "notas", "n"]


def test_set_de_una_clave_nueva_va_al_final_y_texto_sigue_siendo_texto():
    datos = _leer(Frontmatter.editar(BLOQUE).set("fecha", "2026-10-02", texto=True))
    assert datos["fecha"] == "2026-10-02" and list(datos)[-1] == "fecha"


def test_una_clave_no_se_confunde_con_otra_que_empieza_igual():
    fm = Frontmatter.editar("n: 1\nn_total: 2").set("n", 5)
    assert _leer(fm) == {"n": 5, "n_total": 2}


def test_quitar_retira_la_clave_con_su_lista():
    assert _leer(Frontmatter.editar(BLOQUE).quitar("tags").quitar("nada")) == {
        "title": "a: b #c", "notas": "linea\n", "n": 1}


def test_un_bloque_vacio_se_puede_editar():
    assert Frontmatter.editar("").set("k", "v").render() == "---\nk: v\n---"


def test_crear_dos_veces_la_misma_clave_no_la_duplica():
    assert Frontmatter().set("a", 1).set("a", 2).render() == "---\na: 2\n---"

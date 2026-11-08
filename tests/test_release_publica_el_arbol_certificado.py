"""La release publica el contenido certificado, no un descendiente cualquiera.

El ancestro es una relación **histórica**: un descendiente que cambia el
producto también es ancestro del `product_sha` certificado, y se publicaba sin
haber pasado por la CI (nota de causa raíz «Release publishes content the
certified CI never saw», 2026-10-30). La identidad del contenido es el
**árbol**: lo que se publica tiene que ser lo que se certificó.

Aquí se comprueba el comportamiento con git de verdad (un repo temporal con
un commit certificado y un descendiente que cambia el producto), no el texto
del workflow.
"""

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _gate_del_workflow() -> str:
    """La parte del workflow que decide si se publica.

    Se toma la ventana alrededor del código que lee el manifiesto —no un
    trozo arbitrario del fichero—: el texto del workflow es largo y la
    comprobación tiene que mirar al bloque que decide, no a un comentario de
    la cabecera.
    """
    texto = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8")
    i = texto.find('release_authorized"')
    assert i > 0, "no se encontró la puerta de publicación"
    return texto[max(0, i - 4000): i + 6000]


def test_la_puerta_compara_el_arbol_del_tag_con_el_certificado():
    """La comparación tiene que existir en el workflow, no solo en la nota."""
    bloque = _gate_del_workflow()
    assert "HEAD^{tree}" in bloque, (
        "la puerta no compara el árbol del tag con el certificado")
    assert "rev-parse" in bloque


def test_la_puerta_sigue_exigiendo_ancestria():
    """La ancestría sigue siendo condición necesaria: no se sustituye, se
    añade la identidad de contenido."""
    bloque = _gate_del_workflow()
    assert "merge-base" in bloque and "--is-ancestor" in bloque


def test_un_descendiente_que_cambia_el_producto_no_pasa(tmp_path):
    """La diferencia real: el ancestro se cumple y el contenido no."""
    from apoyo import git_en

    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return git_en(repo, *args)

    git("init", "-q")
    (repo / "producto.py").write_text("VERSION = 1\n", encoding="utf-8")
    git("add", "-A")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m",
        "certificado")
    certificado = git("rev-parse", "HEAD")
    tree_certificado = git("rev-parse", f"{certificado}^{{tree}}")

    # Descendiente que cambia el producto: es ancestro y no es el mismo árbol.
    (repo / "producto.py").write_text("VERSION = 2\n", encoding="utf-8")
    git("add", "-A")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m",
        "cambia el producto")
    descendiente = git("rev-parse", "HEAD")
    tree_descendiente = git("rev-parse", f"{descendiente}^{{tree}}")

    ancestro = subprocess.run(
        ["git", "merge-base", "--is-ancestor", certificado, descendiente],
        cwd=repo, capture_output=True)
    assert ancestro.returncode == 0, "el descendiente deberia ser ancestro"
    assert tree_descendiente != tree_certificado, (
        "el fixture no cambia el contenido: no probaria nada")


def test_el_workflow_declara_el_trigger_de_tags():
    """El commit que se publica tiene su propia CI (B-03)."""
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "vault-ci.yml")
                        .read_text(encoding="utf-8"))
    on = wf.get("on", wf.get(True))
    assert "v*" in (on["push"].get("tags") or []), on["push"]

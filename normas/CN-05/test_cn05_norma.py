"""CN-05 desde su paquete: la entrada que sirve el catálogo es la de aquí.

Sin fixtures: lo ejecuta `tests/test_normas_paquete.py`, que es lo que corren
la CI y el `Makefile`, y también `pytest normas/`.
"""

import ast
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
for _ruta in (RAIZ / "scripts", RAIZ):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))


def _norma():
    arbol = ast.parse((Path(__file__).parent / "norma.py").read_text(encoding="utf-8"))
    return next(ast.literal_eval(n.value) for n in arbol.body
                if isinstance(n, ast.Assign) and n.targets[0].id == "NORMA")


#: El cuerpo que se copia en los dos módulos del árbol de prueba. Es el mismo
#: texto en los dos, con nombres de fichero distintos: la copia con el nombre
#: cambiado es la que se cuela sin que nadie la mire.
CUERPO = '''
def _lee_indice(ruta):
    if not ruta.is_file():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))
'''


def _arbol(tmp_path):
    """Un repo mínimo con dos módulos y el mismo cuerpo."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for nombre in ("uno.py", "dos.py"):
        (scripts / nombre).write_text("import json\n" + CUERPO, encoding="utf-8")
    return scripts


def test_cn05_el_catalogo_sirve_la_entrada_del_paquete():
    import vault_norms_catalog

    assert vault_norms_catalog.norma_por_codigo("CN-05") == _norma()


def test_cn05_las_tools_que_declara_existen():
    import vault_grafo_import

    norma = _norma()
    for campo in ("tools_enforcing", "tools_detecting", "tools_del_patron"):
        for tool in norma.get(campo, []):
            modulo = tool.split()[0].split(".")[0]
            assert vault_grafo_import.fuente_de(modulo).is_file(), tool


def test_cn05_no_declara_una_herencia_imposible():
    """`distinguido_de` que nombra una norma que no existe es ruido."""
    from vault_norms_catalog import NORM_CATALOG

    norma = _norma()
    conocidos = {n["code"] for n in NORM_CATALOG}
    for code in norma.get("distinguido_de", {}):
        assert code in conocidos, code


def test_cn05_un_clon_entre_modulos_se_declara():
    import vault_clones

    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        _arbol(raiz)
        r = vault_clones.check(raiz=raiz, baseline=raiz / "baseline.json")
    assert r["ok"] is False
    assert r["new_clones"], r
    assert r["new_shadowing"] == []


def test_cn05_una_sombra_dentro_de_un_modulo_se_declara():
    import vault_clones

    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        scripts = raiz / "scripts"
        scripts.mkdir()
        (scripts / "uno.py").write_text(
            "def _lee():\n    return 1\n\n\ndef _lee():\n    return 2\n", encoding="utf-8")
        r = vault_clones.check(raiz=raiz, baseline=raiz / "baseline.json")
    assert r["new_shadowing"], r


def test_cn05_la_baseline_solo_encoge():
    import vault_clones

    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        scripts = _arbol(raiz)
        baseline = raiz / "baseline.json"

        # Congelar deuda nueva sin `--admitir-nuevos` se niega, y no escribe nada.
        negada = vault_clones.freeze(raiz=raiz, baseline=baseline)
        assert negada["ok"] is False
        assert negada["error_code"] == "DEBT_WOULD_GROW"
        assert not baseline.exists()

        # Con `--admitir-nuevos` se congela. El sitio queda **sin motivo**, y la
        # puerta falla hasta que alguien escribe por qué se queda: una excepción
        # sin dueño no es una excepción.
        congelada = vault_clones.freeze(admitir_nuevos=True, raiz=raiz, baseline=baseline)
        assert congelada["ok"] is True
        r = vault_clones.check(raiz=raiz, baseline=baseline)
        assert r["new_clones"] == []
        assert r["sites_without_motive"], r

        # Se paga el duplicado: uno de los dos módulos deja de existir. El sitio
        # congelado sale como resuelto y la cuenta baja.
        (scripts / "dos.py").unlink()
        r = vault_clones.check(raiz=raiz, baseline=baseline)
    assert r["ok"] is True
    assert r["resolved_since_baseline"], r

"""Qué cuenta como escribir, medido por AST (deuda #3, primera parte).

`_LLAMADAS_DE_ESCRITURA` era una lista de nombres de método. Incluía `replace`,
que también es `str.replace`, y `write_report`, que lee el ledger de
escrituras y no escribe nada. Las dos guardas que la usan —la frontera del
Meta-toolkit y la escritura sin lock tras un timeout— marcaban como escritura
cualquier `texto.replace("a", "b")`. Antes de decidir qué contexto puede
escribir dónde, la medida de «escribe» tiene que ser cierta.
"""

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import vault_arch  # noqa: E402


def _llamada(codigo: str):
    return vault_arch.llamada_de_escritura(ast.parse(codigo).body[0].value)


def test_str_replace_no_es_escribir():
    assert _llamada('"07_Knowledge/x".replace("x", "y")') is None
    assert _llamada('texto.replace("a", "b", 1)') is None
    # Medido en scripts/: trece de los quince `replace` de un argumento
    # que quedaban eran `datetime.replace(tzinfo=...)`.
    assert _llamada("dt.replace(tzinfo=UTC)") is None
    assert _llamada("tmp.replace(target=destino)") == "replace"


def test_path_replace_y_os_replace_si_lo_son():
    assert _llamada("tmp.replace(destino)") == "replace"
    assert _llamada("os.replace(tmp, destino)") == "replace"


def test_write_report_lee_el_ledger_y_no_escribe():
    assert _llamada("write_report()") is None
    assert _llamada("vault_ledger.write_report()") is None


def test_lo_que_escribe_sigue_contando():
    for codigo, nombre in (("p.write_text(t)", "write_text"),
                           ("atomic_write_text(p, t)", "atomic_write_text"),
                           ("shutil.rmtree(p)", "rmtree"),
                           ("p.mkdir(parents=True)", "mkdir")):
        assert _llamada(codigo) == nombre


def test_las_guardas_usan_el_predicado():
    """Una sola definición: las dos guardas no comparan nombres por su cuenta."""
    fuente = Path(vault_arch.__file__).read_text(encoding="utf-8")
    assert fuente.count("in _LLAMADAS_DE_ESCRITURA") == 1

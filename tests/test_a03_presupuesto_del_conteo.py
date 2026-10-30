"""A-03 — el conteo de la suite cabe en su presupuesto con margen declarado.

`vault_doc_counts` cuenta los tests con un `pytest --collect-only` completo
(54,6 s medidos) y la tool se mataba con el techo genérico de 60 s. El
presupuesto propio y la fracción máxima que lo medido puede ocupar viven en la
tool; este test falla si la tool deja de pasarlo a `wrap_main` o si el coste
medido se acerca al presupuesto.
"""
import ast
from pathlib import Path

import vault_grafo_import as gi



def test_la_holgura_del_conteo_esta_declarada_y_es_la_que_se_mide():
    import vault_doc_counts as m
    assert m.COLECCION_MEDIDA_S <= m.FRACCION_MAXIMA_DEL_PRESUPUESTO * m.PRESUPUESTO_S
    assert m.PRESUPUESTO_S > 60, "mas que el techo generico que se medio justo"


def test_la_tool_pasa_su_presupuesto_a_wrap_main():
    arbol = ast.parse(gi.codigo_de(
        Path(gi.DIRECTORIO) / "vault_doc_counts.py").read_text(encoding="utf-8"))
    llamadas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call)
                and getattr(n.func, "id", "") == "wrap_main"]
    assert llamadas, "vault_doc_counts ya no llama a wrap_main"
    assert any(k.arg == "timeout" and getattr(k.value, "id", "") == "PRESUPUESTO_S"
               for c in llamadas for k in c.keywords)

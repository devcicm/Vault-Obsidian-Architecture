"""`fix_whitespace_in_links` resuelve en tiempo lineal una tirada de `[[` sin cierre.

El barrido de `test_filtro_de_expresiones_regulares` cayó en rojo el
2026-10-03 con `vault/kernel/regex.py`: `\[\[([^\]]+)\]\]` tardaba 107 ms
con 2.000 caracteres hostiles. El interior `[^\]]+` aceptaba `[`, así que desde
cada `[[` se recorría la cadena entera: cuadrático (12 ms con 2.000 caracteres,
204 ms con 8.000). La función limpia cada nota que entra por `vault_io`, así
que la entrada la elige quien escribe la nota (AP-51: una tool colgada no
distingue «tardo» de «no hay nada»).

El cebo es de 40.000 caracteres para que la diferencia entre lineal y
cuadrático quede órdenes de magnitud por encima del ruido de la máquina: el
patrón cuadrático tarda segundos y el lineal, menos de un milisegundo.
"""

import time

from vault.kernel.regex import fix_whitespace_in_links


def test_una_tirada_de_corchetes_sin_cierre_no_es_cuadratica():
    cebo = "[[" * 20_000
    inicio = time.perf_counter()
    assert fix_whitespace_in_links(cebo) == cebo
    assert time.perf_counter() - inicio < 0.5


def test_el_espacio_dentro_del_link_se_sigue_colapsando():
    assert fix_whitespace_in_links("ver [[  mapa   de   codigo  ]] y [[]]") == \
        "ver [[mapa de codigo]] y [[]]"

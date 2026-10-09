#!/usr/bin/env python3
"""vault.kernel.escalon — dónde corta una distribución de conteos. Nada más.

Módulo hoja: **no importa ningún `vault_*`** (AP-62). Vivió en
`scripts/vault_kernel.py` hasta 2026-10-09; sale de allí porque tiene dos
consumidores en contextos distintos —el núcleo del **repo** sobre el grafo de
imports (`vault_kernel`, K2) y el núcleo de un **vault** sobre el grafo de
enlaces (`vault_audit`, deuda #11)— y dos definiciones de «alto» serían dos
criterios sin dueño (AP-57). `vault_kernel.escalon` sigue importable y es el
mismo objeto.
"""

from typing import Optional, Sequence, Tuple


def escalon(valores: Sequence[int]) -> Tuple[Optional[int], Optional[float]]:
    """El valor por encima de la mayor caída relativa de la distribución.

    Devuelve `(umbral, ratio)`. Se ignoran los ceros: una caída a cero tiene
    ratio infinito y se llevaría siempre el máximo, dejando el umbral pegado al
    valor más pequeño distinto de cero.

    **Y solo cuenta como caída la que deja un hueco (v40.34).** Entre dos
    enteros consecutivos —2 → 1, 5 → 4— no cabe ningún valor, así que su ratio
    mide la cuantización del conteo y no un corte; y 2/1 = 2.0 existe en casi
    toda distribución de fan-in. Bastaba con que un módulo legítimo llegara a
    fan-in 37 —partiendo el hueco 72 ‖ 27 en dos caídas de 1.95 y 1.37— para
    que 2/1 ganara, el umbral cayera de 72 a 2 y doce módulos con dos o tres
    importadores salieran como `nucleo_no_declarado`. No se ignoran los unos:
    en {12, 1} el corte 12 ‖ 1 es real y tiene hueco. El umbral derivado puede
    oscilar al crecer el repo; lo que no puede es colapsar al suelo de la escala.

    Sin ninguna caída con hueco devuelve `(None, None)`: no hay corte, y
    fabricar uno sería inventar un núcleo que la distribución no tiene.
    """
    v = sorted({x for x in valores if x > 0}, reverse=True)
    con_hueco = [j for j in range(len(v) - 1) if v[j] - v[j + 1] > 1]
    if not con_hueco:
        return None, None
    i = max(con_hueco, key=lambda j: v[j] / v[j + 1])
    return v[i], round(v[i] / v[i + 1], 3)

"""Estándar: la gobernanza del propio repo que no tiene tool en el catálogo.

Carriles, perfil y alcance de la suite, firma de sitio de las baselines y el
contrato de campos con los consumidores. Lo usan las puertas y la suite de este
repo; quien instala el toolkit no lo ejecuta nunca, así que no viaja.

B-3 de la reestructura (2026-10-31): `modulos_fuera_de_la_wheel` sale de las
tools de `gobernanza_del_estandar`, y estos módulos, sin tool propia, viajaban
en la wheel sin que nadie lo decidiera. El subpaquete no está en `packages` de
`pyproject.toml`, y `vault_servicio.SUBPAQUETES_FUERA_DE_LA_WHEEL` lo declara para
que el hook del build y la puerta lo vean. Sigue siendo el contexto
meta_toolkit: un contexto nuevo estrenaría cruces con todo lo que lo mide. Las
rutas viejas quedan como alias en `sys.modules` (no-derogación) y salen de la
wheel con su dueño.
"""

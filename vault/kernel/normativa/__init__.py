"""Normativa: el lenguaje compartido que el kernel publica sobre las notas.

Catálogos de normas, fundamentos y penalizaciones, gramática de Mermaid,
contrato de nota y vocabulario. Siguen siendo kernel —los habla cualquier
contexto y no dependen de ningún dominio—, pero no son infraestructura: viven
aparte de raíz, fs, errores y puertos para que el núcleo puro se lea como tal.

B-1 de la reestructura (2026-10-31): sacarlos a un contexto propio sumaba seis
pares de cruce al `PRESUPUESTO_DE_CRUCES`, porque todos los contextos los
consumen. Un subpaquete dentro del kernel separa sin cruzar. Las rutas viejas
`vault/kernel/<x>.py` se conservan como alias en `sys.modules` (no-derogación).
"""

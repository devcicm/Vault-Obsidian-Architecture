"""Contexto **Índices**: qué notas existen y cómo se encuentran.

Lenguaje ubicuo: índice, entrada, término, sección indexada, carpeta registrada.
El dueño del dato es este contexto: `99_Index/` entero y los registros de
`00_System/` que describen la forma del vault (`custom-folders.json`,
`tag-registry.json`) son suyos, y nadie más debería escribirlos.

Lo que lo hacía frágil no era el algoritmo sino la **resolución de rutas**: ocho
constantes derivadas de `VAULT_ROOT` en tiempo de import (AP-49) repartidas entre
cuatro módulos, cada una calculando por su cuenta dónde vive el índice. Con la
raíz inyectada, dos vaults pueden reindexarse en el mismo intérprete sin
contaminarse — que es la prueba de que la inyección no es decorativa.
"""

from .coherencia import coherencia_indice
from .enumeracion import es_nota_indexable, notas_en_disco
from .repositorio import RepositorioIndices

__all__ = [
    "RepositorioIndices",
    "coherencia_indice",
    "es_nota_indexable",
    "notas_en_disco",
]

"""Shared kernel: el vocabulario que todos los contextos hablan.

No es un contexto de dominio. Es lo único de lo que cualquiera puede depender, y
por eso mismo no depende de nadie: si el kernel importa dominio, deja de ser
kernel y pasa a ser un contexto más con privilegios.
"""

from .contexto import VaultContext, construir
from .puertos import CatalogoNormas, Escritor, Lector, RegistroSecciones, Reloj

__all__ = [
    "VaultContext", "construir",
    "CatalogoNormas", "Escritor", "Lector", "RegistroSecciones", "Reloj",
]

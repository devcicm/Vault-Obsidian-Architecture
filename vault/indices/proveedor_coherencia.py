"""Runtime provider for read-only search index coherence."""

from vault.kernel.productores import registrar
from .coherencia import coherencia_indice
from .repositorio import RepositorioIndices


class _Proveedor:
    def comprobar(self, contexto):
        return coherencia_indice(RepositorioIndices(contexto))


_PROVEEDOR = _Proveedor()


def _ofrecer():
    registrar("coherencia_indices", _PROVEEDOR)


_ofrecer()

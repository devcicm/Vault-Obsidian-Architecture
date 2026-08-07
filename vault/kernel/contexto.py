"""`VaultContext`: el estado ambiental, convertido en argumento.

Hoy la misma información vive en tres sitios que no se hablan: `VAULT_ROOT`
congelado al importar (82 vínculos, AP-49), `_ACTIVE_VAULT_ROOT` mutable dentro
de `vault_io`, y 487 literales de sección esparcidos. Un objeto inmutable que se
pasa por llamada los sustituye a los tres.

Es `frozen=True` por una razón concreta y no por gusto: si el contexto fuera
mutable, dos raíces en el mismo intérprete volverían a poder contaminarse —que
es exactamente el fallo que este refactor tiene que eliminar— solo que ahora
además con la apariencia de estar inyectado.

**La regla que lo hace real:** ningún módulo de dominio importa `VAULT_ROOT`. Si
necesita la raíz, la recibe. Esa es la diferencia entre una costura que existe
—`set_vault_root()` lleva versiones publicado— y una que se usa.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .puertos import CatalogoNormas, Escritor, Lector, RegistroSecciones, Reloj


@dataclass(frozen=True)
class VaultContext:
    """Todo lo que el dominio necesita del mundo exterior, explícito."""

    raiz: Path
    #: Cómo se detectó la raíz (`vault_io.vault_root_origin()`). Viaja **con**
    #: la raíz a propósito: la confianza en un dato es parte del dato. Hoy hay
    #: que preguntarla aparte, así que casi nadie la pregunta y una detección
    #: insegura se usa igual que una explícita.
    origen: str
    secciones: RegistroSecciones
    normas: CatalogoNormas
    escritor: Escritor
    lector: Lector
    reloj: Reloj

    def ruta(self, *partes: str) -> Path:
        """Una ruta dentro del vault, garantizada dentro del vault (AP-36).

        La contención deja de ser algo que cada tool recuerda comprobar y pasa a
        ser invariante del contexto. v39.6 encontró un `vault_restore` que
        escribía fuera de la raíz: no por descuido, sino porque nada en la forma
        del código obligaba a pasar por aquí.
        """
        destino = (self.raiz.joinpath(*partes)).resolve()
        raiz = self.raiz.resolve()
        if destino != raiz and raiz not in destino.parents:
            raise ValueError(
                f"AP-36: {destino} cae fuera del vault {raiz}. Todo side effect "
                f"vive DENTRO del vault; la ruta se deriva del contexto, nunca "
                f"de __file__ ni del CWD."
            )
        return destino

    @property
    def sistema(self) -> Path:
        return self.ruta("00_System")


def construir(raiz: str | Path | None = None) -> VaultContext:
    """Construye el contexto real, resolviendo los puertos contra el kernel.

    Es el único punto del código que habla con `vault_io`, y por eso el único
    que hay que tocar si el kernel cambia. Los adaptadores (`scripts/`, `cli/`,
    el `.mjs` vía runner) llaman aquí una vez por invocación; el dominio recibe
    el resultado y no importa nada más.

    El import de `adaptadores` es diferido a propósito: `vault/` no puede
    depender de que `scripts/` esté en `sys.path` en tiempo de import, que sería
    cometer AP-49 en el módulo que existe para curarlo.
    """
    from .adaptadores import contexto_real

    return contexto_real(raiz)

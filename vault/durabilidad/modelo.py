"""Las entidades de Durabilidad. Sin E/S, sin rutas globales, sin envelope.

Que no importen nada del kernel es la prueba de que son dominio: se pueden
ejercer en un test sin disco y sin vault. Todo lo que necesita el mundo exterior
llega por argumento.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: El contrato publicado declara `min:1`, `max:100` y «default: 20». Vivía solo
#: en el catálogo: el `argparse` de `vault_backup_list` no tenía un argumento
#: (AP-42). Aquí es una regla del dominio, comprobable sin CLI de por medio.
LIMITE_DEFECTO = 20
LIMITE_MIN = 1
LIMITE_MAX = 100


class LimiteInvalido(ValueError):
    """El límite pedido cae fuera del rango publicado."""


def validar_limite(limite: int) -> int:
    if not LIMITE_MIN <= limite <= LIMITE_MAX:
        raise LimiteInvalido(
            f"--limit fuera de rango: {limite} (el contrato publicado declara "
            f"min:{LIMITE_MIN}, max:{LIMITE_MAX})"
        )
    return limite


@dataclass(frozen=True)
class Backup:
    """Una copia registrada. Los nombres de campo son los del envelope.

    Se conservan tal cual —`noteCount`, `sizeKB`, `createdAt` en camelCase entre
    campos snake_case— porque son contrato publicado y no preferencia de estilo.
    Renombrarlos «de paso» sería la clase de rotura silenciosa que este piloto
    existe para no cometer.
    """

    name: str
    label: str = ""
    createdAt: str = ""
    noteCount: int = 0
    fileCount: int = 0
    sizeKB: float = 0.0
    sections: list[str] = field(default_factory=list)

    @classmethod
    def desde_registro(cls, datos: dict[str, Any]) -> "Backup":
        return cls(
            name=datos.get("name", ""),
            label=datos.get("label", ""),
            createdAt=datos.get("createdAt", ""),
            noteCount=datos.get("noteCount", 0),
            fileCount=datos.get("fileCount", 0),
            sizeKB=datos.get("sizeKB", 0),
            sections=list(datos.get("sections", [])),
        )

    @classmethod
    def desde_manifiesto(cls, nombre: str, manifiesto: dict[str, Any]) -> "Backup":
        """Reconstruye desde `.manifest.json` cuando no hay registro.

        Es el camino degradado: un backup copiado a mano, o un registro perdido.
        Que exista es parte del contrato —la tool lo hace hoy— y por eso vive
        aquí y no como un `if` suelto dentro del script.
        """
        vault = manifiesto.get("vault", {})
        totales = vault.get("totals", {})
        return cls(
            name=nombre,
            label=manifiesto.get("label", ""),
            createdAt=manifiesto.get("createdAt", ""),
            noteCount=totales.get("notes", 0),
            fileCount=totales.get("files", 0),
            sizeKB=totales.get("sizeKB", 0),
            sections=[s["folder"] for s in vault.get("sections", [])],
        )

    def a_envelope(self) -> dict[str, Any]:
        """La forma exacta que el consumidor lleva versiones recibiendo."""
        return {
            "name": self.name,
            "label": self.label,
            "createdAt": self.createdAt,
            "noteCount": self.noteCount,
            "fileCount": self.fileCount,
            "sizeKB": self.sizeKB,
            "sections": list(self.sections),
        }


@dataclass(frozen=True)
class RegistroBackups:
    """El conjunto de copias conocidas, del más reciente al más antiguo."""

    backups: tuple[Backup, ...] = ()

    def acotado(self, limite: int = LIMITE_DEFECTO) -> tuple[int, list[Backup]]:
        """Devuelve **cuántos hay** y los que caben en el límite.

        Los dos números por separado a propósito: si el límite cambiara el
        total, quien pagina no podría saber que falta algo.
        """
        return len(self.backups), list(self.backups[: validar_limite(limite)])

"""El repositorio: lo único de Durabilidad que toca disco.

Concentrar aquí la E/S es lo que convierte la contención AP-36 en **invariante
del contexto** en vez de en algo que cada tool recuerda comprobar por su cuenta.
v39.6 encontró un `vault_restore` que escribía fuera del vault; no por descuido,
sino porque nada en la forma del código obligaba a pasar por un sitio único.

Recibe el `VaultContext`. No importa `VAULT_ROOT` ni deriva ninguna ruta al
importarse (AP-49): todas cuelgan de `self._ctx.raiz`, que es lo que permite dos
vaults en el mismo intérprete.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..kernel.contexto import VaultContext
from .modelo import Backup, RegistroBackups

#: Cuelga del vault, no es un hermano: la contención es parte de la definición.
#: Debe seguir coincidiendo con `vault_backup.BACKUP_ROOT`.
CARPETA_BACKUPS = "vault-backups"
FICHERO_REGISTRO = ".backup-registry.json"
FICHERO_MANIFIESTO = ".manifest.json"


class RepositorioDurabilidad:
    def __init__(self, ctx: VaultContext) -> None:
        self._ctx = ctx

    # ── Rutas, todas contenidas ──────────────────────────────────────────────

    @property
    def raiz_backups(self) -> Path:
        """`ctx.ruta()` valida la contención: salir del vault lanza (AP-36)."""
        return self._ctx.ruta(CARPETA_BACKUPS)

    @property
    def fichero_registro(self) -> Path:
        return self._ctx.ruta(CARPETA_BACKUPS, FICHERO_REGISTRO)

    def ruta_de(self, nombre: str) -> Path:
        """La ruta de un backup por nombre, rechazando la evasión.

        `nombre` puede venir de argv o de un manifiesto ajeno, así que se trata
        como entrada hostil: `../../etc` no es un nombre de backup. Es el mismo
        vector que v39.6 encontró en el restore por base64.
        """
        if not nombre or "/" in nombre or "\\" in nombre or nombre.startswith("."):
            raise ValueError(f"nombre de backup no admisible: {nombre!r}")
        return self._ctx.ruta(CARPETA_BACKUPS, nombre)

    # ── Lectura ──────────────────────────────────────────────────────────────

    def _leer_json(self, ruta: Path) -> dict:
        """Un JSON ilegible es «no hay», nunca una excepción hacia arriba.

        Listar backups es la operación a la que acude quien ya tiene un
        problema: que reviente por un registro corrupto es precisamente cuando
        más daño hace.
        """
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError, json.JSONDecodeError, OSError):
            return {}

    def registro_crudo(self) -> dict:
        """El registro tal cual está en disco, para poder reescribirlo.

        `registro()` devuelve entidades y es lo que consume quien lee. Esto es
        para quien tiene que **añadir** una copia sin perder los campos que
        futuras versiones puedan haber puesto en las entradas existentes:
        reconstruir el fichero desde las entidades borraría lo que el dominio
        de hoy no sabe leer.
        """
        datos = self._leer_json(self.fichero_registro)
        if not isinstance(datos.get("backups"), list):
            datos = {"backups": []}
        return datos

    def guardar_registro(self, datos: dict) -> None:
        self.raiz_backups.mkdir(parents=True, exist_ok=True)
        self._ctx.escritor.escribir_json(self.fichero_registro, datos)

    def registro(self) -> RegistroBackups:
        """Las copias conocidas: primero el registro, si no el disco.

        El orden importa y es el vigente: el registro manda, y el escaneo del
        directorio es el camino degradado para cuando no lo hay.
        """
        datos = self._leer_json(self.fichero_registro).get("backups", [])
        if datos:
            return RegistroBackups(tuple(Backup.desde_registro(d) for d in datos))

        raiz = self.raiz_backups
        if not raiz.exists():
            return RegistroBackups()
        encontrados = [
            Backup.desde_manifiesto(
                item.name, self._leer_json(item / FICHERO_MANIFIESTO)
            )
            for item in sorted(raiz.iterdir(), reverse=True)
            if item.is_dir() and not item.name.startswith(".")
        ]
        return RegistroBackups(tuple(encontrados))

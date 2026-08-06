"""Devolver el vault a un snapshot anterior. Operación destructiva.

Todo lo peligroso de esta operación está aquí, en un sitio, y no repartido por
un script de 280 líneas: qué se borra antes de copiar, qué **nunca** se borra, y
de dónde se lee el snapshot. v39.6 encontró un restore que escribía fuera del
vault; no por descuido, sino porque nada en la forma del código obligaba a pasar
por un punto único.

`NO_BORRAR` es la lista que impide que restaurar destruya el propio snapshot del
que se está leyendo. Al mover los backups dentro del vault (v38.1) el barrido
previo pasó a incluirlos: sin esta lista, restaurar se llevaría por delante todo
el historial de copias.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..kernel.contexto import VaultContext
from .repositorio import CARPETA_BACKUPS, FICHERO_MANIFIESTO, RepositorioDurabilidad

#: Lo que el barrido previo al restore no toca nunca.
NO_BORRAR = {"vault-backups", "vault-sandbox"}


class ServicioRestauracion:
    def __init__(self, ctx: VaultContext, raiz_legacy: Path | None = None) -> None:
        self._ctx = ctx
        self._repo = RepositorioDurabilidad(ctx)
        # La ubicación anterior a v38.1: hermana del repo, FUERA de todo vault.
        # Se conserva solo como lectura de respaldo —no-derogación— porque hay
        # copias reales ahí de las que alguien puede necesitar salir. Nada
        # escribe en ella.
        self._legacy = raiz_legacy

    def _localizar(self, nombre: str) -> tuple[Path | None, list[str]]:
        """El snapshot: canónico si existe, si no el legacy. Y dónde se buscó.

        Devolver también los sitios consultados no es cosmética: cuando un
        restore no encuentra su copia, saber dónde miró es la diferencia entre
        diagnosticarlo y adivinarlo.
        """
        buscados: list[str] = []
        try:
            canonico = self._repo.ruta_de(nombre)
        except ValueError:
            return None, buscados
        buscados.append(str(canonico))
        if canonico.exists():
            return canonico, buscados
        if self._legacy is not None:
            legacy = self._legacy / nombre
            buscados.append(str(legacy))
            if legacy.exists():
                return legacy, buscados
        return None, buscados

    def _notas_del_manifiesto(self, ruta: Path) -> int:
        try:
            datos = json.loads((ruta / FICHERO_MANIFIESTO).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return 0
        return datos.get("vault", {}).get("totals", {}).get("notes", 0)

    def restaurar(self, nombre: str, confirmado: bool = False) -> dict:
        """Reemplaza el contenido del vault por el del snapshot.

        `confirmado` no tiene default permisivo a propósito: es la única
        operación del estándar que borra datos del usuario, y una confirmación
        que se puede omitir por olvido no es una confirmación.
        """
        if not confirmado:
            return {
                "ok": False,
                "error": "confirm must be true to proceed. This is a destructive operation.",
                "hint": "Run vault_backup(label) first to backup current state, "
                        "then confirm with confirm:true",
            }

        ruta, buscados = self._localizar(nombre)
        if ruta is None:
            return {"ok": False, "error": f"Backup not found: {nombre}",
                    "searched": buscados}

        notas = self._notas_del_manifiesto(ruta)

        raiz = self._ctx.raiz
        for item in raiz.iterdir():
            if item.name.startswith(".") or item.name in NO_BORRAR:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        restaurados = 0
        for item in ruta.iterdir():
            if item.name.startswith("."):
                continue
            destino = self._ctx.ruta(item.name)
            if item.is_dir():
                shutil.copytree(item, destino)
                restaurados += sum(1 for p in destino.rglob("*") if p.is_file())
            else:
                shutil.copy2(item, destino)
                restaurados += 1

        return {
            "restored_from": nombre,
            "noteCount": notas,
            "files_restored": restaurados,
            "message": f"Vault restored from {nombre} ({notas} notes)",
        }


__all__ = ["NO_BORRAR", "CARPETA_BACKUPS", "ServicioRestauracion"]

"""Reconstruir `search-index.json` y `hash-index.json` desde el disco.

Es la tool de recuperación obligatoria para vaults gestionados por agentes que
no pasan por `vault_write` en cada escritura: si `vault_search` devuelve cero,
el índice miente y hay que rehacerlo desde lo único que no miente, que son los
ficheros.

El parser de frontmatter se **inyecta**: al dominio no le consta si detrás hay
un regex o PyYAML, y eso es lo que permite probar la reconstrucción sin disco.
Es el mismo trato que recibió `vault/durabilidad/cuarentena.py`.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable, Dict, List

from .enumeracion import notas_en_disco
from .repositorio import RepositorioIndices

#: Longitud del extracto que se guarda por nota. Va al índice, así que es
#: contrato con quien lo lee: recortarlo cambia lo que el agente ve al buscar.
PREVIO = 200


def _previo(contenido: str) -> str:
    cuerpo = contenido.split("---", 2)[-1] if contenido.count("---") >= 2 else contenido
    return cuerpo.strip()[:PREVIO].replace("\n", " ")


class ServicioReindex:
    def __init__(
        self,
        repo: RepositorioIndices,
        parsear_frontmatter: Callable[[str], dict],
    ) -> None:
        self._repo = repo
        self._parsear = parsear_frontmatter

    def reconstruir(self, dry_run: bool = False) -> Dict[str, Any]:
        repo = self._repo
        notas: List[Dict[str, Any]] = []
        hashes: Dict[str, Any] = {}
        omitidas = 0

        ficheros = notas_en_disco(repo.raiz, repo.ctx.secciones.ordenadas())

        for ruta in sorted(ficheros):
            try:
                contenido = ruta.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                # Se cuenta, no se traga: `skipped` es el indicador de trabajo
                # que impide que una lectura fallida pase por reconstrucción
                # correcta (AP-37).
                omitidas += 1
                continue

            rel = repo.relativa(ruta)
            meta = self._parsear(contenido) or {}

            etiquetas = meta.get("tags") or []
            if isinstance(etiquetas, str):
                etiquetas = [t.strip() for t in etiquetas.split(",") if t.strip()]

            notas.append({
                "path": rel,
                "title": meta.get("title") or ruta.stem,
                "preview": _previo(contenido),
                "tags": etiquetas,
                "updatedAt": meta.get("updatedAt") or meta.get("createdAt") or "",
            })

            hashes[rel] = {
                "hash": hashlib.sha256(contenido.encode("utf-8")).hexdigest(),
                "size": len(contenido.encode("utf-8")),
                "cia_integrity": meta.get("cia_integrity", "medium"),
            }

        ahora = repo.ctx.reloj.marca()

        if not dry_run:
            repo.dir_indices.mkdir(parents=True, exist_ok=True)
            repo.ctx.escritor.escribir_json(
                repo.indice_busqueda,
                {"notes": notas, "rebuiltAt": ahora, "totalNotes": len(notas)},
            )
            repo.ctx.escritor.escribir_json(
                repo.indice_hashes, {"snapshot_at": ahora, "notes": hashes}
            )

        return {
            "ok": True,
            "indexed": len(notas),
            "skipped": omitidas,
            "dry_run": dry_run,
            "path": repo.relativa(repo.indice_busqueda),
            "hash_index": repo.relativa(repo.indice_hashes),
        }

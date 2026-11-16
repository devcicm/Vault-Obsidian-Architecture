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
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from ..kernel.escritura import escribir_json_si_cambia  # noqa: E402
from ..kernel.frontmatter_parsing import separar_frontmatter
from .enumeracion import es_nota_indexable, notas_en_disco
from .repositorio import RepositorioIndices

#: Longitud del extracto que se guarda por nota. Va al índice, así que es
#: contrato con quien lo lee: recortarlo cambia lo que el agente ve al buscar.
PREVIO = 200

#: Claves de sello temporal de los índices que este servicio reconstruye. No
#: son contenido: dicen CUÁNDO se reconstruyó, y reconstruir lo mismo desde el
#: mismo vault no es un hecho nuevo. El mecanismo vive en el kernel
#: (`vault.kernel.escritura.escribir_json_si_cambia`); qué claves SON sello en
#: ESTOS ficheros lo declara este módulo, que es su dueño.
CLAVES_DE_SELLO = frozenset({"rebuiltAt", "snapshot_at"})


def _previo(contenido: str) -> str:
    cuerpo = separar_frontmatter(contenido)[1]
    return cuerpo.strip()[:PREVIO].replace("\n", " ")


class ServicioReindex:
    def __init__(
        self,
        repo: RepositorioIndices,
        parsear_frontmatter: Callable[[str], dict],
    ) -> None:
        self._repo = repo
        self._parsear = parsear_frontmatter

    def _entrada(self, ruta: Path, contenido: str, meta: dict) -> Dict[str, Any]:
        """La fila de `search-index.json` para una nota. Un solo dueño (AP-57):
        la reconstrucción entera y el refresco de una nota la sacan de aquí, así
        que no pueden discrepar sobre qué ve `vault_search`."""
        etiquetas = meta.get("tags") or []
        if isinstance(etiquetas, str):
            etiquetas = [t.strip() for t in etiquetas.split(",") if t.strip()]
        # The parser consumes universal-newline text, but freshness must also
        # detect changes to the original bytes (including line endings).
        # If the note changed between reads, do not attest the resulting row.
        try:
            crudo = ruta.read_bytes()
            texto = crudo.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
            huella = hashlib.sha256(crudo).hexdigest() if texto == contenido else None
        except (OSError, UnicodeError):
            huella = None
        try:
            mtime = datetime.fromtimestamp(ruta.stat().st_mtime, timezone.utc).isoformat()
        except (OSError, OverflowError, ValueError):
            mtime = None
        titulo = meta.get("title") or ruta.stem
        return {
            "path": self._repo.relativa(ruta),
            "title": titulo,
            "preview": _previo(contenido),
            "tags": etiquetas,
            "updatedAt": meta.get("updatedAt") or meta.get("createdAt") or "",
            "content_hash": huella,
            # Declared metadata and observed filesystem time are distinct
            # evidence. A missing declared date is never inferred from mtime.
            "timestamps": {
                "declared_created_at": meta.get("createdAt"),
                "declared_updated_at": meta.get("updatedAt"),
                "declared_source": "frontmatter",
                "observed_mtime_utc": mtime,
                "observed_mtime_source": "filesystem",
            },
        }

    def refrescar(self, *rutas_escritas: Path, existentes: Sequence[Path] = ()) -> Dict[str, Any]:
        """AP-47: inserta o sustituye la fila de UNA nota recién escrita.

        Solo `vault_write` actualizaba el índice; `vault_ingest` y los `*_save`
        escribían la nota y `vault_search` no la encontraba hasta un reindex.
        Lo llama el gancho del kernel tras cada escritura, igual que el índice
        de sección, y con el mismo criterio de «qué es nota» que la
        reconstrucción. Usa el mismo cerrojo que `atomic_update_json`, así que
        se serializa con `vault_write` y con `vault_reindex`.

        `mas` son las notas que esa misma escritura creó de rebote —el
        `index.md` que el gancho de sección genera—: entran en la misma pasada,
        una sola escritura del índice, en vez de una por nota (AP-37 cuenta
        escrituras, y escribir dos veces el mismo fichero no es más trabajo).

        `existentes` are generated notes whose bytes changed (an updated
        section `index.md`, the change log): in the same pass, only rows that
        a readable index already holds are replaced. They never create the
        index, never rebuild it from a corrupt file and never add a row, so the
        fingerprint stays current without changing what the search returns.
        """
        repo = self._repo
        secciones = repo.ctx.secciones.ordenadas()

        def construir_entradas(rutas_candidatas):
            filas = []
            for r in rutas_candidatas:
                if es_nota_indexable(r, repo.raiz, secciones):
                    contenido = repo.ctx.lector.leer(r)
                    filas.append(self._entrada(r, contenido, self._parsear(contenido) or {}))
            return filas

        entradas = construir_entradas(rutas_escritas)
        entradas_existentes = construir_entradas(existentes)
        if not entradas and not entradas_existentes:
            return {"ok": True, "refreshed": False, "reason": "no_indexable"}
        destino = repo.indice_busqueda
        with repo.ctx.escritor.bloquear(destino):
            legible = True
            try:
                indice = json.loads(repo.ctx.lector.leer(destino))
            except (FileNotFoundError, json.JSONDecodeError):
                legible, indice = False, {}
            if not isinstance(indice, dict):
                legible, indice = False, {}
            filas = indice.get("notes")
            presentes = ({n.get("path") for n in filas if isinstance(n, dict)}
                         if legible and isinstance(filas, list) else set())
            escritas = {e["path"] for e in entradas}
            entradas = entradas + [e for e in entradas_existentes
                                   if e["path"] in presentes and e["path"] not in escritas]
            if not entradas:
                return {"ok": True, "refreshed": False, "reason": "not_indexed"}
            rutas = {e["path"] for e in entradas}
            notas = [n for n in indice.get("notes", []) if n.get("path") not in rutas]
            notas.extend(entradas)
            # Orden canónico por ruta (v41.12): la reconstrucción inserta en
            # orden alfabético, pero el refresco hacía remove+append y el orden
            # final dependía de qué gancho corrió último — el mismo índice con
            # las mismas filas en otra posición era un diff entero en cada
            # corrida (el C3 lo medía por hash). Con orden canónico, refrescar
            # lo ya refrescado no cambia bytes.
            notas.sort(key=lambda n: str(n.get("path", "")))
            indice["notes"] = notas
            if "totalNotes" in indice:
                indice["totalNotes"] = len(notas)
            escribir_json_si_cambia(
                repo.ctx.escritor.escribir_json, destino, indice,
                claves_de_sello=CLAVES_DE_SELLO)
        return {"ok": True, "refreshed": True, "path": entradas[0]["path"],
                "paths": [e["path"] for e in entradas]}

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
            notas.append(self._entrada(ruta, contenido, meta))

            hashes[rel] = {
                "hash": hashlib.sha256(contenido.encode("utf-8")).hexdigest(),
                "size": len(contenido.encode("utf-8")),
                "cia_integrity": meta.get("cia_integrity", "medium"),
            }

        ahora = repo.ctx.reloj.marca()

        if not dry_run:
            repo.dir_indices.mkdir(parents=True, exist_ok=True)
            escribir = repo.ctx.escritor.escribir_json
            escribir_json_si_cambia(
                escribir,
                repo.indice_busqueda,
                {"notes": notas, "rebuiltAt": ahora, "totalNotes": len(notas),
                 "contentHashVersion": 1},
                claves_de_sello=CLAVES_DE_SELLO,
            )
            escribir_json_si_cambia(
                escribir,
                repo.indice_hashes, {"snapshot_at": ahora, "notes": hashes},
                claves_de_sello=CLAVES_DE_SELLO,
            )

        return {
            "ok": True,
            "indexed": len(notas),
            "skipped": omitidas,
            "dry_run": dry_run,
            "path": repo.relativa(repo.indice_busqueda),
            "hash_index": repo.relativa(repo.indice_hashes),
        }

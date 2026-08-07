"""Crear y verificar una copia del vault.

Aquí vive la decisión: qué entra en el snapshot, qué se hashea, con qué regla y
cómo se comprueba después. El script `scripts/vault_backup.py` pasa a ser lo que
debe ser —parsear argv, imprimir el envelope— y esto se puede ejercer sin CLI,
sin subproceso y con dos vaults distintos en el mismo intérprete.

La huella Merkle tiene **versión** (`MERKLE_ALGO`) y el manifiesto la sella. Es
la única forma de corregir qué se hashea sin que toda copia anterior pase a
reportarse corrupta: al verificar manda el algoritmo del manifiesto, no el
instalado. Un manifiesto sin sello es algo 1 — así se escribió lo anterior a
v40.0.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Sequence

from ..kernel.contexto import VaultContext
from .modelo import Backup
from .repositorio import CARPETA_BACKUPS, FICHERO_MANIFIESTO, RepositorioDurabilidad

#: Versión de la regla del hash. Se escribe en el manifiesto y se lee de vuelta.
MERKLE_ALGO = 2

#: Ficheros que cualquier ejecución de cualquier tool reescribe (observabilidad).
#: Estaban dentro del hash, así que dos copias de un vault intacto daban raíz
#: distinta: la medida arrastraba la huella de quien mide, que es AP-44 aplicado
#: a una métrica de integridad. Excluidos desde algo 2.
VOLATILES = frozenset({
    "00_System/.tool-trace.json",
    "00_System/.voice-counter",
})

#: Lo que no entra al snapshot: copias previas —evitaría la recursión ahora que
#: los backups viven DENTRO del vault (AP-36)— y sandboxes.
NO_COPIAR = ("vault-backups", "vault-sandbox")


# ── La huella ────────────────────────────────────────────────────────────────

def _hoja(rel: str, contenido: bytes) -> str:
    return hashlib.sha256((rel + ":").encode() + contenido).hexdigest()


def raiz_merkle(hojas: Sequence[str]) -> str:
    if not hojas:
        return hashlib.sha256(b"empty-vault").hexdigest()
    capa = sorted(hojas)
    while len(capa) > 1:
        siguiente = []
        for i in range(0, len(capa), 2):
            izq = capa[i]
            der = capa[i + 1] if i + 1 < len(capa) else izq
            siguiente.append(hashlib.sha256((izq + der).encode()).hexdigest())
        capa = siguiente
    return capa[0]


def merkle_de(carpeta: Path, algo: int = MERKLE_ALGO) -> tuple[str, int]:
    """`(raiz, numero_de_ficheros)` bajo `carpeta`, con la regla `algo`."""
    hojas: list[str] = []
    for fichero in sorted(carpeta.rglob("*")):
        if not fichero.is_file() or fichero.name == FICHERO_MANIFIESTO:
            continue
        rel = str(fichero.relative_to(carpeta)).replace("\\", "/")
        if algo >= 2 and rel in VOLATILES:
            continue
        try:
            hojas.append(_hoja(rel, fichero.read_bytes()))
        except (PermissionError, OSError):
            continue
    return raiz_merkle(hojas), len(hojas)


# ── Inventario del snapshot ──────────────────────────────────────────────────

def _contar(carpeta: Path) -> tuple[int, int, int]:
    notas = ficheros = tamano = 0
    for item in carpeta.rglob("*"):
        if item.is_file():
            ficheros += 1
            if item.suffix == ".md":
                notas += 1
            try:
                tamano += item.stat().st_size
            except OSError:
                pass
    return notas, ficheros, tamano


def inventario(ruta_backup: Path) -> dict:
    """Secciones y totales del snapshot. Es el `manifest` del envelope."""
    secciones = []
    notas_t = ficheros_t = tamano_t = 0
    for item in sorted(ruta_backup.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            notas, ficheros, tamano = _contar(item)
            if notas or ficheros:
                secciones.append({
                    "folder": item.name, "notes": notas, "files": ficheros,
                    "sizeKB": round(tamano / 1024, 1),
                })
            notas_t += notas
            ficheros_t += ficheros
            tamano_t += tamano
    for item in ruta_backup.iterdir():
        if item.is_file() and item.suffix not in [".json"]:
            try:
                ficheros_t += 1
                tamano_t += item.stat().st_size
            except OSError:
                pass
    return {
        "sections": secciones,
        "totals": {"notes": notas_t, "files": ficheros_t,
                   "sizeKB": round(tamano_t / 1024, 1)},
    }


def slug_de_etiqueta(etiqueta: str | None) -> str:
    if not etiqueta:
        return ""
    s = re.sub(r"[^\w\s-]", "", etiqueta.lower())
    s = re.sub(r"[\s_]+", "-", s)
    return re.sub(r"^-+|-+$", "", s)


# ── El servicio ──────────────────────────────────────────────────────────────

class ServicioSnapshot:
    def __init__(self, ctx: VaultContext) -> None:
        self._ctx = ctx
        self._repo = RepositorioDurabilidad(ctx)

    def crear(self, etiqueta: str | None = None) -> dict:
        """Copia el vault, sella el manifiesto y registra la copia.

        Devuelve el cuerpo del envelope sin los campos del ledger: quien decide
        cuántos ficheros escribió el kernel es el kernel, y lo añade el
        adaptador. Lo que sí sale de aquí es `files_copied`, que es el trabajo
        de esta operación y no lo veía nadie —`shutil` no pasa por el ledger, y
        un backup de 196 ficheros reportaba `written: 1` (AP-37).
        """
        slug = slug_de_etiqueta(etiqueta)
        marca = self._ctx.reloj.ahora().strftime("%Y-%m-%d-%H%M%S")
        nombre = f"vault-{marca}" + (f"-{slug}" if slug else "")
        ruta = self._repo.ruta_de(nombre)
        self._repo.raiz_backups.mkdir(parents=True, exist_ok=True)

        copiados = 0
        for item in self._ctx.raiz.iterdir():
            if item.name.startswith(".") or item.name in NO_COPIAR:
                continue
            destino = ruta / item.name
            if item.is_dir():
                shutil.copytree(item, destino, dirs_exist_ok=True)
                copiados += sum(1 for p in destino.rglob("*") if p.is_file())
            else:
                shutil.copy2(item, destino)
                copiados += 1

        datos = inventario(ruta)
        raiz, cuenta = merkle_de(ruta)
        ahora = self._ctx.reloj.marca()
        self._ctx.escritor.escribir_json(ruta / FICHERO_MANIFIESTO, {
            "name": nombre, "label": slug, "createdAt": ahora, "vault": datos,
            "merkle_root": raiz, "merkle_file_count": cuenta,
            "merkle_algo": MERKLE_ALGO,
        })

        registro = self._repo.registro_crudo()
        registro.setdefault("backups", []).insert(0, Backup(
            name=nombre, label=slug, createdAt=ahora,
            noteCount=datos["totals"]["notes"], fileCount=datos["totals"]["files"],
            sizeKB=datos["totals"]["sizeKB"],
            sections=[s["folder"] for s in datos["sections"]],
        ).a_envelope())
        self._repo.guardar_registro(registro)

        return {
            "name": nombre,
            "path": str(ruta.relative_to(self._ctx.raiz)).replace("\\", "/") + "/",
            "manifest": datos,
            "merkle_root": raiz,
            "merkle_file_count": cuenta,
            "merkle_algo": MERKLE_ALGO,
            "files_copied": copiados,
        }

    def verificar(self, nombre: str) -> dict:
        """Recomputa la huella y la compara con la sellada.

        El algoritmo lo decide el manifiesto. Usar el instalado convertiría
        cada copia anterior en un falso positivo de corrupción: diría que el
        dato se estropeó cuando lo que cambió fue la regla.
        """
        try:
            ruta = self._repo.ruta_de(nombre)
        except ValueError:
            return {"ok": False, "error": f"Backup no encontrado: {nombre}"}
        if not ruta.exists():
            return {"ok": False, "error": f"Backup no encontrado: {nombre}"}

        manifiesto = ruta / FICHERO_MANIFIESTO
        if not manifiesto.exists():
            return {"ok": False,
                    "error": f"manifest {FICHERO_MANIFIESTO} no encontrado en el backup"}
        try:
            datos = json.loads(manifiesto.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            return {"ok": False, "error": f"manifest no legible: {e}"}

        sellada = datos.get("merkle_root")
        if not sellada:
            return {"ok": False,
                    "error": "manifest no contiene merkle_root (backup pre-v29)"}

        algo = datos.get("merkle_algo", 1)
        actual, cuenta = merkle_de(ruta, algo)
        intacto = actual == sellada
        return {
            "ok": True,
            "backup": nombre,
            "merkle_algo": algo,
            "intact": intacto,
            "stored_merkle_root": sellada,
            "current_merkle_root": actual,
            "stored_file_count": datos.get("merkle_file_count"),
            "current_file_count": cuenta,
            "status": "OK — backup integro" if intacto
                      else "CORRUPTO — merkle_root no coincide",
        }


__all__ = [
    "MERKLE_ALGO", "VOLATILES", "NO_COPIAR", "CARPETA_BACKUPS",
    "ServicioSnapshot", "merkle_de", "raiz_merkle", "inventario",
    "slug_de_etiqueta",
]

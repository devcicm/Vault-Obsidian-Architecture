"""Carpetas personalizadas: las que un vault tiene y el estándar no nombró.

Un vault vivo crea subcarpetas dentro de las secciones (`11_Code/tests`,
`07_Knowledge/adr-drafts`). Si nadie las registra, quedan fuera de la indexación
y de la búsqueda: existen en disco y no en el modelo, que es la forma más
silenciosa de perder contenido.

Las secciones canónicas salen del registro inyectado, nunca de una lista propia.
La copia literal que vivía en la tool se quedó en 13 secciones mientras el
estándar ya tenía 22, y las carpetas personalizadas de las nueve restantes eran
invisibles sin que nada fallara — AP-05 dentro del propio toolkit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ..kernel.fallos import FalloDeDominio
from .repositorio import RepositorioIndices

#: Prefijos que marcan una carpeta como no-contenido. `.` es oculta del sistema
#: y `_` es la convención del estándar para material auxiliar (`_datasets`,
#: `_attachments`): registrarlas las metería en índices que no les tocan.
PREFIJOS_IGNORADOS = (".", "_")


def _rel(raiz: Path, ruta: Path) -> str:
    """Relativa y con `/` siempre.

    La versión anterior hacía `str(item.relative_to(VAULT_ROOT))` sin
    normalizar, así que en Windows el escaneo grababa `11_Code\\tests` mientras
    `--add` y `--remove` reciben `11_Code/tests`: una carpeta detectada
    automáticamente no se podía eliminar por su nombre, y el registro no era
    portable entre plataformas. Se normaliza como en todo el resto del contexto.
    """
    return str(Path(ruta).relative_to(raiz)).replace("\\", "/")


class ServicioCarpetas:
    def __init__(self, repo: RepositorioIndices) -> None:
        self._repo = repo

    # ── Registro ─────────────────────────────────────────────────────────────

    def registro(self) -> Dict[str, Any]:
        datos = self._repo.leer_json(self._repo.registro_carpetas)
        if not isinstance(datos.get("folders"), list):
            return {"detected_at": None, "updated_at": None, "folders": []}
        return datos

    def guardar(self, registro: Dict[str, Any]) -> None:
        self._repo.dir_sistema.mkdir(parents=True, exist_ok=True)
        registro["updated_at"] = self._ahora()
        self._repo.ctx.escritor.escribir_json(
            self._repo.registro_carpetas, registro
        )

    def _ahora(self) -> str:
        """`isoformat()`, no `marca()`: es el formato que este fichero ya usa.

        Cambiarlo al del resto del estándar reescribiría con otra forma un
        registro que ya existe en disco de los usuarios. La divergencia queda
        anotada, no corregida por sorpresa.
        """
        return self._repo.ctx.reloj.ahora().isoformat()

    # ── Detección ────────────────────────────────────────────────────────────

    def detectar(self) -> List[Dict[str, Any]]:
        raiz = self._repo.raiz
        ahora = self._ahora()
        encontradas: List[Dict[str, Any]] = []

        for seccion in self._repo.ctx.secciones.ordenadas():
            dir_seccion = raiz / seccion
            if not dir_seccion.exists():
                continue

            for item in sorted(dir_seccion.iterdir()):
                if not item.is_dir() or item.name.startswith(PREFIJOS_IGNORADOS):
                    continue

                rel = _rel(raiz, item)
                encontradas.append({
                    "path": rel,
                    "name": item.name,
                    "section": seccion,
                    "detected_at": ahora,
                    "type": "subfolder",
                    "created_by": "unknown",
                })

                for sub in sorted(item.iterdir()):
                    if sub.is_dir():
                        encontradas.append({
                            "path": _rel(raiz, sub),
                            "name": sub.name,
                            "section": seccion,
                            "parent": rel,
                            "detected_at": ahora,
                            "type": "subfolder",
                            "created_by": "unknown",
                        })

        return encontradas

    # ── Operaciones ──────────────────────────────────────────────────────────

    def escanear(self) -> Dict[str, Any]:
        registro = self.registro()
        conocidas = {f["path"] for f in registro.get("folders", [])}
        nuevas = [f for f in self.detectar() if f["path"] not in conocidas]

        if nuevas:
            registro["folders"].extend(nuevas)
        registro["detected_at"] = self._ahora()
        self.guardar(registro)

        return {
            "ok": True,
            "total_folders": len(registro["folders"]),
            "new_folders": len(nuevas),
            "new_paths": [f["path"] for f in nuevas],
        }

    def listar(self) -> List[Dict[str, Any]]:
        return self.registro().get("folders", [])

    def anadir(self, ruta: str, created_by: str = "manual") -> Dict[str, Any]:
        registro = self.registro()
        ruta = ruta.replace("\\", "/")

        for carpeta in registro.get("folders", []):
            if carpeta["path"] == ruta:
                raise FalloDeDominio("CARPETA_YA_REGISTRADA",
                                     "Carpeta ya registrada", path=ruta)

        entrada = {
            "path": ruta,
            "name": Path(ruta).name,
            "section": ruta.split("/")[0] if "/" in ruta else "",
            "detected_at": self._ahora(),
            "type": "subfolder",
            "created_by": created_by,
        }
        registro["folders"].append(entrada)
        self.guardar(registro)
        return {"ok": True, "folder": entrada}

    def eliminar(self, ruta: str) -> Dict[str, Any]:
        registro = self.registro()
        ruta = ruta.replace("\\", "/")
        antes = len(registro.get("folders", []))
        registro["folders"] = [
            f for f in registro.get("folders", []) if f["path"] != ruta
        ]
        if len(registro["folders"]) == antes:
            raise FalloDeDominio("CARPETA_NO_ENCONTRADA",
                                 "Carpeta no encontrada en el registro",
                                 path=ruta)
        self.guardar(registro)
        return {"ok": True, "removed": ruta}

    def huerfanas(self) -> List[str]:
        """Registradas que ya no existen en disco. El registro también envejece."""
        raiz = self._repo.raiz
        return [
            f["path"]
            for f in self.registro().get("folders", [])
            if not (raiz / f["path"]).exists()
        ]

    def limpiar_huerfanas(self) -> Dict[str, Any]:
        huerfanas = self.huerfanas()
        if not huerfanas:
            return {"ok": True, "removed": 0}
        registro = self.registro()
        registro["folders"] = [
            f for f in registro.get("folders", []) if f["path"] not in huerfanas
        ]
        self.guardar(registro)
        return {"ok": True, "removed": len(huerfanas), "orphans": huerfanas}

    def carpetas_indexables(self) -> List[str]:
        """Secciones canónicas + personalizadas registradas."""
        return list(self._repo.ctx.secciones.ordenadas()) + [
            f["path"] for f in self.registro().get("folders", [])
        ]

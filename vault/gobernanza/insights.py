"""vault.gobernanza.insights — inventario por lotes y comparación de snapshots.

Propuesta `data-engineering-contracts-and-vault-applicability`: antes de
elegir un pipeline, una medida **reproducible** y de solo lectura. Este módulo
es el dominio: no parsea argv ni emite envelopes —eso es del adaptador,
`scripts/vault_insights.py`— y no escribe en el vault.

El contrato del snapshot (AP-36 aplicado al artefacto): vive **fuera** del
vault. Un snapshot dentro sería una nota que el inventario contaría la
próxima vez, y el artefacto contaminaría la medida.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from vault.kernel.frontmatter_parsing import separar_frontmatter

#: La versión del esquema del inventario. Dos snapshots de esquemas distintos
#: no se comparan: mezclarlos convertiría una diferencia de formato en un
#: cambio de dato.
ESQUEMA = 1

#: La clave del frontmatter, compilada **una vez**: dentro del bucle se
#: buscaría en la caché de `re` por cada línea de cada nota.
_RE_CLAVE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")

#: El alcance de la medida, publicado con ella: metadatos autorizados, no
#: verdad del contenido.
ALCANCE = ("solo metadatos autorizados; no mide si el contenido es verdadero, "
           "util o completo")


class SnapshotInvalido(ValueError):
    """El snapshot no se puede leer o no es del esquema esperado."""

    def __init__(self, mensaje: str, causa: str = "DATA_FILE_CORRUPT") -> None:
        self.causa = causa
        super().__init__(mensaje)


def _hash_cuerpo(texto: str) -> str:
    """El hash del cuerpo **sin frontmatter**: el metadato ya va aparte.

    Separar el bloque es criterio con dueño (`vault_lib.separar_frontmatter`,
    AP-57); aquí se usa el del kernel, que es la hoja.
    """
    _fm, cuerpo = separar_frontmatter(texto)
    return hashlib.sha256(cuerpo.encode("utf-8")).hexdigest()[:16]


def _notas(raiz: Path) -> list[Path]:
    from vault.kernel.rutas import ruta_generada  # noqa: F401  (misma frontera)

    from vault_io import is_snapshot_path

    return sorted(
        p for p in raiz.rglob("*.md")
        if p.is_file()
        and not any(parte.startswith(".") for parte in p.relative_to(raiz).parts)
        and not is_snapshot_path(p.relative_to(raiz).as_posix())
        and "node_modules" not in p.parts
    )


def inventario(raiz: Path) -> dict:
    """El inventario de metadatos autorizados, de solo lectura."""
    notas = []
    textos: dict[Path, str] = {}
    for p in _notas(raiz):
        try:
            textos[p] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    for p, texto in textos.items():
        rel = p.relative_to(raiz).as_posix()
        partes = rel.split("/")
        front: dict[str, str] = {}
        if texto.startswith("---"):
            fin = texto.find("\n---", 3)
            if fin > 0:
                for linea in texto[3:fin].splitlines():
                    m = _RE_CLAVE.match(linea)
                    if m:
                        front[m.group(1)] = m.group(2).strip()
        entrantes = sum(1 for otra in textos if otra != p and p.stem in textos[otra])
        notas.append({
            "path": rel,
            "seccion": partes[0] if len(partes) > 1 else "",
            "type": front.get("type"),
            "status": front.get("status"),
            "tags": front.get("tags"),
            "createdAt": front.get("createdAt"),
            "updatedAt": front.get("updatedAt"),
            "bytes": p.stat().st_size,
            "hash_cuerpo": _hash_cuerpo(texto),
            "enlaces_entrantes": entrantes,
        })
    return {
        "ok": True,
        "tool": "vault_insights",
        "schema": ESQUEMA,
        "generated_at": _ahora(),
        "vault": raiz.name,
        "total": len(notas),
        "por_seccion": _por_seccion(notas),
        "alcance": ALCANCE,
        "notas": notas,
    }


def _por_seccion(notas: list[dict]) -> dict:
    cuenta: dict[str, int] = {}
    for n in notas:
        clave = n["seccion"] or "(raiz)"
        cuenta[clave] = cuenta.get(clave, 0) + 1
    return dict(sorted(cuenta.items()))


def _ahora() -> str:
    from vault_lib import utcnow

    return utcnow()

    return utcnow()


def guardar(inventario_: dict, destino: str, raiz: Path) -> dict:
    """Deja el snapshot en `destino`, **fuera del vault**."""
    ruta = Path(destino)
    try:
        dentro = ruta.resolve().is_relative_to(raiz.resolve())
    except (OSError, ValueError):
        dentro = True
    if dentro:
        raise SnapshotInvalido(
            "el snapshot no puede vivir dentro del vault: el inventario lo "
            "contaria y el artefacto contaminaria la medida. Elige una ruta "
            "fuera del vault.", causa="INVALID_PATH")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(inventario_, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return {"ok": True, "tool": "vault_insights", "action": "guardar",
            "path": str(ruta), "notas": inventario_["total"]}


def comparar(a: str, b: str) -> dict:
    """El informe de diferencias entre dos snapshots del mismo esquema."""
    try:
        uno = json.loads(Path(a).read_text(encoding="utf-8"))
        dos = json.loads(Path(b).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SnapshotInvalido(f"snapshot ilegible: {exc}")
    if uno.get("schema") != dos.get("schema"):
        raise SnapshotInvalido(
            f"los snapshots son de esquemas distintos ({uno.get('schema')} y "
            f"{dos.get('schema')}): compararlos mezclaria medidas.",
            causa="SCHEMA_MISMATCH")
    por_ruta_uno = {n["path"]: n for n in uno.get("notas", [])}
    por_ruta_dos = {n["path"]: n for n in dos.get("notas", [])}
    anadidas = sorted(set(por_ruta_dos) - set(por_ruta_uno))
    retiradas = sorted(set(por_ruta_uno) - set(por_ruta_dos))
    modificadas = sorted(
        ruta for ruta in set(por_ruta_uno) & set(por_ruta_dos)
        if por_ruta_uno[ruta].get("hash_cuerpo") != por_ruta_dos[ruta].get("hash_cuerpo")
    )
    return {
        "ok": True,
        "tool": "vault_insights",
        "action": "comparar",
        "desde": {"snapshot": a, "generated_at": uno.get("generated_at"),
                  "total": uno.get("total")},
        "hasta": {"snapshot": b, "generated_at": dos.get("generated_at"),
                  "total": dos.get("total")},
        "anadidas": anadidas,
        "retiradas": retiradas,
        "modificadas": modificadas,
        "delta_total": dos.get("total", 0) - uno.get("total", 0),
        "alcance": ALCANCE,
    }

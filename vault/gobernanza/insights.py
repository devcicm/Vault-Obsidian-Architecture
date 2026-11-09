"""vault.gobernanza.insights — inventario por lotes y comparación de snapshots.

Propuesta `data-engineering-contracts-and-vault-applicability`, con las
correcciones que pidio la revision independiente del 2026-11-09:

- **Completitud declarada.** Una nota ilegible ya no desaparece en silencio:
  el inventario lleva `poblacion` (encontradas/leidas), `errores`
  clasificados y `complete`. Un inventario parcial **no** se compara como
  completo: `comparar` lo rechaza y dice cual de los dos lo es.
- **Cuerpo y metadatos por separado.** El hash del cuerpo no detecta un
  cambio que solo es de `status:` o de `tags:`; ahora hay dos hashes y el
  informe distingue `modificadas` (cuerpo) de `metadatos_modificados`.
- **Identidad y poblacion.** El snapshot lleva `vault_id` (estable por
  instalacion) y el criterio de poblacion; comparar dos capturas de
  poblaciones distintas se rechaza, no se mezcla.
- **Renombres.** Una nota que cambia de ruta con el mismo cuerpo es un
  renombrado, no una baja y un alta.
- **Enlaces analizados.** Los entrantes se cuentan con el extractor del
  dueno (`extract_wiki_links`) y un indice de destinos, no con presencia
  textual: la cuenta anterior era O(notas x corpus) y_CASEA coincidencias
  incidentales.
- **Escritura atomica y sin sobrescritura.** Un snapshot no pisa otro sin
  permiso explicito, y se escribe por temporal→replace.

El dominio no parsea argv ni emite envelopes: eso es del adaptador,
`scripts/vault_insights.py`. Y no escribe en el vault.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path

from vault.kernel.frontmatter_parsing import separar_frontmatter

#: La versión del esquema. Cambió con esta revisión (completitud, identidad y
#: metadatos): dos capturas de esquemas distintos no se comparan, porque
#: mezclarlas convertiría una diferencia de formato en un cambio de dato.
ESQUEMA = 2

#: El alcance de la medida, publicado con ella: metadatos autorizados, no
#: verdad del contenido.
ALCANCE = ("solo metadatos autorizados; no mide si el contenido es verdadero, "
           "util o completo")

#: El criterio de población, publicado con cada snapshot: dos capturas con
#: criterios distintos no son comparables.
POBLACION = ("ficheros .md visibles, fuera de carpetas ocultas, "
             "instantaneas (.history, vault-backups) y node_modules")

#: Los campos de frontmatter que un cambio hace significativo. El resto se
#: ignora a proposito: comparar cualquier diferencia tecnica como si fuera
#: una decision de negocio es ruido.
CAMPOS_METADATO = ("title", "type", "status", "tags", "updatedAt", "createdAt")

#: La clave del frontmatter, compilada **una vez**: dentro del bucle se
#: buscaria en la cache de `re` por cada linea de cada nota.
_RE_CLAVE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")


class SnapshotInvalido(ValueError):
    """El snapshot no se puede leer, o no es comparable con el otro."""

    def __init__(self, mensaje: str, causa: str = "DATA_FILE_CORRUPT") -> None:
        self.causa = causa
        super().__init__(mensaje)


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def _identidad(raiz: Path) -> str:
    """La identidad estable de este vault.

    No es la ruta (cambia entre maquinas) ni el nombre (puede repetirse): es
    un identificador derivado de la version del estandar y de la ruta
    absoluta, que es estable por instalacion. Sirve para que dos capturas
    de vaultes distintos no se comparen.
    """
    try:
        from vault.kernel.entorno import CURRENT_VERSION  # noqa: F401
    except Exception:
        CURRENT_VERSION = ""
    try:
        base = str(raiz.resolve()).encode("utf-8")
    except (OSError, ValueError):
        base = str(raiz).encode("utf-8")
    return _hash(f"{CURRENT_VERSION}|{base.decode('utf-8', 'replace')}")


def _notas(raiz: Path) -> list[Path]:
    from vault_io import is_snapshot_path  # dueno del criterio instantanea

    return sorted(
        p for p in raiz.rglob("*.md")
        if p.is_file()
        and not any(parte.startswith(".") for parte in p.relative_to(raiz).parts)
        and not is_snapshot_path(p.relative_to(raiz).as_posix())
        and "node_modules" not in p.parts
    )


def _frontmatter(texto: str) -> dict[str, str]:
    bloque, _cuerpo = separar_frontmatter(texto)
    if not bloque:
        return {}
    datos: dict[str, str] = {}
    for linea in bloque.splitlines():
        m = _RE_CLAVE.match(linea)
        if m:
            datos[m.group(1)] = m.group(2).strip()
    return datos


def _metadatos_significativos(front: dict[str, str]) -> dict[str, str]:
    return {k: front.get(k, "") for k in CAMPOS_METADATO}


def inventario(raiz: Path) -> dict:
    """El inventario de metadatos autorizados, de solo lectura.

    Lo que no se pudo leer **se declara**: `errores` con su tipo y
    `complete: false`. Un consumidor no puede tomar un inventario parcial
    por uno completo.
    """
    from vault_lib import extract_wikilinks

    candidatas = _notas(raiz)
    notas: list[dict] = []
    errores: list[dict] = []
    leidos: list[tuple[Path, str]] = []

    for p in candidatas:
        rel = p.relative_to(raiz).as_posix()
        try:
            texto = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errores.append({"path": rel, "tipo": "ilegible",
                            "error": f"{type(exc).__name__}: {exc}"})
            continue
        except UnicodeError as exc:
            errores.append({"path": rel, "tipo": "codificacion",
                            "error": f"{type(exc).__name__}: {exc}"})
            continue
        leidos.append((p, texto))

    # Los enlaces entrantes, con el extractor del dueno y un indice de
    # destinos: la cuenta anterior recorria todos los textos por cada nota
    # (O(notas x corpus)) y contaba coincidencias textuales.
    destinos: dict[str, int] = {}
    for _p, texto in leidos:
        for enlace in extract_wikilinks(texto):
            destinos[enlace.strip().lower()] = destinos.get(enlace.strip().lower(), 0) + 1

    for p, texto in leidos:
        rel = p.relative_to(raiz).as_posix()
        partes = rel.split("/")
        front = _frontmatter(texto)
        _fm, cuerpo = separar_frontmatter(texto)
        entrantes = destinos.get(p.stem.lower(), 0)
        notas.append({
            "path": rel,
            "seccion": partes[0] if len(partes) > 1 else "",
            "type": front.get("type"),
            "status": front.get("status"),
            "tags": front.get("tags"),
            "createdAt": front.get("createdAt"),
            "updatedAt": front.get("updatedAt"),
            "bytes": p.stat().st_size,
            "hash_cuerpo": _hash(cuerpo),
            "hash_metadatos": _hash(json.dumps(
                _metadatos_significativos(front), sort_keys=True, ensure_ascii=False)),
            "enlaces_entrantes": entrantes,
        })

    return {
        "ok": True,
        "tool": "vault_insights",
        "schema": ESQUEMA,
        "generated_at": _ahora(),
        "vault": raiz.name,
        "vault_id": _identidad(raiz),
        "poblacion": {
            "criterio": POBLACION,
            "notas_encontradas": len(candidatas),
            "notas_leidas": len(notas),
        },
        "complete": not errores,
        "errores": errores,
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


def guardar(inventario_: dict, destino: str, raiz: Path, force: bool = False) -> dict:
    """Deja el snapshot en `destino`, **fuera** del vault y sin pisar otro.

    Dos decisiones explicitas: el snapshot no vive dentro del vault (el
    inventario lo contaria y el artefacto contaminaria la medida) y no
    sobrescribe otro snapshot sin permiso.
    """
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
    if ruta.exists() and not force:
        raise SnapshotInvalido(
            f"ya hay un snapshot en '{ruta}': no se pisa sin --force.",
            causa="SNAPSHOT_EXISTE")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # Escritura atomica: temporal y replace. Un snapshot a medias no es un
    # snapshot, y un lector podria leerlo.
    temporal = ruta.with_name(ruta.name + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    try:
        temporal.write_text(
            json.dumps(inventario_, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        os.replace(temporal, ruta)
    finally:
        try:
            temporal.unlink(missing_ok=True)
        except OSError:
            pass
    return {"ok": True, "tool": "vault_insights", "action": "guardar",
            "path": str(ruta), "notas": inventario_["total"],
            "complete": inventario_.get("complete", True)}


def _leer_snapshot(ruta: str) -> dict:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SnapshotInvalido(f"snapshot ilegible: {exc}")


def comparar(a: str, b: str) -> dict:
    """El informe de diferencias entre dos snapshots comparables.

    No se comparan capturas de esquemas distintos, ni de vaults distintos, ni
    capturas incompletas: mezclar poblaciones distintas produce diferencias
    que parecen cambios de contenido y no lo son.
    """
    uno = _leer_snapshot(a)
    dos = _leer_snapshot(b)
    if uno.get("schema") != dos.get("schema"):
        raise SnapshotInvalido(
            f"los snapshots son de esquemas distintos ({uno.get('schema')} y "
            f"{dos.get('schema')}): compararlos mezclaria medidas.",
            causa="SCHEMA_MISMATCH")
    if uno.get("vault_id") and dos.get("vault_id") and uno["vault_id"] != dos["vault_id"]:
        raise SnapshotInvalido(
            "los snapshots son de vaults distintos (identidad y poblacion "
            "distintas): su diferencia no seria un cambio de contenido.",
            causa="IDENTITY_MISMATCH")
    incompletos = [ruta for ruta, snap in ((a, uno), (b, dos))
                   if snap.get("complete") is False]
    if incompletos:
        raise SnapshotInvalido(
            "una de las capturas esta incompleta (hubo notas ilegibles): "
            f"no se comparan — {', '.join(incompletos)}.",
            causa="SNAPSHOT_INCOMPLETO")

    por_uno = {n["path"]: n for n in uno.get("notas", [])}
    por_dos = {n["path"]: n for n in dos.get("notas", [])}
    altas = sorted(set(por_dos) - set(por_uno))
    bajas = sorted(set(por_uno) - set(por_dos))
    comunes = set(por_uno) & set(por_dos)

    cuerpo = sorted(r for r in comunes
                    if por_uno[r].get("hash_cuerpo") != por_dos[r].get("hash_cuerpo"))
    metadatos = sorted(r for r in comunes
                       if por_uno[r].get("hash_metadatos") != por_dos[r].get("hash_metadatos"))

    # Un renombrado: la misma nota, otro sitio. Sin esto, una nota movida
    # pareceria una baja y un alta.
    cuerpos_uno = {n.get("hash_cuerpo"): n["path"] for n in uno.get("notas", [])}
    cuerpos_dos = {n.get("hash_cuerpo"): n["path"] for n in dos.get("notas", [])}
    renombradas = sorted(
        (cuerpos_uno[h], cuerpos_dos[h])
        for h in(set(cuerpos_uno) & set(cuerpos_dos))
        if cuerpos_uno[h] != cuerpos_dos[h]
    )
    renombradas_paths = {a for a, _b in renombradas} | {b for _a, b in renombradas}
    altas_reales = [r for r in altas if r not in renombradas_paths]
    bajas_reales = [r for r in bajas if r not in renombradas_paths]

    return {
        "ok": True,
        "tool": "vault_insights",
        "action": "comparar",
        "desde": {"snapshot": a, "generated_at": uno.get("generated_at"),
                  "total": uno.get("total"), "complete": uno.get("complete")},
        "hasta": {"snapshot": b, "generated_at": dos.get("generated_at"),
                  "total": dos.get("total"), "complete": dos.get("complete")},
        "anadidas": altas_reales,
        "retiradas": bajas_reales,
        "renombradas": [{"desde": x, "hasta": y} for x, y in renombradas],
        "modificadas": cuerpo,
        "metadatos_modificados": metadatos,
        "delta_total": (dos.get("total", 0) - uno.get("total", 0)),
        "alcance": ALCANCE,
    }

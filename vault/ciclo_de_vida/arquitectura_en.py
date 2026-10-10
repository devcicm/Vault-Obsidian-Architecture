#!/usr/bin/env python3
"""vault_arquitectura_en — cómo era la arquitectura de un proyecto en una fecha o versión.

## Por qué existe

Pedido el 2026-10-07: «como Google Maps, que pones una fecha y ves cómo eran
las casas; eso, pero con la arquitectura: la v1.0 no tenía, en la v1.5 le
ponen clean architecture, y entre ese rango ver la historia y los ficheros».
El vault ya guardaba todo lo necesario —las versiones tapadas en `.history/`,
`superseded_by:`, el `status` y las notas de release con su fecha— pero
ninguna tool lo leía junto. Sin base de datos y sin git: solo lo que el vault
deja escrito, que es lo que sobrevive a que este toolkit desaparezca.

## Qué lee

- **Qué es arquitectura** (`criterio` en el envelope; basta una razón): el
  `type` de una sección de decisiones o diagramas, o un `type` del registro
  que nombra *architecture*; la ruta bajo esas secciones o bajo una subcarpeta
  `…/architecture`; o un tag `architecture`/`arquitectura`. Fuera: los
  primers (`SCAFFOLD_TYPE`) y los artefactos derivados.
- **El contenido en la fecha D**: la primera versión de `.history/` guardada
  después de D —la que estaba viva hasta entonces— o el fichero actual si no
  la hay. La fecha de cada versión sale de su **nombre**, nunca del mtime:
  copiar el vault lo reescribe entero.
- **Si regía en D**: existía (`createdAt ≤ D`) y no estaba retirada —un status
  que desciende de `deprecated` en `STATUS_TRANSITIONS`, o una sustituta
  (`superseded_by`, resuelta como wikilink) que ya existía en D—. Lo demás
  sale del régimen del status: abierto → `propuesta`, cerrado → `vigente`.
- **La versión**: `vigente_desde:` en la nota (contrato v41) manda sobre la
  fecha; la fecha de una versión sale de su nota de release —un frontmatter
  con `version` y `deploy_at`, que es lo que escribe `vault_release_save`—.

Lo que no se puede decidir no se adivina: una nota sin fecha de creación ni
`vigente_desde` sale en `indeterminadas`, y un frontmatter ilegible en
`ilegibles`.

    python scripts/vault_arquitectura_en.py --fecha 2026-05-03
    python scripts/vault_arquitectura_en.py --version v1.5 --project ans
    python scripts/vault_arquitectura_en.py --desde v1.0 --hasta v1.5 --project ans

No escribe notas. No acepta `--root` (regla 1): el vault sale de `vault_io.get_vault_root()`.
Un error deja su entrada en `00_System/.tool-trace.json`, como en toda tool que emite por
`emit_error`: medido en la regla 7 contra la copia de /ans, que cambió de huella con un
`VERSION_NOT_FOUND`. Para medir un vault ajeno, sobre una copia.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


from vault_errors import emit_error, proyecto_registrado, wrap_main
from vault_history_compact import _parse_history_filename
from vault_io import get_vault_root, is_snapshot_path
from vault_lib import Config, indice_de_nombres, resolver_sustitucion
from vault_norms_catalog import STATUS_TRANSITIONS, normalize_status
from vault_registry import (SCAFFOLD_TYPE, SECTION_TYPES, SUBFOLDERS, es_artefacto_derivado,
                            regimen_de_estado)
from vault.kernel.frontmatter_parsing import (FrontmatterParseError, parse_frontmatter_with_body,
                                              separar_frontmatter)

TOOL = "vault_arquitectura_en"
UTC = timezone.utc

#: Secciones cuyo registro de tipos incluye decisiones o diagramas.
SECCIONES_DE_ARQUITECTURA = tuple(sorted(
    s for s, tipos in SECTION_TYPES.items() if {"decision", "diagram"} & set(tipos)))
#: Tipos que cuentan como arquitectura: los de esas secciones y los que la nombran.
TIPOS_DE_ARQUITECTURA = frozenset(
    {t for s in SECCIONES_DE_ARQUITECTURA for t in SECTION_TYPES[s]}
    | {t for tipos in SECTION_TYPES.values() for t in tipos if "architecture" in t})
SUBCARPETAS_DE_ARQUITECTURA = tuple(sorted(k for k in SUBFOLDERS if k.endswith("/architecture")))
TAGS_DE_ARQUITECTURA = frozenset({"architecture", "arquitectura"})


def _retirados() -> frozenset:
    """`deprecated` y todo lo que desciende de él en `STATUS_TRANSITIONS`."""
    vistos, pendientes = set(), ["deprecated"]
    while pendientes:
        s = pendientes.pop()
        if s not in vistos:
            vistos.add(s)
            pendientes.extend(STATUS_TRANSITIONS.get(s, ()))
    return frozenset(vistos)


RETIRADOS = _retirados()


# ── Lectura ──────────────────────────────────────────────────────────────────

def _datos(texto: str) -> Dict[str, Any]:
    """El frontmatter como lo lee el consumidor; `{}` si la nota no tiene bloque.

    Un bloque que no se parsea lanza `FrontmatterParseError`: quien llama lo
    cuenta como ilegible, no como una nota sin datos (AP-51).
    """
    if separar_frontmatter(texto)[0] is None:
        return {}
    return parse_frontmatter_with_body(texto)[0] or {}


def _instante(valor: Any) -> Optional[datetime]:
    """Un `createdAt`/`deploy_at` como instante UTC; `None` si no se puede leer."""
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=UTC)
    if isinstance(valor, date):
        return datetime.combine(valor, time.min, tzinfo=UTC)
    if not isinstance(valor, str) or not valor.strip():
        return None
    texto = valor.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(texto)
    except ValueError:
        m = re.match(r"\d{4}-\d{2}-\d{2}", texto)
        if not m:
            return None
        d = datetime.fromisoformat(m.group(0))
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _version(valor: Any) -> Optional[Tuple[int, ...]]:
    """`v1.5`, `1.5.0` o `0.8.1` como tupla; `None` si no es una versión.

    Un float de YAML (`vigente_desde: 1.10` sin comillas) se rechaza: ya no
    se distingue de `1.1`, y leerlo sería adivinar.
    """
    if isinstance(valor, bool) or not isinstance(valor, (str, int)):
        return None
    m = re.fullmatch(r"v?(\d+(?:\.\d+)*)", str(valor).strip(), re.IGNORECASE)
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def _cmp_version(a: Tuple[int, ...], b: Tuple[int, ...]) -> int:
    n = max(len(a), len(b))
    a, b = a + (0,) * (n - len(a)), b + (0,) * (n - len(b))
    return (a > b) - (a < b)


def _tags(datos: Dict[str, Any]) -> List[str]:
    t = datos.get("tags")
    if isinstance(t, str):
        return [t.strip().lower()]
    return [str(x).strip().lower() for x in t] if isinstance(t, list) else []


def criterio_de_arquitectura(rel: str, datos: Dict[str, Any]) -> List[str]:
    """Por qué la nota es de arquitectura; vacío si no lo es."""
    tipo = str(datos.get("type") or "").strip().lower()
    if tipo == SCAFFOLD_TYPE or es_artefacto_derivado(rel):
        return []
    razones = []
    if tipo in TIPOS_DE_ARQUITECTURA:
        razones.append(f"type:{tipo}")
    if any(rel == s or rel.startswith(s + "/") for s in SUBCARPETAS_DE_ARQUITECTURA):
        razones.append("subcarpeta")
    elif rel.split("/", 1)[0] in SECCIONES_DE_ARQUITECTURA:
        razones.append("seccion")
    if TAGS_DE_ARQUITECTURA & set(_tags(datos)):
        razones.append("tag")
    return razones


def _clave_de_historial(rel: str) -> str:
    """El stem con el que `vault_undo` nombra las versiones de `rel`."""
    p = Path(rel)
    return f"{p.parent.as_posix().replace('/', '__')}__{p.stem}"


def _versiones_guardadas(raiz: Path) -> Dict[str, List[Tuple[datetime, int, Path]]]:
    """Clave de nota → versiones de `.history/` con fecha, en orden cronológico."""
    carpeta = raiz / Config.HISTORY_DIR
    por_nota: Dict[str, List[Tuple[datetime, int, Path]]] = {}
    if not carpeta.is_dir():
        return por_nota
    for f in carpeta.iterdir():
        if not f.is_file() or not f.name.endswith(".md"):
            continue
        meta = _parse_history_filename(f.name)
        if meta["timestamp"] is not None:
            por_nota.setdefault(meta["stem"], []).append((meta["timestamp"], meta["secuencia"], f))
    for vs in por_nota.values():
        vs.sort(key=lambda v: (v[0], v[1]))
    return por_nota


def _leer(p: Path, ilegibles: List[Dict[str, str]], rel: str) -> Optional[Dict[str, Any]]:
    try:
        return _datos(p.read_text(encoding="utf-8", errors="replace"))
    except (OSError, FrontmatterParseError) as exc:
        ilegibles.append({"path": rel, "fuente": p.name, "error": str(exc)[:200]})
        return None


class Inventario:
    """Lo que el vault deja escrito: notas, sus versiones y las releases."""

    def __init__(self, raiz: Path, proyecto: Optional[str]):
        self.raiz = raiz
        self.proyecto = proyecto
        self.ilegibles: List[Dict[str, str]] = []
        self.notas: Dict[str, Dict[str, Any]] = {}
        self.releases: List[Dict[str, Any]] = []
        historial = _versiones_guardadas(raiz)
        relativas, aliases = [], {}
        for p in sorted(raiz.rglob("*.md")):
            rel_p = p.relative_to(raiz)
            if is_snapshot_path(rel_p):
                continue
            rel = rel_p.as_posix()
            relativas.append(rel_p)
            datos = _leer(p, self.ilegibles, rel)
            if datos is None:
                continue
            al = datos.get("aliases")
            if isinstance(al, list):
                aliases[rel] = [str(a) for a in al]
            if "version" in datos and "deploy_at" in datos:
                self._release(rel, datos)
            if not self._del_proyecto(rel, datos):
                continue
            criterio = criterio_de_arquitectura(rel, datos)
            if criterio:
                self.notas[rel] = {"actual": datos, "criterio": criterio,
                                   "versiones": historial.get(_clave_de_historial(rel), [])}
        self.indice = indice_de_nombres(relativas, aliases)
        self.releases.sort(key=lambda r: r["fecha"])

    def _del_proyecto(self, rel: str, datos: Dict[str, Any]) -> bool:
        if not self.proyecto:
            return True
        p = self.proyecto.lower()
        return (str(datos.get("project") or "").strip().lower() == p
                or rel.lower().startswith(f"01_projects/{p}/") or p in _tags(datos))

    def _release(self, rel: str, datos: Dict[str, Any]) -> None:
        fecha = _instante(datos.get("deploy_at")) or _instante(datos.get("createdAt"))
        v = _version(datos.get("version"))
        if fecha and v:
            self.releases.append({"path": rel, "project": str(datos.get("project") or ""),
                                  "version": str(datos.get("version")), "tupla": v,
                                  "fecha": fecha, "status": datos.get("status")})

    def datos_en(self, rel: str, d: datetime) -> Tuple[Optional[Dict[str, Any]], str]:
        """El frontmatter de `rel` vivo en `d` y de dónde sale."""
        for ts, _, f in self.notas[rel]["versiones"]:
            if ts > d:
                return _leer(f, self.ilegibles, rel), f"{Config.HISTORY_DIR}/{f.name}"
        return self.notas[rel]["actual"], "actual"

    def creada(self, rel: str) -> Optional[datetime]:
        n = self.notas[rel]
        c = _instante(n["actual"].get("createdAt"))
        if c is None and n["versiones"]:
            primera = _leer(n["versiones"][0][2], self.ilegibles, rel) or {}
            c = _instante(primera.get("createdAt"))
        return c


# ── Estado en un punto ───────────────────────────────────────────────────────

def _punto(inv: Inventario, valor: str) -> Dict[str, Any]:
    """Una fecha `YYYY-MM-DD` (fin del día UTC) o una versión con su release."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
        try:
            d = datetime.combine(date.fromisoformat(valor), time.max, tzinfo=UTC)
        except ValueError:
            raise ValueError(f"{valor}: no es una fecha")
        return {"valor": valor, "fecha": d, "version": None, "release": None}
    v = _version(valor)
    if v is None:
        raise ValueError(f"{valor}: ni fecha YYYY-MM-DD ni versión")
    rs = [r for r in inv.releases if _cmp_version(r["tupla"], v) == 0
          and (not inv.proyecto or r["project"].lower() == inv.proyecto.lower())]
    proyectos = sorted({r["project"] for r in rs})
    if len(proyectos) > 1:
        raise LookupError(proyectos)
    r = rs[0] if rs else None
    return {"valor": valor, "fecha": r["fecha"] if r else None, "version": v,
            "release": r["path"] if r else None}


def estado_en(inv: Inventario, rel: str, punto: Dict[str, Any]) -> Dict[str, Any]:
    """`vigente`, `propuesta`, `retirada`, `inexistente` o `indeterminada` en ese punto."""
    actual = inv.notas[rel]["actual"]
    vd_bruto = actual.get("vigente_desde")
    vd = _version(vd_bruto) if vd_bruto is not None else None
    base = {"path": rel, "criterio": inv.notas[rel]["criterio"]}
    if vd_bruto is not None and vd is None:
        base["vigente_desde_invalido"] = repr(vd_bruto)
    d = punto["fecha"]
    if punto["version"] is not None and vd is not None:
        if _cmp_version(vd, punto["version"]) > 0:
            return {**base, "estado": "inexistente"}
    elif d is None:
        return {**base, "estado": "indeterminada", "motivo": "ni release con fecha ni vigente_desde"}
    else:
        creada = inv.creada(rel)
        if creada is None:
            return {**base, "estado": "indeterminada", "motivo": "sin createdAt"}
        if creada > d:
            return {**base, "estado": "inexistente"}
    datos, fuente = inv.datos_en(rel, d) if d else (actual, "actual")
    if datos is None:
        return {**base, "estado": "indeterminada", "motivo": "versión ilegible", "fuente": fuente}
    canon = normalize_status(datos.get("status"))[0] if datos.get("status") else None
    r = {**base, "fuente": fuente, "title": datos.get("title"), "status": canon,
         "status_escrito": datos.get("status"), "type": datos.get("type")}
    if vd is not None:
        r["vigente_desde"] = str(vd_bruto)
    files = datos.get("files")
    if isinstance(files, list):
        r["files"] = [str(f) for f in files]
    sust = datos.get("superseded_by") or actual.get("superseded_by")
    if sust:
        ruta, _ = resolver_sustitucion(sust, Path(rel), inv.indice)
        r["sustituida_por"] = ruta or str(sust)
        # Solo una versión guardada atestigua que la anotación ya estaba en D: la
        # actual pudo recibirla después.
        escrita = fuente != "actual" and bool(datos.get("superseded_by"))
        if _sustituta_ya_regia(inv, ruta, punto, escrita=escrita):
            return {**r, "estado": "retirada", "motivo": "sustituida"}
    if canon in RETIRADOS:
        # El valor ya va en `status`; repetirlo dentro del motivo lo hacía
        # pasar por una emisión de frontmatter escrita a mano (AP-38).
        return {**r, "estado": "retirada", "motivo": "status"}
    if canon is None:
        return {**r, "estado": "vigente" if not datos.get("status") else "indeterminada",
                "motivo": "sin status" if not datos.get("status") else "status desconocido"}
    regimen = regimen_de_estado(canon, STATUS_TRANSITIONS)
    return {**r, "estado": "propuesta" if regimen == "abierto" else "vigente"}


def _sustituta_ya_regia(inv: Inventario, ruta: str, punto: Dict[str, Any], escrita: bool) -> bool:
    """La sustitución ya había ocurrido en ese punto.

    Escrita en la versión viva entonces, sí. Si solo está en la actual
    (`vault_supersede` no guarda versión), la marca el inicio de la sustituta.
    """
    if escrita:
        return True
    if not ruta:
        return False
    destino = inv.raiz / ruta
    datos = _leer(destino, inv.ilegibles, ruta) if destino.is_file() else None
    if not datos:
        return False
    vd = _version(datos.get("vigente_desde"))
    if punto["version"] is not None and vd is not None:
        return _cmp_version(vd, punto["version"]) <= 0
    creada, d = _instante(datos.get("createdAt")), punto["fecha"]
    return bool(creada and d and creada <= d)


def foto(inv: Inventario, punto: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    grupos: Dict[str, List[Dict[str, Any]]] = {
        "vigentes": [], "propuestas": [], "retiradas": [], "indeterminadas": []}
    for rel in sorted(inv.notas):
        e = estado_en(inv, rel, punto)
        clave = {"vigente": "vigentes", "propuesta": "propuestas", "retirada": "retiradas",
                 "indeterminada": "indeterminadas"}.get(e["estado"])
        if clave:
            grupos[clave].append(e)
    return grupos


def _punto_publico(p: Dict[str, Any]) -> Dict[str, Any]:
    return {"valor": p["valor"], "fecha": p["fecha"].isoformat() if p["fecha"] else None,
            "version": ".".join(map(str, p["version"])) if p["version"] else None,
            "release": p["release"]}


def _eventos(inv: Inventario, a: datetime, b: datetime) -> List[Dict[str, Any]]:
    ev: List[Dict[str, Any]] = []
    for rel, n in inv.notas.items():
        c = inv.creada(rel)
        if c and a < c <= b:
            ev.append({"fecha": c, "evento": "creada", "path": rel})
        for ts, _, f in n["versiones"]:
            if a < ts <= b:
                ev.append({"fecha": ts, "evento": "reescrita", "path": rel,
                           "version_anterior": f"{Config.HISTORY_DIR}/{f.name}"})
    for r in inv.releases:
        if a < r["fecha"] <= b and (not inv.proyecto or r["project"].lower() == inv.proyecto.lower()):
            ev.append({"fecha": r["fecha"], "evento": "release", "path": r["path"],
                       "version": r["version"]})
    ev.sort(key=lambda e: (e["fecha"], e["evento"], e["path"]))
    return [{**e, "fecha": e["fecha"].isoformat()} for e in ev]


# ── Envelope ─────────────────────────────────────────────────────────────────

def _criterio_publico() -> Dict[str, Any]:
    return {"tipos": sorted(TIPOS_DE_ARQUITECTURA), "secciones": list(SECCIONES_DE_ARQUITECTURA),
            "subcarpetas": list(SUBCARPETAS_DE_ARQUITECTURA), "tags": sorted(TAGS_DE_ARQUITECTURA),
            "excluye": [f"type:{SCAFFOLD_TYPE}", "artefactos derivados"],
            "retirada_si_status": sorted(RETIRADOS),
            "release": "frontmatter con version y deploy_at"}


def arquitectura_en(fecha: Optional[str] = None, version: Optional[str] = None,
                    desde: Optional[str] = None, hasta: Optional[str] = None,
                    project: Optional[str] = None) -> Dict[str, Any]:
    modos = [m for m, v in (("fecha", fecha), ("version", version)) if v]
    rango = desde or hasta
    if len(modos) + bool(rango) != 1 or (rango and not (desde and hasta)):
        return emit_error(TOOL, "MISSING_REQUIRED_ARG",
                          "exactamente uno: --fecha, --version o --desde con --hasta",
                          pista="--fecha 2026-05-03 | --version v1.5 | --desde v1.0 --hasta v1.5")
    inv = Inventario(get_vault_root(), project)
    try:
        if rango:
            pa, pb = _punto(inv, desde), _punto(inv, hasta)
        else:
            pa = pb = _punto(inv, fecha or version)
    except ValueError as exc:
        return emit_error(TOOL, "INVALID_VALUE", str(exc), pista="YYYY-MM-DD o vX.Y[.Z]")
    except LookupError as exc:
        return emit_error(TOOL, "PROJECT_AMBIGUOUS",
                          f"esa versión tiene release en varios proyectos: {exc.args[0]}",
                          pista="añade --project")
    for p in (pa, pb):
        if p["version"] is not None and p["fecha"] is None and not any(
                _version(n["actual"].get("vigente_desde")) for n in inv.notas.values()):
            return emit_error(TOOL, "VERSION_NOT_FOUND",
                              f"{p['valor']}: ninguna release con esa versión y ninguna nota "
                              "declara vigente_desde",
                              pista="vault_release_save registra la release; o vigente_desde: en la nota")
    base = {"ok": True, "tool": TOOL, "project": project, "notas_de_arquitectura": len(inv.notas),
            "criterio": _criterio_publico(), "ilegibles": inv.ilegibles}
    if not rango:
        return {**base, "modo": "punto", "punto": _punto_publico(pa), **foto(inv, pa)}
    fa, fb = foto(inv, pa), foto(inv, pb)
    vivas = lambda f: {e["path"]: e for k in ("vigentes", "propuestas") for e in f[k]}  # noqa: E731
    va, vb = vivas(fa), vivas(fb)
    retiradas_b = {e["path"]: e for e in fb["retiradas"]}
    cambiaron = [p for p in sorted(set(va) & set(vb))
                 if va[p].get("fuente") != vb[p].get("fuente") or va[p]["estado"] != vb[p]["estado"]]
    r = {**base, "modo": "rango", "desde": _punto_publico(pa), "hasta": _punto_publico(pb),
         "entraron": [vb[p] for p in sorted(set(vb) - set(va))],
         "salieron": [retiradas_b.get(p, {"path": p, "estado": "desaparecida"})
                      for p in sorted(set(va) - set(vb))],
         "cambiaron": [{"path": p, "antes": va[p], "despues": vb[p]} for p in cambiaron],
         "al_final": fb}
    if pa["fecha"] and pb["fecha"]:
        r["eventos"] = _eventos(inv, pa["fecha"], pb["fecha"])
    return r


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_arquitectura_en — la arquitectura de un proyecto en una fecha o versión",
        allow_abbrev=False)
    ap.add_argument("--fecha", help="YYYY-MM-DD: qué arquitectura regía al final de ese día")
    ap.add_argument("--version", help="vX.Y[.Z]: qué regía en esa versión del proyecto")
    ap.add_argument("--desde", help="inicio del rango: fecha o versión")
    ap.add_argument("--hasta", help="fin del rango: fecha o versión")
    # AP-63: el nombre se resuelve antes de filtrar. Sin resolver, un alias o
    # una errata devolvían una arquitectura vacía con ok: true, indistinguible
    # de un proyecto que no decidió nada.
    ap.add_argument("--project", type=proyecto_registrado(TOOL),
                    help="limita a las notas y releases de ese proyecto")
    args = ap.parse_args()
    r = arquitectura_en(fecha=args.fecha, version=args.version, desde=args.desde,
                        hasta=args.hasta, project=args.project)
    print(json.dumps(r, ensure_ascii=False, default=str))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, TOOL))

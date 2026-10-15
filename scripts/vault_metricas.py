#!/usr/bin/env python3
"""vault_metricas — métricas de desarrollo y de producto con objetivo, dueño y tendencia.

## Por qué existe

Hasta 2026-10-14 el repo medía su **deuda** —las baselines llevan objetivo,
fecha, cadencia y dueño desde v40.24— pero no su **proceso** ni su
**producto**. Cuánto tarda la suite, cuántos fallos destapa cada ronda, cuántas
tools fallan el smoke, qué tal le va al agente del banco: esas cifras se
ejecutaban, se leían en un log de `%TEMP%` y se perdían. Sin histórico no hay
tendencia, y sin tendencia «va mejor» es una opinión.

## Lo que es registro y lo que es observación

- `METRICAS` es el registro: qué mide cada una, de dónde sale, en qué sentido
  mejora y a qué se compromete. El plazo —fecha límite, cadencia, dueño— se
  valida con `vault_baseline.validar_plazo`, el mismo contrato que las
  baselines: tres sitios validando la misma fecha serían AP-57.
- Las **calculadas** se derivan del repo en cada ejecución (deuda pendiente,
  baselines vencidas, commits por versión…). No se guardan: guardarlas sería
  una segunda copia del dato (AP-05).
- Las **observadas** salen de ejecuciones caras que no se repiten en cada
  puerta (suite, smoke, banco). Viven en `scripts/metricas-observaciones.json`,
  **solo de añadir**: cada una con el commit que la produjo, y la puerta falla
  si el commit no existe o si una observación que estaba en HEAD desaparece
  (AP-53 — un histórico que se puede reescribir no es un histórico).

## Lo que no hace fallar la puerta

`vencido` (el plazo pasó sin cumplir) y `desactualizada` (la última observación
es más vieja que la cadencia) se publican en `alertas`, como el plano publica
las baselines vencidas: una puerta que se pone roja porque pasó un día haría
que el compromiso cómodo fuese no fecharlo.

    python scripts/vault_metricas.py --check --strict          # la puerta
    python scripts/vault_metricas.py --doc                     # regenera docs/METRICAS.md
    python scripts/vault_metricas.py --registrar-suite LOG     # resumen de pytest
    python scripts/vault_metricas.py --registrar-smoke JSON    # salida de vault_smoke
    python scripts/vault_metricas.py --registrar ID --valor N --fuente TEXTO
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

import vault_baseline
from vault_errors import emit_error, wrap_main
from vault_io import atomic_write_text

RAIZ = Path(__file__).resolve().parent.parent
OBSERVACIONES = RAIZ / "scripts" / "metricas-observaciones.json"
DOC = RAIZ / "docs" / "METRICAS.md"
_REL_OBSERVACIONES = "scripts/metricas-observaciones.json"

TIPOS = ("desarrollo", "producto")
SENTIDOS = ("menor", "mayor")
ORIGENES = ("calculada", "observada")

#: Dueño de los objetivos iniciales. Se fijaron en «no empeorar» respecto a lo
#: medido el día del alta; quien los revise los sube o los baja con su nombre.
_DUENO = "meta_toolkit — vault_metricas"


def _plazo(valor: float, fecha: str = "2027-01-14", cadencia: int = 30) -> Dict[str, Any]:
    return {"valor": valor, "fecha_limite": fecha, "cadencia_dias": cadencia, "dueno": _DUENO}


METRICAS: List[Dict[str, Any]] = [
    # ── Desarrollo ───────────────────────────────────────────────────────────
    {"id": "deuda_pendiente", "tipo": "desarrollo", "origen": "calculada", "sentido": "menor",
     "unidad": "entradas",
     "que": "Deudas declaradas en el plano que siguen `pendiente`.",
     "fuente": "vault_blueprint.DEUDA_DECLARADA",
     "objetivo": _plazo(2)},
    {"id": "normas_vencidas", "tipo": "desarrollo", "origen": "calculada", "sentido": "menor",
     "unidad": "normas",
     "que": "Normas cuya revisión venció: `revisado_en` más su cadencia ya pasó (R4).",
     "fuente": "vault_norms_catalog.gestion_de_normas",
     "objetivo": _plazo(0)},
    {"id": "baselines_vencidas", "tipo": "desarrollo", "origen": "calculada", "sentido": "menor",
     "unidad": "baselines",
     "que": "Baselines cuyo objetivo pasó de fecha sin cumplirse.",
     "fuente": "vault_baseline.estado_objetivo sobre vault_blueprint._BASELINES",
     "objetivo": _plazo(0)},
    {"id": "baselines_por_encima_de_objetivo", "tipo": "desarrollo", "origen": "calculada",
     "sentido": "menor", "unidad": "baselines",
     "que": "Baselines con objetivo que todavía no han encogido hasta él (en plazo o vencidas).",
     "fuente": "vault_baseline.estado_objetivo sobre vault_blueprint._BASELINES",
     "objetivo": _plazo(7)},
    {"id": "commits_ultima_version", "tipo": "desarrollo", "origen": "calculada",
     "sentido": "menor", "unidad": "commits",
     "que": "Commits entre el hash de la penúltima versión del changelog y el de la última.",
     "fuente": "vault_changelog_check.entradas + git rev-list",
     "sin_objetivo_porque": ("mide el tamaño del lote, no su calidad: un objetivo empujaría "
                             "a partir o juntar commits para cumplirlo")},
    {"id": "dias_entre_versiones", "tipo": "desarrollo", "origen": "calculada",
     "sentido": "menor", "unidad": "días",
     "que": "Días entre la fecha de la penúltima versión del changelog y la de la última.",
     "fuente": "vault_changelog_check.entradas",
     "sin_objetivo_porque": ("la versión sube con permiso del usuario, no por calendario: "
                             "fecharla sería medir cuándo se pide el permiso")},
    {"id": "suite_fallos", "tipo": "desarrollo", "origen": "observada", "sentido": "menor",
     "unidad": "tests",
     "que": "Tests en rojo en una ronda completa de la suite (failed + errors).",
     "fuente": "resumen final de `python -m pytest tests/` (--registrar-suite)",
     "objetivo": _plazo(0)},
    {"id": "suite_duracion_s", "tipo": "desarrollo", "origen": "observada", "sentido": "menor",
     "unidad": "s",
     "que": "Duración de una ronda completa de la suite, según pytest.",
     "fuente": "resumen final de `python -m pytest tests/` (--registrar-suite)",
     "objetivo": _plazo(4339)},
    {"id": "suite_tests", "tipo": "desarrollo", "origen": "observada", "sentido": "mayor",
     "unidad": "tests",
     "que": "Tests ejecutados en una ronda completa de la suite.",
     "fuente": "resumen final de `python -m pytest tests/` (--registrar-suite)",
     "sin_objetivo_porque": ("crece por diseño —toda norma con guard lleva test— y un objetivo "
                             "premiaría escribir tests por la cifra")},
    # ── Producto ─────────────────────────────────────────────────────────────
    {"id": "promesas_descubiertas", "tipo": "producto", "origen": "calculada",
     "sentido": "menor", "unidad": "promesas",
     "que": "Promesas a quien instala (versión, dependencia, plataforma, red) sin ejecutor.",
     "fuente": "vault_produccion.check()['descubiertas']",
     "objetivo": _plazo(0)},
    {"id": "colisiones_de_sanadores", "tipo": "desarrollo", "origen": "observada",
     "sentido": "menor", "unidad": "colisiones",
     "que": ("Normas ajenas que un sanador de SANADORES hace subir al reparar las "
             "suyas (AP-55, C8), sobre una copia temporal del vault medido."),
     "fuente": "`collisions_total` de `python scripts/vault_norms_coherence.py --colisiones`",
     "objetivo": _plazo(0)},
    {"id": "smoke_fallos", "tipo": "producto", "origen": "observada", "sentido": "menor",
     "unidad": "tools",
     "que": "Tools del catálogo que fallan el smoke.",
     "fuente": "`failing` de `python scripts/vault_smoke.py` (--registrar-smoke)",
     "objetivo": _plazo(0)},
    {"id": "banco_tareas_fallidas", "tipo": "producto", "origen": "observada",
     "sentido": "menor", "unidad": "tareas",
     "que": "Tareas del banco del agente (orientar, escribir, recuperarse…) que no salen ok.",
     "fuente": "informe JSON de `tests/banco_agente.py` (--registrar-banco)",
     "objetivo": _plazo(0)},
    {"id": "recall_pack_ajeno", "tipo": "producto", "origen": "observada", "sentido": "mayor",
     "unidad": "fracción",
     "que": "Recall del paquete de contexto sobre la copia de un vault ajeno (regla 7).",
     "fuente": "`recuerdo_preexistente.recall_pack` de `banco_agente.py --copiar-de` (--registrar-banco)",
     # Línea base: 1.0 sobre una copia de /vcloud (muestra 25) en df0ff4d. Un vault
     # distinto puede dar otra cifra: la fuente de cada observación dice cuál.
     "objetivo": _plazo(1.0)},
]


# ── Calculadas ───────────────────────────────────────────────────────────────

def _git(*args: str) -> Optional[str]:
    try:
        r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True,
                           encoding="utf-8", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _estados_de_baselines() -> List[str]:
    import vault_blueprint
    return [vault_baseline.estado_objetivo(RAIZ / "scripts" / f, clave, norma)["estado"]
            for f, clave, norma in vault_blueprint._BASELINES
            if (RAIZ / "scripts" / f).exists()]


def _dos_ultimas_versiones() -> List[Dict[str, str]]:
    """Las dos últimas versiones **cerradas** del changelog.

    Mientras dura un bump la cabeza lleva `git: pending`, que no es un commit:
    medirla ponía la puerta `metricas` en rojo justo en el commit que sube la
    versión. Una versión en curso no tiene todavía tamaño ni fecha de cierre.
    """
    import vault_changelog_check
    entradas = [e for e in vault_changelog_check.entradas()
                if e["hash"] not in vault_changelog_check.NO_HASH]
    if len(entradas) < 2:
        raise ValueError("el changelog tiene menos de dos versiones cerradas")
    return entradas[:2]


def _deuda_pendiente() -> int:
    import vault_blueprint
    return sum(1 for d in vault_blueprint.DEUDA_DECLARADA if d.get("estado") == "pendiente")


def _normas_vencidas() -> int:
    from vault_norms_catalog import gestion_de_normas
    return len(gestion_de_normas()["vencidas"])


def _commits_ultima_version() -> int:
    ultima, previa = _dos_ultimas_versiones()
    salida = _git("rev-list", "--count", f"{previa['hash']}..{ultima['hash']}")
    if salida is None:
        raise ValueError(f"git no resuelve {previa['hash']}..{ultima['hash']}")
    return int(salida)


def _dias_entre_versiones() -> int:
    ultima, previa = _dos_ultimas_versiones()
    a = datetime.strptime(previa["fecha"], "%Y-%m-%d").date()
    b = datetime.strptime(ultima["fecha"], "%Y-%m-%d").date()
    return (b - a).days


def _promesas_descubiertas() -> int:
    import vault_produccion
    return int(vault_produccion.check()["descubiertas"])


CALCULOS: Dict[str, Callable[[], float]] = {
    "deuda_pendiente": _deuda_pendiente,
    "normas_vencidas": _normas_vencidas,
    "baselines_vencidas": lambda: sum(1 for e in _estados_de_baselines() if e == "vencido"),
    "baselines_por_encima_de_objetivo": lambda: sum(
        1 for e in _estados_de_baselines() if e in ("en_plazo", "vencido")),
    "commits_ultima_version": _commits_ultima_version,
    "dias_entre_versiones": _dias_entre_versiones,
    "promesas_descubiertas": _promesas_descubiertas,
}


# ── Registro ─────────────────────────────────────────────────────────────────

def _es_numero(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def problemas_de_registro(m: Dict[str, Any]) -> List[str]:
    """Por qué esta entrada del registro no vale. Lista vacía = vale."""
    problemas: List[str] = []
    for campo in ("id", "tipo", "origen", "sentido", "unidad", "que", "fuente"):
        if not (isinstance(m.get(campo), str) and m[campo].strip()):
            problemas.append(f"falta `{campo}`")
    for campo, vocab in (("tipo", TIPOS), ("sentido", SENTIDOS), ("origen", ORIGENES)):
        if m.get(campo) is not None and m[campo] not in vocab:
            problemas.append(f"`{campo}` debe ser uno de {', '.join(vocab)}")
    if m.get("origen") == "calculada" and m.get("id") not in CALCULOS:
        problemas.append("calculada sin entrada en CALCULOS")
    objetivo, motivo = m.get("objetivo"), m.get("sin_objetivo_porque")
    if objetivo is None and motivo is None:
        problemas.append("ni `objetivo` ni `sin_objetivo_porque`: no comprometerse "
                         "también se declara, con su motivo")
    elif objetivo is not None and motivo is not None:
        problemas.append("`objetivo` y `sin_objetivo_porque` a la vez se contradicen")
    elif objetivo is not None:
        if not isinstance(objetivo, dict):
            problemas.append("`objetivo` debe ser un objeto")
        else:
            if not _es_numero(objetivo.get("valor")):
                problemas.append("`objetivo.valor` debe ser un número")
            problemas.extend(vault_baseline.validar_plazo(objetivo))
    elif not (isinstance(motivo, str) and motivo.strip()):
        problemas.append("`sin_objetivo_porque` debe decir por qué, no estar en blanco")
    return problemas


def estado(m: Dict[str, Any], valor: Optional[float],
           hoy: Optional[date] = None) -> Dict[str, Any]:
    """Si la métrica cumple su compromiso. Sin valor no hay cumplimiento: `sin_observar`."""
    hoy = hoy or date.today()
    objetivo = m.get("objetivo")
    if objetivo is None:
        return {"estado": "no_aplica", "valor": valor, "motivo": m.get("sin_objetivo_porque")}
    if valor is None:
        return {"estado": "sin_observar", "valor": None}
    meta = objetivo["valor"]
    cumple = valor <= meta if m["sentido"] == "menor" else valor >= meta
    limite = datetime.strptime(objetivo["fecha_limite"], "%Y-%m-%d").date()
    if cumple:
        e = "cumple"
    elif hoy > limite:
        e = "vencido"
    else:
        e = "en_plazo"
    return {"estado": e, "valor": valor, "objetivo": meta,
            "dias_restantes": (limite - hoy).days}


# ── Observaciones ────────────────────────────────────────────────────────────

def _leer(texto: str) -> List[Dict[str, Any]]:
    datos = json.loads(texto)
    obs = datos.get("observaciones") if isinstance(datos, dict) else None
    if not isinstance(obs, list):
        raise ValueError("se esperaba un objeto con la lista `observaciones`")
    return obs


def _observaciones() -> List[Dict[str, Any]]:
    if not OBSERVACIONES.exists():
        return []
    return _leer(OBSERVACIONES.read_text(encoding="utf-8"))


def _observaciones_en_head() -> List[Dict[str, Any]]:
    texto = _git("show", f"HEAD:{_REL_OBSERVACIONES}")
    return _leer(texto) if texto else []


def _commit_existe(h: str) -> bool:
    return isinstance(h, str) and bool(h) and _git("cat-file", "-e", f"{h}^{{commit}}") is not None


def _clave(o: Dict[str, Any]) -> str:
    return json.dumps(o, sort_keys=True, ensure_ascii=False)


_RESUMEN = re.compile(r"=+ (?P<cuerpo>[^=]*?\bin (?P<dur>[\d.]+)s\b[^=]*?) =+")


def leer_resumen_pytest(texto: str) -> Dict[str, float]:
    """La última línea de resumen de pytest. Sin ella, `ValueError`: un log
    cortado no es una ronda en verde."""
    encontrados = list(_RESUMEN.finditer(texto))
    if not encontrados:
        raise ValueError("no hay línea de resumen de pytest (`N passed … in Xs`)")
    m = encontrados[-1]
    cuenta = {k: int(n) for n, k in re.findall(r"(\d+) (\w+)", m.group("cuerpo"))}
    fallos = cuenta.get("failed", 0) + cuenta.get("errors", 0) + cuenta.get("error", 0)
    return {"suite_fallos": fallos,
            "suite_tests": cuenta.get("passed", 0) + fallos,
            "suite_duracion_s": float(m.group("dur"))}


def registrar(valores: List[Dict[str, Any]], commit: Optional[str] = None,
              fuente: str = "", hoy: Optional[date] = None) -> Dict[str, Any]:
    """Añade observaciones al histórico. Nunca reescribe ni borra las previas."""
    tool = "vault_metricas"
    por_id = {m["id"]: m for m in METRICAS}
    for v in valores:
        m = por_id.get(v.get("metrica"))
        if m is None:
            return emit_error(tool, "INVALID_VALUE", f"métrica desconocida: {v.get('metrica')}",
                              pista=", ".join(i for i, x in por_id.items()
                                              if x["origen"] == "observada"))
        if m["origen"] != "observada":
            return emit_error(tool, "INVALID_VALUE",
                              f"{m['id']} es calculada: se deriva del repo, no se registra",
                              pista="solo se registran métricas observadas")
        if not _es_numero(v.get("valor")):
            return emit_error(tool, "INVALID_VALUE", f"{m['id']}: el valor debe ser un número")
    if not (isinstance(fuente, str) and fuente.strip()):
        return emit_error(tool, "MISSING_REQUIRED_ARG", "toda observación dice de dónde sale",
                          pista="--fuente 'log de la ronda rNN'")
    commit = commit or _git("rev-parse", "--short", "HEAD")
    if not commit or not _commit_existe(commit):
        return emit_error(tool, "INVALID_VALUE", f"commit inexistente: {commit}",
                          pista="el commit sobre el que se midió, --commit HASH")
    # La fecha es la del commit medido, no la del registro: una ronda de hace
    # un mes registrada hoy sigue diciendo cómo estaba el código hace un mes.
    fecha = _git("show", "-s", "--format=%cs", commit) or (hoy or date.today()).isoformat()
    previas = _observaciones() if OBSERVACIONES.exists() else []
    nuevas = [{"metrica": v["metrica"], "valor": v["valor"], "commit": commit,
               "fecha": fecha, "fuente": fuente.strip()} for v in valores]
    datos = {"description": ("Observaciones de vault_metricas: solo de añadir. Cada una "
                             "con el commit sobre el que se midió; la puerta falla si "
                             "una desaparece."),
             "observaciones": previas + nuevas}
    atomic_write_text(OBSERVACIONES, json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", sanitize=False)
    return {"ok": True, "tool": tool, "action": "registrar", "registradas": len(nuevas),
            "added": len(nuevas), "observaciones": nuevas}


# ── Valores, documento y check ───────────────────────────────────────────────

def _ultima(obs: List[Dict[str, Any]], metrica: str) -> Optional[Dict[str, Any]]:
    propias = [o for o in obs if o.get("metrica") == metrica]
    return propias[-1] if propias else None


def documento() -> str:
    """`docs/METRICAS.md`: el registro y el histórico. Sin estados: dependen del día."""
    obs = _observaciones()
    lineas = [
        "# Métricas de desarrollo y de producto",
        "",
        "> **Derivado** de `scripts/vault_metricas.py` (`METRICAS`) y de",
        "> `scripts/metricas-observaciones.json`. Se regenera con",
        "> `python scripts/vault_metricas.py --doc`; lo escrito a mano se pierde.",
        "> El estado de cada métrica (cumple, en plazo, vencido) depende del día y",
        "> no se publica aquí: lo da `python scripts/vault_metricas.py --check`.",
        "",
    ]
    for tipo in TIPOS:
        lineas += [f"## {tipo.capitalize()}", "",
                   "| Métrica | Qué mide | Origen | Mejora si | Objetivo | Fuente |",
                   "|---|---|---|---|---|---|"]
        for m in (x for x in METRICAS if x["tipo"] == tipo):
            o = m.get("objetivo")
            signo = "≤" if m["sentido"] == "menor" else "≥"
            obj = (f"{signo} {o['valor']} {m['unidad']} para {o['fecha_limite']} · cada "
                   f"{o['cadencia_dias']} d · {o['dueno']}" if o
                   else f"— *sin objetivo*: {m['sin_objetivo_porque']}")
            lineas.append(f"| `{m['id']}` | {m['que']} | {m['origen']} | "
                          f"{'baja' if m['sentido'] == 'menor' else 'sube'} | {obj} | "
                          f"{m['fuente']} |")
        lineas.append("")
    lineas += ["## Histórico de observaciones", ""]
    if not obs:
        lineas += ["*Ninguna todavía.*", ""]
    else:
        lineas += ["| Fecha | Commit | Métrica | Valor | Fuente |", "|---|---|---|---|---|"]
        for o in obs:
            lineas.append(f"| {o.get('fecha')} | `{o.get('commit')}` | `{o.get('metrica')}` | "
                          f"{o.get('valor')} | {o.get('fuente')} |")
        lineas.append("")
    return "\n".join(lineas)


def escribir_doc() -> Dict[str, Any]:
    texto = documento()
    previo = DOC.read_text(encoding="utf-8") if DOC.exists() else None
    cambiado = previo != texto
    if cambiado:
        atomic_write_text(DOC, texto, encoding="utf-8", sanitize=False)
    return {"ok": True, "tool": "vault_metricas", "action": "doc",
            "changed": cambiado, "path": "docs/METRICAS.md"}


def check_doc() -> Dict[str, Any]:
    previo = DOC.read_text(encoding="utf-8") if DOC.exists() else None
    return {"ok": previo == documento(), "path": "docs/METRICAS.md"}


def check(hoy: Optional[date] = None) -> Dict[str, Any]:
    hoy = hoy or date.today()
    problemas: List[Dict[str, Any]] = []
    alertas: List[Dict[str, Any]] = []
    ids = [m.get("id") for m in METRICAS]
    for i in sorted({i for i in ids if ids.count(i) > 1}):
        problemas.append({"kind": "id_duplicado", "metrica": i})
    for m in METRICAS:
        for p in problemas_de_registro(m):
            problemas.append({"kind": "registro_invalido", "metrica": m.get("id"), "detalle": p})

    try:
        obs = _observaciones()
    except (OSError, ValueError) as exc:  # json.JSONDecodeError es ValueError
        obs = []
        problemas.append({"kind": "observaciones_ilegibles", "detalle": str(exc)})
    por_id = {m["id"]: m for m in METRICAS}
    commits_vistos: Dict[str, bool] = {}
    for o in obs:
        if not (isinstance(o, dict) and _es_numero(o.get("valor"))
                and all(isinstance(o.get(k), str) and o[k] for k in
                        ("metrica", "commit", "fecha", "fuente"))):
            problemas.append({"kind": "observacion_mal_formada", "observacion": o})
            continue
        m = por_id.get(o["metrica"])
        if m is None:
            problemas.append({"kind": "observacion_de_metrica_desconocida", "observacion": o})
        elif m["origen"] != "observada":
            problemas.append({"kind": "observacion_de_metrica_calculada", "observacion": o})
        if o["commit"] not in commits_vistos:
            commits_vistos[o["commit"]] = _commit_existe(o["commit"])
        if not commits_vistos[o["commit"]]:
            problemas.append({"kind": "observacion_sin_commit", "observacion": o})
    try:
        actuales = {_clave(o) for o in obs}
        for o in _observaciones_en_head():
            if _clave(o) not in actuales:
                problemas.append({"kind": "observacion_borrada", "observacion": o})
    except ValueError as exc:
        problemas.append({"kind": "observaciones_ilegibles", "detalle": f"HEAD: {exc}"})

    filas: List[Dict[str, Any]] = []
    for m in METRICAS:
        if m.get("id") not in por_id or problemas_de_registro(m):
            continue
        fila: Dict[str, Any] = {"metrica": m["id"], "tipo": m["tipo"], "origen": m["origen"]}
        if m["origen"] == "calculada":
            try:
                valor: Optional[float] = CALCULOS[m["id"]]()
            except Exception as exc:  # noqa: BLE001 — el fallo se publica como problema
                problemas.append({"kind": "calculo_fallido", "metrica": m["id"],
                                  "detalle": f"{type(exc).__name__}: {exc}"})
                continue
        else:
            ultima = _ultima(obs, m["id"])
            valor = ultima["valor"] if ultima else None
            if ultima:
                fila["commit"], fila["fecha"] = ultima["commit"], ultima["fecha"]
                cadencia = (m.get("objetivo") or {}).get("cadencia_dias")
                try:
                    edad = (hoy - datetime.strptime(ultima["fecha"], "%Y-%m-%d").date()).days
                except ValueError:
                    edad = None
                if cadencia and edad is not None and edad > cadencia:
                    alertas.append({"kind": "desactualizada", "metrica": m["id"],
                                    "dias": edad, "cadencia_dias": cadencia})
        fila.update(estado(m, valor, hoy=hoy))
        if fila["estado"] == "vencido":
            alertas.append({"kind": "vencido", "metrica": m["id"], "valor": valor,
                            "objetivo": fila.get("objetivo")})
        filas.append(fila)

    if not check_doc()["ok"]:
        problemas.append({"kind": "doc_divergente", "path": "docs/METRICAS.md",
                          "fix": "python scripts/vault_metricas.py --doc"})
    return {"ok": not problemas, "tool": "vault_metricas", "action": "check",
            "metricas": len(METRICAS), "observaciones": len(obs), "filas": filas,
            "alertas": alertas, "problems": problemas,
            "hint": ("Verde dice que el registro es coherente y el histórico no se ha "
                     "reescrito; si una métrica cumple lo dice su fila, y lo vencido "
                     "va en `alertas` sin poner la puerta en rojo.")}


# ── CLI ──────────────────────────────────────────────────────────────────────

def _desde_banco(datos: Dict[str, Any]) -> List[Dict[str, Any]]:
    tareas = datos.get("tareas")
    if not isinstance(tareas, dict):
        raise ValueError("el informe del banco no trae `tareas`")
    valores = [{"metrica": "banco_tareas_fallidas",
                "valor": sum(1 for t in tareas.values() if not (t or {}).get("ok"))}]
    recall = (datos.get("recuerdo_preexistente") or {}).get("recall_pack")
    if _es_numero(recall):
        valores.append({"metrica": "recall_pack_ajeno", "valor": recall})
    return valores


def main() -> int:
    tool = "vault_metricas"
    ap = argparse.ArgumentParser(
        description="vault_metricas — métricas de desarrollo y de producto", allow_abbrev=False)
    ap.add_argument("--check", action="store_true", help="Registro, histórico y documento")
    ap.add_argument("--strict", action="store_true", help="Exit 1 si el check falla")
    ap.add_argument("--doc", action="store_true", help="Regenera docs/METRICAS.md")
    ap.add_argument("--registrar-suite", metavar="LOG", help="Log de una ronda de pytest")
    ap.add_argument("--registrar-smoke", metavar="JSON", help="Salida JSON de vault_smoke")
    ap.add_argument("--registrar-banco", metavar="JSON", help="Informe JSON de banco_agente")
    ap.add_argument("--registrar", metavar="ID", help="Registra una métrica observada")
    ap.add_argument("--valor", type=float, help="Valor para --registrar")
    ap.add_argument("--fuente", help="De dónde sale la observación")
    ap.add_argument("--commit", help="Commit sobre el que se midió (por defecto HEAD)")
    args = ap.parse_args()

    acciones = [a for a in ("check", "doc", "registrar_suite", "registrar_smoke",
                            "registrar_banco", "registrar") if getattr(args, a)]
    if len(acciones) > 1:
        print(json.dumps(emit_error(tool, "CONFLICTING_ARGS",
                                    f"acciones incompatibles: {', '.join(acciones)}",
                                    pista="una acción por llamada"), ensure_ascii=False))
        return 1

    def _fichero(ruta: str) -> str:
        return Path(ruta).read_text(encoding="utf-8", errors="replace")

    try:
        if args.doc:
            r = escribir_doc()
        elif args.registrar_suite:
            resumen = leer_resumen_pytest(_fichero(args.registrar_suite))
            r = registrar([{"metrica": k, "valor": v} for k, v in resumen.items()],
                          commit=args.commit,
                          fuente=args.fuente or f"pytest sobre {Path(args.registrar_suite).name}")
        elif args.registrar_smoke:
            datos = json.loads(_fichero(args.registrar_smoke))
            r = registrar([{"metrica": "smoke_fallos", "valor": int(datos["failing"])}],
                          commit=args.commit,
                          fuente=args.fuente or f"vault_smoke sobre {datos.get('checked')} tools")
        elif args.registrar_banco:
            r = registrar(_desde_banco(json.loads(_fichero(args.registrar_banco))),
                          commit=args.commit,
                          fuente=args.fuente or f"banco_agente sobre {Path(args.registrar_banco).name}")
        elif args.registrar:
            if args.valor is None:
                r = emit_error(tool, "MISSING_REQUIRED_ARG", "--registrar necesita --valor")
            else:
                valor = int(args.valor) if args.valor.is_integer() else args.valor
                r = registrar([{"metrica": args.registrar, "valor": valor}],
                              commit=args.commit, fuente=args.fuente or "")
        else:
            r = check()
    except (OSError, ValueError, KeyError) as exc:
        r = emit_error(tool, "INVALID_VALUE", f"{type(exc).__name__}: {exc}",
                       pista="el fichero no tiene la forma esperada")
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if args.check or not acciones:
        return 1 if args.strict and not r["ok"] else 0
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_metricas"))

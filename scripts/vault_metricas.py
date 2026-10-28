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
    python scripts/vault_metricas.py --registrar-puertas JSON  # salida de vault_gate --strict
    python scripts/vault_metricas.py --registrar ID --valor N --fuente TEXTO
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

import vault_baseline
from vault_errors import emit_error, wrap_main
from vault.kernel import procesos_git
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
    # ── Producto: lo que le cuesta al agente ─────────────────────────────────
    # v41.20. Hasta aquí todas las métricas medían el coste de quien mantiene
    # el repo (suite, puertas, baselines) o el de las tools contadas por
    # unidad de trabajo. Ninguna medía lo que le pasa a quien lo usa, y lo que
    # lo usa es un agente con presupuesto: si consultar la memoria cuesta
    # segundos, deja de consultar la memoria, y eso no rompe nada — solo
    # deja de servir para lo que existe.
    {"id": "contexto_agente_s", "tipo": "producto", "origen": "observada", "sentido": "menor",
     "unidad": "s",
     "que": "Coste de la cadena de consulta de contexto que paga el agente: "
            "vault_query_parse + vault_context_pack sobre un vault real.",
     "fuente": "`vault_metricas --registrar-contexto` (mide la ronda; no acepta "
               "un número a mano: una métrica de producto que se rellena a "
               "mano no mide el producto)",
     "objetivo": {"valor": 12, "fecha_limite": "2026-12-31", "cadencia_dias": 30,
                  "dueno": "meta_toolkit — vault_metricas"}},
    {"id": "skip_path_escritura_s", "tipo": "producto", "origen": "observada", "sentido": "menor",
     "unidad": "s",
     "que": "Coste de una corrida de onboarding que no escribe nada: el caso "
            "que se paga por convención en cada reintento.",
     "fuente": "`vault_metricas --registrar-skip` (doble pasada real sobre un "
               "proyecto demo)",
     "objetivo": {"valor": 2, "fecha_limite": "2026-12-31", "cadencia_dias": 30,
                  "dueno": "meta_toolkit — vault_metricas"}},

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
    {"id": "deuda_viva_baselines", "tipo": "desarrollo", "origen": "calculada", "sentido": "menor",
     "unidad": "sitios",
     "que": ("Sitios de deuda **vivos** en todas las baselines que declaran ser "
             "deuda. Una baseline que declara no serlo queda fuera: su contrato "
             "de estabilidad no es deuda que encoger."),
     "fuente": "vault_baseline.tamano_congelado sobre vault_blueprint._BASELINES",
     "objetivo": {"valor": 92, "fecha_limite": "2027-06-30", "cadencia_dias": 90,
                   "dueno": "meta_toolkit — vault_metricas",
                   "por_que": ("Medido el 2026-10-28: 92 sitios vivos en ocho "
                               "baselines de deuda, de 255 antes de la consolidación "
                               "(la del layout bajó de 175 a 16 sola). El objetivo "
                               "promete que no crece; el plazo y el dueño de cada "
                               "deuda viven en su propia baseline, que es donde se "
                               "reclama el trabajo.")}},
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
    {"id": "puertas_duracion_s", "tipo": "desarrollo", "origen": "observada", "sentido": "menor",
     "unidad": "s",
     "que": ("Suma de lo que tardan las puertas en verde, según vault_gate. La paga cada "
             "commit, no cada ronda: crecer aquí es AP-66 en el proceso del repo."),
     "fuente": "`seconds` de `python scripts/vault_gate.py --strict` (--registrar-puertas)",
     "objetivo": _plazo(87)},
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
    """`git <args>` en el repo, o `None`. Desde AP-68 el verbo lo juzga el
    dueño: aquí son `rev-list`, `show`, `cat-file -e` y `rev-parse` —nunca un
    mutador— y los hashes que salen de METRICAS se validan antes del argv
    (`_hash_o_none`)."""
    try:
        r = procesos_git.ejecutar_git(RAIZ, list(args),
                                      capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError, procesos_git.GitProhibido):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _hash_o_none(valor: Any) -> Optional[str]:
    """Un hash de METRICAS, o `None` si no tiene forma de hash (AP-68).

    METRICAS es un fichero que una persona edita a mano; su columna `commit`
    es una observación, no una confianza. Antes de ponerla en el argv de
    `git show` o `git rev-list` —que un valor que empiece por `--` puede
    alterar— se pasa por el dueño del criterio.
    """
    try:
        return procesos_git.asegurar_hash(str(valor), campo="metricas.commit")
    except procesos_git.RefInvalida:
        return None


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


def _deuda_viva_por_baseline() -> Dict[str, Dict[str, Any]]:
    """La deuda viva, baseline por baseline.

    Solo cuentan las baselines que **declaran** ser deuda: una con
    `sin_objetivo_porque` (el contrato de campos con los consumidores) tiene
    1.471 entradas y ninguna es un sitio que encoger —contarlas inflaría la
    métrica con un contrato que no se negocia.
    """
    import vault_blueprint

    salida: Dict[str, Dict[str, Any]] = {}
    for fichero, clave, norma in vault_blueprint._BASELINES:
        ruta = RAIZ / "scripts" / fichero
        if not ruta.exists():
            continue
        estado = vault_baseline.estado_objetivo(ruta, clave, norma)
        if estado["estado"] == "no_aplica":
            continue
        datos = vault_baseline.cargar_datos(ruta, norma)
        salida.setdefault(fichero, {})[clave] = {
            "sitios": vault_baseline.tamano_congelado(datos.get(clave)),
            "estado": estado["estado"],
            "objetivo": estado.get("objetivo"),
        }
    return salida


def _deuda_viva_baselines() -> int:
    """Los sitios de deuda vivos, sumados."""
    return sum(
        entrada["sitios"]
        for claves in _deuda_viva_por_baseline().values()
        for entrada in claves.values()
    )


def _normas_vencidas() -> int:
    from vault_norms_catalog import gestion_de_normas
    return len(gestion_de_normas()["vencidas"])


def _commits_ultima_version() -> int:
    ultima, previa = _dos_ultimas_versiones()
    # Los dos hashes salen del changelog leído como fichero; validados antes
    # de componer el rango (AP-68).
    h_previa = _hash_o_none(previa.get("hash"))
    h_ultima = _hash_o_none(ultima.get("hash"))
    if not h_previa or not h_ultima:
        raise ValueError(
            f"el changelog no declara hashes con forma de git: "
            f"{previa.get('hash')!r}..{ultima.get('hash')!r}"
        )
    salida = _git("rev-list", "--count", f"{h_previa}..{h_ultima}")
    if salida is None:
        raise ValueError(f"git no resuelve {h_previa}..{h_ultima}")
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
    "deuda_viva_baselines": _deuda_viva_baselines,
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
    # El hash viene del histórico declarado en METRICAS; sin forma de hash no
    # se le pregunta a git (AP-68) —se responde que no existe, que es lo que
    # una observación con un hash inventado merece.
    valido = _hash_o_none(h)
    if not valido:
        return False
    return _git("cat-file", "-e", f"{valido}^{{commit}}") is not None


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
            "deuda_viva_por_baseline": _deuda_viva_por_baseline(),
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


def leer_salida_puertas(datos: Dict[str, Any]) -> List[Dict[str, Any]]:
    """`seconds` de una ronda de `vault_gate` en verde.

    Una ronda en rojo no se registra: la puerta que falla puede caer antes de
    hacer su trabajo, y su cifra saldría más barata que la de una ronda sana.
    """
    if not _es_numero(datos.get("seconds")):
        raise ValueError("la salida de vault_gate no trae `seconds`")
    if datos.get("ok") is not True or datos.get("failing"):
        raise ValueError("ronda de puertas en rojo: su duración no es comparable")
    return [{"metrica": "puertas_duracion_s", "valor": datos["seconds"]}]


#: Las métricas que se miden aquí y no se rellenan a mano. Una métrica de
#: producto cuyo valor entra por `--valor` no mide el producto: mide lo que su
#: autor quiso escribir, que es justo lo que `suites_fallos` y compañía
#: pretendían evitar al volverse observadas.
_MEDIDAS_ANTES: Dict[str, Any] = {}


def _cronometro(funcion, *args, **kwargs) -> float:
    """Segundos que tardó `funcion`, y su valor. Un fallo devuelve `None` y no
    un cero: un runner roto tiene que verse, no leerse como rápido (AP-51)."""
    import time as _time

    inicio = _time.perf_counter()
    try:
        valor = funcion(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — el runner no debe tumbar la tool
        _MEDIDAS_ANTES["error"] = f"{type(exc).__name__}: {exc}"
        return -1.0
    return round(_time.perf_counter() - inicio, 3)


def registrar_contexto(commit: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
    """Mide de verdad la cadena que paga el agente y la registra.

    `vault_query_parse` + `vault_context_pack` sobre un vault temporal: dos
    subprocesos reales, porque el coste que importa incluye el arranque del
    intérprete. El valor va a `contexto_agente_s` con su commit y su fuente.

    `dry_run=True` mide y devuelve sin escribir la observación. Existe porque
    un test que llama a esto no puede mutar el registro del repo: lo hizo
    durante una ronda y puso en carrera al generador del SDD, que lee las
    cifras de observaciones (medido el 2026-10-23: `README.md not
    idempotent` en xdist y verde en serie).
    """
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "vault"
        env = {**os.environ, "VAULT_ROOT": str(vault), "PYTHONIOENCODING": "utf-8"}

        def _correr(args: List[str]) -> float:
            return _cronometro(
                subprocess.run,
                [sys.executable, str(RAIZ / "scripts" / args[0]), *args[1:]],
                capture_output=True, env=env, timeout=300,
            )

        parse = _correr(["vault_query_parse.py", "qué decidimos sobre el vault"])
        pack = _correr(["vault_context_pack.py", "--query", "qué decidimos sobre el vault"])

    if parse < 0 or pack < 0:
        # Por el contrato de errores, no por literales propios (AP-52): un
        # envelope de fallo que no trae `error_code` obliga a quien lo lee a
        # adivinar la recuperación, que es justo el dato que un runner
        # necesita para reintentar.
        return emit_error(
            "vault_metricas", "TOOL_EXECUTION_FAILED",
            f"el runner de contexto no pudo medir: {_MEDIDAS_ANTES.get('error', 'falló')}",
            pista="una métrica de producto que no se puede medir no se registra: "
                  "se declara descubierta",
            args={"action": "registrar_contexto", "parse_s": parse, "pack_s": pack})
    total = round(parse + pack, 3)
    if dry_run:
        # mide igual; no escribe: el registro se muta por una decisión, no
        # por correr el test que comprueba que el runner mide
        return {"ok": True, "tool": "vault_metricas", "action": "registrar_contexto",
                "dry_run": True, "parse_s": parse, "pack_s": pack, "total_s": total,
                "hint": "dry_run: la medición es real y no toca el registro"}
    r = registrar([{"metrica": "contexto_agente_s", "valor": total}],
                  commit=commit,
                  fuente=f"medición real: parse {parse}s + pack {pack}s sobre vault temporal")
    return {**r, "parse_s": parse, "pack_s": pack, "total_s": total}


def registrar_skip_path(commit: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
    """Mide la corrida de onboarding que no escribe nada, sobre un proyecto real
    de verdad (con git), y registra el resultado en `skip_path_escritura_s`.

    Es la deuda que la auditoría del onboarding dejó anotada el 2026-10-21: la
    segunda pasada paga ~7 s para no escribir nada. Declararla como métrica con
    fecha la convierte en algo que se puede no cumplir sin que nadie tenga que
    acordarse.

    **Verifica los envelopes antes de medir.** Un runner que cronometra una
    corrida que falló registra un número rápido y truthful —la forma más
    difícil de detectar de mentir—: por eso la primera pasada tiene que crear
    el vault (`vault_init`) y comprobar `ok`, y la segunda tiene que venir con
    `merge_stats` entero en `skipped`. Un runner que no comprueba lo que mide
    es AP-37 en el sitio donde el coste importa.
    """
    import subprocess
    import tempfile

    def _json_de(stdout: bytes) -> Dict[str, Any]:
        try:
            return json.loads(stdout.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"ok": False, "error_code": "JSON_PARSE_ERROR"}

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        proyecto = base / "proyecto"
        (proyecto / "src").mkdir(parents=True)
        (proyecto / "src" / "mod.py").write_text("def h():\n    return 1\n", encoding="utf-8")
        (proyecto / "README.md").write_text("# demo\n", encoding="utf-8")
        _git = lambda *a: procesos_git.ejecutar_git(  # noqa: E731
            proyecto, list(a), capture_output=True, check=True,
            env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
        _git("init", "-q")
        _git("add", "-A")
        _git("commit", "-q", "-m", "inicio")

        vault = base / "vault"
        # El vault tiene que EXISTIR antes de medir: onboard no crea uno (no se
        # pisa un vault), así que sin este init el runner midiese un rechazo
        # de 0,25 s y lo publicaría como si el skip-path fuera gratis.
        init = subprocess.run(
            [sys.executable, str(RAIZ / "scripts" / "vault_init.py"), "--name", "demo"],
            capture_output=True, env={**os.environ, "VAULT_MASTER": str(base / "casa"),
                                      "PYTHONIOENCODING": "utf-8"},
            timeout=600)
        if not _json_de(init.stdout).get("ok"):
            return emit_error(
                "vault_metricas", "TOOL_EXECUTION_FAILED",
                "no se pudo crear el vault temporal para medir el skip-path",
                pista="sin vault no hay skip-path que medir; se declara, no se estima",
                args={"action": "registrar_skip_path"})
        destino = _json_de(init.stdout).get("vault_root")
        if not destino:
            return emit_error(
                "vault_metricas", "INVALID_JSON",
                "vault_init respondió ok pero sin `vault_root`: no hay dónde medir",
                pista="el runner necesita la ruta real del vault, no una suposición",
                args={"action": "registrar_skip_path"})

        env = {**os.environ, "VAULT_ROOT": str(destino), "PYTHONIOENCODING": "utf-8",
               "VAULT_TOOL_TIMEOUT": "600"}
        args = [sys.executable, str(RAIZ / "scripts" / "vault_onboard.py"),
                "--project", "demo", "--path", str(proyecto)]

        # primera pasada: crea. segunda: todo skipped y no escribe.
        import time as _time

        crudos = []
        for _ in (1, 2):
            t0 = _time.perf_counter()
            crudos.append((subprocess.run(args, capture_output=True, env=env, timeout=900),
                           round(_time.perf_counter() - t0, 3)))
        primera, _ = (_json_de(c[0].stdout) for c in crudos)
        segunda, skip_s = _json_de(crudos[1][0].stdout), crudos[1][1]

    if not (primera.get("ok") and segunda.get("ok")):
        # no se registra un número de una corrida que falló: sería un número
        # rápido y truthful, la peor forma de mentir
        return emit_error(
            "vault_metricas", "TOOL_EXECUTION_FAILED",
            "una de las dos corridas de onboard no salió ok; no se registra "
            "el tiempo de una corrida que no ocurrió",
            pista="mide con un proyecto demo que onboard pueda recorrer; si no, "
                  "la métrica se declara y no se estima",
            args={"action": "registrar_skip_path",
                  "primera_ok": bool(primera.get("ok")),
                  "segunda_ok": bool(segunda.get("ok"))})
    stats = segunda.get("merge_stats") or {}
    if stats.get("created") or stats.get("merged") or not stats.get("skipped"):
        # la segunda pasada tiene que ser skip-path de verdad; si no, se está
        # midiendo otra cosa con el nombre de esta métrica
        return emit_error(
            "vault_metricas", "INVALID_VALUE",
            "la segunda corrida no fue skip-path: la métrica mide esa carrera, "
            "no cualquier segunda corrida",
            pista="se esperaba created=0, merged=0 y skipped>0",
            args={"action": "registrar_skip_path", "merge_stats": stats})

    if dry_run:
        return {"ok": True, "tool": "vault_metricas", "action": "registrar_skip_path",
                "dry_run": True, "merge_stats": stats, "skip_s": skip_s,
                "hint": "dry_run: la medición es real y no toca el registro"}
    r = registrar([{"metrica": "skip_path_escritura_s", "valor": skip_s}],
                  commit=commit,
                  fuente="medición real: onboarding doble pasada sobre proyecto demo "
                         f"con git (2.ª pasada = {stats.get('skipped')} skipped, 0 escrituras)")
    return {**r, "merge_stats": stats, "skip_s": skip_s}


def main() -> int:
    tool = "vault_metricas"
    ap = argparse.ArgumentParser(
        description="vault_metricas — métricas de desarrollo y de producto", allow_abbrev=False)
    ap.add_argument("--check", action="store_true", help="Registro, histórico y documento")
    ap.add_argument("--strict", action="store_true", help="Exit 1 si el check falla")
    ap.add_argument("--doc", action="store_true", help="Regenera docs/METRICAS.md")
    ap.add_argument("--registrar-suite", metavar="LOG", help="Log de una ronda de pytest")
    ap.add_argument("--registrar-smoke", metavar="JSON", help="Salida JSON de vault_smoke")
    ap.add_argument("--registrar-puertas", metavar="JSON", help="Salida JSON de vault_gate --strict")
    ap.add_argument("--registrar-banco", metavar="JSON", help="Informe JSON de banco_agente")
    ap.add_argument("--registrar-contexto", action="store_true",
                    help="Mide la cadena de contexto que paga el agente y la registra")
    ap.add_argument("--registrar-skip", action="store_true",
                    help="Mide el skip-path del onboarding (2.ª pasada, no escribe) y lo registra")
    ap.add_argument("--registrar", metavar="ID", help="Registra una métrica observada")
    ap.add_argument("--valor", type=float, help="Valor para --registrar")
    ap.add_argument("--fuente", help="De dónde sale la observación")
    ap.add_argument("--commit", help="Commit sobre el que se midió (por defecto HEAD)")
    args = ap.parse_args()

    acciones = [a for a in ("check", "doc", "registrar_suite", "registrar_smoke",
                            "registrar_puertas", "registrar_banco", "registrar",
                            "registrar_contexto", "registrar_skip") if getattr(args, a)]
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
        elif args.registrar_puertas:
            datos = json.loads(_fichero(args.registrar_puertas))
            r = registrar(leer_salida_puertas(datos), commit=args.commit,
                          fuente=args.fuente or f"vault_gate sobre {datos.get('gates_total')} puertas")
        elif args.registrar_banco:
            r = registrar(_desde_banco(json.loads(_fichero(args.registrar_banco))),
                          commit=args.commit,
                          fuente=args.fuente or f"banco_agente sobre {Path(args.registrar_banco).name}")
        elif args.registrar_contexto:
            r = registrar_contexto(commit=args.commit)
        elif args.registrar_skip:
            r = registrar_skip_path(commit=args.commit)
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

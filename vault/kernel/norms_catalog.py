#!/usr/bin/env python3
"""Catálogo canónico de normas AP-XX / PAT-X, y el vocabulario de estado.

**Datos, no comportamiento.** Este módulo no lee el vault, no escribe nada y no
importa ninguna tool: es la mitad de `vault_norms` que era una constante de tres
mil líneas. Salió de ahí en v40.26 porque `vault_norms` hacía de catálogo, de
motor y de fachada a la vez, y el 60% del fichero era esta lista.

**Se entra por `vault_norms`, no por aquí.** La fachada reexporta todo lo
público de este módulo, así que ningún llamador tuvo que tocarse al partirlo —
que es lo que hizo el corte barato. Importar directamente de aquí no está
prohibido, pero tampoco es la superficie declarada: los puertos del contexto de
gobernanza siguen nombrando `vault_norms:NORM_CATALOG` y compañía.

**Por qué el vocabulario de estado vive aquí y no en el motor.** `STATUS_VOCAB`,
`LIFECYCLE_REGISTRY`, `STATUS_SYNONYMS`, `STATUS_TRANSITIONS` y
`DOMAIN_STATUS_VOCABS` son lo mismo que el catálogo: la declaración de qué es
legítimo. Las cuatro funciones que los acompañan —`normalize_status`,
`split_domain_status`, `status_frontmatter_lines`, `_canonical_status`— son
puras y no hacen otra cosa que consultarlos; separarlas de sus datos habría
creado un cruce donde no hay ninguno.
"""

from __future__ import annotations


import ast
import re
from datetime import date as _date, timedelta as _timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import vault_grafo_import

# ─── La norma como paquete (deuda #10, piloto AP-65) ──────────────────────────
#
# Una norma puede vivir en `normas/<código>/` en vez de escrita aquí: `norma.py`
# con la entrada, `porque.md` con las rutas de las caras que la cumplen y un
# `test_*.py` (los ejecuta `tests/test_normas_paquete.py`). Este módulo sigue
# siendo la fuente única: la carga en el sitio que ocupaba, así que
# `NORM_CATALOG` no cambia de orden. Se lee con `ast.literal_eval` y no se
# importa —el catálogo es hoja y un `norma.py` con código no lo sería—, y la
# ruta sale del directorio del programa (`vault_grafo_import.DIRECTORIO`)
# porque en la wheel `_impl/` y `normas/` son hermanas igual que `scripts/` y
# `normas/` en el checkout. Hasta el 2026-10-16 salía de este fichero, que
# vivía en `scripts/`; desde `vault/kernel/` su abuelo es `vault/`.

#: Carpeta de los paquetes de norma, hermana del directorio del programa.
RAIZ_NORMAS = (vault_grafo_import.DIRECTORIO.parent / "normas").resolve()

#: Códigos que el catálogo carga desde su paquete, en el orden en que los carga.
NORMAS_EN_PAQUETE: List[str] = []

#: Una cara citada en `porque.md`: `ruta/del/fichero.py::símbolo`.
_RE_CARA = re.compile(r"`([\w./-]+\.py)::(\w+)`")


def _leer_norma(fichero: Path) -> Dict[str, Any]:
    """La asignación `NORMA = {...}` de un `norma.py`, sin ejecutarlo."""
    arbol = ast.parse(fichero.read_text(encoding="utf-8"), filename=str(fichero))
    for nodo in arbol.body:
        if (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                and isinstance(nodo.targets[0], ast.Name)
                and nodo.targets[0].id == "NORMA"):
            return ast.literal_eval(nodo.value)
    raise ValueError(f"{fichero}: no declara NORMA")


def _desde_paquete(code: str) -> Dict[str, Any]:
    """La entrada de `code`, leída de su paquete. Si falta, el import falla:
    un catálogo al que le falta una norma en silencio es peor que ninguno."""
    NORMAS_EN_PAQUETE.append(code)
    return _leer_norma(RAIZ_NORMAS / code / "norma.py")


def forma_de_paquetes(raiz: Optional[Path] = None,
                      cargadas: Optional[Sequence[str]] = None,
                      raiz_repo: Optional[Path] = None) -> List[Dict[str, str]]:
    """Qué paquetes de norma no tienen la forma declarada.

    Falla si falta `norma.py`, `porque.md`, `guard.py`, `heal.py` o un
    `test_*.py`; si el `code` no es
    el nombre de la carpeta; si la carpeta no la carga el catálogo, o la carga
    dos veces; y si `porque.md` cita una cara `ruta::símbolo` que no existe.

    El test y las caras solo se exigen con `raiz_repo`, que es el checkout: la
    wheel no lleva ni los `test_*.py` ni el código de gobernanza que citan, y
    exigirlos allí daría un problema que no lo es.
    """
    raiz = Path(raiz) if raiz else RAIZ_NORMAS
    cargadas = list(NORMAS_EN_PAQUETE if cargadas is None else cargadas)
    if raiz_repo is None and raiz == RAIZ_NORMAS and (raiz.parent / "scripts").is_dir():
        raiz_repo = raiz.parent
    problemas: List[Dict[str, str]] = []

    def falta(paquete: str, problema: str) -> None:
        problemas.append({"paquete": paquete, "problema": problema})

    carpetas = sorted(p for p in raiz.iterdir()
                      if p.is_dir() and not p.name.startswith(("_", "."))) if raiz.is_dir() else []
    for carpeta in carpetas:
        nombre = carpeta.name
        if cargadas.count(nombre) != 1:
            falta(nombre, f"el catálogo la carga {cargadas.count(nombre)} veces, no una")
        for cara in ("norma.py", "porque.md", "guard.py", "heal.py"):
            if not (carpeta / cara).is_file():
                falta(nombre, f"falta {cara}")
        if raiz_repo is not None and not list(carpeta.glob("test_*.py")):
            falta(nombre, "falta un test_*.py")
        if (carpeta / "norma.py").is_file():
            try:
                code = _leer_norma(carpeta / "norma.py").get("code")
            except (SyntaxError, ValueError) as exc:
                falta(nombre, f"norma.py ilegible: {exc}")
            else:
                if code != nombre:
                    falta(nombre, f"declara {code} en la carpeta {nombre}")
        if raiz_repo is not None and (carpeta / "porque.md").is_file():
            texto = (carpeta / "porque.md").read_text(encoding="utf-8")
            for ruta, simbolo in _RE_CARA.findall(texto):
                fichero = Path(raiz_repo) / ruta
                fuente = fichero.read_text(encoding="utf-8") if fichero.is_file() else ""
                if not re.search(rf"^\s*(?:def|class)\s+{simbolo}\b|^{simbolo}\s*=",
                                 fuente, re.M):
                    falta(nombre, f"porque.md cita {ruta}::{simbolo}, que no existe")
    nombres = {c.name for c in carpetas}
    for code in sorted(set(cargadas) - nombres):
        falta(code, "el catálogo la carga y no tiene carpeta")
    return problemas


# ─── Catálogo canónico (fuente de verdad) ──────────────────────────────────────
#
# type:        antipattern | pattern
# category:    content-quality | structure | frontmatter | linking | process
# severity:    critical | high | medium | low  (N/A para patterns)
# enforcement: guard | audit | guard+audit | manual | recommended
#   - guard:     vault_write rechaza en tiempo de escritura
#   - audit:     vault_audit detecta retrospectivamente
#   - guard+audit: ambos
#   - manual:    DEPRECADO (v38) — toda norma debe tener guard o audit; las no
#                automatizables usan audit heurístico (vault_drift_detect)
#   - recommended: patrón positivo a seguir

NORM_CATALOG: List[Dict[str, Any]] = [
    # ── Anti-patrones ──────────────────────────────────────────────────────────
    _desde_paquete("AP-01"),
    _desde_paquete("AP-02"),
    _desde_paquete("AP-03"),
    _desde_paquete("AP-04"),
    _desde_paquete("AP-05"),
    _desde_paquete("AP-06"),
    _desde_paquete("AP-07"),
    _desde_paquete("AP-08"),
    _desde_paquete("AP-09"),
    _desde_paquete("AP-10"),
    _desde_paquete("AP-11"),
    _desde_paquete("AP-12"),
    _desde_paquete("AP-13"),
    _desde_paquete("AP-14"),
    _desde_paquete("AP-15"),
    _desde_paquete("AP-16"),
    _desde_paquete("AP-17"),
    _desde_paquete("AP-18"),
    _desde_paquete("AP-19"),
    _desde_paquete("AP-20"),
    _desde_paquete("AP-21"),
    _desde_paquete("AP-22"),
    # ── Patrones recomendados ──────────────────────────────────────────────────
    _desde_paquete("PAT-1"),
    _desde_paquete("PAT-2"),
    _desde_paquete("PAT-3"),
    _desde_paquete("PAT-4"),
    _desde_paquete("PAT-5"),
    # ── Anti-patrón AP-23 ──────────────────────────────────────────────────────
    _desde_paquete("AP-23"),
    # ── Anti-patrón AP-24 ──────────────────────────────────────────────────────
    _desde_paquete("AP-24"),
    # ── Anti-patrón AP-25 ──────────────────────────────────────────────────────
    _desde_paquete("AP-25"),
    # ── Anti-patrones AP-26..AP-30 ────────────────────────────────────────────
    # Frontmatter incompleto. Estaban aplicados por vault_audit desde v30 (con
    # penalización al health score y etiqueta propia en su salida) pero nunca
    # se registraron aquí: `vault_norms --list` no los mostraba y no tenían
    # severidad, enforcement ni prevención declaradas. El hueco lo detectó el
    # chequeo de contiguidad de vault_sdd_init al dejar de estar clavado en
    # AP-01..AP-25. Registrados sin cambiar el comportamiento del audit.
    _desde_paquete("AP-26"),
    _desde_paquete("AP-27"),
    _desde_paquete("AP-28"),
    _desde_paquete("AP-29"),
    _desde_paquete("AP-30"),
    # ── Anti-patrón AP-31 ──────────────────────────────────────────────────────
    _desde_paquete("AP-31"),
    # ── Anti-patrón AP-32 ──────────────────────────────────────────────────────
    _desde_paquete("AP-32"),
    # ── Anti-patrón AP-33 ──────────────────────────────────────────────────────
    _desde_paquete("AP-33"),
    # ── Anti-patrón AP-34 ──────────────────────────────────────────────────────
    _desde_paquete("AP-34"),
    # ── Anti-patrón AP-35 ──────────────────────────────────────────────────────
    _desde_paquete("AP-35"),
    _desde_paquete("AP-36"),
    # ── Anti-patrón AP-37 ──────────────────────────────────────────────────────
    # Síntoma que la originó: `vault_standard_upgrade --to latest` devolvía
    # `{"ok": true}` habiendo aplicado CERO migraciones, porque _version_index()
    # no normalizaba la minor version y _pending_migrations() devolvía []. El bug
    # sobrevivió versiones enteras porque su respuesta era indistinguible de un
    # éxito real: no había nada en la salida que un test o un agente pudiera
    # contradecir.
    _desde_paquete("AP-37"),
    # ── Anti-patrón AP-38 ──────────────────────────────────────────────────────
    # Síntoma que lo originó: un censo sobre 17 vaults reales (2.929 notas)
    # encontró 54 valores distintos de `status`, de los cuales solo el 6% caía
    # dentro de STATUS_VOCAB — pese a que CN-03 lo audita desde v38. La causa no
    # eran los agentes: el valor no canónico más frecuente, `implementado`
    # (205 notas), lo escribía `vault_pattern_save`. El estándar publicaba NUEVE
    # vocabularios de `status` en competencia y auditaba contra uno solo.
    _desde_paquete("AP-38"),
    # ── Anti-patrón AP-39 ──────────────────────────────────────────────────────
    # Síntoma que lo originó: el mismo censo de 17 vaults midió 1.180 tags
    # distintos para 6.358 usos — el 45% aparece en una sola nota — y 55 familias
    # de casi-duplicados (`ci-cd`/`cicd`/`ci_cd`). El ritmo de invención es plano
    # a lo largo de tres meses (37% → 36% → 34% → 27% → 36%): ninguna sesión
    # hereda el vocabulario de la anterior. La causa, otra vez, era el camino de
    # escritura: `vault_write` consultaba una clave que el tag-registry no tiene,
    # así que la sugerencia no se disparó nunca y un tag inventado costaba cero.
    _desde_paquete("AP-39"),
    _desde_paquete("AP-40"),
    _desde_paquete("AP-41"),
    _desde_paquete("AP-42"),
    _desde_paquete("AP-43"),
    _desde_paquete("AP-44"),
    _desde_paquete("AP-45"),
    # ── Antipatrón AP-46 ───────────────────────────────────────────────────────
    _desde_paquete("AP-46"),
    # ── Antipatrón AP-47 ───────────────────────────────────────────────────────
    _desde_paquete("AP-47"),
    _desde_paquete("AP-48"),
    _desde_paquete("AP-49"),
    _desde_paquete("AP-50"),
    _desde_paquete("AP-51"),
    _desde_paquete("AP-52"),
    _desde_paquete("AP-53"),
    _desde_paquete("AP-54"),
    _desde_paquete("AP-55"),
    _desde_paquete("AP-56"),
    _desde_paquete("AP-57"),
    _desde_paquete("AP-58"),
    _desde_paquete("AP-59"),
    _desde_paquete("AP-60"),
    _desde_paquete("AP-61"),
    # ── Anti-patrón AP-62 ──────────────────────────────────────────────────────
    _desde_paquete("AP-62"),
    # ── Anti-patrón AP-63 ──────────────────────────────────────────────────────
    _desde_paquete("AP-63"),
    _desde_paquete("AP-64"),
    _desde_paquete("AP-65"),
    _desde_paquete("AP-66"),
    # ── Anti-patrón AP-67 ──────────────────────────────────────────────────────
    _desde_paquete("AP-67"),
    # ── Anti-patrón AP-68 ──────────────────────────────────────────────────────
    _desde_paquete("AP-68"),
    # ── Patrón PAT-6 ───────────────────────────────────────────────────────────
    _desde_paquete("PAT-6"),
    # ── Protocolo de sesión SP-XX ──────────────────────────────────────────────
    _desde_paquete("SP-01"),
    _desde_paquete("SP-02"),
    _desde_paquete("SP-03"),
    _desde_paquete("SP-04"),
    # ── Convenciones de nomenclatura CN-XX ────────────────────────────────────
    _desde_paquete("CN-01"),
    _desde_paquete("CN-02"),
    _desde_paquete("CN-03"),
    _desde_paquete("CN-04"),
]

# Índice rápido por código
_NORM_BY_CODE: Dict[str, Dict[str, Any]] = {n["code"]: n for n in NORM_CATALOG}


def norma_por_codigo(code: str) -> Dict[str, Any] | None:
    """La norma con ese código, o `None`.

    El puerto público del índice. `vault_code_tag` —que es del contexto de
    grafo— venía importando `_NORM_BY_CODE` directamente: un nombre privado
    atravesando una frontera, que es lo contrario de una superficie publicada.
    El dict sigue existiendo para uso interno de este módulo; lo que cambia es
    que quien viene de fuera entra por aquí.
    """
    return _NORM_BY_CODE.get(code)


#: Las tools que reescriben una nota que ya existe para repararla, y qué normas
#: repara cada una (deuda #10). El registro es por tool y no por norma: quien
#: escribe un sanador declara aquí lo que sana, y el `tools_healing` de cada
#: norma se deriva —`tools_healing(code)`— en vez de copiarse en 81 paquetes.
#: No entra lo que escribe una nota nueva (eso es prevención, `tools_enforcing`)
#: ni lo que restaura una versión anterior (`vault_undo`, `vault_restore`), que
#: no repara ninguna norma: devuelve lo que había. Cada par lo sostiene una
#: función del sanador que nombra la norma en su cuerpo; si no la hay,
#: `vault_norms --check-framework` falla, porque el registro afirmaría un heal
#: que nadie puede seguir hasta el código (AP-55).
SANADORES: Dict[str, tuple] = {
    "vault_fix_brackets": ("AP-22", "AP-24"),
    "vault_frontmatter_heal": ("AP-56",),
    "vault_frontmatter_completar": ("AP-12", "AP-13", "AP-16", "AP-26", "AP-27",
                                    "AP-28", "AP-29", "AP-30"),
    "vault_supersede": ("AP-17",),
    "vault_project": ("AP-63",),
    "vault_norms_engine": ("AP-46",),
    "vault_graph_fix": ("AP-14", "AP-21"),
    "vault_mermaid_check": ("AP-25",),
}


def tools_healing(code: str) -> List[str]:
    """Las tools de `SANADORES` que reparan `code`, en el orden del registro."""
    return [tool for tool, codigos in SANADORES.items() if code in codigos]


# ─── Gestión de normas (R4): quién responde, cuándo se revisó, cada cuánto ────
#
# Una norma con guard que nadie revisa envejece igual que una sin él: el guard
# sigue en verde midiendo lo que la norma decía cuando se escribió. `revisado_en`
# es un hecho por norma y vive en su `norma.py`; `responsable` y `cadencia_dias`
# se derivan de aquí salvo que el paquete los declare, para no copiar la misma
# constante en cada paquete (AP-47). La carga inicial de `revisado_en` es
# 2026-10-09 en todas: la fecha del último commit que tocó cada `norma.py`
# medida con git, que es cuando se empaquetaron (m186); no afirma una revisión
# de contenido que no se hizo. Revisar una norma es leerla contra el código que
# la sostiene y poner la fecha del día, cambie o no lo demás.

#: Quién responde de una norma que no declara otro `responsable`.
RESPONSABLE_POR_DEFECTO = "mantenedor"

#: Cada cuántos días toca revisar una norma según cómo se aplica. Las que tienen
#: guard o audit se revisan antes porque un detector desfasado da verde falso;
#: las `recommended` solo orientan. `manual` no está: ninguna norma puede serlo
#: (AGENTS.md, regla 5), y una que lo fuera sale como problema por no tener cadencia.
CADENCIA_POR_ENFORCEMENT: Dict[str, int] = {
    "guard": 90, "audit": 90, "guard+audit": 90, "recommended": 180,
}


def gestion_de_normas(hoy: Optional[_date] = None,
                      catalogo: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """El registro de gestión de cada norma, qué entradas están mal formadas y
    cuáles han vencido.

    Problema = el registro no se puede leer (falta `revisado_en`, no es una
    fecha ISO, es posterior a `hoy`, o no hay cadencia ni declarada ni
    derivable). Vencida = `revisado_en + cadencia_dias < hoy`: es trabajo
    pendiente, no una contradicción, y por eso se publica aparte.
    """
    hoy = hoy or _date.today()
    normas: List[Dict[str, Any]] = []
    problemas: List[Dict[str, str]] = []
    vencidas: List[Dict[str, Any]] = []
    for norma in (NORM_CATALOG if catalogo is None else catalogo):
        code = norma["code"]
        cadencia = norma.get("cadencia_dias",
                             CADENCIA_POR_ENFORCEMENT.get(norma.get("enforcement")))
        responsable = norma.get("responsable", RESPONSABLE_POR_DEFECTO)
        bruto = norma.get("revisado_en")
        if not (isinstance(cadencia, int) and not isinstance(cadencia, bool) and cadencia > 0):
            problemas.append({"code": code, "problema": (
                f"sin cadencia: enforcement {norma.get('enforcement')!r} no tiene "
                "cadencia derivada y el paquete no declara `cadencia_dias`")})
            continue
        if not (isinstance(responsable, str) and responsable.strip()):
            problemas.append({"code": code, "problema": "`responsable` en blanco"})
            continue
        try:
            revisado = _date.fromisoformat(bruto) if isinstance(bruto, str) else None
        except ValueError:
            revisado = None
        if revisado is None:
            problemas.append({"code": code, "problema": (
                f"`revisado_en` debe ser una fecha AAAA-MM-DD, no {bruto!r}")})
            continue
        if revisado > hoy:
            problemas.append({"code": code, "problema": (
                f"`revisado_en` {bruto} es posterior a hoy ({hoy.isoformat()})")})
            continue
        vence = revisado + _timedelta(days=cadencia)
        entrada = {"code": code, "responsable": responsable, "revisado_en": bruto,
                   "cadencia_dias": cadencia, "vence_en": vence.isoformat(),
                   "vencida": vence < hoy}
        normas.append(entrada)
        if entrada["vencida"]:
            vencidas.append(entrada)
    return {"hoy": hoy.isoformat(), "normas": normas, "problemas": problemas,
            "vencidas": vencidas}

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "N/A": 4}
_CATEGORY_ORDER = {
    "linking": 0,
    "content-quality": 1,
    "structure": 2,
    "frontmatter": 3,
    "process": 4,
    "session-protocol": 5,
    "convention": 6,
}



# Vocabulario canónico de meta.status (CN-03) — unificado v38.
# Antes existían DOS vocabularios contradictorios: CN-03 (7 valores) y el
# ciclo de vida del spec §status (draft→reviewed→approved→implemented→
# verified→obsolete). Este set es la unión canónica; CN-03 y el spec
# referencian este símbolo como fuente única.
STATUS_VOCAB = {
    "planned",
    "draft",
    "in-progress",
    "reviewed",
    "approved",
    "implemented",
    "verified",
    "deprecated",
    "obsolete",
    "archived",
    "stub",
    "template",
}

#: `STATUS_VOCAB` como tipo (D4, v40.34). Se **deriva** del set, no repite los
#: doce valores: una segunda lista es un segundo dueño, y el set ya tuvo dos
#: vocabularios contradictorios antes de v38. Hereda de `str`, así que
#: `Status.IN_PROGRESS == "in-progress"` y lo que se escribe en el frontmatter
#: no cambia. Comprobar pertenencia se sigue haciendo contra el set: `"x" in
#: Status` lanza TypeError antes de Python 3.12, y el piso es 3.9.
Status = Enum(
    "Status",
    {valor.replace("-", "_").upper(): valor for valor in sorted(STATUS_VOCAB)},
    type=str,
)
Status.__doc__ = "Valor canónico de meta.status (CN-03); derivado de STATUS_VOCAB."

# ─── Registro de lifecycles ──────────────────────────────────────────────────
#
# El catálogo de máquinas de estado vivía escrito a mano dentro de
# `vault_sdd_init.generate_state_machines`, en una cadena constante, y llevaba
# tiempo mintiendo: daba el ciclo de la versión del estándar como «v19 → … →
# v36» estando el repo en v39.5, y el de las tools como
# `active/deprecated/internal/meta/removed` cuando los estados que el tool-spec
# usa de verdad son `active/archived/internal`. Dos de trece filas incorrectas en
# el documento cuyo trabajo entero es describir las máquinas de estado.
#
# El orden que fija AGENTS.md es registro primero y doc después, así que la tabla
# se declara aquí —junto a STATUS_VOCAB, que es la otra verdad sobre estados— y
# el generador del SDD la deriva. Las dos filas que sí tienen fuente viva
# (versión del estándar, estados de tool) se resuelven en tiempo de generación
# contra esa fuente, no se copian.
LIFECYCLE_REGISTRY = [
    {"entity": "Nota", "entity_en": "Note",
     "states": ["active", "archived", "deleted"], "tool": "vault_change_log"},
    {"entity": "Patrón", "entity_en": "Pattern",
     "states": ["planificado", "en_progreso", "implementado", "deprecado", "refactoring"],
     "tool": "vault_pattern_save"},
    {"entity": "Requisito", "entity_en": "Requirement",
     "states": ["draft", "reviewed", "approved", "implemented", "verified", "obsolete"],
     "tool": "vault_requirement_save"},
    {"entity": "Test", "entity_en": "Test",
     "states": ["not_run", "pass", "fail", "blocked", "skip"], "tool": "vault_test_save"},
    {"entity": "Ejecución de runbook", "entity_en": "Runbook execution",
     "states": ["success", "failed", "partial"], "tool": "vault_runbook_log"},
    {"entity": "Incidente", "entity_en": "Incident",
     "states": ["detected", "investigating", "identified", "mitigating", "resolved",
                "closed", "post-mortem"], "tool": "vault_incident_save"},
    {"entity": "Consumo de SLO", "entity_en": "SLO burn",
     "states": ["healthy", "1h-burn", "6h-burn", "30d-burn", "breached"],
     "tool": "vault_slo_save"},
    {"entity": "Tratamiento de riesgo", "entity_en": "Risk treatment",
     "states": ["accept", "mitigate", "transfer", "avoid"], "tool": "vault_risk_save"},
    {"entity": "NCR", "entity_en": "NCR",
     "states": ["open", "in_progress", "pending_verification", "closed", "cancelled"],
     "tool": "vault_ncr_save"},
    {"entity": "Backup", "entity_en": "Backup",
     "states": ["active", "superseded"], "tool": "vault_backup_list"},
    {"entity": "Propagación pendiente", "entity_en": "Propagation pending",
     "states": ["pending", "reviewed"], "tool": "vault_propagate"},
    # `states: None` = se resuelve contra la fuente viva al generar la doc.
    {"entity": "Ciclo de vida de una tool", "entity_en": "Tool lifecycle",
     "states": None, "source": "tool_spec_status", "tool": "vault_mcp_catalog"},
    {"entity": "Versión del estándar", "entity_en": "Standard version",
     "states": None, "source": "standard_version", "tool": "vault_standard_upgrade"},
]


# ─── Sinónimos de estado (AP-38) ─────────────────────────────────────────────
#
# CN-03 lleva desde v38 declarando el vocabulario y auditándolo. Un censo sobre
# 17 vaults reales (2.929 notas) mostró el resultado de auditar sin normalizar:
# **54 valores distintos de `status`, de los cuales solo el 6% caía dentro del
# vocabulario** — y de los 12 canónicos únicamente 4 llegaron a usarse. Los más
# frecuentes eran inventados: `implementado` (205 notas), `active` (60),
# `activo` (53), `accepted` (45), `fixed` (31).
#
# La lección del censo no es que los agentes escriban mal: es que un vocabulario
# que solo se audita *después* de escribir no gobierna nada, porque nadie
# ejecuta el audit — `vault_norms` no aparece ni una vez en las 1.356
# ejecuciones registradas del parque. Por eso este mapa se aplica en la
# escritura, no en la revisión.
#
# Cubre español e inglés porque el parque los mezcla en la misma nota.
STATUS_SYNONYMS = {
    # activo / en curso
    "active": "in-progress",
    "activo": "in-progress",
    "en_desarrollo": "in-progress",
    "en-desarrollo": "in-progress",
    "in_progress": "in-progress",
    "en_progreso": "in-progress",
    "refactoring": "in-progress",
    "wip": "in-progress",
    "investigating": "in-progress",
    "investigado": "in-progress",
    "open": "in-progress",
    "abierto": "in-progress",
    "identificado": "in-progress",
    "pendiente_accion": "in-progress",
    # planificado
    "planificado": "planned",
    "pendiente": "planned",
    "deferred": "planned",
    "proposed": "planned",
    "propuesto": "planned",
    # aprobado
    "accepted": "approved",
    "aceptado": "approved",
    "aceptada": "approved",
    "amended": "approved",
    # implementado
    "implementado": "implemented",
    "implementada": "implemented",
    "completado": "implemented",
    "completada": "implemented",
    "completed": "implemented",
    "complete": "implemented",
    "documentacion_completada": "implemented",
    "documented": "implemented",
    "documentado": "implemented",
    "en_produccion": "implemented",
    "operativo": "implemented",
    "estable": "implemented",
    "vigente": "implemented",
    # verificado
    "fixed": "verified",
    "corregido": "verified",
    "resuelto": "verified",
    "resolved": "verified",
    "validated": "verified",
    "validado": "verified",
    "mitigado": "verified",
    "mitigated": "verified",
    "prevenido": "verified",
    "pass": "verified",
    "implemented-and-validated": "verified",
    # retirado
    "deprecado": "deprecated",
    "deprecada": "deprecated",
    "obsoleto": "obsolete",
    "obsoleta": "obsolete",
    # histórico
    "historical": "archived",
    "archivo-historico": "archived",
    "archivo-histórico": "archived",
    "offline": "archived",
    "no-bug": "archived",
}

#: Sufijos que un estado arrastra y que NO son parte del estado: progreso
#: parcial, versión en que se resolvió, fecha de corrección. El censo los
#: encontró incrustados en el propio campo (`1-fixed-6-pending`, `all-fixed`,
#: `resuelto (v0.58)`, `aceptada (corregida 2026-05-11)`, `mayormente_corregido`).
#: Se extraen a `status_note` en vez de perderse: no-derogación aplicada al dato.
STATUS_QUALIFIERS = {
    "mayormente_corregido": ("verified", "corrección parcial"),
    "partial": ("in-progress", "parcial"),
    "all-fixed": ("verified", "all-fixed"),
    "not_run": ("planned", "not_run"),
}

#: Transiciones permitidas del ciclo de vida. Un estado que no puede alcanzarse
#: desde ninguno otro es inalcanzable, y uno del que no se sale es terminal.
#: `stub` y `template` no participan del ciclo: son marcas de naturaleza de la
#: nota, no fases de su vida.
STATUS_TRANSITIONS = {
    "planned": {"draft", "in-progress", "archived"},
    "draft": {"in-progress", "reviewed", "archived"},
    "in-progress": {"draft", "reviewed", "implemented", "archived"},
    "reviewed": {"approved", "draft", "archived"},
    "approved": {"implemented", "deprecated", "archived"},
    "implemented": {"verified", "deprecated", "archived"},
    "verified": {"deprecated", "obsolete", "archived"},
    "deprecated": {"obsolete", "archived"},
    "obsolete": {"archived"},
    "archived": set(),
    "stub": {"draft", "in-progress", "archived"},
    "template": {"archived"},
}


#: Vocabularios de dominio (AP-38).
#:
#: El censo del parque atribuía los 54 estados a agentes descuidados. Falso: el
#: valor no canónico más frecuente, `implementado` (205 notas), lo escribe
#: `vault_pattern_save`, que trae su propio vocabulario y su propia máquina de
#: transiciones. El estándar publicaba **nueve** vocabularios de `status` en
#: competencia — AP-05 dentro del propio toolkit. Un agente que escribía
#: `implementado` estaba obedeciendo a la tool, no ignorándola.
#:
#: La corrección no es borrar esos vocabularios: `pass` de un test o `P2` de un
#: incidente son información real que `verified` no expresa. Son **otro eje**.
#: Así que `status` queda reservado al ciclo de vida de la nota, canónico, y
#: cada dominio conserva su vocabulario íntegro en su propio campo. Las flags de
#: CLI no cambian: lo que cambia es en qué campo aterriza el valor.
#:
#: Formato: `tool -> (campo_de_dominio, {valor_de_dominio: status_canonico})`.
DOMAIN_STATUS_VOCABS = {
    "vault_pattern_save": ("pattern_state", {
        "planificado": "planned",
        "en_progreso": "in-progress",
        "implementado": "implemented",
        "deprecado": "deprecated",
        "refactoring": "in-progress",
    }),
    "vault_bug_save": ("bug_state", {
        "open": "in-progress",
        "confirmed": "in-progress",
        "in_fix": "in-progress",
        "fixed": "verified",
        "wont_fix": "approved",
        "duplicate": "obsolete",
    }),
    "vault_test_save": ("test_result", {
        "not_run": "planned",
        "pass": "verified",
        "fail": "implemented",
        "blocked": "in-progress",
        "skip": "draft",
    }),
    "vault_incident_save": ("incident_state", {
        "detected": "in-progress",
        "investigating": "in-progress",
        "identified": "in-progress",
        "mitigating": "in-progress",
        "resolved": "verified",
        "closed": "archived",
        "post-mortem": "reviewed",
    }),
    "vault_ncr_save": ("ncr_state", {
        "open": "in-progress",
        "in_progress": "in-progress",
        "pending_verification": "reviewed",
        "closed": "archived",
        "cancelled": "obsolete",
    }),
    "vault_risk_save": ("risk_state", {
        "open": "in-progress",
        "in_treatment": "in-progress",
        "accepted": "approved",
        "closed": "archived",
    }),
    "vault_release_save": ("release_state", {
        "planned": "planned",
        "in_progress": "in-progress",
        "deployed": "implemented",
        "rolled_back": "deprecated",
        "cancelled": "obsolete",
    }),
    "vault_privacy_save": ("privacy_state", {
        "active": "implemented",
        "under_review": "reviewed",
        "deprecated": "deprecated",
        "closed": "archived",
    }),
    # El comentario de vault_preferences decía "alineado con STATUS_VOCAB" y sus
    # dos únicos valores estaban fuera. Una afirmación falsa desde que se
    # escribió, y nadie podía verla porque no había guard que la comprobara.
    "vault_preferences": ("preference_state", {
        "active": "implemented",
        "revoked": "deprecated",
    }),
    # `--status` de infra es texto libre y nunca tuvo validación: es la única
    # de las nueve que no publicaba vocabulario, así que aceptaba cualquier
    # cosa. Se le da uno; lo que no encaje sigue cayendo en `normalize_status`.
    "vault_infra_save": ("infra_state", {
        "active": "implemented",
        "activo": "implemented",
        "provisioning": "in-progress",
        "degraded": "in-progress",
        "decommissioned": "archived",
        "offline": "archived",
    }),
    # `vault_runbook_save` escribía `status: active` a pelo desde su creación:
    # fuera de STATUS_VOCAB, solo aceptado como sinónimo de `in-progress`, que
    # además no es lo que un runbook listo para ejecutarse está. Mismo caso que
    # privacy y preferences: el valor de dominio se conserva, el canónico va en
    # `status` (CN-03, v40.35).
    "vault_runbook_save": ("runbook_state", {
        "active": "implemented",
    }),
    # `vault_qa_save` anunciaba y validaba cinco estados sin registrarlos aquí:
    # `review` y `published` no son canónicos, así que pasaban su validación y
    # `status_frontmatter_lines` los rechazaba después con UNEXPECTED_ERROR
    # crítico (v41.3). Un informe QA publicado es uno aprobado y distribuido:
    # `approved`, como `wont_fix` de un bug; el valor de dominio lo conserva.
    "vault_qa_save": ("qa_state", {
        "draft": "draft",
        "review": "reviewed",
        "approved": "approved",
        "published": "approved",
        "archived": "archived",
    }),
    "vault_project_status": ("project_state", {
        "en_desarrollo": "in-progress",
        "en_revision": "reviewed",
        "bloqueado": "in-progress",
        "completado": "implemented",
        "archivado": "archived",
        "en_produccion": "implemented",
    }),
}


def split_domain_status(tool, raw):
    """Separa el eje de dominio del ciclo de vida de la nota.

    Devuelve `(status_canonico, campo_dominio, valor_dominio)`. El valor de
    dominio se devuelve intacto — se conserva, no se traduce. Si la tool no
    tiene vocabulario propio, o el valor no está en él, cae en
    `normalize_status` y no se emite campo de dominio.
    """
    entrada = DOMAIN_STATUS_VOCABS.get(tool)
    if entrada and raw in entrada[1]:
        campo, mapa = entrada
        return mapa[raw], campo, raw
    canonico, _nota, _regla = normalize_status(raw)
    return canonico, None, None


def status_frontmatter_lines(tool, raw):
    """Las líneas de frontmatter que corresponden a un estado de dominio.

    Devuelve siempre `status:` canónico primero y, si aplica, el campo de
    dominio detrás. Que las 8 tools con vocabulario propio llamen aquí es lo que
    impide que vuelvan a divergir: el orden y los nombres de campo salen de un
    único sitio.
    """
    if raw is None:
        return []
    canonico, campo, valor = split_domain_status(tool, raw)
    if canonico is None:
        raise ValueError(
            f"{tool}: status {raw!r} no pertenece a su vocabulario de dominio "
            f"ni al canónico (CN-03)"
        )
    lineas = [f"status: {canonico}"]
    if campo:
        lineas.append(f"{campo}: {valor}")
    return lineas


def normalize_status(raw):
    """Lleva un `status` cualquiera al vocabulario canónico.

    Devuelve `(canonico, nota, regla)`:

      - `canonico` es un valor de `STATUS_VOCAB`, o `None` si no se pudo decidir
        — y entonces quien llama **rechaza**, no adivina. Inventar un estado es
        peor que no tenerlo: uno se detecta, el otro se hereda.
      - `nota` recoge lo que el valor original arrastraba y no era estado
        (progreso, versión, fecha). Nunca se descarta.
      - `regla` dice por qué se decidió: `canonical`, `synonym`, `qualifier`,
        `parenthetical` o `unknown`. Sirve para auditar la propia normalización.
    """
    if raw is None:
        return None, None, "unknown"

    original = str(raw).strip()
    if not original:
        return None, None, "unknown"

    # Un paréntesis o guion largo suele traer la circunstancia, no el estado:
    # "resuelto (v0.58)" es `verified` con una nota, no un estado nuevo.
    nota = None
    # El prefiltro barato va antes a propósito. `(.*?)\s*` delante de un
    # delimitador que **no está** hace al motor probar cada punto de corte:
    # 10.000 espacios sin paréntesis tardan 417 ms en decir que no. Preguntar
    # primero si hay delimitador cuesta una pasada lineal y evita el caso malo
    # entero, que es además el único que un valor hostil puede provocar.
    if any(c in original for c in "([—-"):
        m = re.match(r"^([^\(\[—-]*?)(?<!\s)\s*[\(\[—-]\s*(.+?)[\)\]]?$", original)
    else:
        m = None
    base = original
    if m and m.group(1).strip():
        candidato_base, candidato_nota = m.group(1).strip(), m.group(2).strip()
        if _canonical_status(candidato_base) is not None:
            base, nota = candidato_base, candidato_nota

    clave = base.lower().replace(" ", "_").replace("__", "_")

    if clave in STATUS_QUALIFIERS:
        canonico, cualificador = STATUS_QUALIFIERS[clave]
        return canonico, nota or cualificador, "qualifier"

    directo = _canonical_status(base)
    if directo is not None:
        regla = "parenthetical" if nota else (
            "canonical" if directo == base.lower() else "synonym"
        )
        return directo, nota, regla

    # "1-fixed-6-pending" y similares: un informe de progreso en el campo de
    # estado. No hay estado que deducir sin mentir, pero el dato se conserva.
    return None, original, "unknown"


def _canonical_status(valor):
    clave = str(valor).strip().lower().replace(" ", "_")
    if clave in STATUS_VOCAB:
        return clave
    guion = clave.replace("_", "-")
    if guion in STATUS_VOCAB:
        return guion
    if clave in STATUS_SYNONYMS:
        return STATUS_SYNONYMS[clave]
    if guion in STATUS_SYNONYMS:
        return STATUS_SYNONYMS[guion]
    return None


#: Una viñeta es una **línea** `-` o `*` seguida de blanco o de fin de línea.
#: superseded_by: este patrón (v40.35) — `^\s*[-*]\s*(.*)`, copiado en tres
#: sitios: el `\s*` cruzaba el salto de línea, así que una viñeta vacía se
#: tragaba la línea siguiente y contaba como llena, y `**negrita**` o `---`
#: pasaban por viñetas. Una lista `- ` / `- [ ]` / `- algo` salía con un 0 %
#: de vacías en vez del 67 %, y AP-20 no frenaba el esqueleto.
_VINETA = re.compile(r"^[ \t]*[-*](?:[ \t]+(.*?))?[ \t]*$", re.MULTILINE)

#: Lo que deja una viñeta sin contenido: nada, una casilla o un enlace vacío.
VINETA_VACIA = ("", "[]", "[[]]", "-", "[ ]")


def vinetas_de_lista(texto: str) -> List[str]:
    """AP-20: el texto de cada viñeta, `""` si está vacía. Dueño único (AP-57):
    `vault_write` lo usa para frenar y `vault_norms` para auditar."""
    return [(m.group(1) or "").strip() for m in _VINETA.finditer(texto)]


def compute_norm_refs(folder: str, content: str, wiki_links: List[str]) -> List[str]:
    """Las normas que aplican a una nota, deducidas de su carpeta y su cuerpo.

    Vive aquí y no en la fachada (v40.27) porque es **derivación de catálogo**:
    no lee el vault, no escribe nada y su única dependencia es `re`. Estaba
    arriba por herencia del fichero único, y eso costaba nueve cruces de
    contexto — nueve tools de Autoría importando `vault_norms`, y con él la
    fachada que reexporta el motor entero, para pedir una lista de códigos.

    Reglas:
      - universales:             AP-11, AP-12, AP-13, AP-16, CN-01, CN-02, SP-01
      - hay wikilinks:           + AP-14, AP-21, AP-22, SP-02
      - hay viñetas:             + AP-20
      - carpeta 03_Decisions/:   + AP-07
      - más de 500 líneas:       + AP-23 (informativa)
    """
    refs: set = {"AP-11", "AP-12", "AP-13", "AP-16", "CN-01", "CN-02", "SP-01"}

    if wiki_links:
        refs.update({"AP-14", "AP-21", "AP-22", "SP-02"})

    if vinetas_de_lista(content):
        refs.add("AP-20")

    folder_lower = folder.lower()
    if folder_lower.startswith("03_decisions") or "decisions" in folder_lower:
        refs.add("AP-07")

    if len(content.split("\n")) > 500:
        refs.add("AP-23")

    return sorted(refs)

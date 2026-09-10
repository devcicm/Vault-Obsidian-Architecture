#!/usr/bin/env python3
"""El motor que audita un vault contra el catálogo de normas.

**Aquí está el comportamiento; en `vault_norms_catalog`, la declaración.** Este
módulo recorre las notas, decide qué norma incumple cada una y sabe repararlo
(el heal de AP-46). Salió de `vault_norms` en v40.26 junto con el catálogo y por
el mismo motivo: un fichero de cinco mil líneas que hacía de catálogo, de motor
y de fachada a la vez.

**Se entra por `vault_norms`.** La fachada reexporta `vault_norms_audit`,
`framework_drift_check`, `heal_ap46` y `cuerpo_sin_marcadores`, así que ningún
llamador se tocó al partir — es lo que hizo el corte barato. El puerto declarado
del contexto sigue siendo `vault_norms:vault_norms_audit`, y se declaró en el
commit **anterior** a este a propósito: con la baseline de cruces indexada por la
cadena `origen -> destino`, hacerlo en el mismo commit habría mezclado «este
cruce siempre fue legítimo» con «este cruce cambió de módulo», y no habría forma
de saber cuál de las dos cosas movió la cifra.

**Los imports diferidos que verás dentro de las funciones se quedan como
estaban.** Son cruces de frontera reconocidos y congelados en
`arch-baseline.json`; invertirlos es otro cambio, y meterlo dentro de un
movimiento de código habría hecho imposible atribuir un fallo a uno de los dos.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml  # el criterio del consumidor, no un regex (AP-44)

from vault_errors import emit_error
from vault_io import (
    is_snapshot_path,
    normalize_stem,
    SNAPSHOT_DIRS,
)
from vault_lib import read_frontmatter as _leer_frontmatter
from vault_lib import yaml_scalar
from vault_registry import NON_SECTION_ROOT_FOLDERS

# La resolución del vault vive con quien lo recorre. Al partir en v40.26 estas
# tres funciones se quedaron un momento en la fachada y el motor las llamaba sin
# tenerlas: compilaba y habría lanzado `NameError` en la primera auditoría. Lo
# vio `test_source_hygiene`, que es exactamente para lo que existe.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
from vault.kernel import construir  # noqa: E402

from vault.gobernanza.auditoria_runtime import auditar_runtime  # noqa: E402

# Solo lo que el motor consulta de verdad. El resto del vocabulario
# (`LIFECYCLE_REGISTRY`, `STATUS_SYNONYMS`, `split_domain_status`…) lo reexporta
# la fachada directamente desde el catálogo: importarlo aquí sin usarlo habría
# creado una dependencia falsa justo en el commit que existe para medir cuáles
# son las de verdad.
from vault_norms_catalog import (
    NORM_CATALOG,
    STATUS_TRANSITIONS,
    STATUS_VOCAB,
    normalize_status,
)


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGobernanza:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGobernanza(construir(root))


def _norm_registry() -> Path:
    return _repo().registro_normas


# Entradas permitidas en la raíz del vault además de las secciones canónicas.
# La lista la declara `vault_registry`: el kernel ya la usaba para no indexar
# esas carpetas, y tenerla aquí a mano hacía que `docs/` —que escribe el propio
# `vault_sdd_init`— violara CN-02 contra el sandbox (AP-05).
_ROOT_ALLOWED = set(NON_SECTION_ROOT_FOLDERS)

#: Alias de compatibilidad. El criterio de "qué es una nota viva" se movió a
#: `vault_io` en cuanto una segunda tool lo necesitó (`vault_mermaid_check`):
#: es del vault, no de este barrido. Se conserva el nombre local porque los
#: tests y las llamadas de este módulo lo usan — no se deroga, se delega.
_SNAPSHOT_DIRS = SNAPSHOT_DIRS
_es_instantanea = is_snapshot_path


#: Primer de sección: `00-10_migrated-primer`, `00-03_decisions-primer`, …
#: Los crea `vault_init` como guía de uso de la carpeta.
_ES_PRIMER = re.compile(r"^\d{2}-\d{2}_.*-primer$")


#: Valores de `type` que identifican una decisión arquitectónica, y por tanto
#: obligan a la estructura Contexto / Decisión / Consecuencias de AP-07.
_ADR_TYPES = ("decision", "adr")


# La hoja reusable es la dueña. El nombre público histórico se conserva.
from vault.kernel.contenido import cuerpo_sin_marcadores


#: superseded_by: `cuerpo_sin_marcadores`. El nombre privado no se borra —la
#: no-derogación vale también para los símbolos— pero dejó de ser el canónico
#: en v40.8: `vault_onboard`, que es de otro contexto, lo importaba tal cual, y
#: un `_` cruzando una frontera no es una superficie publicada.
_cuerpo_sin_marcadores = cuerpo_sin_marcadores


#: Manifiesto público del estándar — referencia del guard anti-drift del marco.
SPEC_FILENAME = "vault-obsidian-architecture.md"

#: Nombres de artefactos que SOLO deben existir dentro de un vault. Si aparecen
#: por encima del vault root son side-effects escritos fuera (AP-36).
_VAULT_ARTIFACT_NAMES = ("00_System", "99_Index", "vault-backups", ".history")

#: Niveles por encima del vault que inspecciona el guard de contaminación.
#: 2 cubre el patrón legacy parent.parent.parent, que en topología spec-repo
#: (vault = <repo>/vault-sandbox) cae en el abuelo del directorio de scripts.
_CONTAMINATION_DEPTH = 2


def _checks_estandar(flag) -> None:
    # ── AP-40: el contrato publicado tiene que ser el que la CLI acepta ───────
    # No mira el vault: mira el repo del estándar. Se audita aquí porque es el
    # único recorrido que un agente corre siempre, y un catálogo roto no se
    # manifiesta como error de datos sino como una tool que nunca funciona.
    try:
        import vault_mcp_catalog as _cat

        _params = _cat.check_params()
        for _p in _params.get("problems", []):
            flag(
                "AP-40",
                f"mcp/nodejs/tools-catalog.json#{_p['tool']}",
                f"{_p['problem']} — correr vault_mcp_catalog --sync.",
            )
    except (ImportError, OSError, ValueError):
        pass

    # ── AP-42: deuda de ejecución declarada ───────────────────────────────────
    # El barrido completo tarda minutos y vive en `vault_smoke --strict` (CI).
    # Aquí se reporta lo barato y lo que de verdad se olvida: la deuda que
    # alguien congeló en la baseline y las tools cuyo ejemplo ni siquiera puede
    # convertirse en una invocación.
    try:
        import vault_smoke as _smoke

        for _t in _smoke.load_baseline():
            flag(
                "AP-42",
                f"scripts/smoke-baseline.json#{_t}",
                f"{_t} está congelada como deuda: su ejemplo documentado no emite "
                "un JSON con `ok`. La baseline solo puede encoger.",
            )
        for _t in sorted(_smoke.TOOLS_CATALOG):
            if _t in _smoke.SIN_SMOKE:
                continue
            if _smoke.invocation(_t) is None and (_smoke.TOOLS_CATALOG[_t] or {}).get("script"):
                flag(
                    "AP-42",
                    f"vault_mcp_catalog.TOOLS_CATALOG#{_t}",
                    f"{_t} no tiene un `example` del que derivar una invocación: "
                    "no se puede ejecutar nunca ni en el smoke ni por un usuario.",
                )
    except (ImportError, OSError, ValueError):
        pass

    # ── AP-43: normas que ninguna tool pronuncia ──────────────────────────────
    # Tampoco mira el vault: mira el catálogo. Una norma sin tools_enforcing ni
    # tools_detecting no llega jamás al agente por el bloque `vault_says`, así
    # que existe para el auditor y no para quien escribe.
    try:
        import vault_voice as _voz

        for _codigo in _voz.coverage().get("silent", []):
            flag(
                "AP-43",
                f"vault_norms.NORM_CATALOG#{_codigo}",
                f"{_codigo} no la pronuncia ninguna tool: declara tools_enforcing "
                "o tools_detecting para que el agente la vea al trabajar.",
            )
    except (ImportError, OSError, ValueError):
        pass



def vault_norms_audit(root: Optional[Path] = None) -> Dict[str, Any]:
    """Compatibilidad histórica: runtime audit más observabilidad del estándar."""
    result = auditar_runtime(root, insertar_checks_estandar=_checks_estandar)
    result["tool"] = "vault_norms.audit"
    return result


# ─── Guard anti-drift del marco de datos (v39) ─────────────────────────────────


def framework_drift_check(spec_path: Optional[Path] = None) -> Dict[str, Any]:
    """Verifica que el manifiesto documente todos los ids del marco de datos.

    El fallo de la Era 4 fue documentar sin ejecutar. Aquí es al revés: el
    registro canónico vive en ``vault_fundamentals`` y este guard falla si el
    manifiesto público se desincroniza de él — en cualquiera de las dos
    direcciones (id registrado que el doc no explica, o id citado en el doc
    que ya no existe en el registro).
    """
    from vault_fundamentals_catalog import FRAMEWORK_REGISTRIES

    spec = Path(spec_path) if spec_path else Path(__file__).resolve().parent.parent / SPEC_FILENAME
    if not spec.exists():
        return emit_error(
            "vault_norms.framework_drift", "FILE_NOT_FOUND",
            f"No se encontró el manifiesto en {spec}",
            args={"spec": str(spec)},
        )

    text = spec.read_text(encoding="utf-8", errors="replace")
    missing: List[Dict[str, str]] = []
    for registry_name, entries in FRAMEWORK_REGISTRIES.items():
        for entry in entries:
            if entry["id"] not in text:
                missing.append(
                    {
                        "registry": registry_name,
                        "id": entry["id"],
                        "name": entry.get("name", ""),
                    }
                )

    # Cobertura de secciones: toda norma catalogada tiene que tener su sección
    # en el manifiesto. La medida es el **encabezado**, no la mención: once
    # normas (AP-25..AP-35) estaban citadas de pasada en entradas de changelog
    # y eso las hacía pasar por documentadas durante diez versiones mientras
    # `vault_norms --list` las mostraba y el manifiesto no las explicaba. Un
    # `in text` habría dado verde — es AP-44 otra vez: medir con el criterio
    # cómodo en vez de con el del lector, que busca la sección.
    encabezados = set(re.findall(r"^#{2,4}\s+((?:AP|PAT|SP|CN)-\d+)", text, re.M))
    sin_seccion = [n["code"] for n in NORM_CATALOG if n["code"] not in encabezados]

    return {
        "ok": not missing and not sin_seccion,
        "tool": "vault_norms.framework_drift",
        "spec": spec.name,
        "total_ids": sum(len(e) for e in FRAMEWORK_REGISTRIES.values()),
        "missing_count": len(missing),
        "missing": missing,
        "norms_total": len(NORM_CATALOG),
        "norms_without_section": sin_seccion,
    }

# ─── AP-46: heal del frontmatter que una tool escribió y nadie releyó ─────────
#
# AP-46 tenía guard y audit, y ni una línea de reparación. El guard evita que se
# escriba mal a partir de ahora; no levanta lo que ya está escrito. El escapado
# se corrigió en los writers en v40.2, y el contraste contra un vault ajeno
# (regla 7) encontró cuatro notas rotas de antes — una de ellas
# `title: ADR-001: Adopción de MCP…`, que YAML lee como un mapeo dentro de un
# mapeo y que deja la nota **entera** sin frontmatter al parsearse: sin id, sin
# tags, sin tipo. La nota existe, el vault la cuenta, y para cualquier consumidor
# es un documento anónimo.
#
# Por qué repara dos clases y no todas: son las dos que un programa puede
# arreglar sin adivinar la intención de nadie. Cualquier otra rotura se reporta
# y se deja, porque el heal que "arregla" un frontmatter ambiguo eligiendo por su
# cuenta es exactamente AP-46 cometida por la herramienta que vino a curarla.



#: Una línea que abre clave de frontmatter. No admite `:` sin espacio detrás a
#: propósito: `title: ADR-001: Adopción…` tiene que seguir siendo **una** clave
#: (`title`) con un valor sucio, no dos claves.
_RE_CLAVE_FM = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s(.*))?$")

#: Continuaciones válidas dentro del bloque: ítems de lista y líneas indentadas.
_RE_CONTINUACION_FM = re.compile(r"^(?:\s+\S|- )")


def _cierra_el_bloque(lineas: List[str]) -> Optional[int]:
    """Dónde termina el frontmatter de una nota cuyo `---` de cierre falta.

    El límite es la última línea consecutiva que sigue teniendo forma de
    frontmatter, contando desde la de después del `---` de apertura. Si la nota
    no tiene ni una sola clave, no hay nada que cerrar y se devuelve `None`: un
    heal que insertara `---` en la primera línea en blanco convertiría el primer
    párrafo del cuerpo en metadatos.
    """
    ultima = None
    for indice, linea in enumerate(lineas[1:], start=1):
        if not linea.strip():
            break
        if _RE_CLAVE_FM.match(linea) or _RE_CONTINUACION_FM.match(linea):
            ultima = indice
            continue
        break
    return ultima


def _reescapa_escalares(lineas: List[str]) -> List[str]:
    """Cita los valores que rompen el YAML, con el criterio del consumidor.

    `yaml_scalar` no cita por si acaso: comprueba que el parser real devuelva el
    mismo texto y solo cita si no. Así lo que ya estaba bien se queda byte a
    byte igual y solo se toca lo que de verdad rompía.
    """
    salida = []
    for linea in lineas:
        match = _RE_CLAVE_FM.match(linea)
        if not match or match.group(2) is None:
            salida.append(linea)
            continue
        clave, valor = match.group(1), match.group(2)
        if not valor.strip():
            salida.append(linea)
            continue
        try:
            yaml.safe_load(f"{clave}: {valor}")
            salida.append(linea)          # parsea: no se toca
        except (yaml.YAMLError, RecursionError):  # AP-61 - ver vault_lib.parse_frontmatter
            salida.append(f"{clave}: {yaml_scalar(valor)}")
    return salida


def _planificar_ap46(raw: str) -> Optional[Dict[str, Any]]:
    """Qué haría el heal con esta nota, sin tocar nada.

    Devuelve `None` si la nota está sana o si su rotura no es de las dos que se
    saben reparar. El texto propuesto se **verifica antes de proponerse**: tiene
    que parsear con `yaml.safe_load` y dejar el cuerpo idéntico. Un heal que no
    comprueba su propio resultado es la misma clase de afirmación no falsable
    que AP-37 persigue.
    """
    if not raw.startswith("---"):
        return None
    lineas = raw.split("\n")

    # Una nota que ya parsea no se toca. La comprobación se repite aquí aunque
    # `heal_ap46` filtre antes: el planificador se llama también suelto —desde
    # los tests y desde cualquier consumidor futuro— y una función que propone
    # reparar lo sano es una trampa esperando a que alguien la llame.
    resto = raw.split("\n", 1)[1] if "\n" in raw else ""
    corte = resto.find("\n---")
    if corte != -1:
        try:
            ya = yaml.safe_load(resto[: corte + 1])
            if isinstance(ya, dict) and ya:
                return None
        except (yaml.YAMLError, RecursionError):  # AP-61 - ver vault_lib.parse_frontmatter
            pass

    # Las dos hipótesis se prueban, no se deducen. Deducir la clase por la
    # presencia de un `\n---` más abajo parecía obvio y estaba mal: tres de las
    # cuatro notas rotas de un vault real llevan una regla horizontal `---` en
    # el cuerpo, así que un bloque **sin cerrar** se clasificaba como "bloque
    # cerrado que no parsea" y se le aplicaba la reparación equivocada. Se
    # prueban las dos y gana la que verifique — el criterio es el resultado,
    # no la corazonada.
    candidatas: List[Tuple[str, List[str]]] = []

    fin = lineas.index("---", 1) if "---" in lineas[1:] else None
    if fin is not None:
        candidatas.append((
            "escalar_sin_escapar",
            lineas[:1] + _reescapa_escalares(lineas[1:fin]) + lineas[fin:],
        ))

    limite = _cierra_el_bloque(lineas)
    if limite is not None:
        candidatas.append((
            "bloque_sin_cerrar",
            lineas[: limite + 1] + ["---"] + lineas[limite + 1 :],
        ))

    for clase, nuevas in candidatas:
        propuesto = "\n".join(nuevas)
        # Verificación con el criterio del consumidor (AP-44), no con el propio.
        try:
            bloque = propuesto.split("\n", 1)[1]
            fin_bloque = bloque.find("\n---")
            if fin_bloque == -1:
                continue
            datos = yaml.safe_load(bloque[: fin_bloque + 1])
        except (yaml.YAMLError, RecursionError):  # AP-61 - ver vault_lib.parse_frontmatter
            continue
        if not isinstance(datos, dict) or not datos:
            continue
        if _cuerpo_de(propuesto) != _cuerpo_de(raw):
            continue                       # el heal movió texto: no se aplica
        return {"clase": clase, "texto": propuesto, "claves": sorted(datos)}

    return None


def _cuerpo_de(texto: str) -> str:
    """El cuerpo, para comprobar que el heal no se llevó nada por delante.

    Sobre el texto roto no se puede usar el frontmatter como referencia —no
    parsea, que es el problema— así que se compara lo que hay tras el primer
    encabezado markdown, que ninguna de las dos reparaciones toca.
    """
    posicion = texto.find("\n#")
    return texto[posicion:] if posicion != -1 else ""


def heal_ap46(root: Optional[Path] = None, apply: bool = False) -> Dict[str, Any]:
    """Repara el frontmatter roto que dejaron los writers de antes de v40.2.

    **No escribe salvo `apply=True`.** El default es el informe, y al revés no:
    esta tool se ejecuta sobre vaults reales cuyo contenido no generó este repo,
    y una reparación automática no pedida sobre material ajeno es exactamente lo
    que la regla 7 dice que no se hace.
    """
    from vault_io import get_vault_root, is_snapshot_path

    raiz = Path(root) if root else get_vault_root()
    if not raiz.exists():
        return emit_error("vault_norms", "VAULT_NOT_FOUND",
                          f"No existe la raíz indicada: {raiz}")

    sello = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino_backup = raiz / ".history" / "ap46-heal" / sello
    reparadas, omitidas = [], []

    for path in sorted(raiz.rglob("*.md")):
        rel = path.relative_to(raiz).as_posix()
        if is_snapshot_path(rel):
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            omitidas.append({"note": rel, "reason": f"ilegible: {type(exc).__name__}"})
            continue
        if not raw.startswith("---"):
            continue
        resto = raw.split("\n", 1)[1] if "\n" in raw else ""
        corte = resto.find("\n---")
        rota = False
        if corte == -1 and not resto.startswith("---"):
            rota = True
        else:
            try:
                yaml.safe_load(resto[: corte + 1] if corte != -1 else "")
            except (yaml.YAMLError, RecursionError):  # AP-61 - ver vault_lib.parse_frontmatter
                rota = True
        if not rota:
            continue

        plan = _planificar_ap46(raw)
        if plan is None:
            omitidas.append({
                "note": rel,
                "reason": "rotura que el heal no sabe reparar sin adivinar; "
                          "arréglala a mano",
            })
            continue

        entrada = {"note": rel, "class": plan["clase"], "keys": plan["claves"]}
        if apply:
            copia = destino_backup / rel
            copia.parent.mkdir(parents=True, exist_ok=True)
            copia.write_bytes(raw.encode("utf-8"))
            path.write_bytes(plan["texto"].encode("utf-8"))
            entrada["backup"] = copia.relative_to(raiz).as_posix()
        reparadas.append(entrada)

    return {
        "ok": True,
        "tool": "vault_norms.heal_ap46",
        "norm": "AP-46",
        "root": str(raiz),
        "applied": apply,
        "healed": len(reparadas) if apply else 0,
        "would_heal": 0 if apply else len(reparadas),
        "notes": reparadas,
        "skipped": omitidas,
        "backup_dir": str(destino_backup.relative_to(raiz)) if apply and reparadas else None,
        "hint": None if apply else (
            "Informe en seco: no se escribió nada. Añade --apply para reparar, "
            "y sobre un vault que no generó este repo, solo si su dueño lo pide."
        ),
    }

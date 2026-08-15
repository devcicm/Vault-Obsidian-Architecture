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


#: Marcadores de pendiente: texto que ocupa sitio sin afirmar nada. La lista
#: sale de lo que escriben los generadores del propio estándar —`vault_onboard`
#: emitía 8 conceptos cuyo cuerpo entero era `_Pendiente. Leer la sección del
#: README._`— más las convenciones habituales de un esqueleto a medio llenar.
#:
#: El marcador tiene que ser la LÍNEA ENTERA, no su comienzo. Casar por prefijo
#: es el error de `PLACEHOLDER_PATTERNS` en `vault_audit` —que descartaba
#: `[[patron-mcp-streaming]]` por empezar con `patron`— repetido aquí: se
#: tragaría «Pendiente de revisar el retry, pero el flujo ya está descrito
#: arriba», que es contenido real. Se admite el envoltorio de énfasis y de
#: viñeta alrededor, y una cola de puntuación o un complemento corto tras dos
#: puntos (`TODO: revisar`) sigue siendo un marcador solo si no trae frase.
#: La sangría va **acotada**, y no es cosmética. `^\s*` seguido de otro `\s*`
#: —con un grupo opcional en medio que puede casar vacío— deja al motor probar
#: cada reparto posible de los espacios entre los dos, que es cuadrático en la
#: longitud de la línea. Medido: 1.000 espacios, 31 ms; 4.000, 500 ms; 16.000,
#: 8,3 s; 64.000, **137 segundos**. Una sola línea de una nota deja colgada la
#: auditoría entera, y esa línea puede entrar por `vault_ingest` desde material
#: que el vault no escribió.
#:
#: Acotarla a dieciséis lo vuelve lineal (64.000 → 83 ms, 1.600 veces más
#: rápido) sin cambiar un solo veredicto: ninguna nota real sangra un marcador
#: más de dieciséis espacios, y los casos con dos, ocho y veintitrés siguen
#: dando lo mismo. Lo que se pierde es la sangría absurda, que es justamente el
#: input que nadie escribe y sí construye quien busca colgar la tool.
_MARCADORES_PENDIENTE = re.compile(
    r"^[ \t]{0,16}(?:[-*+]\s+|>\s*)?[_*]{0,2}\s*(?:"
    r"pendientes?|todo|fixme|tbd|t\.b\.d\.?"
    r"|por (?:definir|documentar|completar|determinar)"
    r"|sin (?:datos|contenido|informaci[oó]n|detectar|detectados?|detectadas?)"
    r"|no (?:detectados?|detectadas?|disponible|aplica)"
    r"|desconocidos?|desconocidas?|n/a"
    r")\s*[_*]{0,2}\s*[.:;!]?\s*[_*]{0,2}\s*$",
    re.IGNORECASE,
)

#: Aparte en cursiva que empieza por un marcador y ocupa la línea entera:
#: `_Pendiente. Leer la sección del README._`. Aquí sí se casa por comienzo,
#: pero el prefijo no basta: la línea completa tiene que ir envuelta en énfasis.
#: Esa envoltura es la que distingue el aparte de un generador de la prosa de un
#: autor —nadie escribe un párrafo real entero en cursiva— y es lo que impide
#: que esta regla se coma contenido, que es el fallo que AP-44 castiga.
_APARTE_PENDIENTE = re.compile(
    r"^\s*(?:[-*+]\s+|>\s*)?([_*]{1,2})\s*(?:pendientes?|todo|tbd|por (?:definir|documentar|completar))"
    r"\b.*\1\s*$",
    re.IGNORECASE,
)


#: Línea que es puro andamiaje tipográfico: encabezado, regla horizontal,
#: separador de tabla, viñeta vacía, comentario HTML.
_LINEA_ANDAMIO = re.compile(
    r"^\s*(?:#{1,6}\s|-{3,}\s*$|\*{3,}\s*$|\|[\s|:-]*\|\s*$|[-*+]\s*$|>\s*$|<!--)"
)


def cuerpo_sin_marcadores(body: str) -> str:
    """Lo que queda de un cuerpo tras quitar andamiaje y marcadores de pendiente.

    Cadena vacía significa que la nota no afirma nada: todo lo que contiene es
    estructura anunciando contenido que no está. Es la mitad del guard de AP-45
    —la otra mitad es que tampoco enlace con nada—.
    """
    if not body:
        return ""
    # El frontmatter ya viene separado, pero un cuerpo puede traer bloques de
    # código vacíos que tampoco afirman nada.
    limpio = re.sub(r"```[^\n]*\n\s*```", "", body)
    # Tabla de solo cabecera y separador: promete columnas y no trae ni una
    # fila. Es andamiaje, igual que un encabezado sin párrafo debajo — y hay
    # que quitarla entera, porque la cabecera sí tiene texto y sobreviviría al
    # filtro línea a línea.
    limpio = re.sub(
        r"^[ \t]*\|.*\|[ \t]*\n[ \t]*\|[\s|:-]+\|[ \t]*$(?!\n[ \t]*\|)",
        "",
        limpio,
        flags=re.MULTILINE,
    )
    utiles = [
        ln
        for ln in limpio.splitlines()
        if ln.strip()
        and not _LINEA_ANDAMIO.match(ln)
        and not _MARCADORES_PENDIENTE.match(ln)
        and not _APARTE_PENDIENTE.match(ln)
    ]
    return "\n".join(utiles).strip()


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


def vault_norms_audit(root: Optional[Path] = None) -> Dict[str, Any]:
    """Audita el vault contra las normas automatizables (ex-manual).

    Cubre: AP-06, AP-07, AP-09, AP-10, AP-15, AP-19, CN-02, CN-03, SP-01.
    Las secciones canónicas se toman de vault_registry (fuente de verdad única,
    PAT-1) — nunca de listas hardcodeadas en el catálogo.
    """
    from datetime import datetime, timezone

    import yaml

    from vault_lib import extract_wikilinks, parse_frontmatter_with_body
    from vault_registry import SECTIONS

    root = (root or _raiz()).resolve()
    canonical_sections = {s["folder"] for s in SECTIONS}
    violations: List[Dict[str, Any]] = []

    def _flag(norm: str, path: str, detail: str) -> None:
        n = next((x for x in NORM_CATALOG if x["code"] == norm), {})
        violations.append(
            {
                "norm": norm,
                "severity": n.get("severity", "medium"),
                "path": path,
                "detail": detail,
            }
        )

    # ── AP-15 + CN-02: higiene de raíz ────────────────────────────────────────
    if root.exists():
        for entry in sorted(root.iterdir()):
            name = entry.name
            if name.startswith(".") and name in _ROOT_ALLOWED:
                continue
            if entry.is_dir():
                if name not in canonical_sections and name not in _ROOT_ALLOWED:
                    _flag(
                        "CN-02",
                        name,
                        f"Carpeta '{name}' en la raíz no es una sección canónica "
                        f"({len(canonical_sections)} secciones válidas en vault_registry).",
                    )
            elif not name.startswith("."):
                _flag("AP-15", name, f"Archivo suelto '{name}' en la raíz del vault.")

    # ── AP-47: el índice refleja el disco ─────────────────────────────────────
    # Se delega en `vault_reindex.index_coherence`, que es quien define qué
    # cuenta como nota indexable, en vez de recontar aquí con el criterio del
    # audit —que excluye `10_Migrated/` y las instantáneas—. Dos criterios para
    # "cuántas notas hay" darían un desfase que `vault_reindex` no arreglaría
    # nunca, porque no es el que él mide (AP-44). Un solo hallazgo por vault: el
    # desfase es del índice, no de cada nota que falta en él.
    if root.exists():
        try:
            from vault_reindex import index_coherence

            coherencia = index_coherence(root)
            if not coherencia["ok"]:
                detalle = {
                    "index_missing": "No existe 99_Index/search-index.json.",
                    "index_corrupt": "99_Index/search-index.json no parsea.",
                }.get(
                    coherencia["status"],
                    f"{coherencia.get('missing_count', 0)} nota(s) en disco fuera "
                    f"del índice y {coherencia.get('stale_count', 0)} entrada(s) "
                    f"que ya no existen "
                    f"({coherencia['on_disk']} en disco / {coherencia['indexed']} "
                    f"indexadas).",
                )
                _flag(
                    "AP-47",
                    "99_Index/search-index.json",
                    f"{detalle} La búsqueda no ve lo que hay escrito, así que el "
                    f"agente lo vuelve a escribir. Remedio: `vault_reindex`.",
                )
        except ImportError:
            pass  # sin la tool no hay nada que contrastar

    # ── Cargar notas una sola vez ─────────────────────────────────────────────
    notes: Dict[str, Dict[str, Any]] = {}
    for md in sorted(root.rglob("*.md")):
        rel = str(md.relative_to(root)).replace("\\", "/")
        if rel.startswith(("10_Migrated/", ".")) or "/.history/" in rel:
            continue
        if _es_instantanea(rel):
            continue
        try:
            raw = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # ── AP-46: frontmatter construido a mano y nunca releído ──────────────
        # Se mira el texto CRUDO a propósito: `parse_frontmatter_with_body`
        # devuelve `{}` tanto para "no tiene frontmatter" como para "lo tiene y
        # está roto", y esa indistinción es justamente lo que dejó a
        # `vault_migrate_docs` publicando bloques sin cerrar. El criterio es el
        # del consumidor —`yaml.safe_load`—, no un regex por líneas (AP-44).
        if raw.startswith("---"):
            resto = raw.split("\n", 1)[1] if "\n" in raw else ""
            corte = resto.find("\n---")
            if corte == -1 and not resto.startswith("---"):
                _flag(
                    "AP-46",
                    rel,
                    "Frontmatter abierto con '---' que nunca cierra: la nota "
                    "entera se lee como metadatos y su cuerpo desaparece para "
                    "quien la consuma.",
                )
            else:
                try:
                    yaml.safe_load(resto[: corte + 1] if corte != -1 else "")
                except Exception as exc:
                    _flag(
                        "AP-46",
                        rel,
                        f"Frontmatter que no parsea como YAML "
                        f"({type(exc).__name__}): lo escribió una tool "
                        f"concatenando líneas y nadie releyó el resultado.",
                    )

        try:
            fm, body = parse_frontmatter_with_body(raw)
        except (OSError, UnicodeDecodeError):
            continue
        notes[rel] = {"fm": fm or {}, "body": body}

    inbound: Dict[str, int] = {}
    for rel, info in notes.items():
        for link in extract_wikilinks(info["body"]):
            inbound[link.split("|")[0].strip().lower()] = (
                inbound.get(link.split("|")[0].strip().lower(), 0) + 1
            )

    for rel, info in notes.items():
        fm, body = info["fm"], info["body"]
        note_type = str(fm.get("type", "")).lower()
        status = str(fm.get("status", "")).lower()
        stem = Path(rel).stem.lower()

        # ── CN-03: vocabulario de status ──────────────────────────────────────
        if status and status not in STATUS_VOCAB:
            _flag("CN-03", rel, f"status '{status}' fuera del vocabulario canónico {sorted(STATUS_VOCAB)}.")

        # ── AP-45: cobertura sin evidencia ────────────────────────────────────
        # Detectable sin ambigüedad: el cuerpo, quitados encabezados y
        # marcadores de pendiente, queda vacío Y no hay un solo wikilink
        # saliente. Las dos condiciones juntas, porque cada una por separado
        # tiene usos legítimos: una nota puede ser un índice de puros enlaces
        # sin prosa, y un apunte corto puede no enlazar todavía con nada.
        #
        # Dos exenciones, ambas por declararse:
        #   `status: template` — los primers de vault_init son andamiaje que
        #   anuncia lo que es, y eso es lo contrario del relleno.
        #   `index` — los índices de sección los genera vault_section_index a
        #   partir de lo que hay; uno vacío refleja una sección vacía, que ya
        #   es el estado honesto.
        if status != "template" and note_type != "index" and stem != "index":
            if not extract_wikilinks(body):
                residuo = _cuerpo_sin_marcadores(body)
                if not residuo:
                    _flag(
                        "AP-45",
                        rel,
                        "Cuerpo sin contenido ni enlaces: solo encabezados y "
                        "marcadores de pendiente. Una sección vacía es un hueco "
                        "visible; esta nota lo tapa sin llenarlo. Bórrala o "
                        "escribe lo que afirma.",
                    )

        # ── AP-09: runbooks fuera de 08_Runbooks ──────────────────────────────
        if note_type == "runbook" and not rel.startswith("08_Runbooks/"):
            _flag("AP-09", rel, "Nota type:runbook fuera de 08_Runbooks/.")

        # ── AP-07: ADRs incompletos ───────────────────────────────────────────
        # No toda nota de 03_Decisions/ es un ADR: la sección aloja también
        # primers y guías de uso, a las que exigir "Contexto/Decisión/
        # Consecuencias" no las mejora — las deforma. Una nota queda fuera solo
        # si DECLARA un `type` ajeno a la decisión; sin `type` sigue tratándose
        # como ADR, para que omitir el campo no sea la vía de escape del guard.
        es_adr = note_type in _ADR_TYPES or not note_type or stem.startswith("adr-")
        if (
            rel.startswith("03_Decisions/")
            and stem != "index"
            and es_adr
            and status not in ("stub", "template")  # stubs se rigen por AP-03
        ):
            required = {
                "Contexto": "context",
                "Decisión": "decisi",
                "Consecuencias": "consecuen|consequence",
            }
            lower_body = body.lower()
            missing = [
                name
                for name, pat in required.items()
                if not re.search(rf"^#+.*({pat})", lower_body, re.MULTILINE | re.IGNORECASE)
            ]
            if missing or not status:
                problems = []
                if missing:
                    problems.append(f"secciones faltantes: {', '.join(missing)}")
                if not status:
                    problems.append("sin campo status")
                _flag("AP-07", rel, "ADR incompleto — " + "; ".join(problems) + ".")

        # ── AP-06: templates sin instancias (sin inbound links) ──────────────
        if note_type == "template" or "template" in [str(t).lower() for t in fm.get("tags", []) or []]:
            if inbound.get(stem, 0) == 0:
                _flag("AP-06", rel, "Template sin inbound links — sin instancias que lo usen.")

        # ── AP-19: shadow indexing ────────────────────────────────────────────
        if (
            "index" in stem
            and stem != "index"
            and not rel.startswith("99_Index/")
            and stem not in ("master-index",)
        ):
            _flag("AP-19", rel, f"Nota índice paralela '{rel}' fuera de 99_Index/ (shadow indexing).")

    # ── AP-39: vocabulario abierto sin memoria ────────────────────────────────
    # Dos señales distintas, y conviene no confundirlas: familias de variantes
    # tipográficas del mismo término (lo que el guard de escritura ya colapsa a
    # partir de ahora, y que aquí solo aparece como deuda anterior), y términos
    # fuera del registro canónico que nadie anotó en la bitácora — el olvido
    # propiamente dicho.
    try:
        import vault_tags as _tags

        # La bitácora vive en el vault detectado; con --root a otro vault los
        # caminos no coinciden y el chequeo diría cualquier cosa menos la verdad.
        # `_raiz()` resuelve al usarse: la constante congelada que había aquí
        # desapareció al migrar el contexto Índices al dominio (AP-49).
        if _tags.raiz().resolve() != root:
            raise ImportError("AP-39 solo audita el vault detectado")

        familias: Dict[str, Dict[str, List[str]]] = {}
        for rel, info in notes.items():
            crudos = info["fm"].get("tags") or []
            if isinstance(crudos, str):
                crudos = [t.strip() for t in crudos.split(",") if t.strip()]
            for crudo in crudos:
                norma = _tags.normalize_tag(str(crudo))
                if not norma:
                    continue
                familias.setdefault(_tags.singular_tag(norma), {}).setdefault(
                    str(crudo), []
                ).append(rel)

        for raiz, variantes in sorted(familias.items()):
            if len(variantes) > 1:
                muestra = ", ".join(f"'{v}'" for v in sorted(variantes)[:4])
                notas = sorted({r for v in variantes.values() for r in v})
                _flag(
                    "AP-39",
                    notas[0],
                    f"{len(variantes)} variantes del mismo término '{raiz}' ({muestra}) "
                    f"en {len(notas)} nota(s) — correr vault_tags --rename para unificar.",
                )

        canonicos_norm = {
            _tags.normalize_tag(t) for t in _tags.canonical_tags()
        }
        anotados = {e["tag"] for e in _tags.load_ledger().get("entries", [])}
        sin_memoria = sorted(
            raiz
            for raiz, variantes in familias.items()
            if raiz not in canonicos_norm
            and not any(_tags.normalize_tag(v) in canonicos_norm for v in variantes)
            # La bitácora guarda la forma normalizada, no la raíz en singular:
            # comparar solo contra `raiz` daría por no anotado todo plural.
            and raiz not in anotados
            and not any(_tags.normalize_tag(v) in anotados for v in variantes)
        )
        if sin_memoria:
            muestra = ", ".join(f"'{t}'" for t in sin_memoria[:6])
            _flag(
                "AP-39",
                "19_Audits/vocabulary/tag-ledger.json",
                f"{len(sin_memoria)} término(s) en uso que no son canónicos ni constan "
                f"en la bitácora ({muestra}) — vocabulario introducido sin dejar rastro "
                f"de quién ni cuándo. Correr vault_tags --backfill-ledger para anotarlos.",
            )
    except ImportError:
        pass

    # ── AP-40: el contrato publicado tiene que ser el que la CLI acepta ───────
    # No mira el vault: mira el repo del estándar. Se audita aquí porque es el
    # único recorrido que un agente corre siempre, y un catálogo roto no se
    # manifiesta como error de datos sino como una tool que nunca funciona.
    try:
        import vault_mcp_catalog as _cat

        _params = _cat.check_params()
        for _p in _params.get("problems", []):
            _flag(
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
            _flag(
                "AP-42",
                f"scripts/smoke-baseline.json#{_t}",
                f"{_t} está congelada como deuda: su ejemplo documentado no emite "
                "un JSON con `ok`. La baseline solo puede encoger.",
            )
        for _t in sorted(_smoke.TOOLS_CATALOG):
            if _t in _smoke.SIN_SMOKE:
                continue
            if _smoke.invocation(_t) is None and (_smoke.TOOLS_CATALOG[_t] or {}).get("script"):
                _flag(
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
            _flag(
                "AP-43",
                f"vault_norms.NORM_CATALOG#{_codigo}",
                f"{_codigo} no la pronuncia ninguna tool: declara tools_enforcing "
                "o tools_detecting para que el agente la vea al trabajar.",
            )
    except (ImportError, OSError, ValueError):
        pass

    # ── AP-44: enlaces que resuelven para la tool pero no para el lector ──────
    # El sintoma automatizable de la verificacion autoconsistente. Obsidian
    # resuelve `[[X]]` por nombre de fichero o por `aliases:`, NUNCA por `title:`.
    # Una tool que indexe por titulo da el enlace por bueno y no lo reporta; el
    # usuario abre el vault y ve un enlace muerto. La diferencia entre ambos
    # criterios es exactamente esta lista: enlaces invisibles para el estandar y
    # rotos para quien lee. En BuilderX eran 46.
    #
    # La reparacion correcta es anadir el titulo a `aliases:` en el destino, no
    # reescribir cada punto de llamada: el texto legible del enlace es contenido,
    # y sustituirlo por un slug degrada la nota para arreglar una metrica.
    try:
        _por_nombre: Set[str] = set()
        _por_titulo: Dict[str, str] = {}
        _vivas = [
            p for p in root.rglob("*.md") if not _es_instantanea(p.relative_to(root))
        ]
        for _n in _vivas:
            _por_nombre.add(normalize_stem(_n.stem))
            _fm = _leer_frontmatter(_n) or {}
            _al = _fm.get("aliases") or _fm.get("alias") or []
            if isinstance(_al, str):
                _al = [_al]
            for _a in _al:
                if isinstance(_a, str) and _a.strip():
                    _por_nombre.add(normalize_stem(_a))
            _t = _fm.get("title")
            if isinstance(_t, str) and _t.strip():
                _por_titulo.setdefault(normalize_stem(_t), _n)

        for _n in _vivas:
            try:
                _txt = _n.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            _rel = str(_n.relative_to(root)).replace("\\", "/")
            for _m in re.finditer(r"\[\[([^\]|#]+)", _txt):
                _dest = _m.group(1).strip()
                _clave = normalize_stem(_dest)
                if _clave in _por_nombre or _clave not in _por_titulo:
                    continue
                _destino = str(_por_titulo[_clave].relative_to(root)).replace("\\", "/")
                _flag(
                    "AP-44",
                    _rel,
                    f"[[{_dest}]] solo resuelve por el `title:` de `{_destino}`: "
                    "Obsidian no mira ese campo, asi que el enlace esta roto para "
                    f"quien lee. Anade `{_dest}` a los `aliases:` del destino.",
                )
    except (OSError, ValueError):
        pass

    # ── AP-41: transiciones de estado ya ocurridas ────────────────────────────
    # El guard de vault_write solo puede detener las futuras. Lo ya escrito está
    # en `.history/`: cada versión guardada es el estado anterior de la nota, así
    # que la secuencia de `status` a lo largo del historial es la traza real de
    # la máquina. Se reporta, no se corrige: el estado actual es un hecho y el
    # camino irregular es justamente la información que interesa.
    historia = root / ".history"
    if historia.is_dir():
        # `<carpeta>__<slug>-<YYYY-MM-DDTHH-MM-SS>.md`
        _re_hist = re.compile(r"^(?P<base>.+)-(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})\.md$")
        secuencias: Dict[str, List[Tuple[str, str]]] = {}
        for version in historia.glob("*.md"):
            m = _re_hist.match(version.name)
            if not m:
                continue
            try:
                fm, _ = parse_frontmatter_with_body(version.read_text(encoding="utf-8"))
            except OSError:
                continue
            estado = str((fm or {}).get("status") or "").strip()
            if estado:
                secuencias.setdefault(m.group("base"), []).append((m.group("ts"), estado))

        for base, puntos in sorted(secuencias.items()):
            rel_nota = base.replace("__", "/") + ".md"
            puntos.sort()
            previo = None
            for _ts, estado in puntos:
                canonico, _n, _r = normalize_status(estado)
                if canonico is None:
                    continue  # deuda de vocabulario: la reporta CN-03/AP-38
                if previo and canonico != previo:
                    permitidos = STATUS_TRANSITIONS.get(previo, set())
                    if canonico not in permitidos:
                        _flag(
                            "AP-41",
                            rel_nota,
                            f"Transición ya ocurrida {previo!r} -> {canonico!r} fuera de "
                            f"STATUS_TRANSITIONS (permitidas desde {previo!r}: "
                            f"{sorted(permitidos) or ['ninguna']}). Anterior al guard; "
                            f"se anota, no se reescribe.",
                        )
                previo = canonico

    # ── AP-36: contención e idempotencia ──────────────────────────────────────
    # (a) Artefactos .bak/.tmp dentro de secciones de contenido
    for sec in sorted(canonical_sections):
        sec_path = root / sec
        if not sec_path.is_dir():
            continue
        for artifact in sec_path.rglob("*"):
            if artifact.is_file() and (
                artifact.suffix in (".bak", ".tmp") or artifact.name.startswith(".tmp.")
            ):
                rel_a = str(artifact.relative_to(root)).replace("\\", "/")
                if "/.trash/" in rel_a or "/.history/" in rel_a:
                    continue  # ubicaciones de mantenimiento permitidas
                _flag("AP-36", rel_a, "Artefacto temporal/backup dentro de una sección de contenido.")
        # (b) Toda sección presente debe tener index.md (rastreabilidad de nodos)
        if sec not in ("00_System", "10_Migrated", "99_Index") and not (sec_path / "index.md").exists():
            _flag("AP-36", f"{sec}/", "Sección sin index.md — nodos no indexados (correr vault_section_index).")
        # (b2) index.md con formato legacy: [[stem|alias]] en celdas de tabla
        # (identidad+título fusionados — genera notas en blanco; sanear con --heal)
        for idx in [sec_path / "index.md", *sec_path.glob("*/index.md")]:
            if not idx.exists():
                continue
            try:
                idx_text = idx.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if re.search(r"^\|\s*\[\[[^\]|]+\|[^\]]+\]\]", idx_text, re.MULTILINE):
                rel_i = str(idx.relative_to(root)).replace("\\", "/")
                _flag(
                    "AP-36",
                    rel_i,
                    "Índice con [[stem|alias]] en celdas — formato legacy; correr vault_section_index --heal.",
                )

    # (c) Contaminación externa: artefactos de vault generados FUERA del vault.
    #
    # Hasta v38.1 esto miraba solo root.parent, un único nivel. No bastaba: el
    # patrón legacy Path(__file__).parent.parent.parent (vault_restore) escribe
    # en el ABUELO del directorio de scripts, que en topología spec-repo queda
    # dos niveles por encima del vault. El guard pasaba en verde mientras la
    # carpeta existía. Ahora se recorren _CONTAMINATION_DEPTH niveles.
    seen_contamination: set = set()
    for level in range(1, _CONTAMINATION_DEPTH + 1):
        ancestor = root.parents[level - 1] if len(root.parents) >= level else None
        if ancestor is None:
            break
        for artifact_name in _VAULT_ARTIFACT_NAMES:
            stray = ancestor / artifact_name
            if not stray.exists() or stray == root / artifact_name or stray == root:
                continue
            key = str(stray)
            if key in seen_contamination:
                continue
            seen_contamination.add(key)
            _flag(
                "AP-36",
                f"{'../' * level}{artifact_name}",
                f"'{artifact_name}' existe {level} nivel(es) por encima del vault "
                f"({stray}) — side-effect escrito fuera del vault root.",
            )

    # (d) Vault mal identificado: la raíz del repo usada COMO vault.
    #
    # Cuando _detect_vault_root() no encuentra ningún vault devuelve la raíz del
    # repo. A partir de ahí los artefactos se escriben "dentro del vault" según
    # las tools, pero fuera de todo vault-* en realidad. El audit no podía verlo
    # porque la contaminación cae DENTRO de root: se reportaba como CN-02
    # ("carpeta scripts no es sección canónica"), culpando al repo de no ser un
    # vault en lugar de señalar que el vault fue mal detectado.
    try:
        from vault_io import VAULT_ROOT as _DETECTED_ROOT
        from vault_io import vault_root_origin, vault_root_is_confident

        # Solo aplica cuando se audita el root AUTO-DETECTADO. Con --root
        # explícito el usuario ya declaró cuál es el vault y la confianza de la
        # detección no dice nada sobre él.
        audits_detected_root = root.resolve() == _DETECTED_ROOT.resolve()
        if audits_detected_root and not vault_root_is_confident():
            _flag(
                "AP-36",
                ".",
                f"vault root detectado por '{vault_root_origin()}': no se encontró ningún "
                f"vault y se está usando {root} como si lo fuera. Los artefactos caerían "
                "fuera de todo vault-*. Crea 'vault-<nombre>/' o exporta VAULT_ROOT.",
            )
    except ImportError:
        pass

    # ── AP-10: migración sin plan de rollback ─────────────────────────────────
    migrated = root / "10_Migrated"
    if migrated.exists():
        # El andamiaje de la sección no es contenido migrado: los `index.md` los
        # genera `vault_reindex` en cada subcarpeta y los primers los crea
        # `vault_init`. Contándolos, una sección vacía recién inicializada ya
        # exigía un mapa de rollback de una migración que nunca ocurrió — en
        # BuilderX eran 6 de las 7 "notas migradas". Un rollback de un `index.md`
        # generado no significa nada.
        migrated_notes = [
            p
            for p in migrated.rglob("*.md")
            if not p.name.startswith("_report-")
            and p.stem != "index"
            and not _ES_PRIMER.match(p.stem)
        ]
        reports = list(migrated.glob("_report-*.md"))
        if migrated_notes and not reports:
            _flag(
                "AP-10",
                "10_Migrated/",
                f"{len(migrated_notes)} notas migradas sin _report-*.md (mapa de rollback para vault_migrate_rollback).",
            )

    # ── SP-01: eliminaciones sin change_log ───────────────────────────────────
    graph_file = root / "99_Index" / "graph.json"
    change_log = root / "00_System" / ".change-log.json"
    if graph_file.exists():
        try:
            graph = json.loads(graph_file.read_text(encoding="utf-8"))
            deleted = [e.get("from", "") for e in graph.get("edges", []) if e.get("to") == "__deleted__"]
            if deleted:
                logged: set = set()
                if change_log.exists():
                    try:
                        logged = {
                            str(e.get("path", "")) for e in json.loads(change_log.read_text(encoding="utf-8"))
                        }
                    except (json.JSONDecodeError, TypeError):
                        pass
                for d in deleted:
                    if d not in logged:
                        _flag("SP-01", d, "Nota eliminada sin entrada en change_log (delete protocol).")
        except (json.JSONDecodeError, OSError):
            pass

    by_norm: Dict[str, int] = {}
    for v in violations:
        by_norm[v["norm"]] = by_norm.get(v["norm"], 0) + 1

    return {
        "ok": True,
        "tool": "vault_norms.audit",
        "vault_root": str(root),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes_scanned": len(notes),
        "total_violations": len(violations),
        "by_norm": by_norm,
        "violations": violations,
    }


# ─── Guard anti-drift del marco de datos (v39) ─────────────────────────────────


def framework_drift_check(spec_path: Optional[Path] = None) -> Dict[str, Any]:
    """Verifica que el manifiesto documente todos los ids del marco de datos.

    El fallo de la Era 4 fue documentar sin ejecutar. Aquí es al revés: el
    registro canónico vive en ``vault_fundamentals`` y este guard falla si el
    manifiesto público se desincroniza de él — en cualquiera de las dos
    direcciones (id registrado que el doc no explica, o id citado en el doc
    que ya no existe en el registro).
    """
    from vault_fundamentals import FRAMEWORK_REGISTRIES

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


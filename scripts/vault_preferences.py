#!/usr/bin/env python3
"""
vault_preferences.py — Preferencias del usuario como contexto estable.

Cierra el hueco `preferences/` del modelo de memoria unificada: el vault sabía
qué se decidió (03_Decisions), qué se aprendió (07_Knowledge) y qué pasó
(04_Sessions), pero no CÓMO quiere trabajar el usuario. Sin eso el agente
vuelve a preguntar lo mismo cada sesión, o peor, actúa contra una preferencia
ya expresada.

Una preferencia NO es conocimiento del dominio:
  - se revoca, no se corrige (por eso `status: revoked`, no borrado — AP-32);
  - tiene fuerza declarada (`must` / `should` / `may`), y el agente debe poder
    distinguir una restricción dura de una inclinación;
  - se carga entera al inicio de sesión, no se busca por relevancia.

Usage:
    python vault_preferences.py --set --category workflow \\
        --title "Confirmar antes de commitear" \\
        --statement "No hagas commit ni push salvo petición explícita" \\
        --strength must --rationale "Reviso siempre el diff antes de publicar"

    python vault_preferences.py --list
    python vault_preferences.py --list --category constraints --strength must
    python vault_preferences.py --context            # bloque listo para inyectar
    python vault_preferences.py --revoke "17_Preferences/workflow/confirmar-antes-de-commitear.md" \\
        --reason "El usuario habilitó auto-commit en CI"
"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vault_errors import emit_error, wrap_main
from vault_norms_catalog import status_frontmatter_lines
from vault_io import (
    write_report,
    assert_within_vault,
    atomic_write_text,
    tomar_lock,
    update_section_index,
)
from vault_lib import separar_frontmatter, slugify, utcnow



sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# La configuración se lee del registro único, no con un default por punto
# de uso. Ver `vault_entorno.py`.
from vault_entorno import leer as _env
from vault.kernel.safety import scan_poison  # noqa: E402

#: Lo que espera una escritura a que otra suelte la nota (igual que vault_write).
_LOCK_TIMEOUT = 10.0

from vault.consulta.repositorio import RepositorioConsulta  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402
from vault.kernel.escritura import apartar_ilegible  # noqa: E402
from vault.kernel.frontmatter_parsing import parse_frontmatter_robust  # noqa: E402
from vault.kernel.indices_structural import describir_reserva, es_nombre_reservado  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioConsulta:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioConsulta(construir(root))


def _preferences_dir() -> Path:
    return _repo().dir_preferencias

# Categorías = subcarpetas registradas en vault_registry.SUBFOLDERS.
# No se declaran aquí dos veces: se derivan del registro para que añadir una
# subcarpeta sea un cambio en un solo sitio (regla de fuente única).
CATEGORIES: List[str] = ["workflow", "style", "tooling", "constraints", "domain"]

# Fuerza normativa, en el sentido de RFC 2119. Es el campo que permite al
# agente distinguir "no toques esto" de "prefiero tabs".
STRENGTHS: List[str] = ["must", "should", "may"]

STRENGTH_WEIGHT: Dict[str, int] = {"must": 3, "should": 2, "may": 1}

# Vocabulario de dominio de las preferencias. NO son valores de STATUS_VOCAB, y
# el comentario anterior afirmaba que sí: una preferencia se revoca, no se
# deprecia, y esa diferencia importa aquí. Viven en `preference_state`; el
# `status` canónico se deriva vía vault_norms.DOMAIN_STATUS_VOCABS (AP-38).
STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"


def _registry_categories() -> List[str]:
    """Categorías válidas según el registro canónico de subcarpetas."""
    try:
        from vault_registry import SUBFOLDERS

        found = [
            key.split("/", 1)[1]
            for key in SUBFOLDERS
            if key.startswith("17_Preferences/")
        ]
        return sorted(found) or CATEGORIES
    except Exception:
        return CATEGORIES


def _preference_files() -> List[Path]:
    if not _preferences_dir().is_dir():
        return []
    return sorted(
        p for p in _preferences_dir().rglob("*.md") if p.name.lower() != "index.md"
    )


def _load_preference(path: Path) -> Optional[Dict[str, Any]]:
    """La preferencia, o None si no lo es o no se pudo leer (ver `_leer_preferencia`)."""
    return _leer_preferencia(path)[0]


def _leer_preferencia(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """La preferencia y, si el fichero no se pudo leer, el motivo.

    Auditoría del 2026-10-15: un YAML roto salía `{}` de `vault_lib`, sin
    `type: preference`, y la nota se descartaba como si no fuera una
    preferencia; un `must` desaparecía del contexto del agente sin aviso.
    """
    # AP-51: «ilegible» y «no es una preferencia» no son el mismo vacío.
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"no se pudo leer: {type(exc).__name__}"
    fm, body, legible, error = parse_frontmatter_robust(raw)
    if not legible:
        return None, f"frontmatter ilegible: {error}"
    if fm.get("type") != "preference":
        return None, None
    rel = path.relative_to(_raiz()).as_posix()
    return {
        "path": rel,
        "title": fm.get("title", path.stem),
        "category": fm.get("category", path.parent.name),
        "strength": str(fm.get("strength", "should")).lower(),
        # El estado de dominio manda; `status` es su proyección canónica. El
        # fallback a `status` sostiene las notas escritas antes de AP-38, que
        # llevan el valor de dominio en el campo canónico.
        "status": str(
            fm.get("preference_state") or fm.get("status") or STATUS_ACTIVE
        ).lower(),
        "statement": fm.get("statement", "").strip(),
        "scope": fm.get("scope", "global"),
        "createdAt": fm.get("createdAt", ""),
        "updatedAt": fm.get("updatedAt", ""),
        "revoked_reason": fm.get("revoked_reason", ""),
        "body": body.strip(),
    }, None


def vault_preferences_set(
    category: str,
    title: str,
    statement: str,
    strength: str = "should",
    rationale: Optional[str] = None,
    scope: str = "global",
    tags: Optional[List[str]] = None,
    agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Registra o actualiza una preferencia.

    Es idempotente por (categoría, título): reescribir la misma preferencia
    actualiza el enunciado y conserva `createdAt`. Una preferencia contradicha
    se reemplaza; una que deja de aplicar se revoca (AP-32, no-derogación).
    """
    category = (category or "").lower().strip()
    valid = _registry_categories()
    if category not in valid:
        return {
            "ok": False,
            "error_code": "INVALID_CATEGORY",
            "error": f"Categoría inválida: '{category}'. Válidas: {valid}",
        }

    strength = (strength or "should").lower().strip()
    if strength not in STRENGTHS:
        return {
            "ok": False,
            "error_code": "INVALID_STRENGTH",
            "error": f"Fuerza inválida: '{strength}'. Válidas: {STRENGTHS}",
        }

    statement = (statement or "").strip()
    if not statement:
        return {
            "ok": False,
            "error_code": "EMPTY_STATEMENT",
            "error": "El enunciado de la preferencia no puede estar vacío",
        }

    # Fase H (C5): las preferencias `must` entran primero al paquete de contexto,
    # por lo que el pre-vuelo anti-poison aquí es obligatorio y no desactivable.
    hallazgos_poison = (
        scan_poison(title or "", "preferences:title")
        + scan_poison(statement, "preferences:statement")
        + scan_poison(rationale or "", "preferences:rationale")
    )
    bloqueantes_poison = [f for f in hallazgos_poison if f.severity in ("critical", "high")]
    if bloqueantes_poison:
        return {
            **emit_error(
                "vault_preferences", "POISON_DETECTED",
                f"Contenido bloqueado por pre-vuelo anti-poison: {bloqueantes_poison[0].detail}",
            ),
            "findings": [f.to_dict() for f in bloqueantes_poison],
        }

    # AP-16: atribución obligatoria. La preferencia dirige el comportamiento
    # del agente; saber quién la registró no es opcional.
    agent = agent or _env("VAULT_AGENT")
    if not agent:
        return {
            "ok": False,
            "error_code": "missing_agent",
            "norm_code": "AP-16",
            "error": "missing_agent",
            "message": (
                "AP-16: se requiere atribución de agente. Usa --agent <nombre> "
                "o exporta VAULT_AGENT."
            ),
        }

    folder = _preferences_dir() / category
    note_path = folder / f"{slugify(title)}.md"
    # El index.md de la carpeta es del generador: una preferencia con ese
    # nombre la pisaría la siguiente regeneración (mismo dueño que vault_write).
    if es_nombre_reservado(note_path.name):
        return {
            **emit_error(
                "vault_preferences", "RESERVED_NAME",
                f"El título '{title}' produce '{note_path.name}': "
                f"{describir_reserva(note_path.name)}. Usar otro título.",
            ),
            "error": "RESERVED_NAME",
        }

    try:
        assert_within_vault(note_path, _raiz())
    except ValueError as exc:
        return {"ok": False, "error_code": "INVALID_PATH", "error": str(exc)}

    # createdAt se lee de la versión previa y se escribe en la nueva: las dos
    # cosas bajo el mismo lock, o un revoke concurrente se pierde.
    lock = tomar_lock(note_path, _LOCK_TIMEOUT)
    if lock is None:
        return emit_error("vault_preferences", "NOTE_LOCKED", f"Preferencia bloqueada: {note_path.name}")
    with lock:
        timestamp = utcnow()
        created = timestamp
        previous = None
        previa_ilegible = None
        if note_path.exists():
            previous, motivo = _leer_preferencia(note_path)
            # AP-51: «no había» y «no se lee» no son el mismo `None`; la rota
            # se aparta entera antes de escribir encima, como un registro.
            if motivo:
                apartada = apartar_ilegible(note_path)
                previa_ilegible = {
                    "error": motivo,
                    "set_aside": apartada.relative_to(_raiz()).as_posix(),
                }
            if previous:
                created = previous.get("createdAt") or timestamp

        # AP-26: toda nota de contenido lleva tags. La categoría y la fuerza son
        # tags implícitos y siempre presentes, así que la norma se cumple sola.
        all_tags = sorted({"preference", category, strength, *(tags or [])})

        # AP-46: el bloque lo escribe su dueño; aquí solo se declaran los campos.
        frontmatter = [
            Frontmatter()
            .set("title", title, texto=True)
            .set("id", str(uuid.uuid4()))
            .set("type", "preference")
            .set("category", category, texto=True)
            .set("strength", strength)
            .lineas(status_frontmatter_lines("vault_preferences", STATUS_ACTIVE))
            .set("scope", scope, texto=True)
            .set("statement", statement, texto=True)
            .set("tags", all_tags)
            # Citados a propósito (`texto=True`): sin comillas, YAML los convierte
            # en datetime y la reescritura de --revoke los devuelve con otro formato.
            .set("createdAt", str(created), texto=True)
            .set("updatedAt", timestamp, texto=True)
            # Una preferencia es integridad alta por definición: si se corrompe o
            # se pierde, el agente actúa contra la voluntad del usuario.
            .set("cia_integrity", "high")
            .set("cia_availability", "high")
            .set("cia_sensitivity", "internal")
            .set("agent", agent)
            .render()
        ]

        body = [f"# {title}", "", f"> **{strength.upper()}** — {statement}", ""]
        if rationale:
            body += ["## Por qué", "", rationale.strip(), ""]
        body += [
            "## Alcance",
            "",
            f"- Categoría: `{category}`",
            f"- Ámbito: `{scope}`",
            f"- Fuerza: `{strength}`",
            "",
        ]

        folder.mkdir(parents=True, exist_ok=True)
        atomic_write_text(note_path, "\n".join(frontmatter) + "\n\n" + "\n".join(body))
    update_section_index("17_Preferences")

    return {
        "ok": True,
        **write_report(),
        "action": "updated" if previous else "created",
        "path": note_path.relative_to(_raiz()).as_posix(),
        "category": category,
        "strength": strength,
        "statement": statement,
        "previous_statement": (previous or {}).get("statement") if previous else None,
        **({"previous_unreadable": previa_ilegible} if previa_ilegible else {}),
    }


def vault_preferences_list(
    category: Optional[str] = None,
    strength: Optional[str] = None,
    scope: Optional[str] = None,
    include_revoked: bool = False,
) -> Dict[str, Any]:
    """Lista las preferencias registradas, ordenadas por fuerza."""
    items: List[Dict[str, Any]] = []
    unreadable: List[Dict[str, str]] = []
    for path in _preference_files():
        pref, motivo = _leer_preferencia(path)
        if motivo:
            unreadable.append({"path": path.relative_to(_raiz()).as_posix(), "error": motivo})
        if pref is None:
            continue
        if not include_revoked and pref["status"] == STATUS_REVOKED:
            continue
        if category and pref["category"] != category.lower():
            continue
        if strength and pref["strength"] != strength.lower():
            continue
        if scope and pref["scope"] != scope:
            continue
        items.append({k: v for k, v in pref.items() if k != "body"})

    items.sort(
        key=lambda p: (-STRENGTH_WEIGHT.get(p["strength"], 0), p["category"], p["title"])
    )

    by_strength: Dict[str, int] = {}
    for item in items:
        by_strength[item["strength"]] = by_strength.get(item["strength"], 0) + 1

    return {
        "ok": True,
        **write_report(),
        "total": len(items),
        "by_strength": by_strength,
        "preferences": items,
        "unreadable": unreadable,
        "hint": "vault_preferences --context para el bloque inyectable",
    }


def vault_preferences_context(max_items: int = 40) -> Dict[str, Any]:
    """Bloque markdown listo para inyectar en el contexto del agente.

    Es la razón de ser de la tool: las preferencias no se buscan por
    relevancia, se cargan enteras. Se ordenan por fuerza para que, si algo se
    trunca por presupuesto, lo primero que sobrevive sea lo obligatorio.
    """
    listing = vault_preferences_list()
    items = listing["preferences"][:max_items]

    lines = ["## Preferencias del usuario", ""]
    for level in STRENGTHS:
        group = [p for p in items if p["strength"] == level]
        if not group:
            continue
        lines.append(f"### {level.upper()}")
        lines.append("")
        for pref in group:
            lines.append(f"- **{pref['title']}** ({pref['category']}): {pref['statement']}")
        lines.append("")

    text = "\n".join(lines).rstrip() + "\n" if items else ""

    return {
        "ok": True,
        **write_report(),
        "total": len(items),
        "truncated": listing["total"] > len(items),
        "context": text,
        "chars": len(text),
    }


def vault_preferences_revoke(path: str, reason: str,
                             agent: Optional[str] = None) -> Dict[str, Any]:
    """Revoca una preferencia sin borrarla.

    No-derogación aplicada al contenido del vault: la preferencia queda con
    `status: revoked` y el motivo. Borrarla destruiría la explicación de por
    qué el agente se comportaba de otra forma en sesiones anteriores.
    """
    agent = agent or _env("VAULT_AGENT")
    if not agent:
        return {
            "ok": False,
            "error_code": "missing_agent",
            "norm_code": "AP-16",
            "error": "missing_agent",
            "message": "AP-16: usa --agent <nombre> o exporta VAULT_AGENT.",
        }

    reason = (reason or "").strip()
    if not reason:
        return {
            "ok": False,
            "error_code": "EMPTY_REASON",
            "error": "Revocar exige un motivo: es lo único que explica el cambio de conducta",
        }

    note_path = (_raiz() / path).resolve()
    try:
        assert_within_vault(note_path, _raiz())
    except ValueError as exc:
        return {"ok": False, "error_code": "INVALID_PATH", "error": str(exc)}

    if not note_path.is_file():
        return {"ok": False, "error_code": "PREFERENCE_NOT_FOUND", "error": f"No existe: {path}"}

    # Leer y reescribir bajo el lock de la nota (el mismo de vault_write):
    # sin él, un --set concurrente se perdía bajo la reescritura del revoke.
    lock = tomar_lock(note_path, _LOCK_TIMEOUT)
    if lock is None:
        return emit_error("vault_preferences", "NOTE_LOCKED", f"Preferencia bloqueada: {note_path.name}")
    with lock:
        pref = _load_preference(note_path)
        if pref is None:
            return {
                "ok": False,
                "error_code": "NOT_A_PREFERENCE",
                "error": f"'{path}' no es una nota de preferencia (falta type: preference)",
            }
        if pref["status"] == STATUS_REVOKED:
            return {"ok": True, "action": "noop", "path": pref["path"],
                    "message": "Ya estaba revocada"}

        raw = note_path.read_text(encoding="utf-8")
        bloque, body = separar_frontmatter(raw)
        revoked_at = utcnow()
        # AP-46: el dueño reescribe solo los campos que cambian. Antes se
        # volvía a serializar el dict entero a mano, y lo que no era texto,
        # lista ni dict salía con `str()`: un campo nulo volvía como la
        # cadena "None". Los instantes van citados, como al crear la nota.
        fm = (
            Frontmatter.editar(bloque or "")
            .set("status", "deprecated")
            .set("preference_state", STATUS_REVOKED)
            .set("revoked_reason", reason, texto=True)
            .set("revoked_at", revoked_at, texto=True)
            .set("revoked_by", agent, texto=True)
            .set("updatedAt", revoked_at, texto=True)
        )

        note = fm.render() + "\n\n" + body.strip() + (
            f"\n\n> **Revocada** el {revoked_at} por `{agent}`: {reason}\n"
        )
        atomic_write_text(note_path, note)
    update_section_index("17_Preferences")

    return {
        "ok": True,
        **write_report(),
        "action": "revoked",
        "path": pref["path"],
        "reason": reason,
        "statement": pref["statement"],
    }


#: Los ficheros que cada cliente lee como instrucciones de proyecto. La lista
#: es **deliberadamente corta**: es la que la propuesta
#: `multi-provider-vault-policy-adapters` documenta con su fuente; un cliente
#: que no esté aquí no se inventa.
ADAPTADORES = {
    "AGENTS.md": "Codex y OpenCode",
    "CLAUDE.md": "Claude Code",
    "GEMINI.md": "Gemini CLI",
    ".github/copilot-instructions.md": "GitHub Copilot",
}


#: Karpathy's schema layer is a file the agent reads on every task: a long one
#: is skimmed, so it carries a budget. The preferences block is the part that
#: grows with the vault and is the part that is cut, pointing at the full list.
LINEAS_MAXIMAS_ADAPTER = 120


def _mapa_de_carpetas() -> list:
    """The folder map, derived from `vault_registry.SECTION_DOCUMENTACION`."""
    from vault_registry import SECTION_DOCUMENTACION

    lineas = ["## Mapa de carpetas", ""]
    lineas += [f"- `{carpeta}` — {clase}: {motivo}"
               for carpeta, (clase, motivo) in SECTION_DOCUMENTACION.items()]
    return lineas + [""]


def _regla_de_nombres() -> list:
    """CN-01 as the norm catalog states it, not a paraphrase."""
    from vault_norms_catalog import norma_por_codigo

    cn01 = norma_por_codigo("CN-01") or {}
    if not cn01:
        return []
    return ["## Nombres de fichero (CN-01)", "",
            f"- {cn01.get('name', '')}", f"- {cn01.get('prevention', '')}", ""]


def _protocolo_de_sesion() -> list:
    """The session protocol steps, from `PROTOCOLO_DE_SESION` (kernel leaf).

    One line per step: the call and what it is for. A step that applies only
    in some sessions says when, because a client that runs it always would
    hit errors it cannot recover from (`DRIFT_SNAPSHOT_MISSING`).
    """
    from vault.kernel.protocolo_de_sesion import PROTOCOLO_DE_SESION

    lineas = ["## Protocolo de sesión", ""]
    for momento in PROTOCOLO_DE_SESION.values():
        lineas.append(f"**{momento['titulo']}**")
        for paso in momento["pasos"]:
            llamada = f"{paso['tool']} {paso['uso']}".strip()
            cuando = f" (solo si {paso['cuando']})" if paso.get("cuando") else ""
            lineas.append(f"- `{llamada}`: {paso['para']}{cuando}")
    return lineas + [""]


def _decisiones() -> list:
    """Where decisions live and how they change, from the registry and AP-07/AP-64.

    Torti Code (phase 4): an agent reads the decisions before changing what
    they explain, writes a new one as a draft, and supersedes a closed one
    instead of rewriting it.
    """
    from vault.kernel.contenido import CARPETA_DECISIONES
    from vault_registry import SECTION_DOCUMENTACION

    _, motivo = SECTION_DOCUMENTACION[CARPETA_DECISIONES]
    return ["## Decisiones", "",
            f"- Leer `{CARPETA_DECISIONES}/` antes de cambiar lo que una decisión explica "
            f"({motivo}).",
            "- Una decisión nueva: `vault_write --adr` (nace en `draft`, con Contexto, "
            "Decisión y Consecuencias).",
            "- Una decisión cerrada no se reescribe: se escribe la sucesora y se enlaza "
            "con `vault_supersede`.",
            ""]


def _comandos_de_prueba(comandos: list) -> list:
    """The test commands the owner declares in `reglas.json`; nothing is invented."""
    if not comandos:
        return []
    return (["## Comando de pruebas", ""]
            + [f"- `{c}` (declarado en `00_System/reglas.json`)" for c in comandos] + [""])


def _cuerpo_adapter(cliente: str, contexto: dict, reglas: dict) -> str:
    """La política del vault, para un cliente que lea instrucciones de proyecto.

    **Entrega, no enforcing.** Este fichero es una instrucción; la frontera de
    permisos es la del backend (`vault_write`, `vault_delete`). Un agente que
    no cargue el fichero sigue sujeto a la misma política, porque la política
    se aplica donde se muta.
    """
    lineas = [
        "<!-- Generado por vault_preferences --adapters. Entrega, no enforcing. -->",
        "",
        f"# Política del vault (adaptador para {cliente})",
        "",
        "> Este fichero es **entrega**, no enforcing: una instrucción que el "
        "cliente",
        "> puede cargar. La política se aplica en la frontera de mutación del "
        "vault",
        "> (`vault_write` / `vault_delete`), no aquí. Si este cliente no carga "
        "el",
        "> fichero, la política sigue vigente.",
        "",
    ]
    inmutables = reglas.get("inmutable") or []
    no_borrar = reglas.get("no_borrar") or []
    if inmutables or no_borrar:
        lineas += ["## Reglas de mutación", ""]
        if inmutables:
            lineas.append("- Secciones **inmutables** (no se reescriben; se "
                          "continúa con una sucesora): "
                          + ", ".join(f"`{s}`" for s in inmutables))
        if no_borrar:
            lineas.append("- Secciones donde **no se borra**: "
                          + ", ".join(f"`{s}`" for s in no_borrar))
        lineas.append("")
    lineas += _mapa_de_carpetas() + _regla_de_nombres() + _decisiones()
    lineas += _comandos_de_prueba(reglas.get("comandos_de_prueba") or [])
    nivel_xp = reglas.get("xp_level")
    if nivel_xp:
        lineas += [
            "## Augmented Coding (SP-06)",
            f"- Nivel XP activo: `{nivel_xp}` (`00_System/reglas.json`): TDD Rojo->Verde->Refactor, iteraciones pequeñas y revisión humana.",
            "",
        ]
    lineas += _protocolo_de_sesion()
    lineas += [
        "## Grafo primero (ahorro de contexto)",
        "- Antes de lanzar búsquedas amplias (`grep`/`Glob`), consulta `vault_subgraph --report`, `--explain <nota>`, `--path <A> <B>` o `vault_context_pack`.",
        "",
    ]
    cola = [
        "",
        "## Dónde vive la política",
        "",
        "- Las preferencias, en `17_Preferences/` del vault (las escribe el "
        "dueño; se revocan, no se borran).",
        "- La inmutabilidad, en `00_System/inmutable.json`; el resto de reglas "
        "de mutación, en `00_System/reglas.json`.",
        f"- Este fichero no pasa de {LINEAS_MAXIMAS_ADAPTER} líneas; lo que no "
        "cabe se lee con `vault_preferences --context`.",
    ]
    lineas += ["## Preferencias del propietario", ""]
    bloque = (contexto.get("context") or contexto.get("block") or "").strip()
    preferencias = bloque.splitlines() or ["(sin preferencias registradas)"]
    hueco = LINEAS_MAXIMAS_ADAPTER - len(lineas) - len(cola)
    if len(preferencias) > hueco:
        resto = len(preferencias) - (hueco - 1)
        preferencias = preferencias[:max(hueco - 1, 0)] + [
            f"(… {resto} líneas más: `vault_preferences --context`)"]
    return "\n".join(lineas + preferencias + cola) + "\n"


def _escribir_adapter(ruta, texto: str, force: bool) -> bool:
    """Write one client adapter; False when an existing file is preserved.

    Both paths go through the canonical atomic writer with the secret guard:
    the adapter embeds vault preferences, which may carry a credential.
    Without `force` the finished temporary file is published with a hard link,
    which fails if anything (a file, a dangling symlink) already holds the
    name, so an `exists()` check cannot race another writer. With `force` the
    replacement is atomic: a reader sees the old or the new file.
    """
    import contextlib
    import uuid as _uuid
    from vault.kernel.escritura import escritura_atomica
    from vault.kernel.fs import guarda_secretos

    if force:
        escritura_atomica(ruta, texto, guardas=(guarda_secretos,))
        return True
    if os.path.lexists(ruta):
        return False
    temporal = ruta.with_name(f".{ruta.name}.{_uuid.uuid4().hex[:8]}.adapter")
    try:
        escritura_atomica(temporal, texto, guardas=(guarda_secretos,))
        try:
            os.link(temporal, ruta)
        except FileExistsError:
            return False
        except OSError:
            # Sistemas de ficheros sin hard links (FAT32, exFAT, algunos mounts):
            # creación exclusiva atómica sin sobrescribir ficheros existentes.
            try:
                fd = os.open(str(ruta), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
            except FileExistsError:
                return False
            try:
                datos = temporal.read_bytes()
                os.write(fd, datos)
                os.fsync(fd)
            finally:
                os.close(fd)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(temporal)
    return True


def vault_preferences_adapters(destino: str, force: bool = False) -> dict:
    """Renderiza la política del vault en los ficheros que leen los clientes.

    `destino` es la carpeta del proyecto donde viven esos ficheros; el dueño
    la elige. **No se pisa un fichero que ya exista** sin `force`: el
    `AGENTS.md` de un proyecto puede ser suyo, y sobrescribirlo es decidir por
    él.
    """
    from pathlib import Path as _Path

    raw_dest = str(destino or "").strip()
    if not raw_dest or ".." in _Path(raw_dest).parts:
        return emit_error(
            "vault_preferences", "INVALID_PATH",
            f"Destino de adaptadores inválido o con traversal '..': {destino!r}",
        )
    base = _Path(raw_dest).resolve()
    if base.exists() and not base.is_dir():
        return emit_error(
            "vault_preferences", "INVALID_PATH",
            f"El destino de adaptadores no es un directorio: {base}",
        )
    # Fase H (C7): bloquear escritura de adaptadores sobre raíces críticas del SO.
    partes_lower = tuple(p.lower() for p in base.parts)
    if (
        len(base.parts) <= 1
        or (len(partes_lower) >= 2 and partes_lower[1] in ("windows", "system32", "etc", "usr", "bin", "sbin", "boot"))
    ):
        return emit_error(
            "vault_preferences", "INVALID_PATH",
            f"Destino de adaptadores rechazado por seguridad (ruta de sistema): {base}",
        )
    try:
        contexto = vault_preferences_context(max_items=40)
    except Exception as exc:  # AP-51: se dice por qué, no se devuelve vacío
        return emit_error("vault_preferences", "PREFERENCES_UNREADABLE",
                          f"no se pudo leer el contexto: {exc}")
    try:
        from vault_io import comandos_de_prueba_declarados, reglas_declaradas, xp_level_declarado

        reglas = {
            **reglas_declaradas(),
            "comandos_de_prueba": comandos_de_prueba_declarados(),
            "xp_level": xp_level_declarado(),
        }
    except Exception:
        return emit_error("vault_preferences", "INVALID_INPUT",
                          "No se pudieron verificar las reglas del vault; no se generaron adaptadores.")
    # PAT-9: the schema the agent reads on every task has a line budget, and
    # an adapter that would exceed it is not written at all. Only the owner's
    # preferences are cut to fit; when the derived part alone is over budget
    # the schema is wrong, and writing it anyway would publish a file the
    # agent skims. Checked for every client before writing any of them.
    cuerpos = {nombre: _cuerpo_adapter(cliente, contexto, reglas)
               for nombre, cliente in ADAPTADORES.items()}
    excedidos = {nombre: len(texto.splitlines()) for nombre, texto in cuerpos.items()
                 if len(texto.splitlines()) > LINEAS_MAXIMAS_ADAPTER}
    if excedidos:
        nombre, lineas = next(iter(excedidos.items()))
        return emit_error(
            "vault_preferences", "VALIDATION_FAILED",
            f"PAT-9: el adaptador {nombre} tendría {lineas} líneas y el presupuesto es "
            f"{LINEAS_MAXIMAS_ADAPTER}; no se escribió ninguno.",
            pista=("La parte derivada (mapa, protocolo, decisiones) no cabe: acortar el "
                   "registro que la produce, no el presupuesto."))
    filas = []
    for nombre, cliente in ADAPTADORES.items():
        ruta = base / nombre
        try:
            escrito = _escribir_adapter(ruta, cuerpos[nombre], force)
        except OSError as exc:
            # Earlier adapters may already be written: say which, never ok.
            from vault.kernel.fs import SecretoDetectado

            codigo = "SECRET_DETECTED" if isinstance(exc, SecretoDetectado) else "FILE_WRITE_ERROR"
            error = emit_error("vault_preferences", codigo,
                               f"No se pudo escribir el adaptador {nombre}: {type(exc).__name__}")
            error["adapters"] = filas + [{"adapter": nombre, "estado": "no escrito"}]
            return error
        filas.append({"adapter": nombre,
                      "estado": "escrito" if escrito else "existente (no se toca)"})
    return {
        "ok": True,
        "tool": "vault_preferences",
        "action": "adapters",
        "path": str(base),
        "adapters": filas,
        "entrega_no_enforcing": (
            "estos ficheros son instrucciones que un cliente puede cargar; la "
            "política se aplica en la frontera de mutación del vault, no aquí"
        ),
    }

def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_preferences — preferencias del usuario como contexto estable",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Registrar una restriccion dura
  python vault_preferences.py --set --category constraints \\
      --title "No mover tools entre repos" \\
      --statement "No propagar scripts a otros repos salvo peticion explicita" \\
      --strength must

  # Listar solo lo obligatorio
  python vault_preferences.py --list --strength must

  # Bloque inyectable al inicio de sesion
  python vault_preferences.py --context

  # Revocar sin borrar (no-derogacion)
  python vault_preferences.py --revoke "17_Preferences/style/tabs.md" \\
      --reason "El proyecto migro a prettier"

Notas:
  - Categorias derivadas de vault_registry.SUBFOLDERS (17_Preferences/*)
  - strength: must | should | may  (fuerza normativa, estilo RFC 2119)
  - AP-16: requiere --agent o VAULT_AGENT
  - Revocar NO borra: marca status: revoked conservando el historico
""",
        allow_abbrev=False,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--set", action="store_true", help="Registra o actualiza")
    mode.add_argument("--list", action="store_true", help="Lista preferencias")
    mode.add_argument("--context", action="store_true", help="Bloque inyectable")
    mode.add_argument("--revoke", metavar="PATH", help="Revoca la preferencia dada")
    mode.add_argument("--adapters", metavar="DIR",
                      help="Renderiza la politica para los clientes que leen "
                           "instrucciones (AGENTS.md, CLAUDE.md, GEMINI.md, "
                           "copilot-instructions.md) en DIR")

    parser.add_argument("--category", help=f"Categoría: {CATEGORIES}")
    parser.add_argument("--title", help="Título de la preferencia")
    parser.add_argument("--statement", help="Enunciado: qué debe hacer el agente")
    # Sin default: en --set significa "should", pero en --list un default
    # convertiría un listado completo en un filtro silencioso por 'should'.
    parser.add_argument("--strength", default=None, choices=STRENGTHS)
    parser.add_argument("--rationale", help="Por qué el usuario lo quiere así")
    parser.add_argument("--scope", default="global",
                        help="Ámbito: 'global' o un slug de proyecto")
    parser.add_argument("--tags", nargs="*", help="Tags adicionales")
    parser.add_argument("--reason", help="Motivo de la revocación")
    parser.add_argument("--include-revoked", action="store_true",
                        help="Incluye las revocadas en --list")
    parser.add_argument("--max-items", type=int, default=40,
                        help="Máximo de preferencias en --context (default: 40)")
    parser.add_argument("--force", action="store_true",
                        help="Con --adapters: sobrescribe un fichero existente")
    parser.add_argument("--agent", help="Agente que ejecuta (AP-16)")

    args = parser.parse_args()

    if args.set:
        missing = [f for f in ("category", "title", "statement")
                   if not getattr(args, f)]
        if missing:
            parser.error(f"--set requiere: {', '.join('--' + m for m in missing)}")
        result = vault_preferences_set(
            category=args.category, title=args.title, statement=args.statement,
            strength=args.strength or "should",
            rationale=args.rationale, scope=args.scope,
            tags=args.tags, agent=args.agent,
        )
    elif args.list:
        result = vault_preferences_list(
            category=args.category, strength=args.strength, scope=args.scope,
            include_revoked=args.include_revoked,
        )
    elif args.context:
        result = vault_preferences_context(max_items=args.max_items)
    elif args.adapters:
        result = vault_preferences_adapters(args.adapters, force=args.force)
    else:
        if not args.reason:
            parser.error("--revoke requiere --reason")
        result = vault_preferences_revoke(args.revoke, args.reason, agent=args.agent)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_preferences"))

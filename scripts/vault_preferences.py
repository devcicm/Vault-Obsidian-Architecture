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
from typing import Any, Dict, List, Optional

from vault_errors import wrap_main
from vault_norms import status_frontmatter_lines
from vault_io import (
    write_report,
    assert_within_vault,
    atomic_write_text,
    update_section_index,
)
from vault_lib import yaml_scalar, parse_frontmatter_with_body, slugify, utcnow



sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# La configuración se lee del registro único, no con un default por punto
# de uso. Ver `vault_entorno.py`.
from vault_entorno import leer as _env

from vault.consulta.repositorio import RepositorioConsulta  # noqa: E402
from vault.kernel import construir  # noqa: E402


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
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    fm, body = parse_frontmatter_with_body(raw)
    if fm.get("type") != "preference":
        return None
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
    }


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

    try:
        assert_within_vault(note_path, _raiz())
    except ValueError as exc:
        return {"ok": False, "error_code": "INVALID_PATH", "error": str(exc)}

    timestamp = utcnow()
    created = timestamp
    previous = None
    if note_path.exists():
        previous = _load_preference(note_path)
        if previous:
            created = previous.get("createdAt") or timestamp

    # AP-26: toda nota de contenido lleva tags. La categoría y la fuerza son
    # tags implícitos y siempre presentes, así que la norma se cumple sola.
    all_tags = sorted({"preference", category, strength, *(tags or [])})

    frontmatter = [
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"id: {uuid.uuid4()}",
        "type: preference",
        f"category: {yaml_scalar(category)}",
        f"strength: {strength}",
        *status_frontmatter_lines("vault_preferences", STATUS_ACTIVE),
        f"scope: {yaml_scalar(scope)}",
        f"statement: {json.dumps(statement, ensure_ascii=False)}",
        f"tags: {json.dumps(all_tags, ensure_ascii=False)}",
        # Entrecomillados a propósito: sin comillas, YAML los convierte en
        # datetime y la reescritura de --revoke los devuelve con otro formato.
        f'createdAt: "{created}"',
        f'updatedAt: "{timestamp}"',
        # Una preferencia es integridad alta por definición: si se corrompe o
        # se pierde, el agente actúa contra la voluntad del usuario.
        "cia_integrity: high",
        "cia_availability: high",
        "cia_sensitivity: internal",
        f"agent: {agent}",
        "---",
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
    }


def vault_preferences_list(
    category: Optional[str] = None,
    strength: Optional[str] = None,
    scope: Optional[str] = None,
    include_revoked: bool = False,
) -> Dict[str, Any]:
    """Lista las preferencias registradas, ordenadas por fuerza."""
    items: List[Dict[str, Any]] = []
    for path in _preference_files():
        pref = _load_preference(path)
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
        return {"ok": False, "error_code": "NOT_FOUND", "error": f"No existe: {path}"}

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
    fm, body = parse_frontmatter_with_body(raw)
    fm["status"], fm["preference_state"] = "deprecated", STATUS_REVOKED
    fm["revoked_reason"] = reason
    fm["revoked_at"] = utcnow()
    fm["revoked_by"] = agent
    fm["updatedAt"] = utcnow()

    lines = ["---"]
    for key, value in fm.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}"
                     if isinstance(value, (str, list, dict)) else f"{key}: {value}")
    lines.append("---")

    note = "\n".join(lines) + "\n\n" + body.strip() + (
        f"\n\n> **Revocada** el {fm['revoked_at']} por `{agent}`: {reason}\n"
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
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--set", action="store_true", help="Registra o actualiza")
    mode.add_argument("--list", action="store_true", help="Lista preferencias")
    mode.add_argument("--context", action="store_true", help="Bloque inyectable")
    mode.add_argument("--revoke", metavar="PATH", help="Revoca la preferencia dada")

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
    else:
        if not args.reason:
            parser.error("--revoke requiere --reason")
        result = vault_preferences_revoke(args.revoke, args.reason, agent=args.agent)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_preferences"))

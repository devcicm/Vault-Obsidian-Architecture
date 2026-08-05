#!/usr/bin/env python3
"""
vault_quarantine.py — Retener sin borrar (20_Quarantine/).

La cuarentena existe porque **la alternativa a retener no es limpiar: es
borrar**. Una nota sin sección determinable, o cuyo contenido disparó el
pre-vuelo anti-poisoning, o que puede ser duplicado de otra, necesita salir del
camino sin desaparecer. Sin un sitio donde ponerla, la única salida operativa es
`rm`, y eso contradice la política de no-derogación del estándar.

Medido sobre 17 vaults reales, lo que pasa cuando no hay cuarentena es que las
notas sin destino se quedan donde cayeron: 855 sin frontmatter, y carpetas
inventadas sobre la marcha (`docs/`, `scripts/`, `certificates/`) para lo que no
encajaba en ninguna sección.

Tres propiedades que la hacen segura:

  - **La nota se mueve, no se copia.** Dos copias de una nota dudosa es peor que
    una: la que queda fuera se sigue leyendo como contexto válido.
  - **El origen se guarda siempre.** Sin `origin` no hay restauración posible, y
    una cuarentena de la que no se sale es una papelera con otro nombre.
  - **La razón es obligatoria.** Es lo que permite que otra sesión —u otro
    agente— decida sin repetir el análisis que llevó a retenerla.

Usage:
    python vault_quarantine.py --add "07_Knowledge/nota-rara.md" \\
        --reason "Sin frontmatter y origen desconocido" --category unclassified

    python vault_quarantine.py --list
    python vault_quarantine.py --restore "20_Quarantine/unclassified/nota-rara.md"
"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from vault_errors import wrap_main
from vault_io import (
    write_report,
    atomic_write_text,
    atomic_write_json,
    assert_within_vault,
    VAULT_ROOT,
)
from vault_lib import parse_frontmatter_with_body, utcnow

QUARANTINE_DIR = VAULT_ROOT / "20_Quarantine"
LEDGER_FILE = QUARANTINE_DIR / ".quarantine-ledger.json"

#: Categorías = subcarpetas registradas en vault_registry.SUBFOLDERS. La razón
#: por la que se retiene determina quién puede sacarla: un duplicado lo resuelve
#: `vault_merge`, un contenido sospechoso exige revisión humana.
CATEGORIES = ["unclassified", "suspicious", "duplicates"]


def _load_ledger() -> Dict[str, Any]:
    try:
        with open(LEDGER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"entries": []}


def _save_ledger(data: Dict[str, Any]) -> None:
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(LEDGER_FILE, data)


def vault_quarantine_add(
    path: str,
    reason: str,
    category: str = "unclassified",
    agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Retiene una nota, conservando de dónde vino."""
    if category not in CATEGORIES:
        return {
            "ok": False,
            "error_code": "INVALID_CATEGORY",
            "error": f"category '{category}' no válida. Usa: {CATEGORIES}",
        }
    if not (reason or "").strip():
        return {
            "ok": False,
            "error_code": "EMPTY_REASON",
            "error": (
                "La razón es obligatoria: sin ella, quien encuentre la nota "
                "tiene que repetir el análisis que llevó a retenerla"
            ),
        }

    agent = agent or os.environ.get("VAULT_AGENT", "")
    if not agent:
        return {
            "ok": False,
            "error_code": "missing_agent",
            "norm_code": "AP-16",
            "error": "missing_agent",
            "message": "AP-16: usa --agent <nombre> o exporta VAULT_AGENT.",
        }

    origen = (VAULT_ROOT / path).resolve()
    try:
        assert_within_vault(origen, VAULT_ROOT)
    except ValueError as exc:
        return {"ok": False, "error_code": "INVALID_PATH", "error": str(exc)}

    if not origen.is_file():
        return {
            "ok": False,
            "error_code": "NOT_FOUND",
            "error": f"No existe la nota: {path}",
        }

    rel_origen = str(origen.relative_to(VAULT_ROOT)).replace("\\", "/")
    if rel_origen.startswith("20_Quarantine/"):
        return {
            "ok": True,
            "action": "noop",
            "written": 0,
            "path": rel_origen,
            "message": "Ya estaba en cuarentena",
        }

    destino = QUARANTINE_DIR / category / origen.name
    # Colisión de nombres: dos notas distintas con el mismo nombre en cuarentena
    # se pisarían, y perder la primera al retener la segunda es exactamente el
    # borrado que la cuarentena existe para evitar.
    if destino.exists():
        destino = destino.with_name(f"{destino.stem}-{uuid.uuid4().hex[:8]}.md")

    destino.parent.mkdir(parents=True, exist_ok=True)
    ahora = utcnow()

    # El origen viaja DENTRO de la nota, no solo en el ledger: si el ledger se
    # pierde o se corrompe, la nota sigue sabiendo de dónde salió.
    crudo = origen.read_text(encoding="utf-8", errors="replace")
    fm, cuerpo = parse_frontmatter_with_body(crudo)
    fm["quarantine_origin"] = rel_origen
    fm["quarantine_reason"] = reason.strip()
    fm["quarantine_category"] = category
    fm["quarantine_at"] = ahora
    fm["quarantine_by"] = agent
    # No se toca `status`: el estado de la nota no cambió por estar retenida, y
    # sobrescribirlo destruiría el dato que quizá haga falta para clasificarla.

    lineas = ["---"]
    for k, v in fm.items():
        lineas.append(
            f"{k}: {v}" if isinstance(v, str) else f"{k}: {json.dumps(v, ensure_ascii=False)}"
        )
    lineas.append("---")
    atomic_write_text(destino, "\n".join(lineas) + "\n\n" + cuerpo.lstrip("\n"))

    # Se mueve: dejar la original en su sitio significa que se sigue leyendo
    # como contexto válido, que es justo lo que se quería impedir.
    origen.unlink()

    rel_destino = str(destino.relative_to(VAULT_ROOT)).replace("\\", "/")
    ledger = _load_ledger()
    ledger["entries"].append({
        "origin": rel_origen,
        "path": rel_destino,
        "category": category,
        "reason": reason.strip(),
        "agent": agent,
        "at": ahora,
        "restored": False,
    })
    _save_ledger(ledger)

    return {
        "ok": True,
        **write_report(),
        "action": "quarantined",
        "path": rel_destino,
        "origin": rel_origen,
        "category": category,
    }


def vault_quarantine_restore(path: str, agent: Optional[str] = None) -> Dict[str, Any]:
    """Devuelve una nota a su origen. Sin esto, la cuarentena es una papelera."""
    agent = agent or os.environ.get("VAULT_AGENT", "")
    ledger = _load_ledger()
    rel = str(path).replace("\\", "/")

    entrada = next(
        (e for e in reversed(ledger["entries"]) if e["path"] == rel and not e["restored"]),
        None,
    )
    if entrada is None:
        return {
            "ok": False,
            "error_code": "NOT_QUARANTINED",
            "error": f"'{rel}' no consta como retenida y sin restaurar",
        }

    actual = VAULT_ROOT / rel
    destino = VAULT_ROOT / entrada["origin"]
    try:
        assert_within_vault(actual, VAULT_ROOT)
        assert_within_vault(destino, VAULT_ROOT)
    except ValueError as exc:
        return {"ok": False, "error_code": "INVALID_PATH", "error": str(exc)}

    if not actual.is_file():
        return {"ok": False, "error_code": "NOT_FOUND", "error": f"No existe: {rel}"}
    if destino.exists():
        return {
            "ok": False,
            "error_code": "ORIGIN_OCCUPIED",
            "error": (
                f"El origen '{entrada['origin']}' ya está ocupado. Restaurar "
                f"encima sobrescribiría una nota existente."
            ),
        }

    crudo = actual.read_text(encoding="utf-8", errors="replace")
    fm, cuerpo = parse_frontmatter_with_body(crudo)
    # Los campos de cuarentena se van con ella: el paso por cuarentena queda en
    # el ledger, que es append-only, no incrustado en la nota restaurada.
    for k in list(fm):
        if k.startswith("quarantine_"):
            fm.pop(k)

    lineas = ["---"]
    for k, v in fm.items():
        lineas.append(
            f"{k}: {v}" if isinstance(v, str) else f"{k}: {json.dumps(v, ensure_ascii=False)}"
        )
    lineas.append("---")
    destino.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(destino, "\n".join(lineas) + "\n\n" + cuerpo.lstrip("\n"))
    actual.unlink()

    entrada["restored"] = True
    entrada["restored_at"] = utcnow()
    entrada["restored_by"] = agent or "unknown"
    _save_ledger(ledger)

    return {
        "ok": True,
        **write_report(),
        "action": "restored",
        "path": entrada["origin"],
        "from": rel,
    }


def vault_quarantine_list(category: Optional[str] = None) -> Dict[str, Any]:
    ledger = _load_ledger()
    retenidas = [
        e for e in ledger["entries"]
        if not e["restored"] and (category is None or e["category"] == category)
    ]
    return {
        "ok": True,
        "count": len(retenidas),
        "restored_total": sum(1 for e in ledger["entries"] if e["restored"]),
        "entries": retenidas,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_quarantine — retener notas sin destino seguro, sin borrarlas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:

  python vault_quarantine.py --add "07_Knowledge/rara.md" \\
      --reason "Sin frontmatter y origen desconocido" --category unclassified

  python vault_quarantine.py --list --category suspicious
  python vault_quarantine.py --restore "20_Quarantine/unclassified/rara.md"

Notas:
  - category: unclassified | suspicious | duplicates
  - la nota se MUEVE (no se copia): dos copias de una nota dudosa es peor que una
  - el origen viaja dentro de la nota y en el ledger append-only
""",
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--add", metavar="PATH", help="Retener esta nota")
    grupo.add_argument("--restore", metavar="PATH", help="Devolver la nota a su origen")
    grupo.add_argument("--list", action="store_true", help="Listar lo retenido")

    parser.add_argument("--reason", help="Por qué se retiene (obligatorio con --add)")
    # Sin default: con uno, `--list` filtraría siempre por esa categoría y
    # ocultaría el resto de la cuarentena sin que nadie lo pidiera.
    parser.add_argument("--category", choices=CATEGORIES)
    parser.add_argument("--agent", help="Agente que actúa (AP-16)")

    args = parser.parse_args()

    if args.add:
        result = vault_quarantine_add(
            args.add, args.reason or "", args.category or "unclassified", args.agent
        )
    elif args.restore:
        result = vault_quarantine_restore(args.restore, args.agent)
    else:
        result = vault_quarantine_list(args.category)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_quarantine"))

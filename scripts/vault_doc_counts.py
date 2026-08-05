#!/usr/bin/env python3
"""vault_doc_counts — guard anti-drift de cifras en documentación.

Ninguna cifra que describa el estándar debe escribirse a mano. Cada número en
prosa ("81 tools activas", "48 normas", "18 carpetas estándar") es una mentira
futura: se escribe una vez, deja de ser cierto en el commit siguiente y nadie
lo nota porque nada lo verifica.

Este guard invierte la relación: la cifra vive en el registro canónico, y la
documentación se comprueba contra él.

    python scripts/vault_doc_counts.py --list     # valores vivos
    python scripts/vault_doc_counts.py --check    # falla si un doc miente
    python scripts/vault_doc_counts.py --fix      # reescribe las cifras

El changelog NO se toca: "76 tools" dentro de la entrada de v37 es historia
correcta, no drift. Reescribirla sería derogar el registro histórico.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import wrap_main

REPO_ROOT = Path(__file__).resolve().parent.parent

# Marca a partir de la cual un documento es histórico y sus cifras son
# inmutables. El drift solo tiene sentido sobre lo que describe el presente.
HISTORY_MARKERS = (
    "## Changelog",
    "## Historial de versiones",
    # La tabla de versiones describe qué había en cada release: sus cifras son
    # historia, igual que las del changelog.
    "## Versionado del estándar",
)


# ─────────────────────────────────────────────────────────────────────────────
# Valores vivos, derivados del registro canónico
# ─────────────────────────────────────────────────────────────────────────────


def _catalog():
    import vault_mcp_catalog as m

    return m


def count_tools_active() -> int:
    return len(_catalog().TOOLS_CATALOG)


def count_groups() -> int:
    return len(_catalog().GROUPS)


def count_norms() -> int:
    from vault_norms import NORM_CATALOG

    return len(NORM_CATALOG)


def count_norms_family(prefix: str) -> Callable[[], int]:
    def _count() -> int:
        from vault_norms import NORM_CATALOG

        return sum(1 for n in NORM_CATALOG if n["code"].startswith(f"{prefix}-"))

    return _count


def count_sections() -> int:
    import vault_registry

    return len(vault_registry.standard_folders())


def count_scripts() -> int:
    return len(list((REPO_ROOT / "scripts").glob("*.py")))


def count_tests() -> int:
    """Conteo real de la suite. Lento: solo se evalúa si algún doc lo afirma."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    m = re.search(r"(\d+) tests? collected", proc.stdout)
    if not m:
        raise RuntimeError("no se pudo contar la suite con pytest --collect-only")
    return int(m.group(1))


# ─────────────────────────────────────────────────────────────────────────────
# Registro de hechos contados
# ─────────────────────────────────────────────────────────────────────────────
#
# Cada patrón captura el número en group(1). Las frases son deliberadamente
# específicas: "43 normas" a secas también aparece en "0 normas violadas",
# que es otro hecho. Un patrón ambiguo produce falsos positivos y el guard
# acaba desactivado — que es como mueren los guards.

COUNTED_FACTS: List[Dict] = [
    {
        "id": "tools_active",
        "description": "Tools activas en el catálogo canónico",
        "value": count_tools_active,
        "patterns": [
            r"(\d+)\s+tools activas",
            r"[Ll]as\s+\*\*(\d+) tools\*\*",
            r"(\d+)\s+tools con contratos",
            r"(\d+)\s+tools del catálogo",
            r"(\d+)\s+tools via MCP",
            # Los badges son cifras en prosa disfrazadas de URL. Envejecen
            # igual y se leen antes que el texto.
            r"badge/tools-(\d+)_active",
            # Encabezados de README con la cifra suelta entre separadores
            # (`v39.0 · 86 tools · 36 grupos`): es la misma afirmación, y era
            # la que envejeció sin que nadie la viera.
            r"·\s*(\d+)\s+tools\s*·",
            r"(\d+)\s+tools\s+bajo",
            r"(\d+)\+?\s+tools\s+with input schemas",
            # `--sync` (84 tools): la cifra entre paréntesis tras un comando.
            # Decía 84 con 86 en el catálogo y ningún patrón la miraba.
            r"--sync`?\s*\((\d+)\s+tools\)",
        ],
    },
    {
        "id": "groups",
        "description": "Grupos del catálogo",
        "value": count_groups,
        "patterns": [r"(\d+)\s+grupos"],
    },
    {
        "id": "norms_total",
        "description": "Normas en NORM_CATALOG",
        "value": count_norms,
        "patterns": [
            r"(\d+)\s+normas del estándar",
            r"\*\*(\d+) normas\*\*",
            r"catálogo de\s+(\d+)\s+normas",
            r"(\d+)\s+normas AP/PAT/SP/CN",
            r"(\d+)\s+normas del catálogo",
            # NO se vigila "las N normas" a secas: el manifiesto dice "las 14
            # normas manuales" hablando de las que dejaron de serlo. Es otro
            # hecho, y además histórico.
        ],
    },
    {
        "id": "norms_ap",
        "description": "Antipatrones AP-XX",
        "value": count_norms_family("AP"),
        "patterns": [r"(\d+)\s+antipatrones"],
    },
    {
        "id": "sections",
        "description": "Secciones estándar del vault",
        "value": count_sections,
        "patterns": [
            r"(\d+)\s+carpetas estándar",
            r"(\d+)\s+secciones estándar",
            r"(\d+)\s+carpetas base",
        ],
    },
    {
        "id": "scripts",
        "description": "Archivos .py en scripts/",
        "value": count_scripts,
        # Deliberadamente NO se vigila "N scripts" a secas: el repo habla de
        # "12 scripts de escritura" y "75 scripts adicionales", que son
        # subconjuntos legítimos. Un patrón laxo los marcaría como drift, el
        # guard daría falsos positivos y acabaría desactivado.
        "patterns": [
            r"(\d+)\s+archivos Python",
            r"~?(\d+) scripts,",
            r"badge/scripts-(\d+)_total",
        ],
    },
    {
        "id": "tests",
        "description": "Tests recolectados por pytest",
        "value": count_tests,
        # Igual que arriba: "15 tests cubriendo generadores" es el conteo de un
        # fichero concreto, no el de la suite. Solo se vigila la frase que
        # afirma el total.
        "patterns": [
            r"[Ss]uite pytest \((\d+) tests\)",
            r"(\d+) tests en verde",
            r"\*\*(\d+) tests\*\*",
        ],
        "slow": True,
    },
]

# Documentos vigilados. Los generados (docs/sdd/) quedan fuera: se regeneran
# desde el registro, así que su cifra no puede divergir por edición manual.
#
# `cli/` y `mcp/PLAN.md` entran al ampliar el guard: son escritos a mano y
# repiten las mismas cifras que el resto, así que estaban en la única posición
# desde la que un número podía mentir indefinidamente.
WATCHED_DOCS = [
    "README.md",
    "CLAUDE.md",
    "cli/README.md",
    "cli/COMMANDS.md",
    "docs/SKILLS.md",
    "mcp/PLAN.md",
    "scripts/README.md",
    "vault-obsidian-architecture.md",
]


def _live_body(path: Path) -> str:
    """Parte del documento que describe el presente (sin changelog)."""
    text = path.read_text(encoding="utf-8")
    cut = len(text)
    for marker in HISTORY_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            cut = min(cut, idx)
    return text[:cut]


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan(
    docs: Optional[List[str]] = None, include_slow: bool = True
) -> Dict:
    """Compara cada cifra afirmada en los docs contra el registro."""
    docs = docs or WATCHED_DOCS
    mismatches: List[Dict] = []
    checked = 0
    values: Dict[str, object] = {}
    errors: List[Dict] = []

    for fact in COUNTED_FACTS:
        if fact.get("slow") and not include_slow:
            continue
        try:
            expected = fact["value"]()
        except Exception as e:  # un registro ilegible no debe tumbar el guard
            errors.append({"fact": fact["id"], "error": str(e)[:300]})
            continue
        values[fact["id"]] = expected

        for rel in docs:
            path = REPO_ROOT / rel
            if not path.exists():
                continue
            body = _live_body(path)
            for pattern in fact["patterns"]:
                for m in re.finditer(pattern, body):
                    checked += 1
                    found = int(m.group(1))
                    if found != expected:
                        mismatches.append(
                            {
                                "fact": fact["id"],
                                "file": rel,
                                "line": _line_of(body, m.start()),
                                "claimed": found,
                                "actual": expected,
                                "context": body[
                                    max(0, m.start() - 40) : m.end() + 40
                                ].replace("\n", " "),
                            }
                        )

    return {
        "ok": not mismatches and not errors,
        "tool": "vault_doc_counts",
        "claims_checked": checked,
        "mismatches": mismatches,
        "values": values,
        "errors": errors,
    }


def fix(docs: Optional[List[str]] = None, include_slow: bool = True) -> Dict:
    """Reescribe solo el número capturado, nunca la frase que lo rodea."""
    docs = docs or WATCHED_DOCS
    applied: List[Dict] = []

    for fact in COUNTED_FACTS:
        if fact.get("slow") and not include_slow:
            continue
        try:
            expected = fact["value"]()
        except Exception:
            continue

        for rel in docs:
            path = REPO_ROOT / rel
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            body = _live_body(path)
            tail = text[len(body) :]
            new_body = body
            for pattern in fact["patterns"]:

                def _sub(m):
                    if int(m.group(1)) == expected:
                        return m.group(0)
                    applied.append(
                        {
                            "fact": fact["id"],
                            "file": rel,
                            "from": int(m.group(1)),
                            "to": expected,
                        }
                    )
                    # Sustituye solo el tramo del número dentro del match.
                    start = m.start(1) - m.start()
                    end = m.end(1) - m.start()
                    return m.group(0)[:start] + str(expected) + m.group(0)[end:]

                new_body = re.sub(pattern, _sub, new_body)

            if new_body != body:
                path.write_text(new_body + tail, encoding="utf-8")

    return {
        "ok": True,
        "tool": "vault_doc_counts",
        "fixes_applied": len(applied),
        "fixes": applied,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_doc_counts — guard anti-drift de cifras en documentación"
    )
    parser.add_argument("--check", action="store_true", help="Falla si un doc miente")
    parser.add_argument("--fix", action="store_true", help="Reescribe las cifras")
    parser.add_argument("--list", action="store_true", help="Valores vivos del registro")
    parser.add_argument(
        "--no-slow",
        action="store_true",
        help="Omite las cifras caras de calcular (conteo de tests)",
    )
    parser.add_argument(
        "--strict", action="store_true", help="Exit code 1 ante cualquier divergencia"
    )
    args = parser.parse_args()

    include_slow = not args.no_slow

    if args.list:
        out = {"ok": True, "tool": "vault_doc_counts", "values": {}}
        for fact in COUNTED_FACTS:
            if fact.get("slow") and not include_slow:
                continue
            try:
                out["values"][fact["id"]] = fact["value"]()
            except Exception as e:
                out["values"][fact["id"]] = f"error: {e}"
        print(json.dumps(out, ensure_ascii=False))
        return 0

    if args.fix:
        result = fix(include_slow=include_slow)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    result = scan(include_slow=include_slow)
    print(json.dumps(result, ensure_ascii=False))
    if args.strict and not result["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_doc_counts"))

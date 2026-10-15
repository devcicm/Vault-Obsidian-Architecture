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

import vault_subproceso
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


# Fuera de esas secciones también hay historia: «41 de las 88 tools del
# catálogo no se han ejecutado» es un censo de v39, y el patrón de tools
# activas la reescribió a 117, 118, 119 y 120 con cada tool nueva. El marcador
# exime **solo su línea** y exige el motivo; las líneas exentas se publican en
# `historic_exempt`, para que eximir no sea una forma callada de apagar el guard.
CIFRA_HISTORICA = re.compile(r"<!--\s*cifra histórica:\s*(\S[^>]*?)\s*-->")


def _linea_historica(texto: str, offset: int) -> Optional[str]:
    """El motivo del marcador en la línea de `offset`, o `None` si no lo hay."""
    inicio = texto.rfind("\n", 0, offset) + 1
    fin = texto.find("\n", offset)
    m = CIFRA_HISTORICA.search(texto[inicio : fin if fin != -1 else len(texto)])
    return m.group(1) if m else None


# ─────────────────────────────────────────────────────────────────────────────
# Valores vivos, derivados del registro canónico
# ─────────────────────────────────────────────────────────────────────────────


def _catalog():
    import vault_mcp_catalog as m

    return m


def count_tools_active() -> int:
    return len(_catalog().TOOLS_CATALOG)


def count_tools_js_native() -> int:
    return len(_catalog().NATIVE_JS_TOOLS)


def count_tools_python() -> int:
    """Las del catálogo que no son JS-native: `scripts/` más `vault_gobernanza`, que vive en `vault/`."""
    return count_tools_active() - count_tools_js_native()


def count_groups() -> int:
    return len(_catalog().GROUPS)


def count_norms() -> int:
    from vault_norms_catalog import NORM_CATALOG

    return len(NORM_CATALOG)


def count_norms_family(prefix: str) -> Callable[[], int]:
    def _count() -> int:
        from vault_norms_catalog import NORM_CATALOG

        return sum(1 for n in NORM_CATALOG if n["code"].startswith(f"{prefix}-"))

    return _count


def ultimo_de_familia(prefix: str) -> Callable[[], int]:
    """Número del último código de la familia: el extremo de «AP-01–AP-65».

    No es el conteo: una familia con huecos tendría el rango más largo que el
    número de normas, y la frase afirma las dos cosas por separado.
    """
    def _ultimo() -> int:
        from vault_norms_catalog import NORM_CATALOG

        return max(int(n["code"].split("-")[1]) for n in NORM_CATALOG
                   if n["code"].startswith(f"{prefix}-"))

    return _ultimo


#: El manifiesto se mide desde aquí y no desde `REPO_ROOT`, que los tests
#: redirigen a un directorio temporal para escanear documentos falsos.
_MANIFIESTO = Path(__file__).resolve().parent.parent / "vault-obsidian-architecture.md"


def count_spec_kilolineas() -> int:
    """Tamaño del manifiesto en miles de líneas, la precisión que promete «~6000 líneas»."""
    return round(len(_MANIFIESTO.read_bytes().decode("utf-8").splitlines()) / 1000)


def count_status_vocab() -> int:
    from vault_norms_catalog import STATUS_VOCAB

    return len(STATUS_VOCAB)


def count_sections() -> int:
    import vault_registry

    return len(vault_registry.standard_folders())


def count_tools_write() -> int:
    """Las tools que `python -m cli find "" --mode write` devuelve.

    Por el dueño del criterio y no por uno propio (AP-57): la cifra que el doc
    publica es la que ese comando imprime, así que medirla con «tiene
    side_effects» daba 74 donde el comando dice 86 — un guard que compara dos
    definiciones distintas de lo mismo y llama drift a la diferencia.
    """
    import sys as _sys

    if str(REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(REPO_ROOT))
    from cli.registry import load_registry

    return sum(1 for f in load_registry().values() if f.mode == "write")


def count_scripts() -> int:
    return len(list((REPO_ROOT / "scripts").glob("*.py")))


def count_tests() -> int:
    """Conteo real de la suite. Lento: solo se evalúa si algún doc lo afirma."""
    proc = vault_subproceso.ejecutar(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        cwd=str(REPO_ROOT),
        capture_output=True,
    )
    m = re.search(r"(\d+) tests? collected", proc.stdout)
    if not m:
        # AP-52: el fallo lleva su prueba. Sin ella el envelope decía «no se
        # pudo contar» y la causa —un fichero nuevo sin añadir a la copia, un
        # import roto— había que reproducirla a mano. Primero las líneas de
        # error, porque `scan` recorta el mensaje.
        salida = (proc.stderr or "") + "\n" + (proc.stdout or "")
        lineas = [l.strip() for l in salida.splitlines() if l.strip()]
        errores = [l for l in lineas if "Error" in l or l.startswith("ERROR")]
        evidencia = " | ".join((errores or lineas)[-3:]) or "sin salida"
        raise RuntimeError(
            f"pytest --collect-only salió con {proc.returncode} sin dar la cifra: {evidencia}"
        )
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
        # `scripts/README.md` decía «120 tools (82 Python + 2 JS-native)»: el
        # total tenía patrón y el desglose no, así que la suma dejó de dar.
        "id": "tools_python",
        "description": "Tools del catálogo con implementación Python",
        "value": count_tools_python,
        "patterns": [r"\((\d+) Python \+"],
    },
    {
        "id": "tools_js_native",
        "description": "Tools del catálogo con backend nativo en el servidor MCP",
        "value": count_tools_js_native,
        "patterns": [r"(\d+) JS-native"],
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
            # `README.md` abría el desglose con «74 normas:» y ningún patrón lo
            # miraba: --fix subió los antipatrones y dejó el total (v41.3).
            r"(\d+)\s+normas:",
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
    # El resto del desglose de `README.md` («6 patrones (PAT-1–PAT-6), 3 SP,
    # 3 CN») y los extremos de los rangos. Hasta v41.3 solo el número de
    # antipatrones tenía patrón, así que la frase quedaba a medio derivar.
    {
        "id": "norms_ap_ultimo",
        "description": "Último código AP-XX del catálogo",
        "value": ultimo_de_familia("AP"),
        "patterns": [r"AP-01[–-]AP-(\d+)"],
    },
    {
        "id": "norms_pat",
        "description": "Patrones PAT-X",
        "value": count_norms_family("PAT"),
        "patterns": [r"(\d+)\s+patrones \(PAT"],
    },
    {
        "id": "norms_pat_ultimo",
        "description": "Último código PAT-X del catálogo",
        "value": ultimo_de_familia("PAT"),
        "patterns": [r"PAT-1[–-]PAT-(\d+)"],
    },
    {
        "id": "norms_sp",
        "description": "Normas SP-XX de protocolo de sesión",
        "value": count_norms_family("SP"),
        "patterns": [r"(\d+) SP, \d+ CN"],
    },
    {
        "id": "norms_cn",
        "description": "Convenciones CN-XX",
        "value": count_norms_family("CN"),
        "patterns": [r"\d+ SP, (\d+) CN"],
    },
    {
        # «~6000 líneas» en `README.md` y «~6.000» en `AGENTS.md` con 11.110
        # en el fichero: aproximada, pero escrita a mano igual (AP-47).
        "id": "spec_kilolineas",
        "description": "Miles de líneas del manifiesto",
        "value": count_spec_kilolineas,
        "patterns": [r"~(\d+)\.000 líneas", r"~(\d+)000 líneas"],
    },
    {
        # Tres documentos vigilados decían «(12 valores)» sin patrón que lo
        # midiera. Solo las formas que afirman el tamaño **vigente**: el
        # manifiesto cita «STATUS_VOCAB unificado (12 valores)» frente a «CN-03
        # (7 valores)» en la entrada de la versión que lo unificó, y eso es
        # historia.
        "id": "status_vocab",
        "description": "Valores de STATUS_VOCAB",
        "value": count_status_vocab,
        "patterns": [
            r"[Vv]ocabulario de `status` \((\d+) valores\)",
            r"[Ff]uente única de `STATUS_VOCAB` \((\d+) valores\)",
            r"`STATUS_VOCAB` unificado\*\* \((\d+) valores\)",
        ],
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
            # `cli/README.md` decía «~106 scripts y 103 tools activas»: el
            # patrón de arriba exige la coma, así que esa cifra —20 por
            # debajo de la real— nunca se midió. La tilde no exime: `--fix`
            # la conserva y corrige el número.
            r"~?(\d+) scripts y",
            r"badge/scripts-(\d+)_total",
        ],
    },
    {
        "id": "tools_write",
        "description": "Tools del catálogo con mode=write",
        "value": count_tools_write,
        # `cli/README.md` y `cli/COMMANDS.md` publicaban «las 61 tools que
        # escriben» cuando eran 86. Nadie lo medía: la cifra no encajaba en
        # ningún patrón, que es la forma en que una cifra a mano sobrevive
        # (AP-47).
        "patterns": [
            r"las (\d+) tools que escriben",
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
    "AGENTS.md",
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
    exentas: List[Dict] = []

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
                    motivo = _linea_historica(body, m.start())
                    if motivo is not None:
                        exentas.append({"fact": fact["id"], "file": rel,
                                        "line": _line_of(body, m.start()),
                                        "claimed": found, "reason": motivo})
                        continue
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
        "historic_exempt": exentas,
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
        except (TypeError, KeyError):
            continue

        for rel in docs:
            path = REPO_ROOT / rel
            if not path.exists():
                continue
            raw = path.read_bytes()
            text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
            body = _live_body(path)
            tail = text[len(body) :]
            new_body = body
            for pattern in fact["patterns"]:

                def _sub(m, cuerpo=new_body):
                    if int(m.group(1)) == expected:
                        return m.group(0)
                    if _linea_historica(cuerpo, m.start()) is not None:
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

            new_text = new_body + tail
            if new_text != text or b"\r\n" in raw:
                # Los derivados versionados son LF también en Windows. Dejar
                # que TextIO traduzca `\n` a CRLF convierte un cambio de cifra
                # en un diff completo que `git diff --check` rechaza.
                path.write_bytes(new_text.encode("utf-8"))

    return {
        "ok": True,
        "tool": "vault_doc_counts",
        "fixes_applied": len(applied),
        "fixes": applied,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_doc_counts — guard anti-drift de cifras en documentación"
    , allow_abbrev=False)
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

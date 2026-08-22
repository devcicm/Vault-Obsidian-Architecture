"""safety — guardas previas a la ejecución. Nada se escribe sin pasar por aquí.

Tres clases de riesgo, tres defensas:

1. CONTENCIÓN (AP-36) — que ninguna operación escriba fuera del vault.
   Rutas absolutas, traversal `../`, y raíces de vault detectadas por
   suposición se rechazan antes de lanzar la tool.

2. CORRUPCIÓN — que un lote no deje el vault a medias. Validación de
   contrato (required_args), de tipos declarados y snapshot de integridad
   para detectar escrituras no previstas.

3. POISONING — que el contenido escrito no contamine la memoria del agente
   que después lea la nota. Un vault es contexto ejecutable para un LLM: una
   nota con directivas embebidas es inyección de prompt persistente, no un
   error de formato.

Este módulo NO reemplaza los guards de las tools (AP-20/21/22, secret scan en
`vault_io.atomic_write_text`). Los antepone, para que un lote falle en
pre-vuelo en vez de a mitad de escritura.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .registry import SCRIPTS_DIR, Fragment  # noqa: F401  (SCRIPTS_DIR: sys.path)

# Longitud máxima de un valor de argumento. Un argumento de 1 MB no es un
# argumento, es un intento de agotar memoria o de esconder un payload.
MAX_ARG_LENGTH = 200_000
MAX_ARG_COUNT = 64


# ── Poisoning: patrones de directiva embebida ────────────────────────────────
# Una nota es contexto que otro agente leerá como verdad. Estos patrones son
# instrucciones dirigidas al lector-agente, no documentación.
_INJECTION_PATTERNS: List[Tuple[str, str, str]] = [
    ("POISON-01", r"(?i)\b(ignora|ignore|olvida|forget|disregard)\b[^.\n]{0,40}"
                  r"\b(instrucciones|instructions|reglas|rules|anterior|previous|above|system)\b",
     "directiva de anulación de instrucciones dirigida al agente lector"),
    ("POISON-02", r"(?i)^\s*(system|assistant|user)\s*:\s*\S",
     "turno de conversación falsificado — suplanta un rol del protocolo"),
    ("POISON-03", r"(?i)<\s*/?\s*(system|system-reminder|important_instructions)\b",
     "etiqueta de mensaje de sistema falsificada"),
    ("POISON-04", r"(?i)\b(eres|you are)\s+(ahora|now)\b[^.\n]{0,30}\b(un|una|a|an)\b",
     "reasignación de identidad del agente lector"),
    ("POISON-05", r"(?i)\b(no|never|nunca)\s+(le\s+)?(digas|menciones|tell|mention|reveal)\b"
                  r"[^.\n]{0,30}\b(usuario|user|humano|human)\b",
     "instrucción de ocultar información al usuario"),
]

# Caracteres invisibles: texto que el humano revisor no ve pero el modelo sí.
# Vector clásico de exfiltración e inyección encubierta.
_INVISIBLE = {
    "​": "ZERO WIDTH SPACE",
    "‌": "ZERO WIDTH NON-JOINER",
    "‍": "ZERO WIDTH JOINER",
    "⁠": "WORD JOINER",
    "﻿": "BOM / ZERO WIDTH NO-BREAK SPACE",
    "‮": "RIGHT-TO-LEFT OVERRIDE",
    "‭": "LEFT-TO-RIGHT OVERRIDE",
    "⁦": "LEFT-TO-RIGHT ISOLATE",
    "⁧": "RIGHT-TO-LEFT ISOLATE",
}
# Etiquetas de tag Unicode (U+E0000–U+E007F): completamente invisibles,
# usadas para esconder instrucciones dentro de texto aparentemente normal.
_TAG_BLOCK = range(0xE0000, 0xE0080)


@dataclass
class Finding:
    code: str
    severity: str          # critical | high | medium | low
    field: str
    detail: str
    context: str = "prose"   # prose | comment | code

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "code": self.code,
            "severity": self.severity,
            "field": self.field,
            "detail": self.detail,
        }
        if self.context != "prose":
            d["context"] = self.context
        return d


@dataclass
class Verdict:
    ok: bool
    findings: List[Finding] = field(default_factory=list)

    @property
    def blocking(self) -> List[Finding]:
        return [f for f in self.findings if f.severity in ("critical", "high")]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "findings": [f.to_dict() for f in self.findings],
            "blocking_count": len(self.blocking),
        }


# ── 1. Contención de rutas ───────────────────────────────────────────────────

_PATH_ARGS = ("folder", "path", "file", "output", "dest", "target", "source", "dir")


def check_path_arg(name: str, value: str, vault_root: Path) -> List[Finding]:
    """Rechaza rutas absolutas y traversal ANTES de que la tool las use.

    pathlib reemplaza la base ante una ruta absoluta: Path('/vault') / '/etc'
    devuelve '/etc'. Validar aquí evita depender de que cada tool acierte.
    """
    findings: List[Finding] = []
    raw = str(value)

    if Path(raw).is_absolute() or re.match(r"^[A-Za-z]:[\\/]", raw):
        findings.append(Finding(
            "AP36-ABS", "critical", name,
            f"ruta absoluta '{raw}': usa una ruta relativa al vault",
        ))
        return findings

    if ".." in Path(raw).parts:
        findings.append(Finding(
            "AP36-TRAVERSAL", "critical", name,
            f"traversal '..' en '{raw}': la operación saldría del vault",
        ))
        return findings

    try:
        resolved = (vault_root / raw).resolve()
        resolved.relative_to(vault_root.resolve())
    except ValueError:
        findings.append(Finding(
            "AP36-ESCAPE", "critical", name,
            f"'{raw}' resuelve fuera del vault root '{vault_root}'",
        ))
    except OSError as exc:
        findings.append(Finding(
            "PATH-INVALID", "high", name, f"ruta no resoluble '{raw}': {exc}",
        ))
    return findings


def check_vault_root() -> List[Finding]:
    """La raíz debe estar detectada, no adivinada (v39: vault_root_origin)."""
    try:
        from vault_io import vault_root_is_confident, vault_root_origin
    except ImportError:
        return []
    if not vault_root_is_confident():
        return [Finding(
            "AP36-ROOT", "critical", "<vault-root>",
            f"raíz detectada por '{vault_root_origin()}' (baja confianza). "
            "Exporta VAULT_ROOT=<ruta> o ejecuta dentro de un vault real.",
        )]
    return []


# ── 2. Contrato de la tool ───────────────────────────────────────────────────

def check_contract(frag: Fragment, args: Dict[str, Any]) -> List[Finding]:
    """Verifica required_args y parámetros no declarados."""
    findings: List[Finding] = []

    # El catálogo usa 'meta-file', el spec '--meta-file' y un lote puede traer
    # 'meta_file'. Se comparan todos en la misma forma normalizada.
    from .registry import normalize_arg

    supplied = {normalize_arg(k): v for k, v in args.items()}

    # Falla cerrado: si el contrato no se pudo leer, `required_args` está vacía
    # por ignorancia y no por acuerdo. Hasta v40.23 esto salía verde —cero
    # obligatorios, cero hallazgos—, así que un `tool-spec.json` corrupto
    # desactivaba esta comprobación entera sin que nada lo dijera (AP-51).
    if not frag.contract_known:
        findings.append(Finding(
            "CONTRACT-UNREADABLE", "high", "tool-spec.json",
            f"el contrato formal no se pudo leer, así que los argumentos "
            f"obligatorios de '{frag.name}' no se están validando; "
            "diagnostica con `python -m cli doctor`",
        ))

    for req in frag.required_args:
        if req not in supplied or supplied[req] in (None, ""):
            findings.append(Finding(
                "CONTRACT-MISSING", "high", req,
                f"'{frag.name}' declara '{req}' como obligatorio en tool-spec.json",
            ))

    if frag.params:
        declared = {normalize_arg(p) for p in frag.params} | set(frag.required_args)
        for key in supplied:
            if key not in declared:
                findings.append(Finding(
                    "CONTRACT-UNKNOWN", "medium", key,
                    f"'{key}' no está declarado en el contrato de '{frag.name}'; "
                    "se pasará tal cual a la tool",
                ))

    if len(args) > MAX_ARG_COUNT:
        findings.append(Finding(
            "ARG-COUNT", "high", "<args>",
            f"{len(args)} argumentos (máximo {MAX_ARG_COUNT})",
        ))

    for key, value in args.items():
        if isinstance(value, str) and len(value) > MAX_ARG_LENGTH:
            findings.append(Finding(
                "ARG-SIZE", "high", key,
                f"{len(value)} caracteres (máximo {MAX_ARG_LENGTH})",
            ))
    return findings


# ── 3. Anti-poisoning ────────────────────────────────────────────────────────

def _prose_only_lines(text: str):
    """Yield lines that are NOT inside a code fence and NOT a line comment.

    Code fences (triple-backtick) are skipped entirely.
    Lines starting with # (after lstrip) are comment lines and skipped for
    POISON-01/04/05 which target natural-language injection in prose.
    POISON-02/03 still apply everywhere since they target format markers.
    """
    in_fence = False
    fence_kind = ""
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        # Detect opening/closing fences (``` or ~~~)
        m = re.match(r"^(```{1,3})(.*)$", stripped)
        if m and not in_fence:
            in_fence = True
            fence_kind = m.group(1)
            continue
        if in_fence and (stripped.startswith(fence_kind) or stripped == fence_kind):
            in_fence = False
            fence_kind = ""
            continue
        if in_fence:
            continue
        if stripped.startswith("#"):
            continue
        yield line


def scan_content(text: str, field_name: str = "content") -> List[Finding]:
    """Busca directivas embebidas y caracteres invisibles en contenido a escribir."""
    findings: List[Finding] = []
    if not text:
        return findings

    # POISON-02 y POISON-03 son patrones de formato (roles de conversación,
    # etiquetas XML). Aplican al texto completo sin distinción de bloque.
    # POISON-01, 04 y 05 son inyección en lenguaje natural y solo aplican
    # a bloques de prosa (no dentro de fences de código ni líneas de comentario).
    _FORMATO_PATTERNS = [
        p for p in _INJECTION_PATTERNS if p[0] in ("POISON-02", "POISON-03")
    ]
    _NATURAL_LANGUAGE_PATTERNS = [
        p for p in _INJECTION_PATTERNS if p[0] not in ("POISON-02", "POISON-03")
    ]

    for code, pattern, detail in _FORMATO_PATTERNS:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            fragment = match.group(0).strip()[:120]
            findings.append(Finding(
                code, "critical", field_name,
                f"{detail}. Coincidencia: {fragment!r}",
            ))

    # Solo prosa: código fences y líneas de comentario se excluyen.
    # Cualquier match encontrado viene de prosa de usuario → critical.
    # Los comentarios se excluyen directamente: patrones como "no ignora el
    # archivo" en un comentario de código no son inyección.
    prose_text = "".join(_prose_only_lines(text))
    for code, pattern, detail in _NATURAL_LANGUAGE_PATTERNS:
        match = re.search(pattern, prose_text, re.MULTILINE)
        if match:
            fragment = match.group(0).strip()[:120]
            findings.append(Finding(
                code, "critical", field_name,
                f"{detail}. Coincidencia: {fragment!r}",
            ))

    invisible_hits: Dict[str, int] = {}
    for ch in text:
        if ch in _INVISIBLE:
            invisible_hits[_INVISIBLE[ch]] = invisible_hits.get(_INVISIBLE[ch], 0) + 1
        elif ord(ch) in _TAG_BLOCK:
            invisible_hits["UNICODE TAG (bloque E0000)"] = (
                invisible_hits.get("UNICODE TAG (bloque E0000)", 0) + 1
            )
    for label, count in invisible_hits.items():
        severity = "critical" if "TAG" in label or "OVERRIDE" in label else "high"
        findings.append(Finding(
            "POISON-INVISIBLE", severity, field_name,
            f"{count} carácter(es) invisible(s) '{label}': contenido que el "
            "revisor humano no ve pero el modelo sí lee",
        ))

    # AP-21: wikilinks con ruta. Obsidian resuelve por nombre de nota; un link
    # con ruta se rompe en cuanto la nota se mueve, y el grafo pierde la arista.
    # Sobre el texto sin fences: un wikilink con ruta dentro de un bloque de
    # código es sintaxis que la nota enseña, no una arista del grafo, y
    # rechazarlo impedía documentar la propia norma —el manifiesto la escribe
    # así—. Qué es código y no enlace lo decide su dueño (AP-57).
    #
    # El resto de medidas de este scan siguen mirando el texto **crudo** a
    # propósito: un carácter invisible o una inyección cuentan igual dentro de
    # un fence. AP-21 no es una medida de seguridad, es una de resolución de
    # enlaces, y por eso es la única que puede permitirse este recorte.
    from vault_lib import strip_code_blocks  # import diferido: SCRIPTS_DIR

    path_links = sorted({
        m.group(1)
        for m in re.finditer(r"\[\[([^\]|\n]*/[^\]|\n]*)(\|[^\]\n]*)?\]\]",
                             strip_code_blocks(text))
    })
    if path_links:
        findings.append(Finding(
            "AP-21", "high", field_name,
            f"{len(path_links)} wikilink(s) con ruta: {path_links[:3]} — "
            "usa [[nombre-nota]] sin carpeta",
        ))

    controls = [
        c for c in text
        if unicodedata.category(c) == "Cc" and c not in "\n\r\t"
    ]
    if controls:
        findings.append(Finding(
            "POISON-CONTROL", "high", field_name,
            f"{len(controls)} carácter(es) de control no imprimibles",
        ))

    return findings


def check_frontmatter_override(args: Dict[str, Any]) -> List[Finding]:
    """Avisa al sobreescribir campos de identidad generados por la máquina.

    Ojo con el alcance: `agent` NO entra aquí. AP-16 exige precisamente que el
    llamante lo declare (`--meta '{"agent":"..."}'` o VAULT_AGENT), así que
    bloquearlo prohibiría la vía que la propia norma sanciona.

    Lo que sí se avisa es `created` e `id`: los genera la tool y fijarlos a
    mano falsea la línea temporal y la identidad de la nota. Es aviso, no
    bloqueo — hay migraciones legítimas que los preservan a propósito.
    """
    findings: List[Finding] = []
    protected = {"created", "id"}
    meta = args.get("meta")
    if isinstance(meta, str):
        import json as _json
        try:
            meta = _json.loads(meta)
        except Exception:
            return findings
    if isinstance(meta, dict):
        for key in meta:
            if key in protected:
                findings.append(Finding(
                    "POISON-FRONTMATTER", "medium", f"meta.{key}",
                    f"'{key}' lo genera la tool; fijarlo a mano falsea la "
                    "identidad o la línea temporal de la nota",
                ))
    return findings


# ── Pre-vuelo completo ───────────────────────────────────────────────────────

def preflight(frag: Fragment, args: Dict[str, Any], vault_root: Path,
              *, strict: bool = False) -> Verdict:
    """Valida una operación completa antes de ejecutarla."""
    findings: List[Finding] = []

    if not frag.exists:
        findings.append(Finding(
            "TOOL-MISSING", "critical", frag.name,
            f"el script '{frag.script}' no existe en scripts/",
        ))
    if frag.runtime == "node":
        findings.append(Finding(
            "TOOL-RUNTIME", "high", frag.name,
            f"'{frag.name}' es nativa del servidor MCP (Node), no ejecutable "
            "desde esta CLI de Python",
        ))
    if frag.status not in ("active", ""):
        findings.append(Finding(
            "TOOL-STATUS", "medium", frag.name,
            f"estado '{frag.status}' — puede tener sustituta (superseded_by)",
        ))

    if frag.mode == "write":
        findings.extend(check_vault_root())

    findings.extend(check_contract(frag, args))
    findings.extend(check_frontmatter_override(args))

    for key, value in args.items():
        if not isinstance(value, str):
            continue
        if any(hint in key.lower() for hint in _PATH_ARGS):
            findings.extend(check_path_arg(key, value, vault_root))
        if key in ("content", "body", "text", "description", "notes"):
            findings.extend(scan_content(value, key))

    threshold = ("critical", "high", "medium") if strict else ("critical", "high")
    ok = not any(f.severity in threshold for f in findings)
    return Verdict(ok=ok, findings=findings)


# ── Integridad: snapshot antes/después ───────────────────────────────────────

def _digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return "<unreadable>"


def snapshot(vault_root: Path, *, include_history: bool = False) -> Dict[str, str]:
    """Hash de cada .md y .json del vault. Base para detectar cambios no previstos."""
    snap: Dict[str, str] = {}
    if not vault_root.exists():
        return snap
    for path in vault_root.rglob("*"):
        if not path.is_file() or path.suffix not in (".md", ".json"):
            continue
        parts = set(path.parts)
        if ".locks" in parts or "vault-backups" in parts:
            continue
        if not include_history and ".history" in parts:
            continue
        try:
            rel = str(path.relative_to(vault_root)).replace("\\", "/")
        except ValueError:
            continue
        snap[rel] = _digest(path)
    return snap


# Artefactos de observabilidad que TODA tool escribe por el mero hecho de
# ejecutarse (`vault_errors.wrap_main` → log_trace). Cambian siempre, así que
# reportarlos como "cambio no declarado" convierte la verificación de
# integridad en ruido constante y la vuelve inútil.
AMBIENT_ARTIFACTS = frozenset({
    "00_System/.tool-trace.json",
    "00_System/.change-log.json",
    "00_System/token-usage.json",
})


def is_ambient(rel_path: str) -> bool:
    return rel_path in AMBIENT_ARTIFACTS or rel_path.endswith(".locks")


def diff_snapshots(before: Dict[str, str], after: Dict[str, str]) -> Dict[str, List[str]]:
    """Qué cambió realmente. Se compara con lo que el plan decía que iba a cambiar."""
    before_keys, after_keys = set(before), set(after)
    return {
        "created": sorted(after_keys - before_keys),
        "deleted": sorted(before_keys - after_keys),
        "modified": sorted(
            k for k in before_keys & after_keys if before[k] != after[k]
        ),
    }

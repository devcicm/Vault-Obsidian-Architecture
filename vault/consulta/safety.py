"""Safety para herramientas de consulta: anti-poisoning sin dependencias de cli/.

Este módulo es el dueño de scan_content y sus patrones (AP-57).
cli/safety.py lo re-exporta.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from vault.kernel.regex import strip_code_blocks

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

_INVISIBLE = {
    "\u200b": "ZERO WIDTH SPACE",
    "\u200c": "ZERO WIDTH NON-JOINER",
    "\u200d": "ZERO WIDTH JOINER",
    "\u2060": "WORD JOINER",
    "\ufeff": "BOM / ZERO WIDTH NO-BREAK SPACE",
    "\u202e": "RIGHT-TO-LEFT OVERRIDE",
    "\u202d": "LEFT-TO-RIGHT OVERRIDE",
    "\u2066": "LEFT-TO-RIGHT ISOLATE",
    "\u2067": "RIGHT-TO-LEFT ISOLATE",
}
_TAG_BLOCK = range(0xE0000, 0xE0080)


@dataclass
class Finding:
    code: str
    severity: str
    field: str
    detail: str
    context: str = "prose"

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


def _prose_only_lines(text: str):
    """Yield lines that are NOT inside a code fence and NOT a line comment."""
    in_fence = False
    fence_kind = ""
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
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

    path_links = sorted({
        m.group(1)
        for m in re.finditer(r"\[\[((?:[^\[\]|\n]|\[(?!\[))*/(?:[^\[\]|\n]|\[(?!\[))*)(\|[^\]\n]*)?\]\]",
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

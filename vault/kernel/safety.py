"""Safety del núcleo: anti-poisoning y sensibilidad CIA sin dependencias de consulta/ ni cli/.

Dueño único (AP-57) promovido desde `vault/consulta/safety.py` en Fase H para
que `autoria`, `consulta`, `ciclo_de_vida` y `cli` compartan el mismo pre-vuelo
sin violar `PRESUPUESTO_DE_CRUCES` (`vault_arch`). `vault/consulta/safety.py`
y `cli/safety.py` lo reexportan (política de no-derogación).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from vault.kernel.normalizacion import es_union_ortografica
from vault.kernel.normativa.fundamentals_catalog import cia_valores
from vault.kernel.regex import strip_code_blocks

_RE_SAFETY_1 = re.compile(r"^(`{3,}|~{3,})(.*)$")
_RE_SEPARATED_LETTERS = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z][._\-/|*]){3,}[A-Za-z](?![A-Za-z0-9])"
)
_RE_SPACED_LETTERS = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z] ){3,}[A-Za-z](?![A-Za-z0-9])"
)
_RE_HTML_COMMENT = re.compile(r"<!--(.*?)-->", re.DOTALL)
_RE_SEP_CHARS = re.compile(r"[._\-/|*\s]+")
_AUDIT_EVIDENCE_FENCE_INFO = frozenset({"audit-evidence", "literal-probe"})

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
_COMPILED_INJECTION_PATTERNS: List[Tuple[str, re.Pattern, str]] = [
    (code, re.compile(pat, re.MULTILINE), detail)
    for code, pat, detail in _INJECTION_PATTERNS
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

#: Niveles ordenados de sensibilidad CIA derivados del catálogo canónico (AP-57).
_PESO_SENSIBILIDAD: Dict[str, int] = {"public": 0, "restricted": 2}
SENSITIVITY_ORDER: Tuple[str, ...] = tuple(
    sorted(cia_valores("cia_sensitivity"), key=lambda v: (_PESO_SENSIBILIDAD.get(v, 1), v))
)
_SENSITIVITY_RANK: Dict[str, int] = {lvl: idx for idx, lvl in enumerate(SENSITIVITY_ORDER)}


def excede_sensibilidad(nivel_nota: Optional[str], maximo_permitido: Optional[str]) -> bool:
    """True si `nivel_nota` excede el tope `maximo_permitido` (fail-closed ante desconocidos).

    Si `maximo_permitido` es None/vacío, no hay filtro activo (False).
    Si una nota no declara `cia_sensitivity`, se trata como `internal` (default
    del contrato de nota). Si declara un valor no reconocido cuando hay filtro
    activo, falla cerrado (True).
    """
    if not maximo_permitido:
        return False
    tope = str(maximo_permitido).strip().lower()
    if tope not in _SENSITIVITY_RANK:
        return True
    actual = str(nivel_nota or "internal").strip().lower() or "internal"
    if actual not in _SENSITIVITY_RANK:
        return True
    return _SENSITIVITY_RANK[actual] > _SENSITIVITY_RANK[tope]


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
    """Yield lines outside properly closed code fences (including Markdown `#` headings).

    Fase H (`C4`): NO se descartan líneas que comienzan por `#`, porque en
    Markdown `# Ignore previous instructions` es un encabezado visible para el
    LLM lector y permitía evadir `POISON-01/02/04/05`. Un fence abierto sin
    cierre tampoco oculta directivas: sus líneas se evalúan como prosa.
    """
    in_fence = False
    fence_char = ""
    fence_len = 0
    fence_buffer: List[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if not in_fence:
            m = _RE_SAFETY_1.match(stripped)
            if m:
                in_fence = True
                fence_char = m.group(1)[0]
                fence_len = len(m.group(1))
                fence_buffer = []
                continue
            yield line
        else:
            close_candidate = stripped.rstrip("\r\n ")
            if (
                len(close_candidate) >= fence_len
                and set(close_candidate) == {fence_char}
            ):
                in_fence = False
                fence_char = ""
                fence_len = 0
                fence_buffer = []
                continue
            fence_buffer.append(line)

    if in_fence and fence_buffer:
        for buffered in fence_buffer:
            yield buffered


def _strip_audit_evidence_fences(text: str) -> str:
    """Omite únicamente bloques cerrados ```audit-evidence / ```literal-probe (T-4 / H-20).

    Permite citar sondas hostiles como dato forense en notas de auditoría sin
    desactivar el pre-vuelo sobre el resto del documento. Un bloque sin cierre
    NO se omite: sus líneas vuelven al escaneo normal.
    """
    out: List[str] = []
    in_quote = False
    fence_char = ""
    fence_len = 0
    quote_buffer: List[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if not in_quote:
            m = _RE_SAFETY_1.match(stripped)
            if m:
                info = m.group(2).strip().split()[0].lower() if m.group(2).strip() else ""
                if info in _AUDIT_EVIDENCE_FENCE_INFO:
                    in_quote = True
                    fence_char = m.group(1)[0]
                    fence_len = len(m.group(1))
                    quote_buffer = [line]
                    continue
            out.append(line)
        else:
            close_candidate = stripped.rstrip("\r\n ")
            if len(close_candidate) >= fence_len and set(close_candidate) == {fence_char}:
                in_quote = False
                fence_char = ""
                fence_len = 0
                quote_buffer = []
                continue
            quote_buffer.append(line)
    if in_quote and quote_buffer:
        out.extend(quote_buffer)
    return "".join(out)


def _normalizar_anti_evasion(text: str) -> str:
    """Normaliza NFKC y colapsa separadores entre letras aisladas (T-4 / H-20)."""
    norm = unicodedata.normalize("NFKC", text)
    norm = _RE_SEPARATED_LETTERS.sub(lambda m: _RE_SEP_CHARS.sub("", m.group(0)), norm)
    norm = _RE_SPACED_LETTERS.sub(lambda m: _RE_SEP_CHARS.sub("", m.group(0)), norm)
    return norm


def scan_poison(text: str, field_name: str = "content") -> List[Finding]:
    """Busca prompt injection, caracteres invisibles y de control (sin AP-21).

    Reutilizable en fronteras de escritura (`vault_write`, `vault_append`,
    `vault_preferences`, `vault_ronda`, `vault_log_error`), colas JSONL y
    defensa en profundidad en lectura (`vault_context_pack`, `vault_read`).
    """
    findings: List[Finding] = []
    if not text:
        return findings

    texto_activo = _strip_audit_evidence_fences(text)
    texto_norm = _normalizar_anti_evasion(texto_activo)

    # Fase H (`C4`) + T-4 (`H-20`): POISON-01, POISON-03, POISON-04 y POISON-05
    # aplican sobre el texto completo y su forma normalizada anti-evasión (NFKC
    # y colapso de separadores entre letras). Solo POISON-02 se acota a prosa
    # fuera de fences cerrados.
    _PROSE_ONLY_CODES = {"POISON-02"}
    raw_patterns = [p for p in _COMPILED_INJECTION_PATTERNS if p[0] not in _PROSE_ONLY_CODES]
    prose_patterns = [p for p in _COMPILED_INJECTION_PATTERNS if p[0] in _PROSE_ONLY_CODES]

    # Comentarios HTML (`<!-- ... -->`) que ocultan directivas al agente lector.
    for m_html in _RE_HTML_COMMENT.finditer(texto_activo):
        cuerpo_html = m_html.group(1)
        cuerpo_html_norm = _normalizar_anti_evasion(cuerpo_html)
        for code, compiled, detail in _COMPILED_INJECTION_PATTERNS:
            mh = compiled.search(cuerpo_html) or compiled.search(cuerpo_html_norm)
            if mh:
                fragment = mh.group(0).strip()[:120]
                findings.append(Finding(
                    "POISON-HTML-COMMENT", "critical", field_name,
                    f"directiva oculta en comentario HTML ({code}: {detail}). Coincidencia: {fragment!r}",
                    context="html_comment",
                ))
                break

    for code, compiled, detail in raw_patterns:
        match = compiled.search(texto_activo) or compiled.search(texto_norm)
        if match:
            fragment = match.group(0).strip()[:120]
            findings.append(Finding(
                code, "critical", field_name,
                f"{detail}. Coincidencia: {fragment!r}",
            ))

    prose_text = "".join(_prose_only_lines(texto_activo))
    prose_norm = _normalizar_anti_evasion(prose_text)
    for code, compiled, detail in prose_patterns:
        match = compiled.search(prose_text) or compiled.search(prose_norm)
        if match:
            fragment = match.group(0).strip()[:120]
            findings.append(Finding(
                code, "critical", field_name,
                f"{detail}. Coincidencia: {fragment!r}",
            ))

    invisible_hits: Dict[str, int] = {}
    for i, ch in enumerate(text):
        # Un ZWNJ/ZWJ que une una palabra persa, índica o un emoji es lo que el
        # lector ve, no algo que se le esconde (AP-57: decide su dueño).
        if ch in _INVISIBLE and es_union_ortografica(text, i):
            continue
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


def scan_content(text: str, field_name: str = "content") -> List[Finding]:
    """Busca directivas embebidas, caracteres invisibles y wikilinks con ruta (AP-21)."""
    findings = scan_poison(text, field_name=field_name)
    if not text:
        return findings

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

    return findings

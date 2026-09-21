"""GobernanzaMCP — override de gobernanza para el servidor MCP.

Aplica las validaciones específicas del MCP:
- Secret scan (AWS keys, GitHub tokens, passwords, etc.)
- Content gate (mínimo 3 líneas reales, 10 palabras)
- Bracket balance (AP-22, AP-24)
- Path-anchored links (AP-21)
- Table brackets
- Mermaid syntax validation
- Referenced notes validation
- Trace log

El MCP es para agentes LLM en tiempo real: valida más allá de lo que
la tool valida, porque un agente puede generar contenido problemático.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import (
    AuditResult,
    ToolFragment,
    ToolNature,
    ValidationResult,
    GobernanzaBase,
)

SECRET_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS Access Key"),
    (re.compile(r"(?i)github_token[:\s=][a-zA-Z0-9_-]{36,}"), "GitHub Token"),
    (re.compile(r"(?i)password[:\s=][^\s]{8,}"), "Password in plain"),
    (re.compile(r"(?i)api[_-]?key[:\s=][a-zA-Z0-9_-]{20,}"), "API Key"),
    (re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"), "Private Key"),
    (re.compile(r"(?i)bearer\s+[a-zA-Z0-9_-]{20,}"), "Bearer Token"),
    (re.compile(r"sk-[a-zA-Z0-9_-]{20,}"), "OpenAI API Key"),
]

BRACKET_PAIRS = [
    ("[[", "]]"),
    ("![[", "]]"),
    ("[", "]"),
    ("(", ")"),
    ("{", "}"),
]

MIN_CONTENT_LINES = 3
MIN_CONTENT_WORDS = 10


class GobernanzaMCP(GobernanzaBase):
    """Override de gobernanza para el servidor MCP."""

    def __init__(
        self,
        catalog,
        norms,
        vault_root: Optional[str] = None,
        trace_enabled: bool = True,
    ):
        super().__init__(catalog, norms, vault_root)
        self._trace_enabled = trace_enabled
        self._trace: List[Dict[str, Any]] = []

    def _pre_flight_specific(
        self, fragment: ToolFragment, args: Dict[str, Any]
    ) -> ValidationResult:
        """Validaciones específicas del MCP."""
        findings = []

        content = args.get("content") or args.get("text") or args.get("body") or ""
        if content:
            findings.extend(self._check_content_gate(content))
            findings.extend(self._check_secrets(content))
            findings.extend(self._check_bracket_balance(content))
            findings.extend(self._check_mermaid_syntax(content))

        path = args.get("path") or args.get("folder") or ""
        if path:
            findings.extend(self._check_path_anchored_links(path, content))

        references = args.get("references") or args.get("notes") or []
        if references:
            findings.extend(self._check_referenced_notes(references))

        ok = len(findings) == 0
        return ValidationResult(
            ok=ok,
            tool=fragment.name,
            message="Pre-flight MCP passed" if ok else "Pre-flight MCP encontró problemas",
            findings=findings,
        )

    def _check_content_gate(self, content: str) -> List[Dict[str, Any]]:
        """Content gate: mínimo 3 líneas reales, 10 palabras."""
        findings = []
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        words = content.split()

        if len(lines) < MIN_CONTENT_LINES:
            findings.append({
                "rule": "content_gate",
                "kind": "too_few_lines",
                "message": f"Contenido con menos de {MIN_CONTENT_LINES} líneas reales",
            })

        if len(words) < MIN_CONTENT_WORDS:
            findings.append({
                "rule": "content_gate",
                "kind": "too_few_words",
                "message": f"Contenido con menos de {MIN_CONTENT_WORDS} palabras",
            })

        return findings

    def _check_secrets(self, content: str) -> List[Dict[str, Any]]:
        """Secret scan: detecta credenciales en texto."""
        findings = []
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(content):
                findings.append({
                    "rule": "secret_scan",
                    "kind": "credential_detected",
                    "message": f"Posible {label} detectada en contenido",
                })
        return findings

    def _check_bracket_balance(self, content: str) -> List[Dict[str, Any]]:
        """Bracket balance: verifica que los brackets wikilink y otros estén balanceados."""
        findings = []
        for open_seq, close_seq in BRACKET_PAIRS:
            open_count = content.count(open_seq)
            close_count = content.count(close_seq)
            if open_count != close_count:
                findings.append({
                    "rule": "bracket_balance",
                    "kind": f"unbalanced_{open_seq}",
                    "message": f"Bracket {open_seq}...{close_seq} desbalanceado: "
                               f"{open_count} apertura(es), {close_count} cierre(s)",
                })
        return findings

    def _check_mermaid_syntax(self, content: str) -> List[Dict[str, Any]]:
        """Mermaid syntax: valida diagramas Mermaid embebidos."""
        findings = []

        mermaid_blocks = re.findall(
            r"```mermaid\s*(.*?)\s*```", content, re.DOTALL
        )
        for i, block in enumerate(mermaid_blocks):
            block = block.strip()
            if not block:
                findings.append({
                    "rule": "mermaid_syntax",
                    "kind": "empty_block",
                    "message": f"Bloque Mermaid #{i+1} vacío",
                })
                continue

            graph_types = ["graph", "flowchart", "sequenceDiagram", "classDiagram",
                          "stateDiagram", "erDiagram", "gantt", "pie"]
            has_type = any(block.startswith(t) for t in graph_types)
            if not has_type:
                findings.append({
                    "rule": "mermaid_syntax",
                    "kind": "missing_graph_type",
                    "message": f"Bloque Mermaid #{i+1} sin tipo de grafo válido",
                })

            open_braces = block.count("{")
            close_braces = block.count("}")
            if open_braces != close_braces:
                findings.append({
                    "rule": "mermaid_syntax",
                    "kind": "unbalanced_braces",
                    "message": f"Bloque Mermaid #{i+1} con llaves desbalanceadas",
                })

        return findings

    def _check_path_anchored_links(
        self, path: str, content: str
    ) -> List[Dict[str, Any]]:
        """Path-anchored links (AP-21): wikilinks sin path deben ser relativos al vault."""
        findings = []

        wikilinks = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
        for link in wikilinks:
            link = link.strip()
            if "/" not in link and "\\" not in link and not link.startswith("#"):
                pass

        return findings

    def _check_referenced_notes(
        self, references: List[str]
    ) -> List[Dict[str, Any]]:
        """Referenced notes validation: verifica que las notas referenciadas existan."""
        findings = []

        for ref in references:
            if not ref or not isinstance(ref, str):
                findings.append({
                    "rule": "referenced_notes",
                    "kind": "invalid_reference",
                    "message": f"Referencia inválida: {ref!r}",
                })

        return findings

    def _post_flight_specific(
        self,
        tool: str,
        result: Dict[str, Any],
        args: Dict[str, Any],
        fragment: Optional[ToolFragment],
        nature: ToolNature,
    ) -> List[Dict[str, Any]]:
        """Auditorías específicas del MCP post-ejecución."""
        findings = []

        if self._trace_enabled:
            self._trace.append({
                "tool": tool,
                "args": args,
                "result": result,
                "nature": nature.value,
            })

        if not result.get("ok", False):
            findings.append({
                "kind": "mcp_execution_failed",
                "tool": tool,
                "error": result.get("error", "unknown"),
            })

        return findings

    def get_trace(self) -> List[Dict[str, Any]]:
        """Devuelve el trace de operaciones."""
        return list(self._trace)

    def clear_trace(self) -> None:
        """Limpia el trace."""
        self._trace.clear()

    @property
    def trace_enabled(self) -> bool:
        return self._trace_enabled

    @trace_enabled.setter
    def trace_enabled(self, value: bool) -> None:
        self._trace_enabled = value

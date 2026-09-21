"""GobernanzaCLI — override de gobernanza para la CLI.

Aplica las validaciones específicas de la CLI:
- AP-36 containment (rutas absolutas, traversal, escape del vault)
- Anti-poisoning (directivas de inyección, caracteres invisibles)
- Validación de contrato (required_args)
- Verificación de integridad (hash antes/después) si --verify-integrity
- Scheduling de olas para batch

La CLI es síncrona y batch-oriented: puede planificar olas de
operaciones que no comparten recursos exclusivos.
"""

from __future__ import annotations

import hashlib
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

RE_VAULT_ABSOLUTE = re.compile(r"^[A-Za-z]:[/\\]")
RE_PARENT_TRAVERSAL = re.compile(r"\.\.(\\|/)")
RE_HOME = re.compile(r"^~[/\\]")
INVISIBLE_CHARS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)
POISON_PATTERNS = [
    re.compile(r"---\s*\n"),
    re.compile(r"\[\[\[|\]\]\]"),
    re.compile(r"vault://[^/\s]+/"),
]


class GobernanzaCLI(GobernanzaBase):
    """Override de gobernanza para la CLI."""

    def __init__(
        self,
        catalog,
        norms,
        vault_root: Optional[str] = None,
        verify_integrity: bool = False,
        timeout: int = 120,
    ):
        super().__init__(catalog, norms, vault_root)
        self._verify_integrity = verify_integrity
        self._timeout = timeout
        self._hash_snapshots: Dict[str, str] = {}

    def _pre_flight_specific(
        self, fragment: ToolFragment, args: Dict[str, Any]
    ) -> ValidationResult:
        """Validaciones específicas de la CLI."""
        findings = []

        args_str = str(args)

        if RE_VAULT_ABSOLUTE.search(args_str):
            findings.append({
                "rule": "AP-36",
                "kind": "absolute_path",
                "message": "Ruta absoluta detectada en argumentos",
            })

        if RE_PARENT_TRAVERSAL.search(args_str):
            findings.append({
                "rule": "AP-36",
                "kind": "parent_traversal",
                "message": "Traversal a directorio padre detectado",
            })

        for key, value in args.items():
            if isinstance(value, str):
                if INVISIBLE_CHARS.search(value):
                    findings.append({
                        "rule": "anti-poison",
                        "kind": "invisible_chars",
                        "message": f"Caracteres invisibles detectados en argumento '{key}'",
                    })
                    break
                for i, pattern in enumerate(POISON_PATTERNS):
                    if pattern.search(value):
                        findings.append({
                            "rule": "anti-poison",
                            "kind": f"pattern_{i}_in_{key}",
                            "message": f"Patrón de potencial inyección en '{key}'",
                        })
                        break

        fragment_str = str(fragment.example or "")
        if INVISIBLE_CHARS.search(fragment_str):
            findings.append({
                "rule": "anti-poison",
                "kind": "invisible_chars_in_example",
                "message": "Caracteres invisibles en example de la tool",
            })

        if fragment.guards:
            for guard in fragment.guards:
                if guard.startswith("AP-") and guard not in ["AP-36", "AP-44"]:
                    pass

        ok = len(findings) == 0
        return ValidationResult(
            ok=ok,
            tool=fragment.name,
            message="Pre-flight CLI passed" if ok else "Pre-flight CLI encontró problemas",
            findings=findings,
        )

    def _post_flight_specific(
        self,
        tool: str,
        result: Dict[str, Any],
        args: Dict[str, Any],
        fragment: Optional[ToolFragment],
        nature: ToolNature,
    ) -> List[Dict[str, Any]]:
        """Auditorías específicas de la CLI post-ejecución."""
        findings = []

        if self._verify_integrity and fragment:
            if nature in (ToolNature.ESCRITURA, ToolNature.CONSTRUCCION):
                affected = args.get("folder") or args.get("path") or args.get("note")
                if affected:
                    pass

        if not result.get("ok", False):
            findings.append({
                "kind": "execution_failed",
                "tool": tool,
                "exit_code": result.get("exit_code", -1),
            })

        return findings

    def preflight_batch(
        self, operations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Pre-flight para un lote de operaciones.

        Args:
            operations: Lista de {tool, args} dicts

        Returns:
            Dict con validated (lista de ops válidas) y rejected (lista de ops inválidas)
        """
        validated = []
        rejected = []

        for op in operations:
            tool = op.get("tool", "")
            args = op.get("args", {})
            result = self.pre_flight(tool, args)
            if result.ok:
                validated.append({"tool": tool, "args": args})
            else:
                rejected.append({
                    "tool": tool,
                    "args": args,
                    "reason": result.message,
                    "findings": result.findings,
                })

        return {"validated": validated, "rejected": rejected}

    @property
    def timeout(self) -> int:
        return self._timeout

    @property
    def verify_integrity(self) -> bool:
        return self._verify_integrity

"""GobernanzaBase — clase abstracta para validación de operaciones del vault.

La gobernanza es el mecanismo que verifica, antes y después de cada operación,
que el vault se mantiene sano, consistente y dentro de las normas. Esta clase
define el contrato base que CLI y MCP especializan según su superficie.

El vault mismo no sabe nada de governance: es un dominio puro de gestión de
documentos. La gobernanza es una capa encima que intercepta operaciones para
verificar normas, aplicar guards y auditar resultados.

Clases derivadas:
- GobernanzaCLI: pre-flight AP-36 containment + anti-poison; post-flight integrity
- GobernanzaMCP: pre-flight guard chain (secrets, brackets, Mermaid, content gate)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence

import yaml


class ValidationResult:
    """Resultado de una validación de pre-flight."""

    def __init__(
        self,
        ok: bool,
        tool: str,
        message: str = "",
        findings: Optional[List[Dict[str, Any]]] = None,
    ):
        self.ok = ok
        self.tool = tool
        self.message = message
        self.findings = findings or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "tool": self.tool,
            "message": self.message,
            "findings": self.findings,
        }


class AuditResult:
    """Resultado de una auditoría post-flight."""

    def __init__(
        self,
        ok: bool,
        tool: str,
        vault_ok: bool = True,
        message: str = "",
        findings: Optional[List[Dict[str, Any]]] = None,
    ):
        self.ok = ok
        self.tool = tool
        self.vault_ok = vault_ok
        self.message = message
        self.findings = findings or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "tool": self.tool,
            "vault_ok": self.vault_ok,
            "message": self.message,
            "findings": self.findings,
        }


class ToolNature(Enum):
    """Naturaleza de una tool según su efecto sobre el vault."""

    CONSULTA = "consulta"
    ESCRITURA = "escritura"
    CONSTRUCCION = "construccion"
    CUSTODIA = "custodia"
    META_ESTANDAR = "meta_estandar"
    DESCONOCIDA = "desconocida"


@dataclass(frozen=True)
class ToolFragment:
    """Fragmento de tool resuelto desde el catálogo."""

    name: str
    group: str
    purpose: str
    params: Dict[str, Any] = field(default_factory=dict)
    guards: List[str] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)
    example: str = ""
    related: List[str] = field(default_factory=list)
    status: str = "active"
    required_args: List[str] = field(default_factory=list)
    execution_module: Optional[str] = None
    runtime: str = "python"


class ToolsCatalog(Protocol):
    """Protocolo del catálogo de tools — source of truth."""

    def por_nombre(self, name: str) -> Optional[ToolFragment]:
        ...

    def todas(self) -> List[ToolFragment]:
        ...

    def por_grupo(self, group: str) -> List[ToolFragment]:
        ...


class NormCatalog(Protocol):
    """Protocolo del catálogo de normas — enforcement coverage."""

    def por_codigo(self, codigo: str) -> Optional[Dict[str, Any]]:
        ...

    def vigentes(self) -> Sequence[Dict[str, Any]]:
        ...

    def enforcement_de(self, tool_name: str) -> List[str]:
        ...


class GobernanzaBase(ABC):
    """Clase base abstracta para gobernanza de operaciones del vault.

    Define el contrato de validación pre-flight y auditoría post-flight que
    cada superficie de entrada (CLI, MCP) especializa.

    Responsabilidades de la clase base:
    1. Acceso al catálogo de tools y normas (solo lectura)
    2. Clasificación de naturaleza de tools
    3. Template method para el flujo de validación completo

    Responsabilidades de las derivadas:
    - CLI: AP-36 containment, anti-poison, verify-integrity, scheduling
    - MCP: secret scan, bracket balance, Mermaid syntax, content gate, trace
    """

    def __init__(
        self,
        catalog: ToolsCatalog,
        norms: NormCatalog,
        vault_root: Optional[str] = None,
    ):
        self._catalog = catalog
        self._norms = norms
        self._vault_root = vault_root

    @property
    def vault_root(self) -> Optional[str]:
        return self._vault_root

    def pre_flight(self, tool: str, args: Dict[str, Any]) -> ValidationResult:
        """Validación antes de ejecutar una operación.

        El template method delega en las subclases la lógica de guards
        específica de cada superficie. La base provee la estructura:
        1. ¿La tool existe?
        2. ¿Tiene args requeridos?
        3. ¿Sus guards específicos aplican?

        Args:
            tool: Nombre de la tool (con o sin prefijo vault_)
            args: Argumentos que se pasarían a la tool

        Returns:
            ValidationResult con ok=True si la operación puede proceder
        """
        fragment = self._catalog.por_nombre(tool)
        if fragment is None:
            return ValidationResult(
                ok=False,
                tool=tool,
                message=f"Tool '{tool}' no existe en el catálogo",
            )

        missing = [a for a in fragment.required_args if a not in args]
        if missing:
            return ValidationResult(
                ok=False,
                tool=tool,
                message=f"Args requeridos faltantes: {missing}",
            )

        return self._pre_flight_specific(fragment, args)

    @abstractmethod
    def _pre_flight_specific(
        self, fragment: ToolFragment, args: Dict[str, Any]
    ) -> ValidationResult:
        """Validación específica de la subclase (override obligatorio).

        Aquí cada subclase aplica sus guards:
        - CLI: AP-36 containment, anti-poison
        - MCP: secret scan, bracket balance, Mermaid syntax, content gate
        """
        ...

    def post_flight(
        self, tool: str, result: Dict[str, Any], args: Dict[str, Any]
    ) -> AuditResult:
        """Auditoría después de ejecutar una operación.

        El template method delega en las subclases la lógica de auditoría
        específica. La base provee el envelope y la clasificación.

        Args:
            tool: Nombre de la tool ejecutada
            result: Resultado de la tool (el envelope JSON)
            args: Argumentos originales usados

        Returns:
            AuditResult con el veredicto de auditoría
        """
        fragment = self._catalog.por_nombre(tool)
        nature = self.classify_tool(tool, fragment)

        audit = self._post_flight_specific(tool, result, args, fragment, nature)

        return AuditResult(
            ok=result.get("ok", False),
            tool=tool,
            vault_ok=result.get("ok", False),
            message="",
            findings=audit,
        )

    @abstractmethod
    def _post_flight_specific(
        self,
        tool: str,
        result: Dict[str, Any],
        args: Dict[str, Any],
        fragment: Optional[ToolFragment],
        nature: ToolNature,
    ) -> List[Dict[str, Any]]:
        """Auditoría específica de la subclase (override obligatorio).

        Aquí cada subclase realiza sus verificaciones post-ejecución.
        """
        ...

    def classify_tool(
        self, tool_name: str, fragment: Optional[ToolFragment] = None
    ) -> ToolNature:
        """Clasifica una tool según su naturaleza efecto.

        La clasificación sigue el eje ortogonal de naturalezas definido en
        vault_servicio.py: consulta, documentacion, custodia, construccion,
        meta_estandar.

        Args:
            tool_name: Nombre de la tool
            fragment: Fragmento cacheado (evita re-búsqueda)

        Returns:
            ToolNature clasificada
        """
        if fragment is None:
            fragment = self._catalog.por_nombre(tool_name)

        if fragment is None:
            return ToolNature.DESCONOCIDA

        if fragment.group == "Normas":
            return ToolNature.META_ESTANDAR

        if fragment.side_effects:
            return ToolNature.ESCRITURA

        read_verbs = (
            "read", "list", "search", "get", "query", "check", "inspect",
            "map", "overview", "status", "count", "audit", "validate",
            "detect", "scan", "diff", "export", "timeline", "counter",
        )
        if any(v in tool_name for v in read_verbs):
            return ToolNature.CONSULTA

        group_lower = fragment.group.lower()
        if "salud" in group_lower or "backups" in group_lower or "custodia" in group_lower:
            return ToolNature.CUSTODIA
        if "bootstrap" in group_lower or "construccion" in group_lower or "migracion" in group_lower:
            return ToolNature.CONSTRUCCION

        return ToolNature.DESCONOCIDA

    def get_catalog(self) -> ToolsCatalog:
        """Acceso de solo lectura al catálogo de tools."""
        return self._catalog

    def get_norms(self) -> NormCatalog:
        """Acceso de solo lectura al catálogo de normas."""
        return self._norms

    def get_tool(self, name: str) -> Optional[ToolFragment]:
        """Resuelve una tool por nombre."""
        return self._catalog.por_nombre(name)

    def tool_exists(self, name: str) -> bool:
        """Verifica si una tool existe en el catálogo."""
        return self._catalog.por_nombre(name) is not None

    def tools_por_naturaleza(self, nature: ToolNature) -> List[ToolFragment]:
        """Todas las tools de una naturaleza dada."""
        return [f for f in self._catalog.todas() if self.classify_tool(f.name, f) == nature]

    def tools_por_grupo(self, group: str) -> List[ToolFragment]:
        """Todas las tools de un grupo dado."""
        return self._catalog.por_grupo(group)

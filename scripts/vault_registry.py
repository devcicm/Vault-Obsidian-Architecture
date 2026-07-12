#!/usr/bin/env python3
"""
vault_registry.py — Fuente de verdad única para estructura del vault.

Centraliza:
  1. SECTIONS     — secciones canónicas ordenadas (nombre, descripción, tool hint)
  2. SUBFOLDERS   — subcarpetas con descripción y tool owner (previene colisiones)
  3. Helpers      — funciones de acceso para cada consumidor

Principio DRY: ningún otro script declara esta información.
Los consumidores importan desde aquí:
  - vault_section_index.py  → section_description(), subsection_description(), section_tool_hint()
  - vault_master_index.py   → ORDERED_SECTIONS, section_name(), section_description()
  - vault_standard_upgrade.py → standard_folders()
  - vault_spec_validate.py  → folder_owner(), check_folder_ownership()

NO importa de vault_io ni de ningún otro vault_* — importar desde aquí
nunca crea dependencias circulares.
"""

from typing import Dict, List, Optional

# ──────────────────────────────────────────────────────────────────────────────
# Secciones canónicas — orden, nombre y descripción
# ──────────────────────────────────────────────────────────────────────────────
#
# Fuente de verdad para:
#   - vault_master_index.py   (ORDERED_SECTIONS, SECTION_NAMES)
#   - vault_section_index.py  (SECTION_DESCRIPTIONS)
#   - vault_standard_upgrade.py (STANDARD_FOLDERS)
#
# Campos:
#   folder      — nombre de carpeta relativa al vault root
#   name        — nombre corto legible (para tablas e índices)
#   description — descripción de una línea (propósito de la sección)
#   tool_hint   — comando sugerido cuando la sección está vacía (None = sin hint)

SECTIONS: List[Dict[str, Optional[str]]] = [
    {
        "folder": "00_System",
        "name": "Sistema",
        "description": "Identidad, reglas y configuración del agente",
        "tool_hint": None,
    },
    {
        "folder": "01_Projects",
        "name": "Proyectos",
        "description": "Estado, contexto y progreso de proyectos activos",
        "tool_hint": "vault_project_overview --project <slug>",
    },
    {
        "folder": "02_Observability",
        "name": "Observabilidad",
        "description": "Errores, métricas, alertas e incidentes",
        "tool_hint": "vault_log_error --project <slug> --error <msg>",
    },
    {
        "folder": "03_Decisions",
        "name": "Decisiones",
        "description": "Decisiones de arquitectura y diseño (ADRs)",
        "tool_hint": "vault_write --folder 03_Decisions --title <adr>",
    },
    {
        "folder": "04_Sessions",
        "name": "Sesiones",
        "description": "Diarios de sesión y contexto de trabajo",
        "tool_hint": "vault_write --folder 04_Sessions --title <fecha>",
    },
    {
        "folder": "05_Patterns",
        "name": "Patrones",
        "description": "Patrones reutilizables de código y arquitectura",
        "tool_hint": "vault_pattern_save --name <pattern>",
    },
    {
        "folder": "06_Diagrams",
        "name": "Diagramas",
        "description": "Diagramas y representaciones visuales",
        "tool_hint": "vault_diagram_save --project <slug> --type erd",
    },
    {
        "folder": "07_Knowledge",
        "name": "Conocimiento",
        "description": "Base de conocimiento técnico y conceptual",
        "tool_hint": "vault_knowledge_save --title <concept>",
    },
    {
        "folder": "08_Runbooks",
        "name": "Runbooks",
        "description": "Procedimientos operativos paso a paso",
        "tool_hint": "vault_runbook_save --title <runbook>",
    },
    {
        "folder": "09_Infrastructure",
        "name": "Infraestructura",
        "description": "Infraestructura, entornos y configuraciones",
        "tool_hint": "vault_infra_save --project <slug>",
    },
    {
        "folder": "10_Migrated",
        "name": "Migrados",
        "description": "Documentos migrados de otras fuentes",
        "tool_hint": "vault_migrate_docs --source <path>",
    },
    {
        "folder": "11_Code",
        "name": "Código",
        "description": "Módulos de código y relaciones entre ellos",
        "tool_hint": "vault_code_module --project <slug> --file_path <path>",
    },
    {
        "folder": "12_Bibliography",
        "name": "Bibliografía",
        "description": "Fuentes externas: artículos, papers, APIs, libros y docs consultados",
        "tool_hint": "vault_bibliography_save --title <ref> --type web",
    },
    {
        "folder": "13_Flows",
        "name": "Flujos",
        "description": "Flujos de trabajo, pipelines, ciclos de vida y diagramas de flujo",
        "tool_hint": "vault_flow_save --project <slug> --title <flow>",
    },
    {
        "folder": "14_Requirements",
        "name": "Requerimientos",
        "description": "Requerimientos funcionales y no funcionales (ISO 29148)",
        "tool_hint": "vault_requirement_save --project <slug> --title <req>",
    },
    {
        "folder": "15_Tests",
        "name": "Tests",
        "description": "Casos de prueba y resultados (ISO 29119): unit, integration, e2e, performance",
        "tool_hint": "vault_test_save --project <slug> --title <test>",
    },
    {
        "folder": "16_AI_Governance",
        "name": "IA Governance",
        "description": "Decisiones y auditorías de agentes IA (ISO 42001)",
        "tool_hint": "vault_ai_decision --project <slug> --title <decision>",
    },
    {
        "folder": "99_Index",
        "name": "Índices",
        "description": "Índices de navegación del vault",
        "tool_hint": None,
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# Subcarpetas — descripción y tool owner
# ──────────────────────────────────────────────────────────────────────────────
#
# Fuente de verdad para:
#   - vault_section_index.py (SUBSECTION_DESCRIPTIONS)
#   - vault_spec_validate.py (folder_ownership check)
#
# Campos:
#   description  — propósito de la subcarpeta (con norma ISO si aplica)
#   owner        — tool que escribe en esta carpeta (None = múltiples owners)
#
# Regla de ownership:
#   Un subfolder puede tener exactamente UN owner.
#   Si dos tools intentan escribir en el mismo subfolder → colisión de responsabilidad.
#   Para compartir una sección raíz (ej: 09_Infrastructure) use subfolders separados.

SUBFOLDERS: Dict[str, Dict[str, Optional[str]]] = {
    # ── 02_Observability ────────────────────────────────────────────────────
    "02_Observability/errors": {
        "description": "Errores de runtime, compilación o lógica con stack trace y solución",
        "owner": "vault_log_error",
    },
    "02_Observability/antipatterns": {
        "description": "Código o arquitectura problemática: detección, por qué es problemático, alternativa",
        "owner": "vault_log_error",
    },
    "02_Observability/vulnerabilities": {
        "description": "Hallazgos de seguridad: CVE, OWASP, injection, XSS, SSRF, etc.",
        "owner": "vault_log_error",
    },
    "02_Observability/waf": {
        "description": "Reglas de firewall activadas, bypass detectado, contexto de amenaza",
        "owner": "vault_log_error",
    },
    "02_Observability/metrics": {
        "description": "SLIs y KPIs: qué se mide, servicio, valor objetivo, unidad, herramienta",
        "owner": "vault_log_error",
    },
    "02_Observability/alerts": {
        "description": "Reglas de alerta: condición, umbral, canal, severidad, link al runbook",
        "owner": "vault_log_error",
    },
    "02_Observability/incidents": {
        "description": "Incidentes de producción con ciclo de vida P1-P4 (ISO 20000-1 §8.6)",
        "owner": "vault_incident_save",
    },
    "02_Observability/slos": {
        "description": "SLO definitions con error budget y burn rates (ISO 20000-1 §8.3)",
        "owner": "vault_slo_save",
    },
    "02_Observability/risks": {
        "description": "Registro de riesgos con score likelihood×impact (ISO 31000:2018)",
        "owner": "vault_risk_save",
    },
    "02_Observability/quality": {
        "description": "No conformidades NCR-YYYY-NNN y acciones correctivas (ISO 9001:2015 §10.2)",
        "owner": "vault_ncr_save",
    },
    "02_Observability/maintenance": {
        "description": (
            "Notas de mantenimiento del vault: fixes aplicados, depuraciones, limpiezas, "
            "reorganizaciones/reclasificaciones de nodos, y stubs pendientes de triage "
            "(subcarpeta stubs/). Separa artefactos de mantenimiento de los nodos de "
            "contenido para que todo sea rastreable sin contaminar el grafo (AP-36)."
        ),
        "owner": "vault_graph_fix",
    },
    # ── 05_Patterns ───────────────────────────────────────────────────────────
    "05_Patterns/design": {
        "description": "Patrones de diseño GoF: Singleton, Factory, Observer, Strategy, Decorator, Proxy, Command, Adapter, Facade",
        "owner": "vault_pattern_save",
    },
    "05_Patterns/architecture": {
        "description": "Patrones arquitectónicos: MVC, Hexagonal, Event-Driven, CQRS, Microservices, Monolith, BFF, Clean Architecture",
        "owner": "vault_pattern_save",
    },
    "05_Patterns/code": {
        "description": "Patrones de código: Retry, Circuit-Breaker, Cache-Aside, Saga, Idempotency, Rate-Limit, Bulkhead",
        "owner": "vault_pattern_save",
    },
    "05_Patterns/integration": {
        "description": "Patrones de integración: REST, GraphQL, WebSocket, Pub-Sub, Webhook, gRPC, Message-Queue, Batch",
        "owner": "vault_pattern_save",
    },
    # ── 06_Diagrams ───────────────────────────────────────────────────────────
    "06_Diagrams/entity": {
        "description": "Diagramas ER y relaciones entre entidades de dominio (Mermaid erDiagram)",
        "owner": "vault_relation_add",
    },
    "06_Diagrams/component": {
        "description": "Diagramas de componentes y módulos de la aplicación (Mermaid graph TD)",
        "owner": "vault_diagram_save",
    },
    "06_Diagrams/sequence": {
        "description": "Diagramas de secuencia de flujos de ejecución (Mermaid sequenceDiagram)",
        "owner": "vault_diagram_save",
    },
    "06_Diagrams/dependency": {
        "description": "Grafo de dependencias entre paquetes o módulos (Mermaid graph LR)",
        "owner": "vault_diagram_save",
    },
    "06_Diagrams/flow": {
        "description": "Flujos generales, decisiones de proceso, diagramas de negocio (Mermaid flowchart TD)",
        "owner": "vault_diagram_save",
    },
    # ── 07_Knowledge ──────────────────────────────────────────────────────────
    "07_Knowledge/glossary": {
        "description": "Glosario de términos de dominio o negocio con definición y contexto",
        "owner": "vault_knowledge_save",
    },
    "07_Knowledge/apis": {
        "description": "Documentación de APIs: endpoints, auth, rate limits, ejemplos de request/response",
        "owner": "vault_knowledge_save",
    },
    "07_Knowledge/concepts": {
        "description": "Conceptos técnicos específicos del proyecto (no documentación genérica)",
        "owner": "vault_knowledge_save",
    },
    "07_Knowledge/business-rules": {
        "description": "Reglas de negocio no obvias: cuándo aplican, excepciones, quién las definió",
        "owner": "vault_knowledge_save",
    },
    "07_Knowledge/configs": {
        "description": "Configuración importante de herramientas, entornos o servicios",
        "owner": "vault_knowledge_save",
    },
    "07_Knowledge/dependencies": {
        "description": "Paquetes o librerías: nombre, versión, propósito, por qué se eligió, alternativas",
        "owner": "vault_knowledge_save",
    },
    "07_Knowledge/frameworks": {
        "description": "Frameworks usados: rol, convenciones adoptadas, decisiones de configuración",
        "owner": "vault_knowledge_save",
    },
    # ── 08_Runbooks ─────────────────────────────────────────────────────────
    "08_Runbooks/deploy": {
        "description": "Release notes y procedimientos de despliegue (ISO 12207:2017 §6.3.7)",
        "owner": "vault_release_save",
    },
    # ── 09_Infrastructure ───────────────────────────────────────────────────
    "09_Infrastructure/envs": {
        "description": "Variables de entorno estáticas por archivo .env — una nota por env file",
        "owner": "vault_env_save",
    },
    "09_Infrastructure/env-matrix": {
        "description": "Matriz multi-entorno dev/staging/prod/dr/perf (ISO 12207:2017 §6.3.4)",
        "owner": "vault_env_matrix",
    },
    "09_Infrastructure/privacy": {
        "description": "Registros de tratamiento de datos personales GDPR Art.30 (ISO 27701:2019)",
        "owner": "vault_privacy_save",
    },
    # ── 12_Bibliography ─────────────────────────────────────────────────────
    "12_Bibliography/web": {
        "description": "Referencias web: artículos, blog posts, documentación online",
        "owner": "vault_bibliography_save",
    },
    "12_Bibliography/papers": {
        "description": "Papers académicos y técnicos",
        "owner": "vault_bibliography_save",
    },
    "12_Bibliography/docs": {
        "description": "Documentación oficial de herramientas y frameworks",
        "owner": "vault_bibliography_save",
    },
    "12_Bibliography/apis": {
        "description": "Referencias de APIs y especificaciones de interfaces",
        "owner": "vault_bibliography_save",
    },
    "12_Bibliography/books": {
        "description": "Libros técnicos consultados",
        "owner": "vault_bibliography_save",
    },
    # ── 13_Flows ────────────────────────────────────────────────────────────
    "13_Flows/workflow": {
        "description": "Flujos de trabajo y procesos de negocio",
        "owner": "vault_flow_save",
    },
    "13_Flows/pipeline": {
        "description": "Pipelines de CI/CD, datos o procesamiento",
        "owner": "vault_flow_save",
    },
    "13_Flows/lifecycle": {
        "description": "Ciclos de vida de entidades, tickets o deploys",
        "owner": "vault_flow_save",
    },
    "13_Flows/dataflow": {
        "description": "Flujos de datos entre componentes o servicios",
        "owner": "vault_flow_save",
    },
    # ── 15_Tests ────────────────────────────────────────────────────────────
    "15_Tests/unit": {
        "description": "Tests unitarios por módulo o función",
        "owner": "vault_test_save",
    },
    "15_Tests/integration": {
        "description": "Tests de integración entre componentes",
        "owner": "vault_test_save",
    },
    "15_Tests/e2e": {
        "description": "Tests end-to-end sobre flujos completos",
        "owner": "vault_test_save",
    },
    "15_Tests/performance": {
        "description": "Tests de rendimiento, carga y estrés",
        "owner": "vault_test_save",
    },
    "15_Tests/security": {
        "description": "Tests de seguridad y penetración",
        "owner": "vault_test_save",
    },
    "15_Tests/acceptance": {
        "description": "Tests de aceptación con criterios de usuario",
        "owner": "vault_test_save",
    },
    # ── 16_AI_Governance ────────────────────────────────────────────────────
    "16_AI_Governance/decisions": {
        "description": "Decisiones formales de agentes IA con trazabilidad ISO 42001",
        "owner": "vault_ai_decision",
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# Helpers — acceso tipado para cada consumidor
# ──────────────────────────────────────────────────────────────────────────────

# Índices derivados — construidos una sola vez al importar el módulo
_SECTION_BY_FOLDER: Dict[str, Dict] = {s["folder"]: s for s in SECTIONS}

ORDERED_SECTIONS: List[str] = [s["folder"] for s in SECTIONS]


def standard_folders() -> List[str]:
    """Lista de carpetas raíz del vault (para vault_standard_upgrade)."""
    return [s["folder"] for s in SECTIONS]


def section_name(folder: str) -> str:
    """Nombre corto de una sección (para tablas en master index)."""
    sec = _SECTION_BY_FOLDER.get(folder.split("/")[0])
    return sec["name"] if sec else folder


def section_description(folder: str) -> str:
    """Descripción de una sección raíz o subcarpeta.

    Busca primero en SUBFOLDERS (descripción específica), luego en SECTIONS
    (descripción del padre). Fallback: 'Subcarpeta de {parent}'.
    """
    folder_key = folder.replace("\\", "/")
    if folder_key in SUBFOLDERS:
        return SUBFOLDERS[folder_key]["description"]
    top = folder_key.split("/")[0]
    sec = _SECTION_BY_FOLDER.get(top)
    if sec:
        return sec["description"]
    return f"Subcarpeta de {top}"


def section_tool_hint(folder: str) -> Optional[str]:
    """Comando sugerido para poblar una sección vacía."""
    top = folder.replace("\\", "/").split("/")[0]
    sec = _SECTION_BY_FOLDER.get(top)
    return sec["tool_hint"] if sec else None


def folder_owner(folder: str) -> Optional[str]:
    """Retorna el tool owner de un subfolder, o None si no está registrado."""
    return SUBFOLDERS.get(folder.replace("\\", "/"), {}).get("owner")


def assert_folder_owner(tool_name: str, folder: str) -> None:
    """Lanza ValueError si otro tool ya declara ownership del folder.

    Llamar desde el FOLDER de cada tool para detectar colisiones en import time.
    No falla si el folder no está en el registro (sección raíz compartida es válida).
    """
    owner = folder_owner(folder)
    if owner is not None and owner != tool_name:
        raise ValueError(
            f"Conflicto de ownership: '{tool_name}' intenta escribir en '{folder}' "
            f"que pertenece a '{owner}'. Registrar un subfolder exclusivo en vault_registry.py."
        )


def check_folder_collisions() -> List[Dict[str, str]]:
    """Detecta todos los conflictos de ownership. Usado por vault_spec_validate."""
    seen: Dict[str, str] = {}
    conflicts = []
    for folder, meta in SUBFOLDERS.items():
        owner = meta.get("owner") or ""
        if not owner:
            continue
        if folder in seen and seen[folder] != owner:
            conflicts.append(
                {
                    "folder": folder,
                    "owner_a": seen[folder],
                    "owner_b": owner,
                }
            )
        else:
            seen[folder] = owner
    return conflicts

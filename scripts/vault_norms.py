#!/usr/bin/env python3
"""
Vault Norms — Catálogo canónico de normas del estándar Vault Obsidian Architecture.

Gestiona AP-XX (anti-patrones) y PAT-X (patrones recomendados): lista, filtra,
muestra detalles, escanea notas para detectar normas aplicables, aplica referencias
de normas a frontmatter, y reconstruye norm-registry.json.

Usage:
    python vault_norms.py --list
    python vault_norms.py --list --type ap --severity critical
    python vault_norms.py --list --category linking --sort severity
    python vault_norms.py --show AP-22
    python vault_norms.py --scan --path "07_Knowledge/concepts/jwt.md"
    python vault_norms.py --apply AP-22 --path "03_Decisions/adr-001.md"
    python vault_norms.py --rebuild
"""

import argparse
import json
import re
import sys
from vault_errors import wrap_main
from vault_io import atomic_write_json, VAULT_ROOT
from pathlib import Path
from typing import Any, Dict, List, Optional

NORM_REGISTRY = VAULT_ROOT / "00_System" / "norm-registry.json"

# ─── Catálogo canónico (fuente de verdad) ──────────────────────────────────────
#
# type:        antipattern | pattern
# category:    content-quality | structure | frontmatter | linking | process
# severity:    critical | high | medium | low  (N/A para patterns)
# enforcement: guard | audit | guard+audit | manual | recommended
#   - guard:     vault_write rechaza en tiempo de escritura
#   - audit:     vault_audit detecta retrospectivamente
#   - guard+audit: ambos
#   - manual:    DEPRECADO (v38) — toda norma debe tener guard o audit; las no
#                automatizables usan audit heurístico (vault_drift_detect)
#   - recommended: patrón positivo a seguir

NORM_CATALOG: List[Dict[str, Any]] = [
    # ── Anti-patrones ──────────────────────────────────────────────────────────
    {
        "code": "AP-01",
        "name": "Documentación alucinada",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Documentar herramientas, endpoints, funciones o comportamientos que no existen "
            "en el código real. El agente genera información convincente pero incorrecta."
        ),
        "signal": "Referencias a scripts/tools que no existen en el repo; funciones con firmas que no coinciden con el código.",
        "prevention": "Verificar existencia real antes de documentar. vault_read + grep sobre el código fuente.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_drift_detect"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-02",
        "name": "Proliferación de versiones del mismo documento",
        "type": "antipattern",
        "category": "structure",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Múltiples notas describiendo la misma entidad: status-v1.md, status-v2.md, "
            "status-final.md, status-final2.md. Variantes: same-folder (AP-02), "
            "cross-folder (AP-18), canonical-shadow (AP-17)."
        ),
        "signal": "vault_audit reporta canonicalShadow o crossFolderDuplicates.",
        "prevention": "Una nota por entidad. Usar .history/ para versiones anteriores (vault_write lo gestiona automáticamente).",
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-03",
        "name": "Stubs sin política de expansión",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Nota con contenido real pero incompleto (≥3 líneas reales) sin fecha de expansión. "
            "Distinción con AP-11: AP-03 tiene información útil, AP-11 no tiene ningún contenido real."
        ),
        "signal": "vault_audit reporta notas con status:stub sin campo expand_by o con expand_by vencido.",
        "prevention": "Agregar meta: {status: stub, expand_by: YYYY-MM-DD} al crear stubs. Enriquecer en cada sesión.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-04",
        "name": "Features aspiracionales documentadas como implementadas",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Documentar comportamientos futuros o planeados como si ya existieran. "
            "Confunde al agente sobre el estado real del sistema."
        ),
        "signal": "Notas sin campo status o con status:planned que describen funcionalidad en presente.",
        "prevention": "Usar status: planned/in-progress/implemented. Nunca describir en presente algo que no está deployado.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_drift_detect"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-05",
        "name": "Múltiples fuentes de verdad para el mismo dato",
        "type": "antipattern",
        "category": "structure",
        "severity": "critical",
        "enforcement": "audit",
        "description": (
            "El mismo dato (IP, URL, versión, configuración) aparece en múltiples notas "
            "con valores inconsistentes. Causa decisiones del agente basadas en datos erróneos."
        ),
        "signal": "IPs/URLs/versiones que difieren entre notas del mismo proyecto.",
        "prevention": "PAT-1 (canonical source anchoring): una nota canónica por dato, las demás hacen [[wiki-link]] a ella.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_graph_inspect"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-06",
        "name": "Templates sin instancias reales",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "low",
        "enforcement": "audit",
        "description": (
            "Archivos de template (SLOs, métricas, alertas, ADRs) que existen en el vault "
            "pero nunca se han instanciado con datos reales."
        ),
        "signal": "Notas con status:template que no tienen notas derivadas con wiki-link hacia ellas.",
        "prevention": "Si un template no tiene instancias en 30 días, moverlo a 10_Migrated/ o eliminarlo.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_norms --audit"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-07",
        "name": "ADRs incompletos",
        "type": "antipattern",
        "category": "process",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "ADRs (Architecture Decision Records) sin secciones Contexto, Opciones evaluadas "
            "y Consecuencias. Un ADR sin estas secciones no aporta valor de auditoría."
        ),
        "signal": "Notas en 03_Decisions/ sin secciones ## Contexto, ## Opciones, ## Consecuencias.",
        "prevention": "Usar vault_write con template de ADR completo. vault_audit puede extenderse para validar secciones.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_norms --audit"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-08",
        "name": "Documentación anclada a versiones obsoletas",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Notas que mencionan versiones específicas de librerías, APIs o protocolos que ya "
            "fueron actualizadas, sin indicar que el contenido puede estar desactualizado."
        ),
        "signal": "Notas con versiones hardcodeadas (v1.2.3) y updatedAt > 90 días.",
        "prevention": "Agregar campo version_pinned al frontmatter con la versión referenciada. vault_audit puede alertar.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_drift_detect"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-09",
        "name": "Runbooks fuera de estructura",
        "type": "antipattern",
        "category": "process",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Procedimientos operativos guardados en carpetas genéricas (07_Knowledge/, 01_Projects/) "
            "en lugar de 06_Runbooks/. Dificulta la localización en incidentes."
        ),
        "signal": "Notas con title que contiene 'runbook', 'procedure', 'how-to' fuera de 06_Runbooks/.",
        "prevention": "Todo runbook va en 06_Runbooks/{proyecto}/. vault_migrate_docs para moverlos.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_norms --audit"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-10",
        "name": "Migración sin plan de rollback",
        "type": "antipattern",
        "category": "process",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Ejecutar vault_migrate_docs sin tener vault_migrate_rollback disponible "
            "o sin snapshot previo. Si la migración introduce errores, no hay manera de revertir."
        ),
        "signal": "vault_migrate_docs ejecutado sin llamar vault_drift_detect --snapshot primero.",
        "prevention": "PAT-4 (phased audit): siempre snapshot → migrate → verify → rollback si falla.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_norms --audit", "vault_migrate_rollback"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-11",
        "name": "Skeleton files — frontmatter válido, contenido vacío",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "critical",
        "enforcement": "guard",
        "description": (
            "Nota creada con frontmatter correcto pero cuerpo vacío o solo con TODO/placeholders. "
            "El agente indexa la nota pero no recibe información útil de ella. "
            "Distinción con AP-03: AP-11 = 0 líneas reales; AP-03 = ≥3 líneas reales pero incompleto."
        ),
        "signal": "vault_write rechaza con error_code: content_too_short.",
        "prevention": "vault_write exige ≥3 líneas de contenido real (00_System exempt). No crear notas que no estén listas.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-12",
        "name": "Frontmatter inconsistente entre notas del mismo tipo",
        "type": "antipattern",
        "category": "frontmatter",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Notas del mismo tipo con campos faltantes, tipos mezclados "
            "(timestamp con/sin comillas, migratedFrom relativo vs absoluto). "
            "Rompe vault_list, búsquedas y deduplicación."
        ),
        "signal": "vault_validate reporta campos faltantes. vault_audit detecta inconsistencias de tipo.",
        "prevention": "vault_write como único punto de creación; nunca editar frontmatter manualmente.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_validate", "vault_audit"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-13",
        "name": "Timestamps inválidos o incompletos en frontmatter",
        "type": "antipattern",
        "category": "frontmatter",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Timestamps solo con fecha (2026-05-07), con '...' literal, sin zona horaria "
            "o en formato no ISO 8601. vault_diff y vault_timeline no pueden ordenar versiones."
        ),
        "signal": "vault_audit detecta createdAt/updatedAt que no coinciden con patrón ISO 8601.",
        "prevention": "vault_write genera timestamps con datetime.now(timezone.utc).isoformat() automáticamente.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-14",
        "name": "Wiki-links rotos o vacíos",
        "type": "antipattern",
        "category": "linking",
        "severity": "critical",
        "enforcement": "guard+audit",
        "description": (
            "[[]] vacíos, [[ ]] con espacio, links a notas renombradas/eliminadas, "
            "o links con path (AP-21). Dos causas raíz: (a) wrong stem, (b) path-anchored. "
            "El agente sigue links que no resuelven."
        ),
        "signal": "vault_audit reporta brokenLinks[]. vault_write rechaza [[]] y [[folder/nota]].",
        "prevention": "Solo escribir [[wiki-link]] cuando la nota destino ya existe. vault_search() antes de linkar.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_audit", "vault_graph"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-15",
        "name": "Archivos externos depositados en la raíz del vault",
        "type": "antipattern",
        "category": "structure",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Archivos .md colocados directamente en vault-{nombre}/ en lugar de en secciones "
            "numeradas. vault_graph parsea sus [[wiki-links]] como broken links reales del proyecto."
        ),
        "signal": "vault_graph reporta decenas de orphans y broken links falsos.",
        "prevention": "Layout correcto: vault/ y scripts/ son hermanos, nunca anidados. Solo 00_System…11_Code y 99_Index son destinos válidos.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_norms --audit"],
        "introduced_version": "v20",
    },
    {
        "code": "AP-16",
        "name": "Sin identificador de agente en frontmatter",
        "type": "antipattern",
        "category": "frontmatter",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Nota sin campo agent: en el frontmatter. Sin este campo es imposible auditar "
            "qué agente creó o modificó la nota (PAT-5: frontmatter as provenance chain)."
        ),
        "signal": "vault_audit reporta notas sin campo agent.",
        "prevention": "vault_write agrega agent: automáticamente. Valores estándar: claude, system, human.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v20",
    },
    {
        "code": "AP-17",
        "name": "Canonical-shadow duplication",
        "type": "antipattern",
        "category": "structure",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Par de notas con SequenceMatcher ratio ≥ 0.85 en títulos. "
            "Típicamente una nota thin creada cuando ya existía la canónica rica. "
            "Penalización vault_audit: −2 por par."
        ),
        "signal": "vault_audit reporta canonicalShadow[] con similarity ≥ 0.85.",
        "prevention": "PAT-3: buscar con vault_search() antes de crear. Si existe una nota similar, enriquecer en lugar de crear.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v25",
    },
    {
        "code": "AP-18",
        "name": "Cross-folder content duplication",
        "type": "antipattern",
        "category": "structure",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Mismo contenido byte-idéntico (MD5) en carpetas distintas. "
            "Penalización vault_audit: −3 por par."
        ),
        "signal": "vault_audit reporta crossFolderDuplicates[].",
        "prevention": "PAT-1: una nota canónica, las demás hacen [[wiki-link]]. Usar vault_change_log --action deleted antes de borrar.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v25",
    },
    {
        "code": "AP-19",
        "name": "Shadow indexing",
        "type": "antipattern",
        "category": "structure",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Índices de sección creados manualmente, duplicando lo que vault_section_index genera "
            "automáticamente. Los índices manuales rotan en AP-02 con el tiempo."
        ),
        "signal": "Múltiples index.md o README.md en una sección que no fueron generados por vault_section_index.",
        "prevention": "vault_section_index es la única herramienta para índices. No editar index.md manualmente.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_norms --audit"],
        "introduced_version": "v25",
    },
    {
        "code": "AP-20",
        "name": "Deceptive skeleton (empty-list)",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "critical",
        "enforcement": "guard",
        "description": (
            "Nota que pasa el content gate de 3 líneas porque tiene bullets, "
            "pero >50% de los bullets están vacíos (- , - [ ], - []). "
            "Variante de AP-11 que evade el guard básico."
        ),
        "signal": "vault_write rechaza con error_code: content_empty_list.",
        "prevention": "vault_write rechaza si empty_bullets/total_bullets > 0.5. Completar los bullets antes de guardar.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": [],
        "introduced_version": "v25",
    },
    {
        "code": "AP-21",
        "name": "Path-anchored wiki-links",
        "type": "antipattern",
        "category": "linking",
        "severity": "critical",
        "enforcement": "guard",
        "description": (
            "[[carpeta/nota]] en lugar de [[nota]]. Obsidian no resuelve paths, "
            "solo stems. El link siempre aparece roto en el grafo."
        ),
        "signal": "vault_write rechaza con error_code: path_anchored_wikilinks.",
        "prevention": "Siempre [[stem]] o [[stem|título visible]]. vault_section_index genera solo [[stem|título]] desde v25.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": [],
        "introduced_version": "v25",
    },
    {
        "code": "AP-22",
        "name": "Bracket sanity — corchetes desbalanceados o vacíos",
        "type": "antipattern",
        "category": "linking",
        "severity": "critical",
        "enforcement": "guard+audit",
        "description": (
            "Corchetes [[ sin ]] matching, o [[]] vacíos. "
            "Se detecta fuera de bloques de código. "
            "vault_write bloquea (hard stop). "
            "vault_write también advierte (non-blocking) si [[target]] no existe: ghost_links[]."
        ),
        "signal": "vault_write rechaza con error_code: malformed_wikilinks. vault_audit reporta malformedWikilinks[].",
        "prevention": "Cada [[ debe tener su ]]. Nunca escribir [[]] vacíos. Verificar que el target exista antes de linkar.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v29",
    },
    # ── Patrones recomendados ──────────────────────────────────────────────────
    {
        "code": "PAT-1",
        "name": "Canonical source anchoring",
        "type": "pattern",
        "category": "structure",
        "severity": "N/A",
        "enforcement": "recommended",
        "description": (
            "Un dominio = una nota canónica rica. Todas las referencias desde otros contextos "
            "son [[wiki-links]] a esa nota canónica, nunca copias del contenido."
        ),
        "signal": "vault_audit muestra 0 canonicalShadow y 0 crossFolderDuplicates.",
        "prevention": "N/A — es el patrón correcto. Aplicar siempre al crear documentación.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v25",
    },
    {
        "code": "PAT-2",
        "name": "Stub enrichment gradient",
        "type": "pattern",
        "category": "content-quality",
        "severity": "N/A",
        "enforcement": "recommended",
        "description": (
            "Un stub con ≥3 líneas reales se enriquece progresivamente en cada sesión que lo toca. "
            "La eliminación solo aplica a skeletons (AP-11) y deceptive skeletons (AP-20)."
        ),
        "signal": "Stubs del vault tienen status:stub y fecha expand_by.",
        "prevention": "N/A — es el patrón correcto.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v25",
    },
    {
        "code": "PAT-3",
        "name": "Duplicate chain resolution",
        "type": "pattern",
        "category": "structure",
        "severity": "N/A",
        "enforcement": "recommended",
        "description": (
            "Algoritmo estándar para resolver duplicados: identificar canónica (más backlinks, "
            "más contenido, ubicación más apropiada) → change_log --action deleted → "
            "mover a 10_Migrated/ → actualizar wiki-links rotos → verificar con vault_audit."
        ),
        "signal": "vault_audit canonicalShadow reducido después de aplicar.",
        "prevention": "N/A — es el algoritmo de resolución.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v25",
    },
    {
        "code": "PAT-4",
        "name": "Phased audit execution",
        "type": "pattern",
        "category": "process",
        "severity": "N/A",
        "enforcement": "recommended",
        "description": (
            "Las auditorías masivas se ejecutan en 4 fases atómicas: "
            "1-Snapshot (vault_drift_detect --snapshot), 2-Detección (vault_audit), "
            "3-Resolución (vault_write, vault_change_log), 4-Verificación (vault_drift_detect --report)."
        ),
        "signal": "0 regresiones entre snapshot y estado final.",
        "prevention": "N/A — es el protocolo de auditoría.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_drift_detect"],
        "introduced_version": "v25",
    },
    {
        "code": "PAT-5",
        "name": "Frontmatter as provenance chain",
        "type": "pattern",
        "category": "frontmatter",
        "severity": "N/A",
        "enforcement": "recommended",
        "description": (
            "Los campos id + createdAt + updatedAt + agent + migratedFrom (si aplica) "
            "forman una cadena de custodia completa. Sin esta cadena es imposible auditar "
            "de dónde vino un dato o qué agente lo introdujo."
        ),
        "signal": "vault_audit reporta 0 notas sin campo agent.",
        "prevention": "N/A — vault_write genera estos campos automáticamente.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v25",
    },
    # ── Anti-patrón AP-23 ──────────────────────────────────────────────────────
    {
        "code": "AP-23",
        "name": "Note complexity ceiling — nota demasiado larga",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Una nota con más de 500 líneas de contenido real se vuelve difícil de mantener "
            "y consume excesivo contexto del LLM. Debe dividirse en sub-notas canónicas "
            "interconectadas con [[wiki-links]] desde la nota original."
        ),
        "signal": "vault_write advierte en la respuesta con ap23_warning cuando content > 500 líneas. "
        "vault_norms --scan reporta AP-23 en notas largas.",
        "prevention": (
            "Al superar 500 líneas, crear sub-notas en la misma carpeta y reemplazar la sección "
            "con [[sub-nota|título]]. La nota original actúa como índice/resumen."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_write", "vault_norms"],
        "introduced_version": "v30",
    },
    # ── Anti-patrón AP-24 ──────────────────────────────────────────────────────
    {
        "code": "AP-24",
        "name": "Bracket imbalance — corchetes sin pareja, anidados o invertidos",
        "type": "antipattern",
        "category": "linking",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Wiki-links malformados por desbalance de corchetes. Tres variantes: "
            "(1) apertura sin cierre ([[nota sin ]]), (2) cierre sin apertura (]] sin [[), "
            "(3) anidamiento incorrecto ([[[[nota]]]] o [[nota]]]]). En Obsidian el link "
            "se renderiza como texto literal, no como enlace navegable. Rompe la trazabilidad "
            "y produce falsos negativos en vault_audit --broken-links."
        ),
        "signal": (
            "vault_write content_gate detecta balance desigual en línea y rechaza la escritura. "
            "vault_audit penaliza con -5 por nota afectada. vault_fix_brackets intenta auto-fix "
            "(eliminación de corchetes extra o inyección de cierre)."
        ),
        "prevention": (
            "Usar siempre el formato [[stem]] o [[stem|alias]]. Validar balance con "
            "vault_fix_brackets --fix antes de commit. El content_gate de vault_write "
            "rechaza contenido con bracket imbalance."
        ),
        "tools_enforcing": ["vault_write", "vault_fix_brackets"],
        "tools_detecting": ["vault_audit", "vault_fix_brackets"],
        "introduced_version": "v34.2",
    },
    # ── Anti-patrón AP-25 ──────────────────────────────────────────────────────
    {
        "code": "AP-25",
        "name": "Mermaid diagram syntax errors — nodos/tipos no definidos",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Diagramas Mermaid con sintaxis inválida: tipos de diagrama no reconocidos "
            "(unknown_type), nodos referenciados pero no definidos (undefined_node), "
            "flechas huérfanas, o sintaxis de etiquetas incorrecta. El diagrama no se "
            "renderiza en Obsidian y pierde su valor documental."
        ),
        "signal": (
            "vault_audit detecta errores con vault_mermaid_check.scan_vault() y los reporta "
            "como AP-25 con penalización -2 por error. La nota se marca como mermaidError "
            "en el output del audit."
        ),
        "prevention": (
            "Validar con vault_mermaid_check antes de commit. Usar tipos conocidos "
            "(graph TD, flowchart LR, sequenceDiagram, classDiagram, etc.). "
            "Asegurar que cada nodo referenciado en una flecha exista como definición previa."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit", "vault_mermaid_check"],
        "introduced_version": "v34.2",
    },
    # ── Anti-patrón AP-31 ──────────────────────────────────────────────────────
    {
        "code": "AP-31",
        "name": "Grafo sin tipos semanticos — edges sin predicate explícito",
        "type": "antipattern",
        "category": "linking",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Todas las aristas del grafo usan el mismo tipo 'wiki-link' sin distinguir "
            "semántica: depends_on, implements, extends, calls, documents, etc. "
            "Sin predicates tipados, el analisis de impacto y las busquedas semanticas "
            "no pueden filtrar por tipo de relacion. "
            "La solucion es mergear las relaciones de entidad (vault_relation_add) y "
            "codigo (vault_code_relation) en el grafo para enriquecerlo con predicates."
        ),
        "signal": (
            "vault_audit detecta edges sin predicate o con predicate='wiki-link' como "
            "unico tipo en graph.json. Penaliza -3 por cada 100 edges sin predicates "
            "tipados (solo si existen relaciones de entidad o codigo sin mergear)."
        ),
        "prevention": (
            "Ejecutar vault_graph --typed o vault_graph_merge periodicamente para "
            "enriquecer el grafo con predicates. Toda relacion registrada via "
            "vault_relation_add o vault_code_relation debe reflejarse en graph-enriched.json."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit", "vault_graph_merge"],
        "introduced_version": "v37",
    },
    # ── Anti-patrón AP-32 ──────────────────────────────────────────────────────
    {
        "code": "AP-32",
        "name": "Relaciones tipadas sin predicate valido en la ontologia",
        "type": "antipattern",
        "category": "linking",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Una relacion registrada en entity relations o code relations usa un "
            "relationType/type que no existe en vault-ontology.json. Esto produce "
            "edges que no pueden interpretarse semanticamente en el grafo enriquecido. "
            "Ej: relationType='inherits' cuando el predicate canonico es 'extends'."
        ),
        "signal": (
            "vault_graph_merge reporta unknown_predicates[] con el predicate invalido "
            "y la fuente (entity/code). Sugiere el predicate canonico mas cercano."
        ),
        "prevention": (
            "Usar solo predicates del vocabulario canonico en vault-ontology.json. "
            "Para entity relations: has_one, has_many, belongs_to, many_to_many, "
            "implements, extends, depends_on, uses, calls, owns, aggregates. "
            "Para code relations: imports, extends, implements, calls, uses, re-exports, depends_on."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_graph_merge", "vault_audit"],
        "introduced_version": "v37",
    },
    # ── Anti-patrón AP-33 ──────────────────────────────────────────────────────
    {
        "code": "AP-33",
        "name": "Predicado no canonico — sinonimo no normalizado",
        "type": "antipattern",
        "category": "linking",
        "severity": "low",
        "enforcement": "audit",
        "description": (
            "Las relaciones de entidad usan `relationType` y las de codigo usan `type` "
            "para el mismo concepto semantico. Ademas, predicates que semanticamente "
            "son equivalentes deben unificarse: `imports` en codigo ≈ `depends_on` "
            "a nivel build-time. La ontologia define el mapeo de sinonimos."
        ),
        "signal": (
            "vault_graph_merge normaliza automaticamente y reporta normalized_predicates[] "
            "con el mapeo aplicado. vault_audit puede reportar instancias donde el "
            "predicate original no era canonico."
        ),
        "prevention": (
            "Al registrar relaciones, usar predicates del vocabulario canonico. "
            "La ontologia maneja el mapeo relationType→predicate y type→predicate "
            "automaticamente. No requiere accion manual."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_graph_merge"],
        "introduced_version": "v37",
    },
    # ── Anti-patrón AP-34 ──────────────────────────────────────────────────────
    {
        "code": "AP-34",
        "name": "Relacion tipada huerfana — endpoint inexistente en el vault",
        "type": "antipattern",
        "category": "linking",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Una relacion tipada (entity o code) referencia un endpoint que no existe "
            "como nota en el vault. Ej: relacion `User -- has_many --> Order` donde "
            "no existen `User.md` ni `Order.md`. El grafo enriquecido tendra edges "
            "hacia nodos fantasma que nunca resolveran."
        ),
        "signal": (
            "vault_audit detecta orphan_typed_relations[] listando la relacion y "
            "los endpoints faltantes. vault_graph_merge reporta unresolved_entities[]."
        ),
        "prevention": (
            "SP-02: verificar que los endpoints existan antes de registrar la relacion. "
            "Ejecutar vault_search o vault_list para confirmar que las notas "
            "referenciadas en fromEntity/toEntity existen en el vault."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit", "vault_graph_merge"],
        "introduced_version": "v37",
    },
    # ── Anti-patrón AP-35 ──────────────────────────────────────────────────────
    {
        "code": "AP-35",
        "name": "Silos de relacion — sistemas de grafos aislados",
        "type": "antipattern",
        "category": "structure",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "El vault mantiene tres sistemas de relaciones en silos aislados: "
            "(a) wiki-links en graph.json, (b) entity relations en "
            "06_Diagrams/entity/*-relations.json, (c) code relations en "
            "11_Code/.code-index.json. Ninguno de estos sistemas se integra "
            "con los otros, produciendo un grafo de conocimiento fragmentado. "
            "vault_impact y BFS solo ven wiki-links, ignorando relaciones "
            "semanticas ricas registradas en los otros sistemas."
        ),
        "signal": (
            "vault_audit reporta silo_flags[]: entity_relations sin mergear "
            "(AP-35-entity), code_relations sin mergear (AP-35-code), y "
            "graph_enriched_outdated si el enriquecido tiene >24h."
        ),
        "prevention": (
            "Ejecutar vault_graph_merge periodicamente (recomendado: cada sesion "
            "o cada vez que se registren nuevas relaciones). vault_graph --typed "
            "genera graph-enriched.json que unifica los tres sistemas."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit", "vault_graph_merge"],
        "introduced_version": "v37",
    },
    {
        "code": "AP-36",
        "name": "Contención e idempotencia — side-effects fuera del vault o no rastreables",
        "type": "antipattern",
        "category": "structure",
        "severity": "critical",
        "enforcement": "guard+audit",
        "description": (
            "Toda operación de tooling debe: (1) escribir ÚNICAMENTE dentro del vault root "
            "(backups, traces, locks, stubs, logs incluidos); (2) ser idempotente — ejecutarla "
            "dos veces no duplica artefactos ni carpetas; (3) dejar sus artefactos indexados o "
            "en ubicaciones registradas (vault_registry) para rastreabilidad. Casos históricos: "
            "vault-backups escrito en el abuelo del repo, 00_System/99_Index generados fuera "
            "del vault por detección de root defectuosa, .bak junto a nodos de contenido."
        ),
        "signal": (
            "Carpetas vault-backups/00_System/99_Index como hermanos del vault; archivos .bak/.tmp "
            "dentro de secciones de contenido; secciones sin index.md."
        ),
        "prevention": (
            "Rutas de salida derivadas SIEMPRE de VAULT_ROOT (nunca de __file__ ni cwd). "
            "Artefactos de mantenimiento van a 02_Observability/maintenance/ o 00_System/. "
            "vault_norms --audit detecta artefactos sueltos y secciones sin índice."
        ),
        "tools_enforcing": ["vault_section_index (guard CN-02)", "vault_io.assert_within_vault"],
        "tools_detecting": ["vault_norms --audit"],
        "introduced_version": "v38",
    },
    # ── Patrón PAT-6 ───────────────────────────────────────────────────────────
    {
        "code": "PAT-6",
        "name": "Semantic graph enrichment — enriquecimiento periodico del grafo",
        "type": "pattern",
        "category": "linking",
        "severity": "N/A",
        "enforcement": "recommended",
        "description": (
            "Ejecutar vault_graph --typed al final de cada sesion productiva para "
            "generar graph-enriched.json con predicates semanticos unificados. "
            "El grafo enriquecido combina wiki-links, entity relations y code relations "
            "en un solo grafo consultable con filtros por predicate, cardinalidad "
            "y tipo de nodo. Esto habilita busquedas de conocimiento semanticas "
            "y analisis de impacto con tipos."
        ),
        "signal": "graph-enriched.json existe y tiene updated_at < 24 horas.",
        "prevention": (
            "N/A — es el patron correcto. Agregar vault_graph --typed al session "
            "protocol como paso automatico antes de vault_audit."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_graph_merge", "vault_audit"],
        "introduced_version": "v37",
    },
    # ── Protocolo de sesión SP-XX ──────────────────────────────────────────────
    {
        "code": "SP-01",
        "name": "Delete protocol — change_log obligatorio antes de eliminar",
        "type": "antipattern",
        "category": "session-protocol",
        "severity": "critical",
        "enforcement": "audit",
        "description": (
            "Antes de eliminar cualquier nota del vault, el agente DEBE llamar: "
            "vault_change_log --action deleted --path <nota> --reason <motivo>. "
            "Sin este registro, la nota desaparece sin rastro auditado."
        ),
        "signal": "Nota eliminada que no aparece en 00_System/.change-log.json con action: deleted.",
        "prevention": (
            "Regla de gobernanza: verificar en .change-log.json antes de delete. "
            "Si no hay entrada → llamar vault_change_log primero, luego eliminar."
        ),
        "tools_enforcing": ["vault_change_log"],
        "tools_detecting": ["vault_norms --audit"],
        "introduced_version": "v30",
    },
    {
        "code": "SP-02",
        "name": "Forward-link verification — buscar antes de linkar",
        "type": "antipattern",
        "category": "session-protocol",
        "severity": "high",
        "enforcement": "guard",
        "description": (
            "Antes de escribir [[nombre-nota]] en contenido, verificar que la nota destino "
            "ya existe: vault_search(query:'nombre-nota'). Si no hay resultado, escribir "
            "en texto plano hasta que la nota exista. "
            "vault_write advierte con ghost_links[] (no bloquea) si el target no existe."
        ),
        "signal": "vault_write retorna ghost_links[] en la respuesta de éxito.",
        "prevention": "vault_search() antes de cada [[wiki-link]] nuevo. No crear links especulativos.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_graph", "vault_audit"],
        "introduced_version": "v30",
    },
    {
        "code": "SP-03",
        "name": "Session snapshot pattern — delta antes de operaciones masivas",
        "type": "antipattern",
        "category": "session-protocol",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Antes de cualquier operación masiva (migración, rename en lote, vault_tags --rename "
            "múltiple, delete en lote), capturar snapshot con vault_delta --snapshot. "
            "Permite detectar regresiones y calcular impacto real de la operación."
        ),
        "signal": "Operación masiva sin snapshot previo → no hay baseline para detectar regresiones.",
        "prevention": (
            "PAT-4 (phased audit): snapshot → operación → vault_audit() → comparar score. "
            "vault_delta --snapshot antes de cada sesión con cambios masivos."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_backup"],
        "introduced_version": "v30",
    },
    # ── Convenciones de nomenclatura CN-XX ────────────────────────────────────
    {
        "code": "CN-01",
        "name": "Kebab-case filenames — nombres de archivo en minúsculas con guiones",
        "type": "antipattern",
        "category": "convention",
        "severity": "high",
        "enforcement": "guard",
        "description": (
            "Los archivos .md del vault deben usar kebab-case: minúsculas, palabras separadas "
            "por guiones, sin espacios ni caracteres especiales. "
            "vault_write aplica slugify() automáticamente al título para generar el filename. "
            "Ej: 'ADR-001 Auth Decision' → adr-001-auth-decision.md."
        ),
        "signal": "Archivos con espacios, mayúsculas o caracteres especiales en el nombre.",
        "prevention": "Siempre usar vault_write para crear notas. Nunca crear archivos .md directamente.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_validate"],
        "introduced_version": "v30",
    },
    {
        "code": "CN-02",
        "name": "Numbered folder structure — secciones numeradas como únicos destinos",
        "type": "antipattern",
        "category": "convention",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Solo las secciones numeradas del registro canónico (vault_registry.SECTIONS, "
            "fuente de verdad única — PAT-1) son destinos válidos para notas. "
            "Crear carpetas ad-hoc o escribir en la raíz viola este estándar (ver AP-15). "
            "NO duplicar la lista aquí: consultarla con vault_folder_registry o vault_registry."
        ),
        "signal": "Carpeta con nombre que no sigue el patrón NN_Nombre en el vault.",
        "prevention": "Elegir la sección más apropiada del vocabulario estándar. AP-15 para raíz del vault.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_section_index (guard)", "vault_norms --audit"],
        "introduced_version": "v30",
    },
    {
        "code": "CN-03",
        "name": "Standard status vocabulary — vocabulario canónico de meta.status",
        "type": "antipattern",
        "category": "convention",
        "severity": "low",
        "enforcement": "audit",
        "description": (
            "El campo meta.status (o status en frontmatter) debe usar solo valores de "
            "vault_norms.STATUS_VOCAB (fuente única, v38 — unifica el vocabulario CN-03 "
            "original con el ciclo de vida del spec §status): planned | draft | in-progress | "
            "reviewed | approved | implemented | verified | deprecated | obsolete | archived | "
            "stub | template. Valores fuera del vocabulario rompen filtros de vault_list y vault_audit."
        ),
        "signal": "vault_list filtra por status y retorna 0 cuando el valor es no-estándar.",
        "prevention": "Usar solo valores de STATUS_VOCAB. vault_norms --audit los valida (CN-03).",
        "tools_enforcing": [],
        "tools_detecting": ["vault_norms --audit"],
        "introduced_version": "v30",
    },
]

# Índice rápido por código
_NORM_BY_CODE: Dict[str, Dict[str, Any]] = {n["code"]: n for n in NORM_CATALOG}

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "N/A": 4}
_CATEGORY_ORDER = {
    "linking": 0,
    "content-quality": 1,
    "structure": 2,
    "frontmatter": 3,
    "process": 4,
    "session-protocol": 5,
    "convention": 6,
}


# ─── Funciones públicas ────────────────────────────────────────────────────────


def compute_norm_refs(folder: str, content: str, wiki_links: List[str]) -> List[str]:
    """
    Compute the list of norm codes that apply to a note based on its folder and content.
    Used by vault_write to auto-embed norm_refs in frontmatter.

    Rules:
      - Universal (every note):    AP-11, AP-12, AP-13, AP-16, CN-01, CN-02, SP-01
      - Wiki-links present:        + AP-14, AP-21, AP-22, SP-02
      - Bullet-heavy content:      + AP-20
      - 03_Decisions/ folder:      + AP-07
      - 06_Runbooks/ folder:       + AP-09 excluded (note IS in correct folder)
      - Content > 500 lines:       + AP-23 (advisory)
    """
    refs: set = {"AP-11", "AP-12", "AP-13", "AP-16", "CN-01", "CN-02", "SP-01"}

    if wiki_links:
        refs.update({"AP-14", "AP-21", "AP-22", "SP-02"})

    bullets = re.findall(r"^\s*[-*]\s*(.*)", content, re.MULTILINE)
    if bullets:
        refs.add("AP-20")

    folder_lower = folder.lower()
    if folder_lower.startswith("03_decisions") or "decisions" in folder_lower:
        refs.add("AP-07")

    if len(content.split("\n")) > 500:
        refs.add("AP-23")

    return sorted(refs)


def vault_norms_list(
    norm_type: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    sort_by: str = "code",
) -> Dict[str, Any]:
    """List norms with optional filters."""
    norms = list(NORM_CATALOG)

    if norm_type:
        t = norm_type.lower()
        if t in ("ap", "antipattern"):
            norms = [n for n in norms if n["type"] == "antipattern"]
        elif t in ("pat", "pattern"):
            norms = [n for n in norms if n["type"] == "pattern"]

    if category:
        norms = [n for n in norms if n["category"] == category.lower()]

    if severity:
        norms = [n for n in norms if n["severity"].lower() == severity.lower()]

    if sort_by == "severity":
        norms.sort(key=lambda n: (_SEVERITY_ORDER.get(n["severity"], 9), n["code"]))
    elif sort_by == "category":
        norms.sort(key=lambda n: (_CATEGORY_ORDER.get(n["category"], 9), n["code"]))
    elif sort_by == "enforcement":
        norms.sort(key=lambda n: (n["enforcement"], n["code"]))
    else:
        norms.sort(key=lambda n: n["code"])

    rows = []
    for n in norms:
        rows.append(
            {
                "code": n["code"],
                "name": n["name"],
                "type": n["type"],
                "category": n["category"],
                "severity": n["severity"],
                "enforcement": n["enforcement"],
            }
        )

    return {
        "ok": True,
        "total": len(rows),
        "norms": rows,
    }


def vault_norms_show(code: str) -> Dict[str, Any]:
    """Show full details of a single norm by code."""
    code = code.upper()
    norm = _NORM_BY_CODE.get(code)
    if not norm:
        return {
            "ok": False,
            "error": f"Norm '{code}' not found. Valid codes: {sorted(_NORM_BY_CODE.keys())}",
        }
    return {"ok": True, "norm": dict(norm)}


def vault_norms_scan(path: str) -> Dict[str, Any]:
    """Detect which norms are applicable to a vault note based on content analysis."""
    note_path = VAULT_ROOT / path
    if not note_path.exists():
        return {"ok": False, "error": f"Note not found: {path}"}

    try:
        content = note_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"ok": False, "error": str(e)}

    rel = path.replace("\\", "/")
    folder = rel.split("/")[0] if "/" in rel else ""

    applicable: List[Dict[str, Any]] = []

    def _add(code: str, reason: str) -> None:
        norm = _NORM_BY_CODE.get(code)
        if norm:
            applicable.append({"code": code, "name": norm["name"], "reason": reason})

    # Frontmatter checks
    has_frontmatter = content.startswith("---")
    fm: Dict[str, str] = {}
    if has_frontmatter:
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    fm[k.strip()] = v.strip().strip("\"'")

    if not fm.get("agent"):
        _add("AP-16", "campo agent ausente en frontmatter")
    if not fm.get("createdAt") or not fm.get("updatedAt"):
        _add("AP-13", "timestamps createdAt/updatedAt ausentes o incompletos")
    if not fm.get("id") or not fm.get("title"):
        _add("AP-12", "campos id/title ausentes en frontmatter")

    # Content length
    body = content.split("---", 2)[-1] if has_frontmatter else content
    real_lines = [
        l for l in body.split("\n") if l.strip() and not l.strip().startswith("TODO")
    ]
    if len(real_lines) == 0:
        _add("AP-11", "sin contenido real — skeleton file")
    elif len(real_lines) < 3:
        _add("AP-11", f"solo {len(real_lines)} línea(s) real(es) — posible skeleton")

    # Bullet ratio (AP-20)
    bullets = re.findall(r"^\s*[-*]\s*(.*)", body, re.MULTILINE)
    if bullets:
        empty = [
            b
            for b in bullets
            if not b.strip() or b.strip() in ("[]", "[[]]", "-", "[ ]")
        ]
        ratio = len(empty) / len(bullets)
        if ratio > 0.5:
            _add("AP-20", f"{int(ratio * 100)}% de bullets vacíos — deceptive skeleton")

    # Wiki-link checks
    clean = re.sub(r"```[\s\S]*?```", "", body)
    clean = re.sub(r"`[^`]+`", "", clean)
    wiki_links = re.findall(r"\[\[([^\]]+)\]\]", clean)

    if wiki_links:
        # AP-21: path-anchored
        path_links = [l for l in wiki_links if "/" in l]
        if path_links:
            _add("AP-21", f"path-anchored wiki-links: {path_links[:3]}")

        # AP-22: bracket balance
        opens = len(re.findall(r"\[\[", clean))
        closes = len(re.findall(r"\]\]", clean))
        empty_brackets = re.findall(r"\[\[\s*\]\]", clean)
        if opens != closes or empty_brackets:
            _add("AP-22", f"corchetes desbalanceados ({opens} vs {closes}) o vacíos")

        # AP-14: check for ghost links (note doesn't exist)
        all_stems = {
            p.stem.lower().replace("-", "").replace("_", "").replace(" ", "")
            for p in VAULT_ROOT.rglob("*.md")
            if ".history" not in str(p)
        }
        ghost = [
            l
            for l in wiki_links
            if l.split("|")[0]
            .strip()
            .lower()
            .replace("-", "")
            .replace("_", "")
            .replace(" ", "")
            not in all_stems
        ]
        if ghost:
            _add("AP-14", f"wiki-links posiblemente rotos: {ghost[:3]}")
    else:
        # AP-22: check even without wiki-links (unmatched brackets in text)
        opens = len(re.findall(r"\[\[", clean))
        closes = len(re.findall(r"\]\]", clean))
        if opens != closes:
            _add("AP-22", f"corchetes desbalanceados ({opens} vs {closes})")

    # Folder-specific checks
    if "03_Decisions" in rel or "adr" in rel.lower():
        sections = re.findall(r"^#{1,3}\s+(.+)", body, re.MULTILINE)
        section_names = [s.lower() for s in sections]
        missing = [
            s
            for s in (
                "contexto",
                "context",
                "opciones",
                "options",
                "consecuencias",
                "consequences",
            )
            if not any(s in n for n in section_names)
        ]
        if missing:
            _add(
                "AP-07", f"ADR posiblemente incompleto (secciones faltantes detectadas)"
            )

    if "06_Runbooks" not in rel and any(
        kw in note_path.stem.lower() for kw in ("runbook", "procedure", "playbook")
    ):
        _add("AP-09", "runbook fuera de 06_Runbooks/")

    # Always recommend PAT-5 (provenance chain)
    if not all(fm.get(f) for f in ("id", "createdAt", "updatedAt", "agent")):
        _add("PAT-5", "cadena de provenance incompleta (id/createdAt/updatedAt/agent)")

    return {
        "ok": True,
        "path": rel,
        "applicable_norms": applicable,
        "total": len(applicable),
    }


def vault_norms_apply(code: str, path: str) -> Dict[str, Any]:
    """Add a norm_refs entry to a note's frontmatter."""
    code = code.upper()
    if code not in _NORM_BY_CODE:
        return {"ok": False, "error": f"Norm '{code}' not found."}

    note_path = VAULT_ROOT / path
    if not note_path.exists():
        return {"ok": False, "error": f"Note not found: {path}"}

    try:
        content = note_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"ok": False, "error": str(e)}

    if not content.startswith("---"):
        return {
            "ok": False,
            "error": "Note has no YAML frontmatter. Use vault_write to create proper notes.",
        }

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {"ok": False, "error": "Malformed frontmatter (no closing ---)"}

    fm_block = parts[1]
    body = parts[2]

    # Parse existing norm_refs
    norm_refs_match = re.search(r"^norm_refs:\s*(.+)$", fm_block, re.MULTILINE)
    if norm_refs_match:
        existing_raw = norm_refs_match.group(1).strip()
        try:
            existing_refs = json.loads(existing_raw)
        except json.JSONDecodeError:
            existing_refs = [
                r.strip().strip('"')
                for r in existing_raw.strip("[]").split(",")
                if r.strip()
            ]
        if code in existing_refs:
            return {
                "ok": True,
                "path": path,
                "norm_refs": existing_refs,
                "message": f"{code} already present",
            }
        existing_refs.append(code)
        new_refs_line = f"norm_refs: {json.dumps(existing_refs)}"
        fm_block = re.sub(
            r"^norm_refs:\s*.+$", new_refs_line, fm_block, flags=re.MULTILINE
        )
    else:
        # Insert norm_refs after last field in frontmatter
        new_refs_line = f"norm_refs: {json.dumps([code])}"
        fm_block = fm_block.rstrip("\n") + f"\n{new_refs_line}\n"

    new_content = f"---{fm_block}---{body}"

    from vault_io import atomic_write_text

    atomic_write_text(note_path, new_content)

    # Read back to return final norm_refs
    norm_refs_match2 = re.search(r"^norm_refs:\s*(.+)$", fm_block, re.MULTILINE)
    final_refs = (
        json.loads(norm_refs_match2.group(1).strip()) if norm_refs_match2 else [code]
    )

    return {
        "ok": True,
        "path": path,
        "norm_refs": final_refs,
        "message": f"Added {code} to norm_refs",
    }


def vault_norms_rebuild() -> Dict[str, Any]:
    """Regenerate 00_System/norm-registry.json from the embedded catalog."""
    from datetime import datetime, timezone

    registry = {
        "version": "v29",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "total": len(NORM_CATALOG),
        "antipatterns": len([n for n in NORM_CATALOG if n["type"] == "antipattern"]),
        "patterns": len([n for n in NORM_CATALOG if n["type"] == "pattern"]),
        "by_severity": {
            sev: len([n for n in NORM_CATALOG if n["severity"] == sev])
            for sev in ("critical", "high", "medium", "low", "N/A")
        },
        "by_category": {
            cat: len([n for n in NORM_CATALOG if n["category"] == cat])
            for cat in (
                "content-quality",
                "structure",
                "frontmatter",
                "linking",
                "process",
            )
        },
        "by_enforcement": {
            enf: len([n for n in NORM_CATALOG if n["enforcement"] == enf])
            for enf in ("guard", "audit", "guard+audit", "manual", "recommended")
        },
        "norms": NORM_CATALOG,
    }

    NORM_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(NORM_REGISTRY, registry)

    return {
        "ok": True,
        "registry": str(NORM_REGISTRY.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "total": registry["total"],
        "antipatterns": registry["antipatterns"],
        "patterns": registry["patterns"],
        "by_severity": registry["by_severity"],
    }


# ─── Audit — enforcement automático de normas ex-manuales ─────────────────────

# Vocabulario canónico de meta.status (CN-03) — unificado v38.
# Antes existían DOS vocabularios contradictorios: CN-03 (7 valores) y el
# ciclo de vida del spec §status (draft→reviewed→approved→implemented→
# verified→obsolete). Este set es la unión canónica; CN-03 y el spec
# referencian este símbolo como fuente única.
STATUS_VOCAB = {
    "planned",
    "draft",
    "in-progress",
    "reviewed",
    "approved",
    "implemented",
    "verified",
    "deprecated",
    "obsolete",
    "archived",
    "stub",
    "template",
}

# Entradas permitidas en la raíz del vault además de las secciones canónicas
_ROOT_ALLOWED = {".obsidian", ".trash", ".history", ".git", ".locks", "vault-backups"}


def vault_norms_audit(root: Optional[Path] = None) -> Dict[str, Any]:
    """Audita el vault contra las normas automatizables (ex-manual).

    Cubre: AP-06, AP-07, AP-09, AP-10, AP-15, AP-19, CN-02, CN-03, SP-01.
    Las secciones canónicas se toman de vault_registry (fuente de verdad única,
    PAT-1) — nunca de listas hardcodeadas en el catálogo.
    """
    from datetime import datetime, timezone

    from vault_lib import extract_wikilinks, parse_frontmatter_with_body
    from vault_registry import SECTIONS

    root = (root or VAULT_ROOT).resolve()
    canonical_sections = {s["folder"] for s in SECTIONS}
    violations: List[Dict[str, Any]] = []

    def _flag(norm: str, path: str, detail: str) -> None:
        n = next((x for x in NORM_CATALOG if x["code"] == norm), {})
        violations.append(
            {
                "norm": norm,
                "severity": n.get("severity", "medium"),
                "path": path,
                "detail": detail,
            }
        )

    # ── AP-15 + CN-02: higiene de raíz ────────────────────────────────────────
    if root.exists():
        for entry in sorted(root.iterdir()):
            name = entry.name
            if name.startswith(".") and name in _ROOT_ALLOWED:
                continue
            if entry.is_dir():
                if name not in canonical_sections and name not in _ROOT_ALLOWED:
                    _flag(
                        "CN-02",
                        name,
                        f"Carpeta '{name}' en la raíz no es una sección canónica "
                        f"({len(canonical_sections)} secciones válidas en vault_registry).",
                    )
            elif not name.startswith("."):
                _flag("AP-15", name, f"Archivo suelto '{name}' en la raíz del vault.")

    # ── Cargar notas una sola vez ─────────────────────────────────────────────
    notes: Dict[str, Dict[str, Any]] = {}
    for md in sorted(root.rglob("*.md")):
        rel = str(md.relative_to(root)).replace("\\", "/")
        if rel.startswith(("10_Migrated/", ".")) or "/.history/" in rel:
            continue
        try:
            fm, body = parse_frontmatter_with_body(md.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        notes[rel] = {"fm": fm or {}, "body": body}

    inbound: Dict[str, int] = {}
    for rel, info in notes.items():
        for link in extract_wikilinks(info["body"]):
            inbound[link.split("|")[0].strip().lower()] = (
                inbound.get(link.split("|")[0].strip().lower(), 0) + 1
            )

    for rel, info in notes.items():
        fm, body = info["fm"], info["body"]
        note_type = str(fm.get("type", "")).lower()
        status = str(fm.get("status", "")).lower()
        stem = Path(rel).stem.lower()

        # ── CN-03: vocabulario de status ──────────────────────────────────────
        if status and status not in STATUS_VOCAB:
            _flag("CN-03", rel, f"status '{status}' fuera del vocabulario canónico {sorted(STATUS_VOCAB)}.")

        # ── AP-09: runbooks fuera de 08_Runbooks ──────────────────────────────
        if note_type == "runbook" and not rel.startswith("08_Runbooks/"):
            _flag("AP-09", rel, "Nota type:runbook fuera de 08_Runbooks/.")

        # ── AP-07: ADRs incompletos ───────────────────────────────────────────
        if (
            rel.startswith("03_Decisions/")
            and stem != "index"
            and status not in ("stub", "template")  # stubs se rigen por AP-03
        ):
            required = {
                "Contexto": "context",
                "Decisión": "decisi",
                "Consecuencias": "consecuen|consequence",
            }
            lower_body = body.lower()
            missing = [
                name
                for name, pat in required.items()
                if not re.search(rf"^#+.*({pat})", lower_body, re.MULTILINE | re.IGNORECASE)
            ]
            if missing or not status:
                problems = []
                if missing:
                    problems.append(f"secciones faltantes: {', '.join(missing)}")
                if not status:
                    problems.append("sin campo status")
                _flag("AP-07", rel, "ADR incompleto — " + "; ".join(problems) + ".")

        # ── AP-06: templates sin instancias (sin inbound links) ──────────────
        if note_type == "template" or "template" in [str(t).lower() for t in fm.get("tags", []) or []]:
            if inbound.get(stem, 0) == 0:
                _flag("AP-06", rel, "Template sin inbound links — sin instancias que lo usen.")

        # ── AP-19: shadow indexing ────────────────────────────────────────────
        if (
            "index" in stem
            and stem != "index"
            and not rel.startswith("99_Index/")
            and stem not in ("master-index",)
        ):
            _flag("AP-19", rel, f"Nota índice paralela '{rel}' fuera de 99_Index/ (shadow indexing).")

    # ── AP-36: contención e idempotencia ──────────────────────────────────────
    # (a) Artefactos .bak/.tmp dentro de secciones de contenido
    for sec in sorted(canonical_sections):
        sec_path = root / sec
        if not sec_path.is_dir():
            continue
        for artifact in sec_path.rglob("*"):
            if artifact.is_file() and (
                artifact.suffix in (".bak", ".tmp") or artifact.name.startswith(".tmp.")
            ):
                rel_a = str(artifact.relative_to(root)).replace("\\", "/")
                if "/.trash/" in rel_a or "/.history/" in rel_a:
                    continue  # ubicaciones de mantenimiento permitidas
                _flag("AP-36", rel_a, "Artefacto temporal/backup dentro de una sección de contenido.")
        # (b) Toda sección presente debe tener index.md (rastreabilidad de nodos)
        if sec not in ("00_System", "10_Migrated", "99_Index") and not (sec_path / "index.md").exists():
            _flag("AP-36", f"{sec}/", "Sección sin index.md — nodos no indexados (correr vault_section_index).")

    # (c) Contaminación hermana: artefactos de vault generados FUERA del vault
    for sibling_name in ("00_System", "99_Index", "vault-backups"):
        sibling = root.parent / sibling_name
        if sibling.exists() and sibling != root / sibling_name:
            _flag(
                "AP-36",
                f"../{sibling_name}",
                f"'{sibling_name}' existe como hermano del vault — side-effect fuera del vault root.",
            )

    # ── AP-10: migración sin plan de rollback ─────────────────────────────────
    migrated = root / "10_Migrated"
    if migrated.exists():
        migrated_notes = [p for p in migrated.rglob("*.md") if not p.name.startswith("_report-")]
        reports = list(migrated.glob("_report-*.md"))
        if migrated_notes and not reports:
            _flag(
                "AP-10",
                "10_Migrated/",
                f"{len(migrated_notes)} notas migradas sin _report-*.md (mapa de rollback para vault_migrate_rollback).",
            )

    # ── SP-01: eliminaciones sin change_log ───────────────────────────────────
    graph_file = root / "99_Index" / "graph.json"
    change_log = root / "00_System" / ".change-log.json"
    if graph_file.exists():
        try:
            graph = json.loads(graph_file.read_text(encoding="utf-8"))
            deleted = [e.get("from", "") for e in graph.get("edges", []) if e.get("to") == "__deleted__"]
            if deleted:
                logged: set = set()
                if change_log.exists():
                    try:
                        logged = {
                            str(e.get("path", "")) for e in json.loads(change_log.read_text(encoding="utf-8"))
                        }
                    except (json.JSONDecodeError, TypeError):
                        pass
                for d in deleted:
                    if d not in logged:
                        _flag("SP-01", d, "Nota eliminada sin entrada en change_log (delete protocol).")
        except (json.JSONDecodeError, OSError):
            pass

    by_norm: Dict[str, int] = {}
    for v in violations:
        by_norm[v["norm"]] = by_norm.get(v["norm"], 0) + 1

    return {
        "ok": True,
        "tool": "vault_norms.audit",
        "vault_root": str(root),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes_scanned": len(notes),
        "total_violations": len(violations),
        "by_norm": by_norm,
        "violations": violations,
    }


# ─── CLI ───────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Norms — catálogo de normas AP-XX y PAT-X",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Listar todas las normas
  python vault_norms.py --list

  # Filtrar por tipo, severidad o categoría
  python vault_norms.py --list --type ap --severity critical
  python vault_norms.py --list --category linking --sort severity
  python vault_norms.py --list --type pat

  # Detalle de una norma
  python vault_norms.py --show AP-22

  # Escanear una nota para detectar normas aplicables
  python vault_norms.py --scan --path "07_Knowledge/concepts/jwt.md"

  # Agregar referencia de norma al frontmatter
  python vault_norms.py --apply AP-22 --path "03_Decisions/adr-001.md"

  # Reconstruir norm-registry.json
  python vault_norms.py --rebuild
""",
    )

    parser.add_argument("--list", action="store_true", help="Listar normas")
    parser.add_argument(
        "--show", metavar="CODE", help="Mostrar detalle de una norma (ej: AP-22)"
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Escanear nota para detectar normas aplicables",
    )
    parser.add_argument(
        "--apply", metavar="CODE", help="Agregar referencia de norma al frontmatter"
    )
    parser.add_argument(
        "--rebuild", action="store_true", help="Regenerar norm-registry.json"
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Auditar el vault contra las normas automatizables (AP-06/07/09/10/15/19, CN-02/03, SP-01)",
    )
    parser.add_argument(
        "--root", help="Vault root para --audit (default: VAULT_ROOT auto-detect)"
    )
    parser.add_argument(
        "--path", help="Ruta relativa de la nota (para --scan y --apply)"
    )
    parser.add_argument(
        "--type",
        choices=["ap", "pat", "antipattern", "pattern"],
        help="Filtrar por tipo",
    )
    parser.add_argument(
        "--category",
        choices=["content-quality", "structure", "frontmatter", "linking", "process", "session-protocol", "convention"],
        help="Filtrar por categoria",
    )
    parser.add_argument(
        "--severity",
        choices=["critical", "high", "medium", "low"],
        help="Filtrar por severidad",
    )
    parser.add_argument(
        "--sort",
        choices=["code", "severity", "category", "enforcement"],
        default="code",
        help="Ordenar por (default: code)",
    )

    args = parser.parse_args()

    if args.audit:
        if args.root:
            from vault_io import set_vault_root
            set_vault_root(Path(args.root))  # AP-36: traces al vault objetivo
        result = vault_norms_audit(Path(args.root) if args.root else None)
    elif args.rebuild:
        result = vault_norms_rebuild()
    elif args.show:
        result = vault_norms_show(args.show)
    elif args.scan:
        if not args.path:
            parser.error("--scan requiere --path")
        result = vault_norms_scan(args.path)
    elif args.apply:
        if not args.path:
            parser.error("--apply requiere --path")
        result = vault_norms_apply(args.apply, args.path)
    elif args.list:
        result = vault_norms_list(
            norm_type=args.type,
            category=args.category,
            severity=args.severity,
            sort_by=args.sort,
        )
    else:
        parser.print_help()
        return 0

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_norms"))

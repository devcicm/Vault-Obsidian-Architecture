#!/usr/bin/env python3
"""vault_fundamentals_catalog — los registros del marco de datos, y nada más.

Hoja del núcleo: no importa ningún `vault_*`, solo `typing`. Si algún día lo
necesita, ha dejado de ser un catálogo y deja de tener sitio aquí.

## Por qué existe (AP-62, v40.28)

Los registros vivían dentro de `vault_fundamentals`, que además de declararlos
los **verifica**: lee notas, escribe `data-fundamentals.json` y tiene CLI. Tres
módulos de otros contextos —`vault_manifest`, `vault_spec_memory` y
`vault_vocabulario`— entraban por ahí para leer `FUNDAMENTALS` o `cia_valores`,
y con el import se llevaban las cuatro dependencias del verificador. Contaba
como tres cruces de frontera de negocio lo que eran tres lecturas de una tabla.

Es el mismo corte que v40.27 hizo con el catálogo de normas, y por el mismo
motivo: **el que declara y el que decide con lo declarado no son el mismo
módulo**, aunque hayan nacido en el mismo fichero.

`vault_fundamentals` los sigue reexportando, así que ningún llamador de fuera se
rompe (no-derogación). Quien solo quiera el dato lo pide aquí.

## Qué NO va aquí

La verificación. `check_note`, `framework_ids`, la cobertura por tool y los
exportadores se quedan en `vault_fundamentals`, que es donde tienen que estar:
deciden, tocan disco y necesitan el vault. Traérselos convertiría esta hoja en
otro módulo dios, que es exactamente la deuda que el corte cierra.
"""

from typing import Any, Dict, List

# ──────────────────────────────────────────────────────────────────────────────
# Canonical registry — single source of truth for the 8 fundamentals
# ──────────────────────────────────────────────────────────────────────────────

FUNDAMENTALS: List[Dict[str, Any]] = [
    {
        "id": "F1",
        "name": "INTEGRIDAD",
        "english": "integrity",
        "description": "Los datos están completos y siguen las reglas definidas, sin que falte información esencial en los registros.",
        "dq_dimension": "integrity",
        "verifies": [
            "Frontmatter parseable (YAML válido)",
            "Campos estructurales obligatorios presentes: id, title, createdAt",
            "No hay corrupción de delimitadores '---'",
        ],
        "frontmatter_fields": ["id", "title", "createdAt"],
        "tools": [
            "vault_quality_check",
            "vault_validate",
            "vault_write",
            "vault_read",
            "vault_pattern_save",
            "vault_diagram_save",
            "vault_flow_save",
            "vault_requirement_save",
            "vault_test_save",
            "vault_infra_save",
            "vault_env_save",
            "vault_restore",
            "vault_migrate_rollback",
            "vault_security_scan",
            "vault_standard_upgrade",
            "vault_fundamentals",
        ],
    },
    {
        "id": "F2",
        "name": "CONSISTENCIA",
        "english": "consistency",
        "description": "La información es uniforme y coherente en todos los sistemas y bases de datos, evitando contradicciones.",
        "dq_dimension": "consistency",
        "verifies": [
            "Todos los wiki-links [[...]] resuelven a notas existentes",
            "El campo type coincide con la sección de carpeta (type:project → 01_Projects/)",
            "Los índices JSON están sincronizados con el contenido",
        ],
        "frontmatter_fields": ["type"],
        "tools": [
            "vault_quality_check",
            "vault_audit",
            "vault_graph",
            "vault_reindex",
            "vault_impact",
            "vault_propagate",
            "vault_relation_add",
            "vault_code_relation",
            "vault_merge",
            "vault_search",
            "vault_list",
            "vault_knowledge_get",
            "vault_pattern_list",
            "vault_infra_map",
            "vault_code_map",
            "vault_code_query",
            "vault_backup_list",
            "vault_migrate_docs",
            "vault_master_index",
            "vault_section_index",
            "vault_project_overview",
            "vault_fundamentals",
        ],
    },
    {
        "id": "F3",
        "name": "COMPLETITUD",
        "english": "completeness",
        "description": "No existen campos vacíos o nulos en los datos obligatorios necesarios para el análisis o la operación.",
        "dq_dimension": "completeness",
        "verifies": [
            "Campo updatedAt presente (ciclo de vida)",
            "Cuerpo de la nota tiene al menos 3 lineas de contenido",
            "Tags requeridos en toda nota de contenido (>=1 tag, salvo index/system)",
        ],
        "frontmatter_fields": ["updatedAt", "tags", "status", "type"],
        "tools": [
            "vault_quality_check",
            "vault_write",
            "vault_audit",
            "vault_append",
            "vault_knowledge_save",
            "vault_runbook_save",
            "vault_read",
            "vault_knowledge_get",
            "vault_diagram_save",
            "vault_flow_save",
            "vault_requirement_save",
            "vault_test_save",
            "vault_infra_save",
            "vault_code_module",
            "vault_env_save",
            "vault_master_index",
            "vault_project_status",
            "vault_project_overview",
            "vault_token_counter",
            "vault_token_service",
            "vault_tokens",
        ],
    },
    {
        "id": "F4",
        "name": "EXACTITUD",
        "english": "accuracy",
        "description": "El dato es una representación fiel de la realidad, siendo preciso y correcto en su contenido.",
        "dq_dimension": "accuracy",
        "verifies": [
            "El campo type coincide con la sección de carpeta donde reside la nota",
            "Si existe campo path en frontmatter, coincide con la ruta real",
            "El stem del archivo coincide con title (sin tildes/espacios convertidos)",
            "La documentación refleja el estado real del código (drift detection)",
        ],
        "frontmatter_fields": ["type", "path"],
        "tools": [
            "vault_quality_check",
            "vault_drift_detect",
            "vault_diff",
            "vault_code_map",
            "vault_code_module",
            "vault_migrate_docs",
            "vault_fundamentals",
        ],
    },
    {
        "id": "F5",
        "name": "VALIDEZ",
        "english": "validity",
        "description": "Los datos siguen los formatos, tipos y estándares de negocio establecidos.",
        "dq_dimension": "validity",
        "verifies": [
            "Valores de status, type en conjuntos permitidos",
            "Campos CIA (cia_integrity, cia_availability, cia_sensitivity) con valores válidos",
            "Timestamps en formato ISO 8601",
            "IDs siguen el formato del esquema",
        ],
        "frontmatter_fields": [
            "status",
            "type",
            "cia_integrity",
            "cia_availability",
            "cia_sensitivity",
        ],
        "tools": [
            "vault_validate",
            "vault_quality_check",
            "vault_env_save",
            "vault_security_scan",
            "vault_fundamentals",
        ],
    },
    {
        "id": "F6",
        "name": "ACTUALIDAD",
        "english": "timeliness",
        "description": "Los datos están disponibles en el momento necesario y reflejan la información más reciente.",
        "dq_dimension": "timeliness",
        "verifies": [
            "Nota actualizada dentro del umbral según cia_integrity (15d para critical/high, 30d default)",
            "O marcada como evergreen: true en frontmatter",
            "updatedAt presente y no en el futuro",
        ],
        "frontmatter_fields": ["updatedAt", "evergreen", "cia_integrity"],
        "tools": [
            "vault_quality_check",
            "vault_audit",
            "vault_drift_detect",
            "vault_diff",
            "vault_backup",
            "vault_project_status",
            "vault_timeline",
            "vault_token_counter",
            "vault_token_service",
            "vault_tokens",
            "vault_fundamentals",
        ],
    },
    {
        "id": "F7",
        "name": "AUTENTICIDAD",
        "english": "authenticity",
        "description": "La fuente de los datos y la identidad de quien los genera o modifica es legítima y verificable.",
        "dq_dimension": "authenticity",
        "verifies": [
            "Campo agent presente en frontmatter (AP-16: identidad del agente)",
            "Valor de agent no vacío y reconocible (claude, user, etc.)",
        ],
        "frontmatter_fields": ["agent"],
        "tools": [
            "vault_quality_check",
            "vault_validate",
            "vault_write",
            "vault_append",
            "vault_knowledge_save",
            "vault_bibliography_save",
            "vault_ai_decision",
            "vault_pattern_save",
            "vault_diagram_save",
            "vault_flow_save",
            "vault_requirement_save",
            "vault_test_save",
            "vault_infra_save",
            "vault_env_save",
        ],
    },
    {
        "id": "F8",
        "name": "NO_REPUDIO",
        "english": "non_repudiation",
        "description": "El autor de una acción o cambio en los datos no puede negar su autoría, dejando un rastro auditable.",
        "dq_dimension": "non_repudiation",
        "verifies": [
            "Al menos una entrada en .change-log.json referencia la ruta de la nota",
            "El cambio incluye timestamp, agent y reason inmutables",
            "Eliminaciones registradas obligatoriamente antes de borrar",
        ],
        "frontmatter_fields": [],
        "tools": [
            "vault_change_log",
            "vault_quality_check",
            "vault_log_error",
            "vault_ai_decision",
            "vault_runbook_log",
            "vault_backup",
            "vault_restore",
            "vault_migrate_rollback",
            "vault_standard_upgrade",
            "vault_timeline",
            "vault_fundamentals",
        ],
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Marco de datos y gobernanza (v39) — registros canónicos complementarios
#
# Los 8 fundamentos responden "¿el dato es bueno?". Estos cuatro registros
# responden las otras preguntas del marco: sobre qué pilar se apoyan (CIA),
# qué tan reutilizable es el activo (FAIR), qué escala maneja (V's) y bajo
# qué normas se alinea (ISO). Mismo shape que FUNDAMENTALS: id estable,
# descripción, mecanismo real y tools que lo implementan — nunca teoría suelta.
# ──────────────────────────────────────────────────────────────────────────────

CIA_TRIAD: List[Dict[str, Any]] = [
    {
        "id": "CIA-C",
        "name": "CONFIDENCIALIDAD",
        "english": "confidentiality",
        "description": "El dato solo es accesible para quien debe verlo; el vault marca su nivel de exposición y evita filtrar secretos al grafo.",
        "frontmatter_field": "cia_sensitivity",
        "values": ["public", "internal", "restricted"],
        "default": "internal",
        "effect": "restricted activa revisión en vault_security_scan; sensitive:true en 02_Observability/envs impide volcar el valor del secreto, solo su proveedor y referencia.",
        "tools": [
            "vault_security_scan",
            "vault_env_save",
            "vault_privacy_save",
            "vault_validate",
            "vault_quality_check",
        ],
    },
    {
        "id": "CIA-I",
        "name": "INTEGRIDAD",
        "english": "integrity",
        "description": "El dato no se corrompe ni se altera de forma no rastreable entre escritura y lectura.",
        "frontmatter_field": "cia_integrity",
        "values": ["critical", "high", "medium", "low"],
        "default": "medium",
        "effect": "critical|high endurece el umbral de actualidad de 30d a 15d y penaliza 5 pts (vs 1 pt) en el health score; pondera stale_risk en vault_impact y selecciona la estrategia critical-path en vault_propagate.",
        "tools": [
            "vault_quality_check",
            "vault_audit",
            "vault_impact",
            "vault_propagate",
            "vault_backup",
            "vault_validate",
        ],
    },
    {
        "id": "CIA-A",
        "name": "DISPONIBILIDAD",
        "english": "availability",
        "description": "El dato se puede recuperar cuando se necesita, incluso tras un borrado o una migración fallida.",
        "frontmatter_field": "cia_availability",
        "values": ["high", "medium", "low"],
        "default": "medium",
        "effect": "Respaldado por .history/ en cada escritura, backups con manifiesto Merkle en VAULT_ROOT/vault-backups/ (AP-36) y rollback quirúrgico de migración (AP-10).",
        "tools": [
            "vault_backup",
            "vault_restore",
            "vault_backup_list",
            "vault_migrate_rollback",
            "vault_diff",
            "vault_validate",
        ],
    },
]


FAIR_PRINCIPLES: List[Dict[str, Any]] = [
    {
        "id": "FAIR-F",
        "name": "FINDABLE",
        "spanish": "LOCALIZABLE",
        "description": "Cada nota tiene identificador único y persistente, y es descubrible sin conocer su ruta.",
        "mechanism": "Campo id obligatorio (F1), search-index.json con scoring título×4, índices de sección auto-generados e índice maestro en 99_Index/.",
        "metric": "cobertura de id + notas huérfanas (orphans) en vault_audit",
        "tools": [
            "vault_search",
            "vault_reindex",
            "vault_section_index",
            "vault_master_index",
            "vault_list",
        ],
    },
    {
        "id": "FAIR-A",
        "name": "ACCESSIBLE",
        "spanish": "ACCESIBLE",
        "description": "El dato se lee sin runtime propietario, sin base de datos y sin la herramienta que lo creó.",
        "mechanism": "Markdown plano + YAML en el sistema de archivos. Abre en cualquier editor, versiona en git, se lee sin Obsidian instalado. Las tools son una conveniencia, no un requisito de lectura.",
        "metric": "cero dependencias de lectura — todo artefacto es .md o .json",
        "tools": ["vault_read", "vault_knowledge_get", "vault_project_overview"],
    },
    {
        "id": "FAIR-I",
        "name": "INTEROPERABLE",
        "spanish": "INTEROPERABLE",
        "description": "El dato usa vocabularios y formatos compartidos, y se conecta con otros datos del mismo dominio.",
        "mechanism": "Frontmatter YAML con vocabulario canónico (type, status vía STATUS_VOCAB, tags), wiki-links [[nota]] como aristas del grafo, Mermaid para diagramas, graph.json como representación explícita, MCP como protocolo de consumo.",
        "metric": "broken links = 0 · consistencia type↔carpeta (F4)",
        "tools": [
            "vault_graph",
            "vault_relation_add",
            "vault_diagram_save",
            "vault_norms",
            "vault_mcp_catalog",
        ],
    },
    {
        "id": "FAIR-R",
        "name": "REUSABLE",
        "spanish": "REUTILIZABLE",
        "description": "El dato trae su procedencia y licencia, de modo que otro agente o persona pueda confiar en él y reutilizarlo.",
        "mechanism": "Cadena de procedencia PAT-5 (agent:, createdAt, updatedAt, norm_refs), historial completo en .history/, change-log append-only y LICENSE del repositorio.",
        "metric": "cobertura del campo agent (F7) + entradas de change-log (F8)",
        "tools": [
            "vault_change_log",
            "vault_diff",
            "vault_timeline",
            "vault_delta",
            "vault_code_tag",
        ],
    },
]


BIGDATA_VS: List[Dict[str, Any]] = [
    {
        "id": "V1",
        "name": "VOLUMEN",
        "english": "volume",
        "description": "Cuánto conocimiento acumula el vault sin degradar la navegación.",
        "metric": "total de notas y tamaño del grafo",
        "artifact": "00_System/graph.json · vault_audit.stats",
        "control": "AP-23 (techo de complejidad por nota) e índices por sección evitan que el crecimiento rompa la búsqueda.",
        "tools": ["vault_audit", "vault_graph", "vault_list"],
    },
    {
        "id": "V2",
        "name": "VELOCIDAD",
        "english": "velocity",
        "description": "A qué ritmo cambia el conocimiento entre sesiones.",
        "metric": "cambios por sesión y por ventana temporal",
        "artifact": "00_System/.change-log.json · session-delta",
        "control": "SP-03 exige snapshot antes de operaciones masivas; vault_impact propaga el cambio a los nodos dependientes.",
        "tools": ["vault_change_log", "vault_delta", "vault_impact", "vault_timeline"],
    },
    {
        "id": "V3",
        "name": "VARIEDAD",
        "english": "variety",
        "description": "Cuántas naturalezas distintas de conocimiento conviven bajo el mismo esquema.",
        "metric": "18 secciones canónicas × vocabulario del campo type",
        "artifact": "vault_registry.SECTIONS",
        "control": "CN-02 restringe los destinos a secciones numeradas; F4 (exactitud) verifica que type coincida con la carpeta.",
        "tools": ["vault_write", "vault_validate", "vault_norms", "vault_registry"],
    },
    {
        "id": "V4",
        "name": "VERACIDAD",
        "english": "veracity",
        "description": "Cuánto se puede confiar en lo que el vault afirma. La V que más importa a un agente LLM.",
        "metric": "overall_dq_score (0.0–1.0) y notas bajo umbral 0.7",
        "artifact": "00_System/quality-index.json · vault_audit.dqHealth",
        "control": "AP-01 (documentación alucinada), AP-04 (features aspiracionales), AP-11 (skeleton files) y el content gate de vault_write.",
        "tools": ["vault_quality_check", "vault_audit", "vault_drift_detect", "vault_validate"],
    },
    {
        "id": "V5",
        "name": "VALOR",
        "english": "value",
        "description": "Cuánto del conocimiento almacenado se convierte en decisión útil para el agente.",
        "metric": "health score (0–100) y nextActions pendientes",
        "artifact": "vault_audit.score · vault_audit.nextActions",
        "control": "El audit deja de ser diagnóstico y emite la lista ejecutable de comandos para recuperar 100/100.",
        "tools": ["vault_audit", "vault_project_overview", "vault_onboard"],
    },
    {
        "id": "V6",
        "name": "VARIABILIDAD",
        "english": "variability",
        "description": "Cuánto deriva el significado de una nota respecto al código o la realidad que describe.",
        "metric": "drift detectado entre documentación y fuente",
        "artifact": "vault_drift_detect · @vault: tags en código",
        "control": "AP-08 (documentación anclada a versiones obsoletas) y trazabilidad bidireccional código↔vault.",
        "tools": ["vault_drift_detect", "vault_code_sync", "vault_code_tag"],
    },
]


ISO_COVERAGE: List[Dict[str, Any]] = [
    {
        "id": "ISO-25010",
        "norm": "ISO/IEC 25010:2023",
        "title": "Systems and software quality models",
        "clause": "Modelo de calidad de producto",
        "implemented_by": "Scoring multidimensional de calidad y no conformidades",
        "tools": ["vault_quality_check", "vault_ncr_save"],
    },
    {
        "id": "ISO-42001",
        "norm": "ISO/IEC 42001:2023",
        "title": "Artificial intelligence management system",
        "clause": "Gobernanza de decisiones asistidas por IA",
        "implemented_by": "16_AI_Governance/ — registro de decisiones de IA con responsable y alcance",
        "tools": ["vault_ai_decision"],
    },
    {
        "id": "ISO-29148",
        "norm": "ISO/IEC/IEEE 29148:2018",
        "title": "Requirements engineering",
        "clause": "Especificación y trazabilidad de requerimientos",
        "implemented_by": "14_Requirements/ — requerimientos con criterios de aceptación",
        "tools": ["vault_requirement_save"],
    },
    {
        "id": "ISO-29119",
        "norm": "ISO/IEC/IEEE 29119-3:2021",
        "title": "Software testing — Test documentation",
        "clause": "Documentación de pruebas",
        "implemented_by": "15_Tests/ — casos de prueba enlazados a requerimientos",
        "tools": ["vault_test_save", "vault_test_runner"],
    },
    {
        "id": "ISO-20000",
        "norm": "ISO/IEC 20000-1:2018",
        "title": "Service management system",
        "clause": "Gestión de incidentes y niveles de servicio",
        "implemented_by": "02_Observability/incidents/ y SLOs de producción",
        "tools": ["vault_incident_save", "vault_slo_save"],
    },
    {
        "id": "ISO-22301",
        "norm": "ISO 22301:2019",
        "title": "Business continuity management",
        "clause": "Continuidad y recuperación",
        "implemented_by": "Backups con manifiesto Merkle, restore verificable y runbooks de rollback",
        "tools": ["vault_backup", "vault_restore", "vault_runbook_save"],
    },
    {
        "id": "ISO-12207",
        "norm": "ISO/IEC/IEEE 12207:2017",
        "title": "Software life cycle processes",
        "clause": "Procesos de release y entornos",
        "implemented_by": "Registro de releases y matriz de entornos",
        "tools": ["vault_release_save", "vault_env_matrix"],
    },
    {
        "id": "ISO-31000",
        "norm": "ISO 31000:2018",
        "title": "Risk management",
        "clause": "Identificación, evaluación y tratamiento de riesgos",
        "implemented_by": "02_Observability/risks/ con score likelihood × impact",
        "tools": ["vault_risk_save"],
    },
    {
        "id": "ISO-27001",
        "norm": "ISO/IEC 27001:2022",
        "title": "Information security management",
        "clause": "Controles de seguridad de la información",
        "implemented_by": "Escaneo de secretos, clasificación cia_sensitivity y directivas DS-",
        "tools": ["vault_security_scan", "vault_env_save"],
    },
    {
        "id": "ISO-27005",
        "norm": "ISO/IEC 27005:2022",
        "title": "Information security risk management",
        "clause": "Riesgo de seguridad de la información",
        "implemented_by": "Asignación automática de CIA por tipo y nivel de impacto del riesgo",
        "tools": ["vault_risk_save"],
    },
    {
        "id": "ISO-27701",
        "norm": "ISO/IEC 27701:2019",
        "title": "Privacy information management",
        "clause": "Tratamiento de datos personales (con GDPR Art. 30 y 35)",
        "implemented_by": "09_Infrastructure/privacy/ con detección automática de DPIA",
        "tools": ["vault_privacy_save"],
    },
    {
        "id": "ISO-9001",
        "norm": "ISO 9001:2015",
        "title": "Quality management systems",
        "clause": "§9.2 Auditoría interna · §10.2 No conformidad y acción correctiva",
        "implemented_by": "NCR con ID auto-generado, 5-Whys y verificación de eficacia",
        "tools": ["vault_ncr_save", "vault_audit"],
    },
    {
        "id": "ISO-8601",
        "norm": "ISO 8601",
        "title": "Date and time representation",
        "clause": "Formato de marcas temporales",
        "implemented_by": "Todo timestamp del vault es UTC en formato YYYY-MM-DDTHH:mm:ss.sssZ (AP-13)",
        "tools": ["vault_write", "vault_validate", "vault_lib"],
    },
]


#: Registros del marco, expuestos como mapa para exportadores y guards.
FRAMEWORK_REGISTRIES: Dict[str, List[Dict[str, Any]]] = {
    "cia_triad": CIA_TRIAD,
    "fundamentals": FUNDAMENTALS,
    "fair_principles": FAIR_PRINCIPLES,
    "bigdata_vs": BIGDATA_VS,
    "iso_coverage": ISO_COVERAGE,
}


def cia_valores(campo: str) -> set:
    """Valores admitidos por un campo CIA, según `CIA_TRIAD`.

    El vocabulario estaba escrito a mano dos veces más —en `_check_fundamentals`
    aquí mismo y como constantes de módulo en `vault_validate`— pese a que el
    registro ya lo declara en `values`. Las tres copias coinciden hoy; la que se
    quede atrás cuando el registro cambie reprobará notas válidas o aprobará las
    que no lo son, y en ninguno de los dos casos habrá un test que lo note. La
    asimetría es real y del registro: DISPONIBILIDAD no admite `critical`.
    """
    for c in CIA_TRIAD:
        if c["frontmatter_field"] == campo:
            return set(c["values"])
    return set()
